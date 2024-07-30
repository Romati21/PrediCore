from fastapi import FastAPI, Depends, HTTPException, Request, Form, UploadFile, File
from sqlalchemy.orm import Session
from app import models, repository
from app.database import SessionLocal, engine
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from datetime import date, datetime
from pydantic import BaseModel
from pathlib import Path
import qrcode, os, math
from PIL import Image, ImageDraw, ImageFont
import io, base64, re, random, string, logging


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if not os.path.exists("./static/drawings"):
    os.makedirs("./static/drawings")

if not os.path.exists("static/modified_drawings"):
    os.makedirs("static/modified_drawings")

class Order(BaseModel):
    order_number: str
    customer_name: str
    product_name: str
    quantity: int

models.Base.metadata.create_all(bind=engine)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("form.html", {"request": request})

@app.post("/submit")
async def submit_data(batch_number: str = Form(...), part_number: str = Form(...), quantity: int = Form(...), db: Session = Depends(get_db)):
    inventory_item = repository.create_inventory(db, batch_number, part_number, quantity)
    return {"Успех": "Данные добавлены"}

@app.get("/data", response_class=HTMLResponse)
async def show_data(request: Request, db: Session = Depends(get_db)):
    inventory = repository.get_inventory(db)
    return templates.TemplateResponse("data.html", {"request": request, "data": inventory})

@app.post("/api/create_order")
async def create_order(order: Order, db: Session = Depends(get_db)):
    # Генерация уникального номера заказа (вы можете использовать свою логику)
    unique_id = repository.generate_unique_id(db)

    # Создание QR-кода
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(f"Order ID: {unique_id}, Customer: {order.customer_name}, Product: {order.product_name}, Quantity: {order.quantity}")
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    # Сохранение QR-кода в байтовый поток
    buffer = io.BytesIO()
    img.save(buffer)
    qr_code = base64.b64encode(buffer.getvalue()).decode()

    # Сохранение заказа в базу данных
    new_order = repository.create_order(db, unique_id, order.customer_name, order.product_name, order.quantity)

    return JSONResponse({
        "order_id": unique_id,
        "qr_code": qr_code
    })


def generate_qr_code_with_text(data, text):
    BASE_DIR = Path(__file__).resolve().parent
    FONT_PATH = BASE_DIR / "static" / "fonts" / "CommitMonoNerdFont-Bold.otf"

    qr = qrcode.QRCode(version=1, box_size=10, border=3, error_correction=qrcode.constants.ERROR_CORRECT_H)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert('RGB')

    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(str(FONT_PATH), 280)  # Выберите шрифт и размер
    text_width, text_height = draw.textbbox((0, 0), text, font=font)[2:] # Используем textbbox
    text_x = (img.width - text_width) // 2
    text_y = (img.height - text_height) // 2 - 10  #  Сдвигаем текст вверх
    draw.text((text_x + 1, text_y + 1), text, font=font, fill="black") #  Черная тень
    draw.text((text_x, text_y), text, font=font, fill="white")        #  Белый текст

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    img_str = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/png;base64,{img_str}"


