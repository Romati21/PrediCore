import random
from fastapi.responses import RedirectResponse
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fastapi import APIRouter, Depends, HTTPException, Request, Form
from sqlalchemy.orm import Session
from app.models import User
from app.database import get_db
from passlib.context import CryptContext
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.auth.auth import get_current_user_optional
from typing import Optional
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

router = APIRouter()
templates = Jinja2Templates(directory="templates")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Генерация OTP
def generate_otp():
    return random.randint(100000, 999999)

# Отправка OTP на почту
def send_otp_email(email: str, otp: str):
    try:
        sender = os.getenv("EMAIL_SENDER")
        password = os.getenv("EMAIL_PASSWORD")
        
        if not sender or not password:
            raise ValueError("Email configuration not found in environment variables")

        # Создаем сообщение
        msg = MIMEMultipart()
        msg['From'] = sender
        msg['To'] = email
        msg['Subject'] = 'Код для восстановления пароля'

        # Текст письма
        body = f"Ваш код для восстановления пароля: {otp}"
        msg.attach(MIMEText(body, 'plain'))

        # Подключаемся к Gmail SMTP-серверу
        smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", "465"))
        
        with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
            server.login(sender, password)
            text = msg.as_string()
            server.sendmail(sender, email, text)

        print("Письмо успешно отправлено!")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка отправки email: {str(e)}")

# Обработчик запроса восстановления пароля
@router.post("/forgot_password")
async def forgot_password(email: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=400, detail="Пользователь с таким email не найден")

    otp = generate_otp()
    # Сохраняем OTP в базе данных или кэш-системе
    user.otp = str(otp)  # Преобразуем OTP в строку и сохраняем в базе данных
    db.commit()

    # Отправляем OTP на почту
    send_otp_email(email, str(otp))
    # Перенаправляем на страницу ввода OTP
    return RedirectResponse(url="/recovery", status_code=303)

# Обработчик для сброса пароля
@router.post("/reset_password")
async def reset_password(
    otp: str = Form(...),
    new_password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.otp == otp).first()
    if not user:
        raise HTTPException(status_code=400, detail="Неверный код подтверждения")

    # Обновляем пароль
    hashed_password = pwd_context.hash(new_password)
    user.password_hash = hashed_password
    user.otp = None  # Удаляем использованный OTP
    db.commit()

    # Перенаправляем пользователя на страницу авторизации
    return RedirectResponse(url="/login", status_code=303)

@router.get("/forgot_password", response_class=HTMLResponse)
async def forgot_password_page(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    return templates.TemplateResponse("forgot_password.html", {"request": request, "current_user": current_user})

@router.get("/recovery", response_class=HTMLResponse)
async def recovery_page(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    return templates.TemplateResponse("recovery.html", {"request": request, "current_user": current_user})
