from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from datetime import datetime, timezone
from jose import jwt
from app.auth.auth import refresh_access_token, SECRET_KEY, ALGORITHM, get_cookie_settings, get_token_expiration
import logging
from starlette.datastructures import Headers
from app.database import SessionLocal
from app.models import UserSession
from app.services import session_service

class TokenRefreshMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        # Получаем response от следующего middleware или конечной точки
        response = await call_next(request)

        try:
            # Получаем access token из cookies
            access_token = request.cookies.get("access_token")
            if access_token:
                # Декодируем токен для получения JTI
                payload = jwt.decode(
                    access_token.replace('Bearer ', '').replace('"', ''),
                    SECRET_KEY,
                    algorithms=[ALGORITHM],
                    options={"verify_exp": False}
                )
                access_jti = payload.get("jti")
                
                if access_jti:
                    # Обновляем время последней активности сессии
                    with SessionLocal() as db:
                        session = db.query(UserSession).filter(
                            UserSession.access_token_jti == access_jti,
                            UserSession.is_active == True
                        ).first()
                        
                        if session:
                            session_service.update_session_activity(db, session)
                            logging.debug(f"Updated last activity for session {session.id}")

        except Exception as e:
            logging.error(f"Error updating session activity: {str(e)}")

        # Проверяем, был ли сгенерирован новый access token в get_current_user
        new_access_token = getattr(request.state, 'new_access_token', None)
        if new_access_token:
            # Получаем настройки для cookie
            cookie_settings = get_cookie_settings(request)
            token_expiration = get_token_expiration()

            # Устанавливаем новый access token в cookies с правильным сроком действия
            response.set_cookie(
                key="access_token",
                value=new_access_token,
                max_age=token_expiration["access_token"],
                **cookie_settings
            )

            # Логируем успешное обновление токена
            logging.info("Access token was successfully refreshed")

        return response
