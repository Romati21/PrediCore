from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request, Response
from typing import Optional

class TokenRefreshMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Проверяем, был ли создан новый токен
        new_token = getattr(request.state, 'new_access_token', None)
        if new_token and isinstance(response, Response):
            response.set_cookie(
                key="access_token",
                value=new_token,
                httponly=True,
                samesite='lax',
                secure=request.url.scheme == "https",
                max_age=1800
            )

        return response

class TokenUpdateMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # Если есть новый access token в state, обновляем куки
        new_token = getattr(request.state, 'new_access_token', None)
        if new_token:
            response.set_cookie(
                key="access_token",
                value=new_token,
                httponly=True,
                samesite='lax',
                secure=request.url.scheme == "https",
                max_age=1800
            )

        return response
