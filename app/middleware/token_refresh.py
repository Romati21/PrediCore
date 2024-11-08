from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request, Response
import logging

class TokenRefreshMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        # Выполняем запрос
        response = await call_next(request)

        # Проверяем наличие новых токенов
        tokens_info = getattr(request.state, 'new_tokens', None)

        if tokens_info and isinstance(response, Response):
            try:
                # Устанавливаем новый access token
                if 'access_token' in tokens_info:
                    access_info = tokens_info['access_token']
                    response.set_cookie(
                        key="access_token",
                        value=f"Bearer {access_info['token']}",  # Добавляем префикс Bearer
                        max_age=access_info['expires_in'],
                        httponly=True,
                        samesite='lax',
                        secure=request.url.scheme == "https"
                    )
                    logging.info("Access token updated")

                # Устанавливаем новый refresh token если есть
                if 'refresh_token' in tokens_info:
                    refresh_info = tokens_info['refresh_token']
                    response.set_cookie(
                        key="refresh_token",
                        value=refresh_info['token'],
                        max_age=refresh_info['expires_in'],
                        httponly=True,
                        samesite='lax',
                        secure=request.url.scheme == "https"
                    )
                    logging.info("Refresh token updated")

            except Exception as e:
                logging.error(f"Error setting tokens in cookies: {str(e)}")

        return response


def foo():
    print("Hello, World!")
