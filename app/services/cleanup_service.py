from sqlalchemy.orm import Session
from app.models import UserSession
from datetime import datetime, timezone, timedelta
import logging
import asyncio

class SessionCleanupService:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._running = False
        self._stop_event = asyncio.Event()

    def cleanup_all_old_sessions(self, db: Session) -> tuple[int, int]:
        """
        Очищает старые и неактивные сессии.
        
        Returns:
            tuple[int, int]: (количество деактивированных сессий, количество удаленных сессий)
        """
        try:
            current_time = datetime.now(timezone.utc)
            
            # Деактивируем сессии, неактивные более 7 дней
            inactive_threshold = current_time - timedelta(days=7)
            deactivated = db.query(UserSession).filter(
                UserSession.is_active == True,
                UserSession.last_activity < inactive_threshold
            ).update({
                "is_active": False
            })
            
            # Удаляем сессии старше 30 дней
            deletion_threshold = current_time - timedelta(days=30)
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

    async def run_cleanup_task(self):
        """Запускает асинхронную задачу очистки сессий"""
        self._running = True
        self._stop_event.clear()
        
        while self._running and not self._stop_event.is_set():
            try:
                from app.database import SessionLocal
                db = SessionLocal()
                try:
                    deactivated, deleted = self.cleanup_all_old_sessions(db)
                    self.logger.info(f"Async cleanup completed: {deactivated} deactivated, {deleted} deleted")
                finally:
                    db.close()
                
                # Ждем 24 часа или до получения сигнала остановки
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=86400)  # 24 часа
                except asyncio.TimeoutError:
                    continue  # Продолжаем цикл после таймаута
                
            except Exception as e:
                self.logger.error(f"Error in cleanup task: {str(e)}")
                # Ждем 5 минут перед повторной попыткой в случае ошибки
                await asyncio.sleep(300)

    async def stop(self):
        """Останавливает задачу очистки"""
        self._running = False
        self._stop_event.set()

# Создаем глобальный экземпляр сервиса
cleanup_service = SessionCleanupService()
