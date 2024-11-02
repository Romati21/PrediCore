import logging
from datetime import datetime, timedelta, timezone
from ipaddress import ip_address, IPv4Address, IPv6Address
from sqlalchemy.orm import Session
from app.models import UserSession, User
from typing import Optional

class SessionService:
    def __init__(self):
        self.logger = self._setup_session_logging()

    @staticmethod
    def _setup_session_logging() -> logging.Logger:
        """Настройка логирования для сессий"""
        logger = logging.getLogger('session_manager')
        handler = logging.FileHandler('logs/sessions.log')
        handler.setFormatter(
            logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        )
        logger.addHandler(handler)
        return logger

    @staticmethod
    def validate_ip_address(ip: str) -> bool:
        """Проверка валидности IP адреса"""
        try:
            ip_obj = ip_address(ip)
            return isinstance(ip_obj, (IPv4Address, IPv6Address))
        except ValueError:
            return False

    def cleanup_old_sessions(
        self,
        db: Session,
        user_id: int,
        max_age_days: int = 30
    ) -> None:
        """Очистка старых неактивных сессий"""
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=max_age_days)
            result = db.query(UserSession).filter(
                UserSession.user_id == user_id,
                UserSession.last_activity < cutoff_date,
                UserSession.is_active == False
            ).delete()

            db.commit()
            self.logger.info(
                f"Cleaned up {result} old sessions for user_id {user_id}"
            )
        except Exception as e:
            db.rollback()
            self.logger.error(
                f"Error cleaning up sessions for user_id {user_id}: {str(e)}"
            )
            raise

    def create_session(
        self,
        db: Session,
        user: User,
        ip_address: str,
        user_agent: str,
        access_token_jti: str,
        refresh_token_jti: str
    ) -> Optional[UserSession]:
        """Создание новой сессии"""
        try:
            if not self.validate_ip_address(ip_address):
                self.logger.warning(f"Invalid IP address attempted: {ip_address}")
                return None

            session = UserSession(
                user_id=user.id,
                ip_address=ip_address,
                user_agent=user_agent,
                last_activity=datetime.now(timezone.utc),
                access_token_jti=access_token_jti,
                refresh_token_jti=refresh_token_jti
            )

            db.add(session)
            db.commit()

            self.logger.info(
                f"Created new session for user {user.username} from IP {ip_address}"
            )
            return session

        except Exception as e:
            db.rollback()
            self.logger.error(
                f"Error creating session for user {user.username}: {str(e)}"
            )
            raise

    def get_active_sessions_count(
        self,
        db: Session,
        user_id: int
    ) -> int:
        """Получение количества активных сессий пользователя"""
        return db.query(UserSession).filter(
            UserSession.user_id == user_id,
            UserSession.is_active == True
        ).count()
