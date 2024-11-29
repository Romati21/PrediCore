from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from datetime import datetime, timezone
from jose import jwt
from app.auth.auth import refresh_access_token, SECRET_KEY, ALGORITHM
import logging
from starlette.datastructures import Headers

class TokenRefreshMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        access_token = request.cookies.get("access_token")
        refresh_token = request.cookies.get("refresh_token")

        logging.debug(f"Incoming access_token: {access_token}")
        logging.debug(f"Incoming refresh_token: {refresh_token}")

        if access_token and refresh_token:
            try:
                payload = jwt.decode(
                    access_token.replace('Bearer ', '').replace('"', ''),
                    SECRET_KEY,
                    algorithms=[ALGORITHM],
                    options={"verify_exp": False}
                )
                exp_timestamp = payload.get("exp", 0)
                current_time = datetime.now(timezone.utc).timestamp()

                # Если токен истекает через 5 минут или уже истек
                if (exp_timestamp - current_time) < 300:
                    new_access_token, _ = refresh_access_token(refresh_token)

                    logging.debug(f"Generated new access_token: {new_access_token}")

                    # Устанавливаем обновленный токен в cookies
                    response = await call_next(request)
                    response.set_cookie(
                        key="access_token",
                        value=new_access_token,
                        httponly=True,
                        samesite='lax',
                        max_age=1800
                    )

                    # Создаем новый объект запроса с обновленным заголовком
                    updated_headers = Headers(
                        {**request.headers, "Authorization": f"Bearer {new_access_token}"}
                    )
                    request = Request(
                        scope={**request.scope, "headers": updated_headers.raw},
                        receive=request.receive
                    )

                    return await call_next(request)

            except Exception as e:
                logging.error(f"Error refreshing token: {e}")

        return await call_next(request)
