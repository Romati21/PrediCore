from datetime import datetime, timezone
from typing import Optional, Dict, Any
from jose import JWTError, jwt

def should_refresh_access_token(token: str, secret_key: str, algorithm: str) -> bool:
    """Проверяет, нужно ли обновить access token"""
    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm], options={"verify_exp": False})
        exp_timestamp = int(payload.get("exp", 0))
        current_time = int(datetime.now(timezone.utc).timestamp())
        
        # Обновляем токен если до истечения осталось менее 5 минут
        return (exp_timestamp - current_time) < 300
    except JWTError:
        return False

def decode_token_payload(token: str, secret_key: str, algorithm: str) -> Optional[Dict[str, Any]]:
    """Безопасно декодирует payload токена"""
    try:
        return jwt.decode(token, secret_key, algorithms=[algorithm], options={"verify_exp": False})
    except JWTError:
        return None
