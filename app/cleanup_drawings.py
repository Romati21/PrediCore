import os
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

def cleanup_original_drawings(order_number: str):
    modified_drawings_dir = Path("static/modified_drawings")
    original_drawings_dir = Path("static/drawings")

    if not modified_drawings_dir.exists() or not original_drawings_dir.exists():
        logger.warning("Одна из директорий не существует. Очистка невозможна.")
        return

    # Ищем все файлы, начинающиеся с номера заказа в папке с оригинальными чертежами
    original_drawings = list(original_drawings_dir.glob(f"{order_number}*"))

    if original_drawings:
        for original_drawing in original_drawings:
            # Проверяем, существует ли модифицированная версия
            modified_drawing = list(modified_drawings_dir.glob(f"{order_number}*"))
            if modified_drawing:
                try:
                    original_drawing.unlink()
                    logger.info(f"Удален оригинальный чертеж: {original_drawing}")
                except Exception as e:
                    logger.error(f"Ошибка при удалении файла {original_drawing}: {str(e)}")
            else:
                logger.warning(f"Модифицированный чертеж для {original_drawing.name} не найден. Пропускаем удаление.")
    else:
        logger.warning(f"Оригинальные чертежи для заказа {order_number} не найдены.")

    # Удаляем стандартизированные версии, если они есть
    standardized_drawings = list(original_drawings_dir.glob(f"{order_number}*_standardized.png"))
    for std_drawing in standardized_drawings:
        try:
            std_drawing.unlink()
            logger.info(f"Удален стандартизированный чертеж: {std_drawing}")
        except Exception as e:
            logger.error(f"Ошибка при удалении стандартизированного файла {std_drawing}: {str(e)}")

    logger.info(f"Очистка оригинальных чертежей для заказа {order_number} завершена.")

# Пример использования:
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    cleanup_original_drawings()
