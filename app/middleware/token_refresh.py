from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from datetime import datetime, timezone
from jose import jwt, JWTError
from app.auth.auth import refresh_access_token, SECRET_KEY, ALGORITHM, get_cookie_settings, get_token_expiration
import logging
from starlette.datastructures import Headers
from app.database import SessionLocal
from app.models import UserSession
from app.services import session_service

class TokenRefreshMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        try:
            # Получаем access token из cookies
            access_token = request.cookies.get("access_token")
            refresh_token = request.cookies.get("refresh_token")

            if access_token and refresh_token:
                try:
                    # Пробуем декодировать access token
                    payload = jwt.decode(
                        access_token.replace('Bearer ', '').replace('"', ''),
                        SECRET_KEY,
                        algorithms=[ALGORITHM]
                    )
                    
                    # Если токен валиден, обновляем активность сессии
                    access_jti = payload.get("jti")
                    if access_jti:
                        with SessionLocal() as db:
                            session = db.query(UserSession).filter(
                                UserSession.access_token_jti == access_jti,
                                UserSession.is_active == True
                            ).first()
                            
                            if session:
                                session_service.update_session_activity(db, session)
                                logging.debug(f"Updated last activity for session {session.id}")
                
                except JWTError as e:
                    # Если access token истек, пробуем его обновить
                    logging.debug(f"Access token error: {str(e)}, attempting refresh")
                    try:
                        with SessionLocal() as db:
                            new_access_token, _ = refresh_access_token(refresh_token, db)
                            request.state.new_access_token = new_access_token
                    except Exception as refresh_error:
                        logging.error(f"Failed to refresh token: {str(refresh_error)}")

        except Exception as e:
            logging.error(f"Error in token refresh middleware: {str(e)}")

        # Получаем response от следующего middleware или конечной точки
        response = await call_next(request)

        # Если был сгенерирован новый access token, устанавливаем его в cookie
        new_access_token = getattr(request.state, 'new_access_token', None)
        if new_access_token:
            cookie_settings = get_cookie_settings(request)
            token_expiration = get_token_expiration()

            response.set_cookie(
                key="access_token",
                value=f"Bearer {new_access_token}",
                max_age=token_expiration["access_token"],
                **cookie_settings
            )
            logging.info("Access token was successfully refreshed")

        return response
