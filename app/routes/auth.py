from fastapi import APIRouter, Depends, HTTPException, status, Request, Form, BackgroundTasks
from jose import JWTError, jwt
from app import models, schemas
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from app.database import get_db
# from app.routes.auth import access_token_data
from app.auth.auth import (
    authenticate_user, create_access_token, get_password_hash, 
    get_current_active_user, is_admin, create_refresh_token, 
    refresh_access_token, get_current_user, SECRET_KEY, 
    ALGORITHM, get_current_user_optional, ACCESS_TOKEN_EXPIRE_MINUTES,
    get_cookie_settings, get_token_expiration
)
from datetime import timedelta, date, timezone
from fastapi.templating import Jinja2Templates
from typing import Dict, Any, Optional
from app.auth.auth import authenticate_user, revoke_token
import logging
from datetime import datetime
import pytz
from contextlib import contextmanager
from app.services import session_service
from fastapi.responses import RedirectResponse
from app.services import cleanup_service
from app.schemas import RefreshTokenRequest

@contextmanager
def transaction(db: Session):
    try:
        yield
        db.commit()
    except Exception:
        db.rollback()
        raise

# Настраиваем логирование
logging.basicConfig(
    filename='auth.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, current_user: Optional[models.User] = Depends(get_current_user_optional)):
    return templates.TemplateResponse("register.html", {"request": request, "current_user": current_user})

@router.post("/register", response_model=schemas.User)
async def register_user(
    full_name: str = Form(...),
    birth_date: str = Form(...),
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    try:
        # Проверяем, существует ли пользователь с таким email
        db_user_by_email = db.query(models.User).filter(models.User.email == email).first()
        if db_user_by_email:
            logging.error(f"User with email {email} already exists")
            raise HTTPException(status_code=400, detail="Пользователь с таким адресом электронной почты уже существует")

        db_user_by_username = db.query(models.User).filter(models.User.username == username).first()
        if db_user_by_username:
            logging.error(f"User with username {username} already exists")
            raise HTTPException(status_code=400, detail="Пользователь с таким именем пользователя уже существует")

        try:
            user_data = schemas.UserCreate(
                full_name=full_name,
                birth_date=birth_date,
                username=username,
                email=email,
                password=password
            )
        except ValueError as e:
            logging.error(f"Validation error: {str(e)}")
            raise HTTPException(status_code=422, detail=str(e))

        hashed_password = get_password_hash(user_data.password)
        db_user = models.User(
            username=user_data.username,
            email=user_data.email,
            full_name=user_data.full_name,
            password_hash=hashed_password,
            role=models.UserRole.WORKER,  # Устанавливаем роль "Рабочий" по умолчанию
            birth_date=user_data.birth_date
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user
    except Exception as e:
        logging.error(f"Unexpected error during registration: {str(e)}")
        raise

@router.post("/token", response_model=schemas.Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Неверное имя пользователя или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user.username})
    refresh_token = create_refresh_token(data={"sub": user.username})
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}

@router.post("/token/refresh", response_model=schemas.Token)
async def refresh_token_endpoint(
    request: Request,
    token_request: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    try:
        # Декодируем refresh_token
        payload = jwt.decode(token_request.refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            logging.warning(f"Invalid token type in refresh attempt - IP: {request.client.host}")
            raise HTTPException(status_code=401, detail="Invalid token type")

        username = payload.get("sub")
        if not username:
            logging.warning(f"Missing username in token payload - IP: {request.client.host}")
            raise HTTPException(status_code=401, detail="Invalid token")

        # Проверяем, не отозван ли токен
        jti = payload.get("jti")
        if not jti:
            logging.warning(f"Missing JTI in token payload - User: {username}, IP: {request.client.host}")
            raise HTTPException(status_code=401, detail="Invalid token")

        if db.query(models.RevokedToken).filter(models.RevokedToken.jti == jti).first():
            logging.warning(f"Attempt to use revoked token - User: {username}, IP: {request.client.host}")
            raise HTTPException(status_code=401, detail="Token has been revoked")

        # Проверяем сессию
        session = db.query(models.UserSession).filter(
            models.UserSession.refresh_token_jti == jti,
            models.UserSession.is_active == True
        ).first()

        if not session:
            logging.warning(f"No active session found for token - User: {username}, IP: {request.client.host}")
            raise HTTPException(status_code=401, detail="Invalid session")

        # Обновляем время последней активности сессии
        session.last_activity = datetime.utcnow()
        
        # Создаем новый access_token
        new_access_token, new_access_jti = create_access_token(
            data={"sub": username},
            request=request
        )

        # Создаем новый refresh_token с ротацией
        new_refresh_token, new_refresh_jti = create_refresh_token(
            data={"sub": username},
            request=request
        )

        # Обновляем JTI в сессии
        session.access_token_jti = new_access_jti
        session.refresh_token_jti = new_refresh_jti

        # Отзываем старый refresh token
        revoked_token = models.RevokedToken(
            jti=jti,
            revoked_at=datetime.utcnow()
        )
        db.add(revoked_token)

        try:
            db.commit()
        except Exception as e:
            db.rollback()
            logging.error(f"Database error during token refresh - User: {username}, Error: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

        logging.info(f"Token refresh successful - User: {username}, IP: {request.client.host}, Session: {session.id}")

        response = JSONResponse(content={
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer"
        })

        # Устанавливаем новые токены в cookies
        cookie_settings = get_cookie_settings(request)
        token_expiration = get_token_expiration()

        response.set_cookie(
            key="access_token",
            value=f"Bearer {new_access_token}",
            max_age=token_expiration["access_token"],
            **cookie_settings
        )

        response.set_cookie(
            key="refresh_token",
            value=new_refresh_token,
            max_age=token_expiration["refresh_token"],
            **cookie_settings
        )

        return response

    except JWTError as e:
        logging.warning(f"JWT decode error during refresh - IP: {request.client.host}, Error: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        logging.error(f"Unexpected error during token refresh - IP: {request.client.host}, Error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/users/me/", response_model=schemas.User)
async def read_users_me(current_user: schemas.User = Depends(get_current_active_user)):
    return current_user

@router.get("/admin/users", response_class=HTMLResponse)
async def admin_users_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if current_user.role != models.UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для доступа"
        )

    users = db.query(models.User).all()

    # Создаем ответ
    response = templates.TemplateResponse(
        "users_list.html",
        {
            "request": request,
            "users": users,
            "current_user": current_user,
            "UserRole": models.UserRole
        }
    )

    # Если был создан новый access token, обновляем куки
    new_token = getattr(request.state, 'new_access_token', None)
    if new_token:
        response.set_cookie(
            key="access_token",
            value=new_token,
            httponly=True,
            samesite='lax',
            secure=request.url.scheme == "https",
            max_age=1800
        )

    return response

@router.put("/users/{user_id}/role")
async def update_user_role(
    user_id: int,
    role_data: schemas.UserRoleUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(is_admin)
):
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if db_user is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    old_role = db_user.role.value

    try:
        new_role = models.UserRole(role_data.role)
        db_user.role = new_role
        db.commit()
        db.refresh(db_user)

        # Логируем изменение роли
        logging.info(
            f"Role changed - User: {db_user.username}, "
            f"Old role: {old_role}, "
            f"New role: {new_role.value}, "
            f"Changed by: {current_user.username}, "
            f"IP: {request.client.host}, "
            f"Time: {get_moscow_time()}"
        )

        return {"success": True, "new_role": new_role.value}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Неверное значение роли: {str(e)}")

@router.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    current_user: Optional[models.User] = Depends(get_current_user_optional)
):
    return templates.TemplateResponse("auth.html", {"request": request, "current_user": current_user})

def get_moscow_time():
    moscow_tz = pytz.timezone('Europe/Moscow')
    return datetime.now(moscow_tz)

def get_client_ip(request: Request) -> str:
    """Get client IP address from request, checking X-Real-IP header first"""
    return request.headers.get("X-Real-IP") or request.client.host

@router.post("/login", response_class=JSONResponse)
async def login_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    logging.info(f"Login attempt with username: {username}")
    
    user = authenticate_user(db, username, password)
    if not user:
        logging.warning(f"Failed login attempt - Username: {username}, IP: {get_client_ip(request)}")
        return JSONResponse(
            content={"error": "Неверное имя пользователя или пароль"},
            status_code=400
        )

    # Подсчитываем количество активных сессий
    active_sessions = db.query(models.UserSession).filter(
        models.UserSession.user_id == user.id,
        models.UserSession.is_active == True
    ).count()

    MAX_ACTIVE_SESSIONS = 5
    if active_sessions >= MAX_ACTIVE_SESSIONS:
        # Создаем временный токен для доступа к странице сессий
        temp_token, temp_jti = create_access_token(
            data={
                "sub": user.username,
                "temp_access": True,
                "purpose": "session_management"
            },
            expires_delta=timedelta(minutes=10)
        )

        response = JSONResponse(
            content={
                "status": "too_many_sessions",
                "message": "Достигнуто максимальное количество активных сессий",
                "redirect_url": f"/sessions?temp_token={temp_token}"
            },
            status_code=200
        )

        cookie_settings = get_cookie_settings(request)
        response.set_cookie(
            key="temp_token",
            value=temp_token,
            max_age=600,  # 10 минут
            **cookie_settings
        )

        return response

    # Для обычного входа
    access_token, access_jti = create_access_token(
        data={"sub": user.username},
        request=request
    )
    refresh_token, refresh_jti = create_refresh_token(
        data={"sub": user.username},
        request=request
    )

    # Создаем сессию
    session = session_service.create_session(
        db=db,
        user=user,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent", ""),
        access_token_jti=access_jti,
        refresh_token_jti=refresh_jti
    )

    if not session:
        raise HTTPException(
            status_code=400,
            detail="Ошибка создания сессии"
        )

    response = JSONResponse(content={"success": True, "message": "Успешный вход"})

    cookie_settings = get_cookie_settings(request)
    token_expiration = get_token_expiration()

    # Устанавливаем токены в cookies с правильными сроками действия
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        max_age=token_expiration["access_token"],
        **cookie_settings
    )
    response.set_cookie(
        key="refresh_token",
        value=f"Bearer {refresh_token}",
        max_age=token_expiration["refresh_token"],
        **cookie_settings
    )

    # Обновляем время последнего входа
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()

    return response


@router.post("/logout")
async def logout(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # Находим текущую сессию по access token
    access_token = request.cookies.get("access_token")
    if access_token:
        try:
            payload = jwt.decode(access_token, SECRET_KEY, algorithms=[ALGORITHM])
            jti = payload.get("jti")
            if jti:
                current_session = db.query(models.UserSession).filter(
                    models.UserSession.access_token_jti == jti,
                    models.UserSession.is_active == True
                ).first()

                if current_session:
                    current_session.revoke_tokens(
                        db,
                        current_user,
                        "User logout"
                    )
        except JWTError:
            logging.warning("Failed to decode token during logout")

    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")

    return response

@router.post("/logout/all")
async def logout_all_sessions(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Выход из всех сессий пользователя"""
    current_user.revoke_all_sessions(db, current_user, "User initiated logout from all sessions")

    response = JSONResponse(content={"message": "Successfully logged out from all sessions"})
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")

    return response

@router.post("/revoke-all-tokens")
async def revoke_all_user_tokens(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(is_admin)
):
    # Получаем все активные сессии пользователя
    user_sessions = db.query(models.UserSession).filter(
        models.UserSession.user_id == user_id,
        models.UserSession.is_active == True
    ).all()

    for session in user_sessions:
        if session.access_token_jti:
            await revoke_token(
                session.access_token_jti,
                "Admin revoked all tokens",
                db,
                current_user
            )
        if session.refresh_token_jti:
            await revoke_token(
                session.refresh_token_jti,
                "Admin revoked all tokens",
                db,
                current_user
            )
        session.is_active = False

    db.commit()
    return {"message": "All tokens have been revoked"}

async def cleanup_expired_tokens(db: Session):
    try:
        current_time = datetime.now(timezone.utc)
        db.query(models.RevokedToken).filter(
            models.RevokedToken.expires_at < current_time
        ).delete()
        db.commit()
    except Exception as e:
        logging.error(f"Error during token cleanup: {str(e)}")
        db.rollback()

@router.get("/sessions", response_class=HTMLResponse)
async def sessions_page(
    request: Request,
    temp_token: str = None,
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(get_current_user_optional)
):
    try:
        # Пытаемся получить токен из параметра URL или из куки
        temp_token = temp_token or request.cookies.get('temp_token')

        if temp_token:
            try:
                payload = jwt.decode(temp_token, SECRET_KEY, algorithms=[ALGORITHM])
                if not payload.get("temp_access"):
                    raise HTTPException(status_code=401, detail="Недействительный токен")
                username = payload.get("sub")
                user = db.query(models.User).filter(models.User.username == username).first()
                if not user:
                    raise HTTPException(status_code=404, detail="Пользователь не найден")

                # Получаем активные сессии и их количество
                active_sessions = models.UserSession.get_active_sessions(db, user.id)
                active_sessions_count = models.UserSession.get_active_sessions_count(db, user.id)

                # Устанавливаем current_user
                current_user = user

                return templates.TemplateResponse(
                    "sessions.html",
                    {
                        "request": request,
                        "sessions": active_sessions,
                        "active_sessions_count": active_sessions_count,
                        "is_temp_access": True,
                        "user": user,
                        "current_user": current_user
                    }
                )
            except JWTError as e:
                logging.error(f"JWT Error: {str(e)}")
                return RedirectResponse(url="/login", status_code=302)

        # Если нет временного токена, пробуем обычную аутентификацию
        user = await get_current_user(request, db)
        active_sessions = models.UserSession.get_active_sessions(db, user.id)
        active_sessions_count = models.UserSession.get_active_sessions_count(db, user.id)

        # Устанавливаем current_user
        current_user = user

        return templates.TemplateResponse(
            "sessions.html",
            {
                "request": request,
                "sessions": active_sessions,
                "active_sessions_count": active_sessions_count,
                "is_temp_access": False,
                "user": user,
                "current_user": current_user
            }
        )

    except HTTPException as e:
        logging.error(f"Session page error: {str(e)}")
        return RedirectResponse(url="/login", status_code=302)

@router.post("/sessions/{session_id}/terminate")
async def terminate_session(
    session_id: int,
    request: Request,
    temp_token: str = None,
    db: Session = Depends(get_db)
):
    logging.info(f"Attempting to terminate session {session_id}")

    try:
        # Проверяем временный токен или обычную аутентификацию
        if temp_token:
            try:
                logging.info("Using temp token authentication")
                payload = jwt.decode(temp_token, SECRET_KEY, algorithms=[ALGORITHM])
                if not payload.get("temp_access"):
                    raise HTTPException(status_code=401, detail="Недействительный токен")
                username = payload.get("sub")
                user = db.query(models.User).filter(models.User.username == username).first()
                logging.info(f"Found user {username} using temp token")
            except JWTError as e:
                logging.error(f"JWT Error: {str(e)}")
                raise HTTPException(status_code=401, detail="Недействительный токен")
        else:
            logging.info("Using standard authentication")
            user = await get_current_user(request, db)

        if not user:
            logging.error("User not found")
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        # Находим сессию
        session = db.query(models.UserSession).filter(
            models.UserSession.id == session_id,
            models.UserSession.user_id == user.id
        ).first()

        if not session:
            logging.error(f"Session {session_id} not found for user {user.id}")
            raise HTTPException(status_code=404, detail="Сессия не найдена")

        logging.info(f"Found session {session_id} for user {user.id}")

        try:
            # Отзываем токены сессии
            await session.revoke_tokens(db, user, "User terminated session via session management")
            logging.info(f"Successfully terminated session {session_id}")

            return {"message": "Сессия успешно завершена"}

        except Exception as e:
            logging.error(f"Error during session termination: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Ошибка при завершении сессии: {str(e)}"
            )

    except HTTPException as e:
        raise e
    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Внутренняя ошибка сервера: " + str(e)
        )

@router.post("/sessions/terminate-all")
async def terminate_all_sessions(
    request: Request,
    temp_token: str = None,
    db: Session = Depends(get_db)
):
    try:
        if temp_token:
            try:
                payload = jwt.decode(temp_token, SECRET_KEY, algorithms=[ALGORITHM])
                if not payload.get("temp_access"):
                    raise HTTPException(status_code=401, detail="Недействительный токен")
                username = payload.get("sub")
                user = db.query(models.User).filter(models.User.username == username).first()
            except JWTError:
                raise HTTPException(status_code=401, detail="Недействительный токен")
        else:
            user = await get_current_user(request, db)

        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        # Получаем все активные сессии
        active_sessions = db.query(models.UserSession).filter(
            models.UserSession.user_id == user.id,
            models.UserSession.is_active == True
        ).all()

        # Отзываем все сессии
        for session in active_sessions:
            await session.revoke_tokens(db, user, "User terminated all sessions")

        return {"message": "Все сессии успешно завершены"}

    except HTTPException as e:
        raise e
    except Exception as e:
        logging.error(f"Error terminating all sessions: {str(e)}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")

# Добавляем маршруты для очистки сессий
@router.get("/admin/cleanup-sessions", response_class=HTMLResponse)
async def cleanup_sessions_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(is_admin)
):
    """Страница управления очисткой сессий"""
    # Получаем статистику по сессиям
    total_sessions = db.query(models.UserSession).count()
    active_sessions = db.query(models.UserSession).filter(
        models.UserSession.is_active == True
    ).count()
    expired_sessions = db.query(models.UserSession).filter(
        models.UserSession.is_active == True,
        models.UserSession.last_activity < datetime.now(timezone.utc) - timedelta(days=7)
    ).count()

    return templates.TemplateResponse(
        "cleanup_sessions.html",
        {
            "request": request,
            "total_sessions": total_sessions,
            "active_sessions": active_sessions,
            "expired_sessions": expired_sessions,
            "current_user": current_user
        }
    )

@router.post("/admin/cleanup-sessions")
async def manual_cleanup_sessions(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(is_admin)
):
    """Ручной запуск очистки сессий"""
    try:
        await cleanup_service.cleanup_expired_sessions(db)
        return {"success": True, "message": "Очистка сессий успешно выполнена"}
    except Exception as e:
        logging.error(f"Error during manual cleanup: {str(e)}")
        return {
            "success": False,
            "message": "Произошла ошибка при очистке сессий",
            "error": str(e)
        }
