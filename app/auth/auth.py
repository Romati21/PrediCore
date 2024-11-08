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


def refresh_access_token(refresh_token: str) -> tuple[str, str]:
    """Создает новый access token на основе refresh token"""
    try:
        # Декодируем refresh token
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")

        if not username:
            raise ValueError("Invalid refresh token")

        # Создаем новый access token
        jti = str(uuid.uuid4())
        exp = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

        token_data = {
            "sub": username,
            "exp": int(exp.timestamp()),
            "iat": int(datetime.now(timezone.utc).timestamp()),
            "jti": jti,
            "type": "access"
        }

        new_token = jwt.encode(token_data, SECRET_KEY, algorithm=ALGORITHM)
        return new_token, jti

    except JWTError as e:
        logging.error(f"Error refreshing access token: {str(e)}")
        raise ValueError("Invalid refresh token")


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

    # Используем timezone-aware datetime объекты
    current_time = datetime.now(timezone.utc)

    if expires_delta:
        expire = current_time + expires_delta
    else:
        expire = current_time + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    # Генерируем уникальный идентификатор токена
    jti = str(uuid.uuid4())

    # Добавляем служебные поля в токен
    to_encode.update({
        "exp": int(expire.timestamp()),  # Конвертируем в UNIX timestamp
        "iat": int(current_time.timestamp()),  # Добавляем время создания
        "jti": jti,
        "type": "access"
    })

    # Добавляем информацию о клиенте, если доступна
    if request:
        to_encode.update({
            "ip": request.client.host,
            "user_agent": request.headers.get("user-agent")
        })

    try:
        token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return token, jti
    except Exception as e:
        raise ValueError(f"Error creating access token: {str(e)}")

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

def create_refresh_token(
    data: dict,
    request: Optional[Request] = None,
    expires_delta: Optional[timedelta] = None
) -> Tuple[str, str]:  # (token, jti)
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
    jti = str(uuid.uuid4())

    current_time = datetime.now(timezone.utc)
    if expires_delta:
        expire = current_time + expires_delta
    else:
        expire = current_time + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode.update({
        "exp": int(expire.timestamp()),  # Конвертируем в UNIX timestamp
        "iat": int(current_time.timestamp()),  # Добавляем время создания токена
        "jti": jti,
        "type": "refresh"
    })

    if request:
        # Добавляем информацию о клиенте
        to_encode["ip"] = request.client.host
        to_encode["user_agent"] = request.headers.get("user-agent")

    try:
        token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return token, jti
    except Exception as e:
        logging.error(f"Error creating refresh token: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Error creating refresh token"
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

async def get_current_user(
    request: Request,
    db: Session = Depends(get_db)
) -> models.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Не удалось подтвердить учетные данные",
        headers={"WWW-Authenticate": "Bearer"},
    )

    access_token = request.cookies.get('access_token')
    refresh_token = request.cookies.get('refresh_token')

    if not access_token:
        raise credentials_exception

    try:
        token = access_token.replace('"', '').replace('Bearer ', '')

        # Сначала декодируем без проверки срока действия
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            options={"verify_exp": False}
        )

        # Проверяем срок действия вручную
        exp_timestamp = int(payload.get("exp", 0))
        current_time = int(datetime.now(timezone.utc).timestamp())

        # Если токен истек или истекает в ближайшие 5 минут
        if current_time > exp_timestamp or (exp_timestamp - current_time) < 300:
            if not refresh_token:
                raise credentials_exception

            try:
                # Декодируем refresh token
                refresh_payload = jwt.decode(
                    refresh_token,
                    SECRET_KEY,
                    algorithms=[ALGORITHM]
                )

                # Проверяем срок действия refresh token
                refresh_exp = int(refresh_payload.get("exp", 0))
                should_refresh_token = (refresh_exp - current_time) < 24 * 60 * 60

                # Создаем новый access token
                new_token, new_jti = refresh_access_token(refresh_token)

                # Инициализируем токены
                tokens_info = {
                    'access_token': {
                        'token': new_token,
                        'jti': new_jti,
                        'expires_in': ACCESS_TOKEN_EXPIRE_MINUTES * 60
                    }
                }

                # Если refresh token скоро истекает, создаем новый
                if should_refresh_token:
                    new_refresh_token, new_refresh_jti = create_refresh_token(
                        data={"sub": refresh_payload.get("sub")}
                    )
                    tokens_info['refresh_token'] = {
                        'token': new_refresh_token,
                        'jti': new_refresh_jti,
                        'expires_in': REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
                    }

                # Обновляем сессию в БД
                current_refresh_jti = refresh_payload.get("jti")
                if current_refresh_jti:
                    session = db.query(models.UserSession).filter(
                        models.UserSession.refresh_token_jti == current_refresh_jti,
                        models.UserSession.is_active == True
                    ).first()

                    if session:
                        session.access_token_jti = new_jti
                        if should_refresh_token:
                            session.refresh_token_jti = new_refresh_jti
                        session.last_activity = datetime.now(timezone.utc)
                        db.commit()

                # Сохраняем информацию о новых токенах
                request.state.new_tokens = tokens_info

                # Используем новый payload для получения пользователя
                payload = jwt.decode(new_token, SECRET_KEY, algorithms=[ALGORITHM])

            except JWTError as e:
                logging.error(f"Failed to refresh tokens: {str(e)}")
                raise credentials_exception

        username = str(payload.get("sub", ""))
        if not username:
            raise credentials_exception

    except JWTError as e:
        logging.error(f"Token validation error: {str(e)}")
        raise credentials_exception

    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        raise credentials_exception

    return user

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
