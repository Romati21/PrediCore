from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt, ExpiredSignatureError
from passlib.context import CryptContext
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from app import models, schemas
from app.database import get_db
import secrets
from jose import ExpiredSignatureError
import uuid
from ipaddress import ip_address, IPv4Address, IPv6Address
from user_agents import parse
from fastapi import Request, HTTPException
from typing import Dict, Any, Optional
from fastapi.responses import Response
from starlette.background import BackgroundTask


# Настройки JWT
SECRET_KEY = secrets.token_hex(32)  # Генерирует 64-символьный
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7  # Refresh-токен истекает через 7 дней

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

MAX_FAILED_ATTEMPTS = 5  # Максимум неудачных попыток
LOCKOUT_TIME = 15  # Время блокировки в минутах после 5 неудачных попыток

def authenticate_user(db: Session, username: str, password: str):
    user = db.query(models.User).filter(models.User.username == username).first()

    if not user:
        return False

    # Если поле failed_login_attempts равно None, присваиваем ему 0
    if user.failed_login_attempts is None:
        user.failed_login_attempts = 0
        db.commit()

    # Проверяем, не заблокирован ли пользователь
    if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
        current_time = datetime.now(timezone.utc)

        # Убедимся, что last_failed_login имеет timezone
        last_failed = user.last_failed_login
        if last_failed and last_failed.tzinfo is None:
            last_failed = last_failed.replace(tzinfo=timezone.utc)

        if last_failed:
            time_since_last_failed = current_time - last_failed
            if time_since_last_failed < timedelta(minutes=LOCKOUT_TIME):
                raise HTTPException(
                    status_code=403,
                    detail=f"Аккаунт временно заблокирован. Попробуйте через {LOCKOUT_TIME - time_since_last_failed.minutes} минут."
                )
            else:
                # Сбрасываем счетчик попыток, если прошло достаточно времени
                user.failed_login_attempts = 0
                db.commit()

    # Проверяем пароль
    if not verify_password(password, user.password_hash):
        user.failed_login_attempts += 1
        user.last_failed_login = datetime.now(timezone.utc)  # Используем timezone-aware datetime
        db.commit()
        return False

    # Если авторизация успешна, сбрасываем счетчик
    user.failed_login_attempts = 0
    db.commit()
    return user


def refresh_access_token(refresh_token: str) -> Dict[str, str]:
    try:
        # Декодируем refresh token
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=401,
                detail="Invalid refresh token"
            )

        # Создаем новый access token
        new_token_data = create_access_token(data={"sub": username})
        return new_token_data

    except ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail="Refresh token expired"
        )
    except JWTError:
        raise HTTPException(
            status_code=401,
            detail="Invalid refresh token"
        )


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

# def authenticate_user(db: Session, username: str, password: str):
#     user = db.query(models.User).filter(models.User.username == username).first()
#     if not user or not verify_password(password, user.password_hash):
#         return False
#     return user

def create_access_token(
    data: dict,
    request: Request = None,
    expires_delta: timedelta = None
) -> tuple[str, str]:  # Возвращаем (token, jti)
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    jti = str(uuid.uuid4())
    to_encode.update({
        "exp": expire,
        "jti": jti,
        "type": "access"
    })

    if request:
        to_encode["ip"] = request.client.host
        to_encode["user_agent"] = request.headers.get("user-agent")

    token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return token, jti

async def validate_token(token: str, db: Session, request: Request = None) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        # Проверяем, не отозван ли токен
        jti = payload.get("jti")
        if not jti:
            raise HTTPException(status_code=401, detail="Invalid token format")

        revoked_token = db.query(RevokedToken).filter(
            RevokedToken.jti == jti
        ).first()

        if revoked_token:
            raise HTTPException(status_code=401, detail="Token has been revoked")

        # Проверяем IP-адрес, если токен содержит эту информацию
        if request and "ip" in payload:
            token_ip = ip_address(payload["ip"])
            request_ip = ip_address(request.client.host)

            # Проверяем, совпадают ли IP-адреса
            if token_ip != request_ip:
                logging.warning(
                    f"IP address mismatch - Token IP: {token_ip}, "
                    f"Request IP: {request_ip}, "
                    f"User: {payload.get('sub')}"
                )
                raise HTTPException(
                    status_code=401,
                    detail="IP address mismatch"
                )

        return payload

    except JWTError as e:
        raise HTTPException(status_code=401, detail="Invalid token")

async def revoke_token(
    token: str,
    reason: str,
    db: Session,
    current_user: models.User
) -> None:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        jti = payload.get("jti")
        expires_at = datetime.fromtimestamp(payload.get("exp"))

        revoked_token = RevokedToken(
            jti=jti,
            revoked_at=datetime.utcnow(),
            expires_at=expires_at,
            revoked_by_user_id=current_user.id,
            reason=reason,
            token_type=payload.get("type", "unknown")
        )

        db.add(revoked_token)
        db.commit()

        logging.info(
            f"Token revoked - JTI: {jti}, "
            f"User: {current_user.username}, "
            f"Reason: {reason}"
        )

    except JWTError:
        raise HTTPException(status_code=400, detail="Invalid token format")

def create_refresh_token(
    data: dict,
    request: Request = None,
    expires_delta: timedelta = None
) -> tuple[str, str]:  # Возвращаем (token, jti)
    to_encode = data.copy()
    jti = str(uuid.uuid4())

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode.update({
        "exp": expire,
        "jti": jti,
        "type": "refresh"
    })

    if request:
        to_encode["ip"] = request.client.host
        to_encode["user_agent"] = request.headers.get("user-agent")

    token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return token, jti

async def get_current_user(
    request: Request,
    db: Session = Depends(get_db)
) -> models.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Не удалось подтвердить учетные данные",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Получаем токен из кук
    token = None
    if 'access_token' in request.cookies:
        auth_cookie = request.cookies.get('access_token')
        token = auth_cookie.replace('"', '').replace('Bearer ', '')

    if not token:
        raise credentials_exception

    try:
        # Пытаемся декодировать access token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception

    except ExpiredSignatureError:
        # Специальная обработка истекшего токена
        if 'refresh_token' in request.cookies:
            refresh_token = request.cookies.get('refresh_token')
            try:
                # Пробуем создать новый access token
                new_token_data = refresh_access_token(refresh_token)

                # Устанавливаем новый токен в куки
                request.state.new_access_token = new_token_data["token"]

                # Декодируем новый токен
                payload = jwt.decode(new_token_data["token"], SECRET_KEY, algorithms=[ALGORITHM])
                username = payload.get("sub")

            except (JWTError, ExpiredSignatureError):
                raise credentials_exception
        else:
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    user = db.query(models.User).filter(models.User.username == username).first()
    if user is None:
        raise credentials_exception

    return user


from typing import Optional

async def get_current_user_optional(
    request: Request,
    db: Session = Depends(get_db)
) -> Optional[models.User]:
    try:
        return await get_current_user(request, db)
    except HTTPException:
        return None


async def get_current_active_user(current_user: schemas.User = Depends(get_current_user)):
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Неактивный пользователь")
    return current_user

def is_admin(
    request: Request,
    current_user: models.User = Depends(get_current_user)
):
    if not current_user or current_user.role != models.UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для выполнения операции"
        )
    return current_user
