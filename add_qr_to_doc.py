from PIL import Image
import os

def add_qr_code_to_document(document_path, qr_code_path):
    """
    Добавляет QR-код в правый нижний угол документа, не выходя за рамки.

    Args:
        document_path: Путь к файлу документа.
        qr_code_path: Путь к файлу QR-кода.
    """
    try:
        document = Image.open(document_path)
        qr_code = Image.open(qr_code_path)

        # Определяем размер QR-кода, чтобы он поместился в рамке
        frame_width, frame_height = document.size
        qr_size = min(frame_width // 5, frame_height // 5)
        qr_code = qr_code.resize((qr_size, qr_size))

        # Находим координаты для вставки QR-кода
        qr_x = frame_width - qr_size - 10
        qr_y = frame_height - qr_size - 10

        # Вставляем QR-код в документ
        document.paste(qr_code, (qr_x, qr_y))

        # Создаем имя файла для измененного документа
        base, ext = os.path.splitext(document_path)
        new_document_path = f"{base}_with_qr{ext}"

        # Сохраняем измененный документ в новый файл
        document.save(new_document_path)
        print(f"QR-код добавлен в документ: {new_document_path}")

    except FileNotFoundError:
        print(f"Ошибка: файл не найден - {document_path} или {qr_code_path}")
    except Exception as e:
        print(f"Ошибка при добавлении QR-кода: {e}")

if __name__ == "__main__":
    # Запрашиваем пути к файлам у пользователя
    document_path = input("Введите путь к файлу документа: ")
    qr_code_path = input("Введите путь к файлу QR-кода: ")

    add_qr_code_to_document(document_path, qr_code_path)
