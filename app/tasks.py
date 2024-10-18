import shutil
from app.database import SessionLocal
from app import models
from datetime import datetime, timedelta
import os
import logging

logger = logging.getLogger(__name__)

TEMP_DIR = 'static/temp'

def cleanup_unused_drawings(db):
    unused_threshold = datetime.now() - timedelta(days=30)
    unused_drawings = db.query(models.Drawing).filter(models.Drawing.last_used_at < unused_threshold).all()
    for drawing in unused_drawings:
        if os.path.exists(drawing.file_path):
            os.remove(drawing.file_path)
        db.delete(drawing)
    db.commit()

# Асинхронная функция для очистки временной папки
async def clean_temp_folder():
    try:
        if os.path.exists(TEMP_DIR):
            shutil.rmtree(TEMP_DIR)
        os.makedirs(TEMP_DIR)
        logger.info("Временная папка успешно очищена")
    except Exception as e:
        logger.error(f"Ошибка при очистке временной папки: {str(e)}")
