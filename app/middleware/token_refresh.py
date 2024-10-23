from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
from fastapi.responses import Response

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
