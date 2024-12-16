from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from datetime import datetime, timezone
from jose import jwt, JWTError, ExpiredSignatureError
from app.auth.auth import refresh_access_token, SECRET_KEY, ALGORITHM, get_cookie_settings, get_token_expiration
import logging
from starlette.datastructures import Headers
from app.database import SessionLocal
from app.models import UserSession, RevokedToken
from app.services import session_service
import os

# Настройка логирования
log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'logs')
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, 'token_refresh.log')

# Настраиваем логгер
logger = logging.getLogger('token_refresh')
logger.setLevel(logging.INFO)

# Создаем обработчик для файла
file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.INFO)

# Создаем форматтер
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)

# Добавляем обработчик к логгеру
logger.addHandler(file_handler)

class TokenRefreshMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        # Настраиваем логирование для отслеживания процесса
        request_id = id(request)
        logger.info(f"[{request_id}] Starting token refresh middleware")

        # Инициализируем состояние
        request.state.new_access_token = None
        request.state.new_refresh_token = None
        request.state.clear_tokens = False

        # Получаем access token из cookies
        access_token = request.cookies.get("access_token")
        refresh_token = request.cookies.get("refresh_token")

        logger.info(f"[{request_id}] Tokens present - Access: {bool(access_token)}, Refresh: {bool(refresh_token)}")

        if access_token and refresh_token:
            try:
                # Очищаем токены от лишних кавычек и префикса Bearer
                access_token = access_token.replace('Bearer ', '').replace('"', '')
                refresh_token = refresh_token.replace('"', '')

                # Проверяем refresh token
                try:
                    refresh_payload = jwt.decode(
                        refresh_token,
                        SECRET_KEY,
                        algorithms=[ALGORITHM]
                    )
                    if refresh_payload.get("type") != "refresh":
                        logger.warning(f"[{request_id}] Invalid refresh token type")
                        request.state.clear_tokens = True
                        return await call_next(request)

                    # Проверяем, не был ли refresh token отозван
                    with SessionLocal() as db:
                        refresh_jti = refresh_payload.get("jti")
                        if refresh_jti:
                            revoked = db.query(RevokedToken).filter(
                                RevokedToken.jti == refresh_jti
                            ).first()
                            if revoked:
                                logger.warning(f"[{request_id}] Refresh token has been revoked")
                                request.state.clear_tokens = True
                                return await call_next(request)

                except JWTError as e:
                    logger.error(f"[{request_id}] Invalid refresh token: {str(e)}")
                    request.state.clear_tokens = True
                    return await call_next(request)

                now = datetime.now(timezone.utc).timestamp()
                refresh_exp = refresh_payload.get("exp")
                
                # Проверяем срок действия refresh token
                if refresh_exp and refresh_exp <= now:
                    logger.warning(f"[{request_id}] Refresh token has expired")
                    request.state.clear_tokens = True
                    return await call_next(request)

                # Проверяем access token
                try:
                    access_payload = jwt.decode(
                        access_token,
                        SECRET_KEY,
                        algorithms=[ALGORITHM]
                    )
                    
                    if access_payload.get("type") == "refresh":
                        logger.warning(f"[{request_id}] Access token is actually a refresh token, attempting to restore")
                        with SessionLocal() as db:
                            try:
                                new_access_token, _ = refresh_access_token(refresh_token, db)
                                request.state.new_access_token = new_access_token
                                logger.info(f"[{request_id}] Successfully restored correct access token")
                                return await call_next(request)
                            except Exception as e:
                                logger.error(f"[{request_id}] Error restoring access token: {str(e)}")
                                request.state.clear_tokens = True
                                return await call_next(request)
                    
                    # Проверяем время жизни access token
                    exp = access_payload.get("exp")
                    
                    if exp:
                        time_left = exp - now
                        logger.info(f"[{request_id}] Access token expires in {time_left:.2f} seconds")
                    
                    # Если до истечения токена осталось менее 10 минут или он уже истек
                    should_refresh = exp is None or (exp - now) < 600  # 10 минут
                    
                    if not should_refresh:
                        # Если токен валиден, обновляем активность сессии
                        access_jti = access_payload.get("jti")
                        if access_jti:
                            with SessionLocal() as db:
                                session = db.query(UserSession).filter(
                                    UserSession.access_token_jti == access_jti,
                                    UserSession.is_active == True
                                ).first()
                                
                                if session:
                                    session_service.update_session_activity(db, session)
                                    logger.info(f"[{request_id}] Updated last activity for session {session.id}")
                                else:
                                    logger.warning(f"[{request_id}] No active session found for JTI: {access_jti}")
                                    request.state.clear_tokens = True
                                    return await call_next(request)
                    else:
                        # Если токен скоро истечет, обновляем его
                        logger.info(f"[{request_id}] Access token expires soon, refreshing")
                        with SessionLocal() as db:
                            try:
                                # Проверяем время жизни refresh token
                                if refresh_exp and (refresh_exp - now) < 172800:  # Меньше 48 часов
                                    # Если refresh token скоро истечет, обновляем оба токена
                                    new_access_token, new_refresh_token = refresh_access_token(refresh_token, db, new_refresh=True)
                                    request.state.new_access_token = new_access_token
                                    request.state.new_refresh_token = new_refresh_token
                                    logger.info(f"[{request_id}] Generated new access and refresh tokens")
                                else:
                                    # Иначе только обновляем access token
                                    new_access_token, _ = refresh_access_token(refresh_token, db)
                                    request.state.new_access_token = new_access_token
                                    logger.info(f"[{request_id}] Generated new access token only")
                            except Exception as e:
                                logger.error(f"[{request_id}] Error refreshing tokens: {str(e)}")
                                # Не очищаем токены при ошибке обновления, 
                                # так как старые токены могут быть еще валидными
                                return await call_next(request)

                except ExpiredSignatureError:
                    # Если access token просто истек, пробуем обновить его
                    logger.info(f"[{request_id}] Access token expired, attempting refresh")
                    with SessionLocal() as db:
                        try:
                            new_access_token, _ = refresh_access_token(refresh_token, db)
                            request.state.new_access_token = new_access_token
                            logger.info(f"[{request_id}] Successfully refreshed expired access token")
                        except Exception as e:
                            logger.error(f"[{request_id}] Error refreshing expired token: {str(e)}")
                            request.state.clear_tokens = True
                            return await call_next(request)

                except JWTError as e:
                    logger.error(f"[{request_id}] Invalid access token: {str(e)}")
                    request.state.clear_tokens = True
                    return await call_next(request)

            except Exception as e:
                logger.error(f"[{request_id}] Error in token refresh middleware: {str(e)}")
                request.state.clear_tokens = True
                return await call_next(request)

        elif refresh_token:  # Есть только refresh token
            logger.info(f"[{request_id}] Only refresh token present, attempting to restore access token")
            try:
                # Очищаем refresh token
                refresh_token = refresh_token.replace('"', '')

                # Проверяем refresh token
                refresh_payload = jwt.decode(
                    refresh_token,
                    SECRET_KEY,
                    algorithms=[ALGORITHM]
                )
                
                if refresh_payload.get("type") != "refresh":
                    logger.warning(f"[{request_id}] Invalid refresh token type")
                    request.state.clear_tokens = True
                    return await call_next(request)

                # Проверяем срок действия
                now = datetime.now(timezone.utc).timestamp()
                refresh_exp = refresh_payload.get("exp")
                if refresh_exp and refresh_exp <= now:
                    logger.warning(f"[{request_id}] Refresh token has expired")
                    request.state.clear_tokens = True
                    return await call_next(request)

                # Пробуем восстановить access token
                with SessionLocal() as db:
                    try:
                        new_access_token, _ = refresh_access_token(refresh_token, db)
                        request.state.new_access_token = new_access_token
                        logger.info(f"[{request_id}] Successfully restored access token")
                    except Exception as e:
                        logger.error(f"[{request_id}] Error restoring access token: {str(e)}")
                        request.state.clear_tokens = True
                        return await call_next(request)

            except JWTError as e:
                logger.error(f"[{request_id}] Invalid refresh token while restoring access: {str(e)}")
                request.state.clear_tokens = True
                return await call_next(request)
            except Exception as e:
                logger.error(f"[{request_id}] Error while restoring access token: {str(e)}")
                request.state.clear_tokens = True
                return await call_next(request)

        # Получаем response от следующего middleware или конечной точки
        response = await call_next(request)

        try:
            # Если был сгенерирован новый access token, устанавливаем его в cookie
            new_access_token = request.state.new_access_token
            new_refresh_token = request.state.new_refresh_token
            clear_tokens = request.state.clear_tokens

            if clear_tokens:
                # Очищаем куки при ошибке
                cookie_settings = get_cookie_settings(request)
                response.delete_cookie("access_token", **cookie_settings)
                response.delete_cookie("refresh_token", **cookie_settings)
                logger.info(f"[{request_id}] Cleared authentication cookies due to error")
            
            elif new_access_token:
                # Устанавливаем новые токены
                cookie_settings = get_cookie_settings(request)
                token_expiration = get_token_expiration()

                response.set_cookie(
                    key="access_token",
                    value=f"Bearer {new_access_token}",
                    max_age=token_expiration['access_token'],
                    **cookie_settings
                )
                logger.info(f"[{request_id}] Set new access token")

                if new_refresh_token:
                    response.set_cookie(
                        key="refresh_token",
                        value=new_refresh_token,
                        max_age=token_expiration['refresh_token'],
                        **cookie_settings
                    )
                    logger.info(f"[{request_id}] Set new refresh token")

        except Exception as e:
            logger.error(f"[{request_id}] Error setting cookies in middleware: {str(e)}")
            # В случае ошибки установки кук, пытаемся очистить их
            try:
                cookie_settings = get_cookie_settings(request)
                response.delete_cookie("access_token", **cookie_settings)
                response.delete_cookie("refresh_token", **cookie_settings)
            except:
                pass

        logger.info(f"[{request_id}] Completed token refresh middleware")
        return response