@app.get("/print_order/{order_id}", response_class=HTMLResponse)
async def print_order(request: Request, order_id: int, db: Session = Depends(get_db)):
    order = db.query(models.ProductionOrder).filter(models.ProductionOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")

    # Генерация QR-кода
    qr_code_data = f"Заказ-наряд №: {order.order_number}\n" \
                    f"Дата публикации: {order.publication_date.strftime('%d.%m.%Y')}\n" \
                    f"Обозначение чертежа: {order.drawing_designation}\n" \
                    f"Количество: {order.quantity}\n" \
                    f"Желательная дата изготовления: {order.desired_production_date_start.strftime('%d.%m.%Y')} - {order.desired_production_date_end.strftime('%d.%m.%Y')}\n" \
                    f"Необходимый материал: {order.required_material}\n" \
                    f"Срок поставки металла: {order.metal_delivery_date}\n" \
                    f"Примечания: {order.notes}"

    qr_code_img = generate_qr_code_with_text(qr_code_data, order.order_number)


    return templates.TemplateResponse("order_blank.html", {"request": request, "order": order, "qr_code_img": qr_code_img})

@app.get("/production_order_form", response_class=HTMLResponse)
async def production_order_form(request: Request):
    return templates.TemplateResponse("production_order_form.html", {"request": request})

def generate_order_number(drawing_designation, db):
    # Извлекаем первые две цифры из drawing_designation
    match = re.search(r'\d{2}', drawing_designation)
    if match:
        prefix = match.group()
    else:
        prefix = '00'  # Если цифры не найдены, используем '00'

    def generate_unique_code():
        # Генерируем 4-значный код из цифр и заглавных букв
        chars = string.ascii_uppercase + string.digits
        return ''.join(random.choice(chars) for _ in range(4))

    while True:
        unique_code = generate_unique_code()
        order_number = f'{prefix}{unique_code}'

        # Проверяем, существует ли уже такой order_number
        existing_order = db.query(models.ProductionOrder).filter_by(order_number=order_number).first()
        if not existing_order:
            return order_number

@app.post("/submit_production_order")
async def submit_production_order(
    drawing_designation: str = Form(...),
    drawing_file: UploadFile = File(...),
    quantity: int = Form(...),
    desired_production_date_start: str = Form(...),
    desired_production_date_end: str = Form(...),
    required_material: str = Form(...),
    publication_date=date.today(),
    metal_delivery_date: str = Form(...),
    notes: str = Form(None),
    db: Session = Depends(get_db)
):
    date_format = "%d.%m.%Y"
    try:
        desired_production_date_start_parsed = datetime.strptime(desired_production_date_start, date_format).date()
        desired_production_date_end_parsed = datetime.strptime(desired_production_date_end, date_format).date()
    except ValueError as e:
        return {"error": f"Ошибка формата даты. Используйте {date_format}"}

    # Генерируем order_number
    order_number = generate_order_number(drawing_designation, db)

    # Сохраняем загруженный файл
    file_location = f"./static/drawings/{order_number}_{drawing_file.filename}"
    with open(file_location, "wb+") as file_object:
        file_object.write(await drawing_file.read())

    drawing_link = f"/static/drawings/{order_number}_{drawing_file.filename}"

    production_order = repository.create_production_order(
        db=db,
        order_number=order_number,
        drawing_designation=drawing_designation,
        drawing_link=drawing_link,
        quantity=quantity,
        desired_production_date_start=desired_production_date_start_parsed,
        desired_production_date_end=desired_production_date_end_parsed,
        required_material=required_material,
        metal_delivery_date=metal_delivery_date,
        notes=notes or ""
    )
    return RedirectResponse(url="/production_order_form", status_code=303)

@app.get("/production_orders", response_class=HTMLResponse)
async def show_production_orders(request: Request, db: Session = Depends(get_db)):
    orders = repository.get_production_orders(db)
    return templates.TemplateResponse("production_orders.html", {"request": request, "orders": orders})

@app.post("/process_drawing")
async def process_drawing(request: Request, order_number: str, drawing_url: str, db: Session = Depends(get_db)):
    try:
        # 1. Загружаем чертеж с локального сайта
        response = requests.get(drawing_url)
        response.raise_for_status()  # Проверяем на ошибки HTTP

        # 2. Создаем временный файл
        temp_filename = f"drawing_{order_number}_{''.join(random.choice(string.ascii_letters) for _ in range(8))}.jpg"
        temp_filepath = Path("temp") / temp_filename
        temp_filepath.parent.mkdir(exist_ok=True)
        with open(temp_filepath, "wb") as temp_file:
            temp_file.write(response.content)

        # 3. Добавляем QR-код
        qr_code_data = f"Заказ-наряд №: {order_number}" #  Данные для QR-кода
        qr_code_img = generate_qr_code_with_text(qr_code_data, order_number)

        # 4. Открываем изображение, добавляем QR-код и сохраняем
        drawing_img = Image.open(temp_filepath)
        qr_code_img = Image.open(io.BytesIO(base64.b64decode(qr_code_img.split(",")[1])))
        qr_code_img = qr_code_img.resize((100, 100))  # Изменяем размер QR-кода
        drawing_img.paste(qr_code_img, (drawing_img.width - 110, drawing_img.height - 110))  # Помещаем QR-код в правый нижний угол
        drawing_img.save(temp_filepath)

        # 5. Генерируем URL для печати
        print_url = f"/print_drawing/{temp_filename}"

        return {"status": "success", "print_url": print_url}

    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка загрузки чертежа: {e}")
        raise HTTPException(status_code=500, detail="Ошибка загрузки чертежа")
    except Exception as e:
        logger.error(f"Ошибка обработки чертежа: {e}")
        raise HTTPException(status_code=500, detail="Ошибка обработки чертежа")

@app.get("/print_drawing/{filename}", response_class=HTMLResponse)
async def print_drawing(request: Request, filename: str):
    # 1. Проверяем, существует ли файл
    filepath = Path("temp") / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Чертеж не найден")

    # 2. Отдаем HTML для печати
    return templates.TemplateResponse("print_drawing.html", {"request": request, "drawing_path": f"/temp/{filename}"})

def mm_to_pixels(mm, dpi):
    """Конвертирует миллиметры в пиксели."""
    return int(mm / 25.4 * dpi)

def standardize_image(image_path, target_dpi=300):
    with Image.open(image_path) as img:
        # Получаем текущее DPI
        dpi = img.info.get('dpi', (96, 96))
        dpi = max(dpi[0], 96)

        # Сохраняем исходные размеры
        original_width, original_height = img.size

        # Вычисляем новые размеры для целевого DPI
        new_width = int(img.width * target_dpi / dpi)
        new_height = int(img.height * target_dpi / dpi)

        # Изменяем размер изображения
        img_resized = img.resize((new_width, new_height), Image.LANCZOS)

        # Устанавливаем новое DPI
        img_resized.info['dpi'] = (target_dpi, target_dpi)

        # Сохраняем стандартизированное изображение
        standardized_path = image_path.replace('.', '_standardized.')
        img_resized.save(standardized_path, dpi=(target_dpi, target_dpi))

    return standardized_path, (original_width, original_height), (new_width, new_height)

@app.get("/view_drawing/{order_id}")
async def view_drawing(request: Request, order_id: int, db: Session = Depends(get_db)):
    order = db.query(models.ProductionOrder).filter(models.ProductionOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")

    # Генерация QR-кода
    qr_code_data = f"Заказ-наряд №: {order.order_number}\n" \
                   f"Дата публикации: {order.publication_date.strftime('%d.%m.%Y')}\n" \
                   f"Обозначение чертежа: {order.drawing_designation}\n" \
                   f"Количество: {order.quantity}\n" \
                   f"Желательная дата изготовления: {order.desired_production_date_start.strftime('%d.%m.%Y')} - {order.desired_production_date_end.strftime('%d.%m.%Y')}\n" \
                   f"Необходимый материал: {order.required_material}\n" \
                   f"Срок поставки металла: {order.metal_delivery_date}\n" \
                   f"Примечания: {order.notes}"

    qr_code_img = generate_qr_code_with_text(qr_code_data, order.order_number)

    # Получаем путь к чертежу
    drawing_path = order.drawing_link.lstrip('/')

    # Проверяем, существует ли уже обработанный чертеж
    modified_drawings_dir = "static/modified_drawings"
    modified_drawing_filename = f"{order.order_number}_{Path(drawing_path).stem}_modified.png"
    modified_drawing_path = os.path.join(modified_drawings_dir, modified_drawing_filename)

    if os.path.exists(modified_drawing_path):
        # Если обработанный чертеж существует, используем его
        img = Image.open(modified_drawing_path).convert('RGBA')
        original_size = new_size = img.size  # Используем текущий размер как оригинальный и новый
    else:
        # Если обработанного чертежа нет, выполняем стандартизацию
        standardized_drawing_path, original_size, new_size = standardize_image(drawing_path)
        img = Image.open(standardized_drawing_path).convert('RGBA')

    # Теперь мы всегда работаем с изображением 300 DPI
    dpi = 300

    # Определяем ориентацию чертежа
    is_landscape = img.width > img.height

    # Преобразуем base64 QR-код в изображение
    qr_code = Image.open(io.BytesIO(base64.b64decode(qr_code_img.split(',')[1])))

    # Вычисляем размер QR-кода относительно оригинального размера изображения
    original_width, original_height = original_size
    if is_landscape:
        qr_size_ratio = 0.14  # 14% от высоты изображения для альбомной ориентации
        qr_size_px = int(original_height * qr_size_ratio)
    else:
        qr_size_ratio = 0.2  # 20% от ширины изображения для портретной ориентации
        qr_size_px = int(original_width * qr_size_ratio)

    # Масштабируем размер QR-кода для нового размера изображения
    scale_factor = new_size[0] / original_size[0]
    qr_size_px = int(qr_size_px * scale_factor)

    qr_code = qr_code.resize((qr_size_px, qr_size_px), Image.LANCZOS)

    # Вычисляем позицию для QR-кода (правый нижний угол с отступом)
    offset_ratio = 0.015 # 2% от размера изображения
    offset_px = int(img.width * offset_ratio)
    qr_position = (img.width - qr_code.width - offset_px, img.height - qr_code.height - offset_px)

    # Создаем новое изображение с белым фоном для QR-кода
    qr_background = Image.new('RGBA', (qr_size_px + 20, qr_size_px + 20), (255, 255, 255, 255))
    qr_background.paste(qr_code, (10, 10))

    # Вставляем QR-код с белым фоном
    img.paste(qr_background, (qr_position[0] - 10, qr_position[1] - 10), qr_background)

    # Добавляем дату загрузки
    draw = ImageDraw.Draw(img)

    # Используем TrueType шрифт
    BASE_DIR = Path(__file__).resolve().parent
    FONT_PATH = BASE_DIR / "static" / "fonts" / "CommitMonoNerdFont-Bold.otf"

    # Вычисляем размер шрифта относительно размера изображения
    if is_landscape:
        font_size_ratio = 0.30 # 1.5% от высоты изображения для альбомной ориентации
        font_size = int(img.height * font_size_ratio)
    else:
        font_size_ratio = 0.39  # 2% от ширины изображения для портретной ориентации
        font_size = int(img.width * font_size_ratio)

    # Устанавливаем минимальный и максимальный размер шрифта
    min_font_size = 12
    max_font_size = 96
    font_size = max(min(font_size, max_font_size), min_font_size)

    font = ImageFont.truetype(str(FONT_PATH), font_size)

    upload_date = datetime.fromtimestamp(os.path.getmtime(drawing_path)).strftime('%d.%m.%Y')

    # Вычисляем позицию для даты (левый нижний угол с отступом)
    date_offset_ratio = 0.015  # 2% от размера изображения
    date_offset_px = int(img.width * date_offset_ratio)

    bbox = draw.textbbox((0, 0), f"{upload_date}", font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    date_position = (date_offset_px, img.height - text_height - date_offset_px)

    # Рисуем текст с тенью для лучшей читаемости
    shadow_color = (200, 200, 200)  # Светло-серый цвет для тени
    draw.text((date_position[0]+1, date_position[1]+1), f"{upload_date}", font=font, fill=shadow_color)
    draw.text(date_position, f"{upload_date}", font=font, fill=(0, 0, 0))

    # Сохраняем модифицированное изображение
    if not os.path.exists(modified_drawings_dir):
        os.makedirs(modified_drawings_dir)

    modified_drawing_path = os.path.join(modified_drawings_dir, f"{order.order_number}_{upload_date}.png")
    img.save(modified_drawing_path, format='PNG')


    return templates.TemplateResponse("view_drawing.html", {"request": request, "order": order, "drawing_path": "/" + modified_drawing_path})

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8443,
        ssl_keyfile="key.pem",
        ssl_certfile="cert.pem"
    )
