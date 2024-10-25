import logging
import asyncio
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.database import get_db
from app.models import UserSession

class SessionCleanupService:
    def __init__(self):
        self.is_running = False
        self.cleanup_interval = 24 * 60 * 60  # 24 часа в секундах
        self._sleep_task = None  # Добавляем отслеживание задачи сна

    async def cleanup_expired_sessions(self, db: Session):
        """Очистка истекших сессий"""
        try:
            current_time = datetime.now(timezone.utc)
            cutoff_time = current_time - timedelta(days=7)

            expired_sessions = db.query(UserSession).filter(
                UserSession.is_active == True,
                or_(
                    UserSession.expired_at < current_time,
                    UserSession.last_activity < cutoff_time
                )
            ).all()

            count = len(expired_sessions)
            if count > 0:
                for session in expired_sessions:
                    session.is_active = False
                    session.cleanup_reason = "Автоматическая очистка истекших сессий"
                    session.expired_at = current_time

                    if session.access_token_jti or session.refresh_token_jti:
                        await session.revoke_tokens(
                            db=db,
                            revoked_by_user=session.user,
                            reason="Автоматическая очистка истекших сессий"
                        )

                db.commit()
                logging.info(f"Cleaned up {count} expired sessions")

        except Exception as e:
            db.rollback()
            logging.error(f"Error during session cleanup: {str(e)}")

    async def run_cleanup_task(self):
        """Запуск периодической очистки"""
        logging.info("Starting cleanup service...")
        self.is_running = True

        while self.is_running:
            try:
                db = next(get_db())
                try:
                    await self.cleanup_expired_sessions(db)
                finally:
                    db.close()
            except Exception as e:
                logging.error(f"Error in cleanup task: {str(e)}")

            if self.is_running:  # Проверяем перед сном
                try:
                    # Создаем задачу сна, которую можно отменить
                    self._sleep_task = asyncio.create_task(asyncio.sleep(self.cleanup_interval))
                    await self._sleep_task
                except asyncio.CancelledError:
                    logging.info("Cleanup task sleep cancelled")
                    break

        logging.info("Cleanup service stopped")

    async def stop(self):
        """Корректное завершение сервиса"""
        logging.info("Stopping cleanup service...")
        self.is_running = False
        if self._sleep_task and not self._sleep_task.done():
            self._sleep_task.cancel()
            try:
                await self._sleep_task
            except asyncio.CancelledError:
                pass
        logging.info("Cleanup service stopped")
