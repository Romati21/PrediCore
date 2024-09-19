import hashlib
import os
import aiofiles
from fastapi import UploadFile
from datetime import datetime

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff'}

def calculate_file_hash(file_content: bytes) -> str:
    """
    Асинхронно вычисляет SHA-256 хеш для загруженного файла.
    """
    return hashlib.sha256(file_content).hexdigest()

def get_file_path(file_hash: str, file_extension: str) -> str:
    """
    Генерирует путь для сохранения файла на основе его хеша.
    """
    today = datetime.now()
    directory = os.path.join('static', 'drawings', str(today.year), f"{today.month:02d}", f"{today.day:02d}")
    os.makedirs(directory, exist_ok=True)
    return os.path.join(directory, f"{file_hash}{file_extension}")

async def save_file(file_content: bytes, file_path: str) -> None:
    """
    Асинхронно сохраняет загруженный файл по указанному пути.
    """
    directory = os.path.dirname(file_path)
    os.makedirs(directory, exist_ok=True)
    async with aiofiles.open(file_path, 'wb') as out_file:
        await out_file.write(file_content)

def get_file_size(file_path: str) -> int:
    """
    Возвращает размер файла в байтах.
    """
    return os.path.getsize(file_path)

def get_mime_type(filename: str) -> str:
    """
    Определяет MIME-тип файла на основе его расширения.
    """
    extension = os.path.splitext(filename)[1].lower()
    mime_types = {
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.gif': 'image/gif',
        '.bmp': 'image/bmp',
        '.tiff': 'image/tiff',
        '.pdf': 'application/pdf'
    }
    return mime_types.get(extension, 'application/octet-stream')

async def delete_file(file_path: str) -> None:
    try:
        os.remove(file_path)
    except OSError as e:
        print(f"Error deleting file {file_path}: {e}")


def is_allowed_file(filename: str) -> bool:
    return os.path.splitext(filename)[1].lower() in ALLOWED_EXTENSIONS


