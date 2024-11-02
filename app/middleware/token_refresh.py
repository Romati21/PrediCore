# app/middleware/token_refresh.py
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request, Response
from typing import Optional
import logging

class TokenRefreshMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        
        # Проверяем наличие информации о новых токенах
        tokens_info = getattr(request.state, 'new_tokens', None)
        if tokens_info and isinstance(response, Response):
            try:
                # Устанавливаем новый access token
                if 'access_token' in tokens_info:
                    access_info = tokens_info['access_token']
                    response.set_cookie(
                        key="access_token",
                        value=access_info['token'],
                        max_age=access_info['expires_in'],
                        httponly=True,
                        samesite='lax',
                        secure=request.url.scheme == "https"
                    )
                    logging.info("Access token refreshed successfully")

                # Устанавливаем новый refresh token, если он есть
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
                    logging.info("Refresh token updated successfully")

            except Exception as e:
                logging.error(f"Error setting refreshed tokens: {str(e)}")

        return response

# class TokenUpdateMiddleware(BaseHTTPMiddleware):
#     async def dispatch(self, request: Request, call_next) -> Response:
#         response = await call_next(request)

#         # Если есть новый access token в state, обновляем куки
#         new_token = getattr(request.state, 'new_access_token', None)
#         if new_token:
#             response.set_cookie(
#                 key="access_token",
#                 value=new_token,
#                 httponly=True,
#                 samesite='lax',
#                 secure=request.url.scheme == "https",
#                 max_age=1800
#             )

#         return response
