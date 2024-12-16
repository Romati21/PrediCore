from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt, ExpiredSignatureError
from passlib.context import CryptContext
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from app import models, schemas
from app.database import get_db
from app.models import User, UserSession, RevokedToken
import secrets
from jose import ExpiredSignatureError
import uuid
from ipaddress import ip_address, IPv4Address, IPv6Address
from user_agents import parse
from fastapi import Request, HTTPException
from typing import Dict, Any, Optional, cast, TypedDict, Tuple
from fastapi.responses import Response
from starlette.background import BackgroundTask
import logging


# Настройки JWT
SECRET_KEY = "0915c30082502482c60dee76b9eda80c434d8b8e637c020865db0bfc836012f31874884c0c0512ae3954bf0edfb8d87bb3e32cc978b8f042f5df22851aa3318a"
# SECRET_KEY = secrets.token_hex(32)  # Генерирует 64-символьный
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

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


def refresh_access_token(refresh_token: str, db: Session, create_new_refresh: bool = False) -> tuple[str, Optional[str]]:
    """
    Обновляет access token используя refresh token.
    
    Args:
        refresh_token: Refresh token для обновления access token
        db: Сессия базы данных
        create_new_refresh: Создавать ли новый refresh token
        
    Returns:
        tuple[str, Optional[str]]: Кортеж из (access_token, refresh_token).
            refresh_token будет None если create_new_refresh=False
        
    Raises:
        ValueError: Если refresh token невалиден или истек
    """
    try:
        # Декодируем refresh token
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        
        # Проверяем тип токена
        if payload.get("type") != "refresh":
            logging.warning("Attempt to use non-refresh token for refresh")
            raise ValueError("Invalid token type")

        refresh_exp = payload.get("exp")
        refresh_jti = payload.get("jti")
        current_time = datetime.now(timezone.utc).timestamp()

        # Проверяем срок действия
        if refresh_exp is None:
            logging.warning("Refresh token without expiration time")
            raise ValueError("Refresh token does not contain an expiration time")
        if current_time > refresh_exp:
            logging.warning("Attempt to use expired refresh token")
            raise ValueError("Refresh token has expired")

        # Проверяем наличие JTI
        if not refresh_jti:
            logging.warning("Refresh token without JTI")
            raise ValueError("Refresh token does not contain JTI")

        # Проверяем, не отозван ли токен
        if db.query(RevokedToken).filter(RevokedToken.jti == refresh_jti).first():
            logging.warning(f"Attempt to use revoked token with JTI: {refresh_jti}")
            raise ValueError("Token has been revoked")

        # Проверяем активность сессии
        session = db.query(UserSession).filter(
            UserSession.refresh_token_jti == refresh_jti,
            UserSession.is_active == True
        ).first()

        if not session:
            logging.warning(f"No active session found for refresh token JTI: {refresh_jti}")
            raise ValueError("Session not found or inactive")

        username = payload.get("sub")
        if not username:
            logging.warning("Refresh token without username")
            raise ValueError("Invalid refresh token")

        # Проверяем существование пользователя
        user = db.query(User).filter(User.username == username).first()
        if not user:
            logging.warning(f"User not found: {username}")
            raise ValueError("User not found")

        # Создаем данные для токена с информацией о клиенте
        token_data = {
            "sub": username,
            "ip": session.ip_address,
            "user_agent": session.user_agent
        }

        # Создаем новый access token
        new_access_token, new_access_jti = create_access_token(
            data=token_data
        )
        
        # Обновляем JTI в сессии
        session.access_token_jti = new_access_jti
        session.last_activity = datetime.now(timezone.utc)

        new_refresh_token = None
        if create_new_refresh:
            # Создаем новый refresh token
            new_refresh_token, new_refresh_jti = create_refresh_token(
                data=token_data
            )
            
            # Отзываем старый refresh token
            revoked_token = RevokedToken(
                jti=refresh_jti,
                revoked_at=datetime.now(timezone.utc),
                reason="Token rotation"
            )
            db.add(revoked_token)
            
            # Обновляем JTI в сессии
            session.refresh_token_jti = new_refresh_jti

        try:
            db.commit()
            logging.info(f"Successfully refreshed tokens for user: {username}")
        except Exception as e:
            db.rollback()
            logging.error(f"Database error during token refresh: {str(e)}")
            raise ValueError("Failed to update session")

        if create_new_refresh:
            return new_access_token, new_refresh_token
        return new_access_token, None

    except JWTError as e:
        logging.error(f"JWT error during token refresh: {str(e)}")
        raise ValueError(f"Failed to refresh token: {str(e)}")
    except Exception as e:
        logging.error(f"Unexpected error during token refresh: {str(e)}")
        raise ValueError(f"Failed to refresh token: {str(e)}")


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
    request: Optional[Request] = None,
    expires_delta: Optional[timedelta] = None
) -> Tuple[str, str]:  # (token, jti)
    """
    Создает JWT access token с указанными данными и временем жизни.

    Args:
        data: Словарь с данными для токена
        request: FastAPI Request объект для получения IP и User-Agent
        expires_delta: Опциональное время жизни токена

    Returns:
        Tuple[str, str]: Кортеж из (token, jti)
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # Добавляем информацию о клиенте, если есть request
    if request:
        to_encode.update({
            "ip": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent")
        })
    
    # Добавляем стандартные поля
    jti = str(uuid.uuid4())
    to_encode.update({
        "exp": expire,
        "jti": jti,
        "type": "access",
        "iat": datetime.now(timezone.utc)
    })
    
    # Создаем токен
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt, jti

def create_refresh_token(
    data: dict,
    request: Optional[Request] = None,
    expires_delta: Optional[timedelta] = None
) -> Tuple[str, str]:
    """
    Создает refresh token с указанными данными и сроком действия.

    Args:
        data: Словарь с данными для кодирования в токен
        request: Объект запроса для добавления информации об IP и User-Agent
        expires_delta: Срок действия токена

    Returns:
        Tuple[str, str]: Кортеж из токена и его JTI
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    # Добавляем информацию о клиенте, если есть request
    if request:
        to_encode.update({
            "ip": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent")
        })

    # Добавляем стандартные поля
    jti = str(uuid.uuid4())
    to_encode.update({
        "exp": expire,
        "jti": jti,
        "type": "refresh",
        "iat": datetime.now(timezone.utc)
    })
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt, jti


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
    """
    Отзыв JWT токена с сохранением информации в базе данных.

    Args:
        token: JWT токен для отзыва
        reason: Причина отзыва токена
        db: Сессия базы данных
        current_user: Текущий пользователь

    Raises:
        HTTPException: При невалидном формате токена или отсутствии required полей
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        # Получаем JTI с проверкой
        jti = payload.get("jti")
        if not jti:
            raise HTTPException(status_code=400, detail="Token has no JTI claim")

        # Получаем время истечения с проверкой
        exp_timestamp = payload.get("exp")
        if not exp_timestamp:
            raise HTTPException(status_code=400, detail="Token has no expiration claim")

        # Конвертируем UNIX timestamp в datetime с UTC
        try:
            expires_at = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
        except (TypeError, ValueError) as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid expiration timestamp: {str(e)}"
            )

        # Создаем запись об отозванном токене
        revoked_token = RevokedToken(
            jti=jti,
            revoked_at=datetime.now(timezone.utc),
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

    except JWTError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid token format: {str(e)}"
        )
    except Exception as e:
        db.rollback()
        logging.error(f"Error revoking token: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while revoking token"
        )

# Определяем типы в начале файла
class TokenPayload(TypedDict):
    sub: str
    exp: int
    jti: str
    type: str

def get_username_from_payload(payload: TokenPayload) -> str:
    """Извлекает и проверяет username из payload"""
    username = payload.get("sub")
    if not username or not isinstance(username, str):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )
    return username

async def get_current_user(request: Request, db: Session = Depends(get_db)) -> models.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Не удалось подтвердить учетные данные",
        headers={"WWW-Authenticate": "Bearer"},
    )

    access_token = request.cookies.get('access_token')
    refresh_token = request.cookies.get('refresh_token')

    if not access_token:
        logging.debug("Access token отсутствует")
        raise credentials_exception

    try:
        token = access_token.replace('"', '').replace('Bearer ', '')
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            options={"verify_exp": False}
        )

        exp_timestamp = int(payload.get("exp", 0))
        current_time = int(datetime.now(timezone.utc).timestamp())

        username = payload.get("sub")
        if not username:
            raise credentials_exception

        user = db.query(models.User).filter(models.User.username == username).first()
        if not user:
            raise credentials_exception

        # Если токен истекает скоро или уже истек
        if current_time > exp_timestamp or (exp_timestamp - current_time) < 300:
            if not refresh_token:
                logging.debug("Refresh token отсутствует")
                raise credentials_exception

            try:
                logging.debug("Access token истек, обновляем")
                new_access_token, _ = refresh_access_token(refresh_token, db)
                
                # Устанавливаем новый access token в response
                request.state.new_access_token = new_access_token
                
            except (JWTError, ValueError) as e:
                logging.error(f"Error refreshing token: {str(e)}")
                raise credentials_exception

        return user

    except JWTError as e:
        logging.error(f"Error in get_current_user: {str(e)}")
        raise credentials_exception

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

def get_cookie_settings(request: Request) -> dict:
    """Возвращает стандартные настройки для cookie"""
    settings = {
        "httponly": True,
        "samesite": 'strict',
        "secure": request.url.scheme == "https",
        "path": "/",
    }
    
    # Получаем домен из запроса
    domain = request.headers.get("host", "").split(":")[0]
    
    # Если домен не localhost и не IP адрес, добавляем его в настройки
    if domain and not domain.startswith("localhost") and not _is_ip_address(domain):
        settings["domain"] = domain
        
    return settings

def _is_ip_address(host: str) -> bool:
    """Проверяет, является ли строка IP адресом"""
    try:
        ip_address(host)
        return True
    except ValueError:
        return False

def get_token_expiration() -> dict:
    """Возвращает время истечения для токенов в секундах (max_age)"""
    return {
        "access_token": ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # в секундах
        "refresh_token": REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60  # в секундах
    }
