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

            # Проверяем количество активных сессий
            active_sessions = self.get_active_sessions_count(db, user.id)
            if active_sessions >= 5:  # Максимум 5 активных сессий
                self.logger.warning(f"Too many active sessions for user {user.username} ({active_sessions})")
                # Деактивируем самую старую сессию
                oldest_session = db.query(UserSession).filter(
                    UserSession.user_id == user.id,
                    UserSession.is_active == True
                ).order_by(UserSession.created_at.asc()).first()
                
                if oldest_session:
                    oldest_session.is_active = False
                    oldest_session.deactivated_at = datetime.now(timezone.utc)
                    oldest_session.deactivation_reason = "Too many active sessions"
                    self.logger.info(f"Deactivated oldest session {oldest_session.id} for user {user.username}")

            current_time = datetime.now(timezone.utc)
            session = UserSession(
                user_id=user.id,
                ip_address=ip_address,
                user_agent=user_agent,
                created_at=current_time,
                last_activity=current_time,
                access_token_jti=access_token_jti,
                refresh_token_jti=refresh_token_jti,
                is_active=True
            )

            db.add(session)
            db.commit()

            self.logger.info(
                f"Created new session {session.id} for user {user.username} from IP {ip_address}"
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

    def cleanup_all_old_sessions(self, db: Session) -> tuple[int, int]:
        """
        Очищает старые и неактивные сессии.

        Returns:
            tuple[int, int]: (количество деактивированных сессий, количество удаленных сессий)
        """
        try:
            current_time = datetime.now(timezone.utc)

            # Деактивируем сессии, неактивные более 3 дней
            inactive_threshold = current_time - timedelta(days=3)
            deactivated = db.query(UserSession).filter(
                UserSession.is_active == True,
                UserSession.last_activity < inactive_threshold
            ).update({
                "is_active": False,
                "deactivated_at": current_time,
                "deactivation_reason": "Inactive for 3 days"
            })

            # Удаляем сессии старше 7 дней
            deletion_threshold = current_time - timedelta(days=7)
            deleted = db.query(UserSession).filter(
                UserSession.last_activity < deletion_threshold
            ).delete()

            db.commit()
            self.logger.info(f"Session cleanup: {deactivated} sessions deactivated, {deleted} sessions deleted")
            return deactivated, deleted

        except Exception as e:
            self.logger.error(f"Error during session cleanup: {str(e)}")
            db.rollback()
            return 0, 0

    def update_session_activity(self, db: Session, session: UserSession) -> bool:
        """Обновляет время последней активности сессии"""
        try:
            # Проверяем, не слишком ли старая сессия
            current_time = datetime.now(timezone.utc)
            session_age = current_time - session.created_at
            
            if session_age > timedelta(days=7):
                self.logger.warning(f"Session {session.id} is too old (age: {session_age.days} days), deactivating")
                session.is_active = False
                session.deactivated_at = current_time
                session.deactivation_reason = "Session expired"
                db.commit()
                return False
                
            # Проверяем, не была ли сессия неактивной слишком долго
            if session.last_activity:
                inactivity_period = current_time - session.last_activity
                if inactivity_period > timedelta(days=3):
                    self.logger.warning(f"Session {session.id} was inactive for too long ({inactivity_period.days} days), deactivating")
                    session.is_active = False
                    session.deactivated_at = current_time
                    session.deactivation_reason = "Long inactivity"
                    db.commit()
                    return False

            session.last_activity = current_time
            db.commit()
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating session activity: {str(e)}")
            db.rollback()
            return False
