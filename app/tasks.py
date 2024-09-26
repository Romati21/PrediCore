import shutil
from app.database import SessionLocal
from app import models
from datetime import datetime, timedelta
import os

def cleanup_unused_drawings(db):
    unused_threshold = datetime.now() - timedelta(days=30)
    unused_drawings = db.query(models.Drawing).filter(models.Drawing.last_used_at < unused_threshold).all()
    for drawing in unused_drawings:
        if os.path.exists(drawing.file_path):
            os.remove(drawing.file_path)
        db.delete(drawing)
    db.commit()

def clean_temp_folder():
    temp_dir = 'static/temp'
    shutil.rmtree(temp_dir)
    os.makedirs(temp_dir)
