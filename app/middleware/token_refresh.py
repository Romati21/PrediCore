from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from datetime import datetime, timezone
from jose import jwt
from app.auth.auth import refresh_access_token, SECRET_KEY, ALGORITHM, get_cookie_settings, get_token_expiration
import logging
from starlette.datastructures import Headers

class TokenRefreshMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        # Получаем response от следующего middleware или конечной точки
        response = await call_next(request)

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
