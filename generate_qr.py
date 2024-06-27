import qrcode
import os

def generate_qr_code(data: str, batch_number: str, filename: str, size: int = 512):
    """
    Генерирует QR-код с заданными данными и сохраняет его в файл.

    Args:
        data: Данные, которые нужно закодировать в QR-код.
        batch_number: Номер партии, который будет включен в имя файла.
        filename: Имя файла для сохранения QR-кода (включая расширение .png).
        size: Размер QR-кода в пикселях (по умолчанию 512x512).
    """
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    img.resize((size, size)).save(filename)

if __name__ == "__main__":
    batch_number = input("Номер партии: ")
    part_number = input("Номер детали: ")
    quantity = input("Количество: ")

    data = f"Партия: {batch_number}, Деталь: {part_number}, Количество: {quantity}"

    qr_code_dir = "static/qr_codes/"
    os.makedirs(qr_code_dir, exist_ok=True)

    filename = os.path.join(qr_code_dir, f"qr_code_{batch_number}.png")  # Добавляем номер партии в имя файла
    generate_qr_code(data, batch_number, filename, size=86)
    print(f"QR-код сохранен в файл: {filename}")
