from fastapi import APIRouter, Depends, HTTPException, status, Request, Form
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from app import models, schemas
from app.database import get_db
from app.auth.auth import authenticate_user, create_access_token, get_password_hash, get_current_active_user, is_admin, create_refresh_token, refresh_access_token
from datetime import timedelta, date
from fastapi.templating import Jinja2Templates

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

@router.put("/users/{user_id}/role", response_model=schemas.User)
async def update_user_role(user_id: int, role_update: schemas.UserRoleUpdate, db: Session = Depends(get_db), admin: schemas.User = Depends(is_admin)):
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if db_user is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    db_user.role = role_update.role
    db.commit()
    db.refresh(db_user)
    return db_user
