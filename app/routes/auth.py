from fastapi import APIRouter, Depends, HTTPException, status, Request, Form
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from app import models, schemas
from app.database import get_db
from app.auth.auth import authenticate_user, create_access_token, get_password_hash, get_current_active_user, is_admin, create_refresh_token, refresh_access_token, get_current_user
from datetime import timedelta, date
from fastapi.templating import Jinja2Templates
from app.auth.auth import authenticate_user


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
    db: Session = Depends(get_db),
    current_user: models.User = Depends(is_admin)
):
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if db_user is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    try:
        # Преобразуем значение роли в соответствующий enum
        new_role = models.UserRole(role_data.role)
        db_user.role = new_role
        db.commit()
        db.refresh(db_user)
        return {"success": True, "new_role": new_role.value}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Неверное значение роли: {str(e)}")

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("auth.html", {"request": request})

@router.post("/login", response_class=JSONResponse)
async def login_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = authenticate_user(db, username, password)
    if not user:
        return JSONResponse(
            content={"error": "Неверное имя пользователя или пароль"},
            status_code=400
        )

    # Создаем токены без дополнительной обертки
    access_token = create_access_token(data={"sub": user.username})
    refresh_token = create_refresh_token(data={"sub": user.username})

    response = JSONResponse(
        content={"success": True, "message": "Успешный вход"}
    )

    # Сохраняем токены без дополнительного форматирования
    response.set_cookie(
        key="access_token",
        value=access_token,  # Без префикса Bearer
        httponly=True,
        samesite='lax',
        max_age=1800
    )

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        samesite='lax',
        max_age=604800
    )

    return response
