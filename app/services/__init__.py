# app/services/__init__.py
import logging
from .session_service import SessionService
from .session_cleanup import SessionCleanupService

logging.info("Initializing services...")
session_service = SessionService()
cleanup_service = SessionCleanupService()
logging.info("Services initialized")

__all__ = ['session_service', 'cleanup_service']
