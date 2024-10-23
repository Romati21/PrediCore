from fastapi import APIRouter, Depends, HTTPException, status, Request, Form
from jose import JWTError, jwt
from app.models import User, UserSession, RevokedToken
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from app import models, schemas
from app.database import get_db
# from app.routes.auth import access_token_data
from app.auth.auth import authenticate_user, create_access_token, get_password_hash, get_current_active_user, is_admin, create_refresh_token, refresh_access_token, get_current_user, SECRET_KEY, ALGORITHM
from datetime import timedelta, date
from fastapi.templating import Jinja2Templates
from typing import Dict, Any
from app.auth.auth import authenticate_user, revoke_token
import logging
from datetime import datetime
import pytz
from contextlib import contextmanager

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
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@router.post("/register", response_model=schemas.User)
async def register_user(
    full_name: str = Form(...),
    birth_date: str = Form(...),
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    # Проверяем, существует ли пользователь с таким email
    db_user_by_email = db.query(models.User).filter(models.User.email == email).first()
    if db_user_by_email:
        raise HTTPException(status_code=400, detail="Пользователь с таким адресом электронной почты уже существует")

    db_user_by_username = db.query(models.User).filter(models.User.username == username).first()
    if db_user_by_username:
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
async def refresh_token_endpoint(refresh_token: str, db: Session = Depends(get_db)):
    new_access_token = refresh_access_token(refresh_token)
    return {"access_token": new_access_token, "refresh_token": refresh_token, "token_type": "bearer"}


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

    # Получаем всех пользователей с их ролями
    users = db.query(models.User).all()

    # Добавляем отладочную информацию
    for user in users:
        print(f"User {user.username} has role: {user.role.value}")

    return templates.TemplateResponse(
        "users_list.html",
        {
            "request": request,
            "users": users,
            "current_user": current_user,
            "UserRole": models.UserRole  # Передаем enum в шаблон
        }
    )

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
async def login_page(request: Request):
    return templates.TemplateResponse("auth.html", {"request": request})

def get_moscow_time():
    moscow_tz = pytz.timezone('Europe/Moscow')
    return datetime.now(moscow_tz)

@router.post("/login", response_class=JSONResponse)
async def login_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    # Проверка на количество активных сессий
    user = authenticate_user(db, username, password)
    if not user:
        logging.warning(
            f"Failed login attempt - Username: {username}, "
            f"IP: {request.client.host}"
        )
        return JSONResponse(
            content={"error": "Неверное имя пользователя или пароль"},
            status_code=400
        )

    active_sessions = db.query(UserSession).filter(
        UserSession.user_id == user.id,
        UserSession.is_active == True
    ).count()

    MAX_ACTIVE_SESSIONS = 5
    if active_sessions >= MAX_ACTIVE_SESSIONS:
        raise HTTPException(
            status_code=400,
            detail="Достигнуто максимальное количество активных сессий"
        )

    # Создаем токены с информацией об IP и User-Agent
    access_token_data = create_access_token(
        data={"sub": user.username},
        request=request
    )
    refresh_token_data = create_refresh_token(
        data={"sub": user.username},
        request=request
    )

    # Создаем новую сессию
    user_agent_string = request.headers.get("user-agent", "")

    session = UserSession(
        user_id=user.id,
        ip_address=request.client.host,
        user_agent=user_agent_string,
        last_activity=datetime.utcnow(),
        access_token_jti=access_token_data.get("jti"),
        refresh_token_jti=refresh_token_data.get("jti")
    )

    db.add(session)
    db.commit()

    response = JSONResponse(content={"success": True, "message": "Успешный вход"})

    # Настройки безопасности для cookies
    cookie_settings = {
        "httponly": True,
        "samesite": 'lax',
        "secure": request.url.scheme == "https"
    }

    response.set_cookie(
        key="access_token",
        value=access_token_data["token"],
        max_age=1800,  # 30 минут
        **cookie_settings
    )

    response.set_cookie(
        key="refresh_token",
        value=refresh_token_data["token"],
        max_age=604800,  # 7 дней
        **cookie_settings
    )

    logging.info(
        f"Successful login - Username: {username}, "
        f"IP: {request.client.host}, "
        f"Session ID: {session.id}"
    )

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

    response = JSONResponse(content={"message": "Successfully logged out"})
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
    user_sessions = db.query(UserSession).filter(
        UserSession.user_id == user_id,
        UserSession.is_active == True
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
        current_time = datetime.utcnow()
        db.query(RevokedToken).filter(
            RevokedToken.expires_at < current_time
        ).delete()
        db.commit()
    except Exception as e:
        logging.error(f"Error during token cleanup: {str(e)}")
        db.rollback()
