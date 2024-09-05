from fastapi import FastAPI, WebSocket, Depends, HTTPException, Request, Form, UploadFile, File, BackgroundTasks
from app.utils import file_utils
import asyncio
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.websockets import WebSocketDisconnect
from sqlalchemy.orm import Session
from app import models, repository, schemas
from app.database import SessionLocal, engine
from app.cleanup_drawings import cleanup_original_drawings
from app.websocket_manager import manager
from app.schemas import ProductionOrderCreate
from datetime import date, datetime
from pydantic import BaseModel
from pathlib import Path
from sqlalchemy.sql import func
from sqlalchemy.orm import Session
from PIL import Image, ImageDraw, ImageFont, ImageFile
from typing import List, Optional
import qrcode, os, math, time, shutil, io, base64, re, random, string, logging, json, traceback
import aiofiles
from pydantic import ValidationError
import os
from PIL import Image, ImageDraw, ImageFont
import logging
import hashlib
import mimetypes


# Настройка логгирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Определяем все необходимые директории
STATIC_DIR = "static"
TEMP_DIR = os.path.join(STATIC_DIR, "temp")
UPLOAD_DIR = os.path.join(STATIC_DIR, "uploads")
DRAWINGS_DIR = os.path.join(STATIC_DIR, "drawings")
QR_CODE_DIR = os.path.join(STATIC_DIR, "qr_codes")
MODIFIED_DRAWINGS_DIR = os.path.join(STATIC_DIR, "modified_drawings")
ARCHIVED_DRAWINGS_DIR = os.path.join(STATIC_DIR, "archived_drawings")

# Список всех директорий, которые нужно создать
DIRECTORIES_TO_CREATE = [
    STATIC_DIR,
    TEMP_DIR,
    DRAWINGS_DIR,
    MODIFIED_DRAWINGS_DIR,
    ARCHIVED_DRAWINGS_DIR,
    UPLOAD_DIR,
    QR_CODE_DIR
]

# Создаем все необходимые директории
for directory in DIRECTORIES_TO_CREATE:
    os.makedirs(directory, exist_ok=True)

def generate_timestamp():
    return f"{int(time.time()):08X}"

class Order(BaseModel):
    order_number: str
    customer_name: str
    product_name: str
    quantity: int

models.Base.metadata.create_all(bind=engine)

app = FastAPI()
static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    logger.info(f"WebSocket соединение установлено: {websocket.client}")
    try:
        while True:
            data = await websocket.receive_text()
            if data == 'pong':
                continue  # Игнорируем pong-сообщения
            elif data != 'ping':
                logger.info(f"Получено сообщение: {data}")
                await manager.broadcast(f"Message text was: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info(f"WebSocket соединение закрыто: {websocket.client}")
    except Exception as e:
        logger.error(f"Ошибка WebSocket: {e}")
        manager.disconnect(websocket)

def calculate_file_hash(file_path):
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        # Читаем и обновляем хэш блоками по 4K
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

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

# @app.post("/api/create_order")
# async def create_order(order: Order, db: Session = Depends(get_db)):
#     # Генерация уникального номера заказа (вы можете использовать свою логику)
#     unique_id = repository.generate_unique_id(db)

#     # Создание QR-кода
#     qr = qrcode.QRCode(version=1, box_size=10, border=5)
#     qr.add_data(f"Order ID: {unique_id}, Customer: {order.customer_name}, Product: {order.product_name}, Quantity: {order.quantity}")
#     qr.make(fit=True)
#     img = qr.make_image(fill_color="black", back_color="white")

#     # Сохранение QR-кода в байтовый поток
#     buffer = io.BytesIO()
#     img.save(buffer)
#     qr_code = base64.b64encode(buffer.getvalue()).decode()

#     # Сохранение заказа в базу данных
#     new_order = repository.create_order(db, unique_id, order.customer_name, order.product_name, order.quantity)

#     return JSONResponse({
#         "order_id": unique_id,
#         "qr_code": qr_code
#     })


def generate_qr_code_with_text(data, text):
    BASE_DIR = Path(__file__).resolve().parent
    FONT_PATH = BASE_DIR / "static" / "fonts" / "CommitMonoNerdFont-Bold.otf"

    qr = qrcode.QRCode(version=1, box_size=10, border=3, error_correction=qrcode.constants.ERROR_CORRECT_H)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert('RGB')

    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(str(FONT_PATH), 140)  # Выберите шрифт и размер
    text_width, text_height = draw.textbbox((0, 0), text, font=font)[2:]  # Используем textbbox
    text_x = (img.width - text_width) // 2
    text_y = (img.height - text_height) // 2 - 10  # Сдвигаем текст вверх
    draw.text((text_x + 1, text_y + 1), text, font=font, fill="black")  # Черная тень
    draw.text((text_x, text_y), text, font=font, fill="white")  # Белый текст

    return img

def save_qr_code(order, drawing):
    qr_data = f"Order: {order.order_number}, Drawing: {drawing.file_name}"
    qr_image = generate_qr_code_with_text(qr_data, order.order_number)

    # Создаем директорию для QR-кодов, если она не существует
    os.makedirs(QR_CODE_DIR, exist_ok=True)

    # Генерируем имя файла QR-кода
    qr_filename = f"qr_code_{order.id}_{drawing.id}.png"
    qr_path = os.path.join(QR_CODE_DIR, qr_filename)

    # Сохраняем изображение
    qr_image.save(qr_path, format="PNG")

    # Возвращаем относительный путь к файлу QR-кода
    return os.path.relpath(qr_path, 'static')

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

@app.get("/production_orders", response_class=HTMLResponse)
async def show_production_orders(request: Request, db: Session = Depends(get_db)):
    orders = db.query(models.ProductionOrder).order_by(models.ProductionOrder.publication_date.desc()).all()
    logger.info(f"Получено {len(orders)} заказов из базы данных")
    return templates.TemplateResponse("production_orders.html", {"request": request, "orders": orders})



class OrderDataCreate(BaseModel):
    drawing_designation: str
    quantity: int
    desired_production_date_start: date
    desired_production_date_end: date
    required_material: str
    metal_delivery_date: str
    notes: str = None

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff'}

def is_allowed_file(filename: str) -> bool:
    return os.path.splitext(filename)[1].lower() in ALLOWED_EXTENSIONS

async def save_upload_file(upload_file: UploadFile, destination: str) -> str:
    try:
        async with aiofiles.open(destination, 'wb') as out_file:
            content = await upload_file.read()
            if len(content) > MAX_FILE_SIZE:
                raise HTTPException(status_code=413, detail="File too large")
            await out_file.write(content)
        return destination
    except Exception:
        raise HTTPException(status_code=500, detail="Could not save file")

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


@app.post("/create_order")
async def create_order(
    drawing_designation: str = Form(...),
    quantity: int = Form(...),
    desired_production_date_start: str = Form(...),
    desired_production_date_end: str = Form(...),
    required_material: str = Form(...),
    metal_delivery_date: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    drawing_files: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    try:
        logger.info(f"Received order data: drawing_designation={drawing_designation}, "
                    f"quantity={quantity}, desired_production_date_start={desired_production_date_start}, "
                    f"desired_production_date_end={desired_production_date_end}, "
                    f"required_material={required_material}, metal_delivery_date={metal_delivery_date}, "
                    f"notes={notes}, number of files: {len(drawing_files)}")

        start_date = datetime.strptime(desired_production_date_start, "%d.%m.%Y").date()
        end_date = datetime.strptime(desired_production_date_end, "%d.%m.%Y").date()

        # Генерируем уникальный номер заказа
        order_number = generate_order_number(drawing_designation, db)

        order_data = schemas.ProductionOrderCreate(
            order_number=order_number,
            drawing_designation=drawing_designation,
            quantity=quantity,
            desired_production_date_start=start_date,
            desired_production_date_end=end_date,
            required_material=required_material,
            metal_delivery_date=metal_delivery_date,
            notes=notes,
            publication_date=datetime.now().date(),
            drawing_files=[]  # Пустой список, который мы заполним позже
        )

        new_order = repository.create_production_order(db, order_data)
        logger.info(f"Order created with ID: {new_order.id} and number: {new_order.order_number}")

        processed_files = []
        for drawing_file in drawing_files:
            if not file_utils.is_allowed_file(drawing_file.filename):
                raise HTTPException(status_code=400, detail=f"Invalid file type: {drawing_file.filename}")

            processed_file = await process_uploaded_file(drawing_file)
            processed_files.append(processed_file)

            file_size = os.path.getsize(processed_file['path'])
            mime_type = file_utils.get_mime_type(processed_file['path'])

            drawing = repository.get_or_create_drawing(db, processed_file['hash'], processed_file['path'], processed_file['filename'], file_size, mime_type)
            order_drawing = repository.create_order_drawing(db, new_order.id, drawing.id)

            # Генерируем QR-код
            qr_data = f"Order: {new_order.order_number}, Drawing: {drawing.file_name}"
            qr_image = generate_qr_code_with_text(qr_data, new_order.order_number)

            # Создаем директорию для QR-кодов, если она не существует
            os.makedirs(QR_CODE_DIR, exist_ok=True)

            # Сохраняем QR-код
            qr_filename = f"qr_code_{new_order.id}_{drawing.id}.png"
            qr_path = os.path.join(QR_CODE_DIR, qr_filename)
            qr_image.save(qr_path, format="PNG")

            # Обновляем путь к QR-коду в базе данных
            order_drawing.qr_code_path = os.path.relpath(qr_path, 'static')

        new_order.drawing_link = ','.join([file['path'] for file in processed_files])
        db.commit()

        # Отправляем уведомление о новом заказе
        await manager.broadcast(json.dumps({"action": "new_order", "order": new_order.to_dict()}))

        return JSONResponse(content={
            "message": "Order created successfully", 
            "order_id": new_order.id,
            "order_number": new_order.order_number,
            "processed_files": processed_files
        }, status_code=201)

    except ValidationError as e:
        logger.error(f"Validation error: {e.json()}")
        raise HTTPException(status_code=422, detail=f"Validation error: {e.errors()}")
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error creating order: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

@app.post("/edit_production_order/{order_id}")
async def update_production_order(
    request: Request,
    order_id: int,
    drawing_designation: str = Form(...),
    drawing_files: List[UploadFile] = File(None),
    quantity: int = Form(...),
    desired_production_date_start: str = Form(...),
    desired_production_date_end: str = Form(...),
    required_material: str = Form(...),
    metal_delivery_date: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    delete_drawing: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    try:
        logger.info(f"Начало обновления заказа {order_id}")

        order = db.query(models.ProductionOrder).filter(models.ProductionOrder.id == order_id).first()
        if not order:
            raise HTTPException(status_code=404, detail="Заказ не найден")

        # Обновляем данные заказа
        order.drawing_designation = drawing_designation
        order.quantity = quantity
        order.desired_production_date_start = datetime.strptime(desired_production_date_start, "%d.%m.%Y").date()
        order.desired_production_date_end = datetime.strptime(desired_production_date_end, "%d.%m.%Y").date()
        order.required_material = required_material
        order.metal_delivery_date = metal_delivery_date
        order.notes = notes

        # Обработка удаления чертежей
        if delete_drawing:
            delete_drawing_list = delete_drawing.split(',')
            for drawing_id in delete_drawing_list:
                order_drawing = db.query(models.OrderDrawing).filter(
                    models.OrderDrawing.order_id == order.id,
                    models.OrderDrawing.drawing_id == int(drawing_id)
                ).first()
                if order_drawing:
                    db.delete(order_drawing)
                    drawing = db.query(models.Drawing).filter(models.Drawing.id == int(drawing_id)).first()
                    if drawing:
                        drawing.archived_at = func.now()
                        db.add(drawing)
                        logger.info(f"Drawing {drawing_id} archived for order {order_id}")

        # Обработка новых чертежей
        if drawing_files:
            for drawing_file in drawing_files:
                if drawing_file.filename:
                    processed_file = await process_uploaded_file(drawing_file)

                    file_size = os.path.getsize(processed_file['path'])
                    mime_type = file_utils.get_mime_type(processed_file['path'])

                    drawing = repository.get_or_create_drawing(db, processed_file['hash'], processed_file['path'], processed_file['filename'], file_size, mime_type)

                    existing_order_drawing = db.query(models.OrderDrawing).filter(
                        models.OrderDrawing.order_id == order.id,
                        models.OrderDrawing.drawing_id == drawing.id
                    ).first()

                    if not existing_order_drawing:
                        order_drawing = repository.create_order_drawing(db, order.id, drawing.id)

                        qr_data = f"Order: {order.order_number}, Drawing: {drawing.file_name}"
                        qr_image = generate_qr_code_with_text(qr_data, order.order_number)

                        qr_filename = f"qr_code_{order.id}_{drawing.id}.png"
                        qr_path = os.path.join(QR_CODE_DIR, qr_filename)
                        qr_image.save(qr_path, format="PNG")

                        order_drawing.qr_code_path = os.path.relpath(qr_path, 'static')

                    logger.info(f"Drawing {drawing.file_name} added/updated for order {order_id}")

        db.commit()
        logger.info(f"Заказ успешно обновлен: {order.id}")

        update_message = json.dumps({"action": "update_order", "order": order.to_dict()})
        logger.info(f"Отправка уведомления об обновлении: {update_message}")
        await manager.broadcast(update_message)

        return JSONResponse(content={
            "message": "Order updated successfully",
            "order_id": order.id,
            "order_number": order.order_number
        }, status_code=200)

    except Exception as e:
        logger.error(f"Ошибка при обновлении заказа: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка при обновлении заказа: {str(e)}")


def archive_drawing(drawing_path: str, order_number: str) -> str:
    try:
        logger.info(f"Попытка архивации чертежа: {drawing_path}")

        source_path = os.path.join(STATIC_DIR, drawing_path)
        if not os.path.exists(source_path):
            logger.error(f"Исходный файл не найден: {source_path}")
            return None

        # Создаем имя для архивного файла
        archive_filename = f"archived_{order_number}_{os.path.basename(drawing_path)}"
        archive_path = os.path.join(ARCHIVED_DRAWINGS_DIR, archive_filename)

        # Перемещаем файл в архивную директорию
        shutil.move(source_path, archive_path)
        logger.info(f"Чертеж успешно перемещен в архив: {archive_path}")

        return os.path.join('archived_drawings', archive_filename)
    except Exception as e:
        logger.error(f"Ошибка при архивации чертежа: {str(e)}")
        return None

@app.put("/update_order/{order_id}")
async def update_order(
    order_id: int,
    order_data: schemas.ProductionOrderUpdate,
    drawing_file: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    try:
        # Обновляем данные заказа
        updated_order = repository.update_production_order(db, order_id, order_data)

        if drawing_file:
            # Если загружен новый чертеж, обрабатываем его
            file_hash = await file_utils.calculate_file_hash(drawing_file)
            file_path = file_utils.get_file_path(file_hash)
            await file_utils.save_file(drawing_file, file_path)
            file_size = file_utils.get_file_size(file_path)
            mime_type = file_utils.get_mime_type(drawing_file.filename)

            # Создаем или получаем запись о чертеже
            drawing = repository.get_or_create_drawing(db, file_hash, file_path, drawing_file.filename, file_size, mime_type)

            # Удаляем старые связи чертежей с заказом
            repository.delete_order_drawings(db, order_id)

            # Создаем новую связь чертежа с заказом
            order_drawing = repository.create_order_drawing(db, order_id, drawing.id)

        return {"message": "Order updated successfully", "order_id": updated_order.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/production_order_form", response_class=HTMLResponse)
async def production_order_form(request: Request):
    return templates.TemplateResponse("production_order_form.html", {"request": request, "order": None})


def process_drawing(drawing_path: str, order: models.ProductionOrder) -> str:
    try:
        logger.info(f"Начало обработки чертежа: {drawing_path}")

        # Проверяем существование файла
        if not os.path.exists(drawing_path):
            logger.error(f"Файл не найден: {drawing_path}")
            return None

        with Image.open(drawing_path).convert('RGBA') as img:
            logger.info(f"Изображение открыто успешно. Размер: {img.size}")

            # Генерация QR-кода
            qr_code_data = f"Заказ-наряд №: {order.order_number}\n" \
                           f"Дата публикации: {order.publication_date.strftime('%d.%m.%Y')}\n" \
                           f"Обозначение чертежа: {order.drawing_designation}\n" \
                           f"Количество: {order.quantity}\n" \
                           f"Желательная дата изготовления: {order.desired_production_date_start.strftime('%d.%m.%Y')} - {order.desired_production_date_end.strftime('%d.%m.%Y')}\n" \
                           f"Необходимый материал: {order.required_material}\n" \
                           f"Срок поставки металла: {order.metal_delivery_date}\n" \
                           f"Примечания: {order.notes}"
            logger.info("QR-код данные подготовлены")

            qr_code_img = generate_qr_code_with_text(qr_code_data, order.order_number)
            logger.info("QR-код сгенерирован")

            qr_code = Image.open(io.BytesIO(base64.b64decode(qr_code_img.split(',')[1])))
            logger.info("QR-код изображение создано")

            # Определяем ориентацию чертежа
            is_landscape = img.width > img.height
            logger.info(f"Ориентация чертежа: {'альбомная' if is_landscape else 'портретная'}")

            # Вычисляем размер QR-кода
            if is_landscape:
                qr_size_ratio = 0.14  # 14% от высоты изображения для альбомной ориентации
                qr_size_px = int(img.height * qr_size_ratio)
            else:
                qr_size_ratio = 0.2  # 20% от ширины изображения для портретной ориентации
                qr_size_px = int(img.width * qr_size_ratio)
            logger.info(f"Размер QR-кода: {qr_size_px}x{qr_size_px} пикселей")

            # Создаем новое изображение с белым фоном для QR-кода
            qr_background = Image.new('RGBA', (qr_size_px, qr_size_px), (255, 255, 255, 255))
            qr_code = qr_code.resize((qr_size_px, qr_size_px), Image.LANCZOS).convert('RGBA')
            logger.info("QR-код подготовлен для вставки")

            # Наложение QR-кода на белый фон
            qr_background.alpha_composite(qr_code)
            logger.info("QR-код наложен на белый фон")

            # Вычисляем позицию для QR-кода (правый нижний угол с отступом)
            offset_ratio = 0.015  # 1.5% от размера изображения
            offset_px = int(img.width * offset_ratio)
            qr_position = (img.width - qr_size_px - offset_px, img.height - qr_size_px - offset_px)
            logger.info(f"Позиция QR-кода: {qr_position}")

            # Вставляем QR-код
            img.alpha_composite(qr_background, qr_position)
            logger.info("QR-код вставлен в изображение")

            # Добавляем дату загрузки
            draw = ImageDraw.Draw(img)
            upload_date = datetime.now().strftime('%d.%m.%Y')

            # Используем TrueType шрифт
            BASE_DIR = Path(__file__).resolve().parent
            FONT_PATH = BASE_DIR / "static" / "fonts" / "CommitMonoNerdFont-Bold.otf"
            font_size = 56
            font = ImageFont.truetype(str(FONT_PATH), font_size)
            logger.info(f"Шрифт загружен: {FONT_PATH}")

            # Вычисляем позицию для даты (левый нижний угол с отступом)
            date_position = (offset_px, img.height - offset_px - font_size)
            logger.info(f"Позиция даты: {date_position}")

            # Рисуем текст с тенью для лучшей читаемости
            shadow_color = (200, 200, 200)  # Светло-серый цвет для тени
            draw.text((date_position[0]+1, date_position[1]+1), f"{upload_date}", font=font, fill=shadow_color)
            draw.text(date_position, f"{upload_date}", font=font, fill=(0, 0, 0))
            logger.info("Дата добавлена на изображение")

            # Сохранение обработанного чертежа
            processed_filename = f"{order.order_number}_{int(time.time())}.png"
            processed_filepath = os.path.join(MODIFIED_DRAWINGS_DIR, processed_filename)
            img.save(processed_filepath, format='PNG')
            logger.info(f"Обработанный чертеж сохранен: {processed_filepath}")

            # Проверяем, что файл действительно сохранился
            if os.path.exists(processed_filepath):
                logger.info(f"Файл успешно сохранен: {processed_filepath}")
                return processed_filepath
            else:
                logger.error(f"Не удалось сохранить файл: {processed_filepath}")
                return None

    except Exception as e:
        logger.error(f"Ошибка при обработке чертежа: {str(e)}", exc_info=True)
        return None

@app.get("/print_drawing/{filename}", response_class=HTMLResponse)
async def print_drawing(request: Request, filename: str):
    # 1. Проверяем, существует ли файл
    filepath = os.path.join(TEMP_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Чертеж не найден")

    # 2. Отдаем HTML для печати
    return templates.TemplateResponse("print_drawing.html", {"request": request, "drawing_path": f"/static/temp/{filename}"})

def mm_to_pixels(mm, dpi):
    """Конвертирует миллиметры в пиксели."""
    return int(mm / 25.4 * dpi)

# Увеличиваем лимит для больших файлов
Image.MAX_IMAGE_PIXELS = None
ImageFile.LOAD_TRUNCATED_IMAGES = True

def standardize_image(image_path, target_dpi=300, max_size=(5000, 5000)):
    try:
        # Создаем имя для стандартизированного изображения
        base_name = os.path.basename(image_path)
        standardized_path = os.path.join(TEMP_DIR, f"{base_name}_standardized.png")

        # Проверяем, существует ли уже стандартизированное изображение
        if os.path.exists(standardized_path):
            # Если существует, просто возвращаем путь к нему и его размеры
            with Image.open(standardized_path) as img:
                return str(standardized_path), img.size, img.size

        # Открываем изображение
        with Image.open(image_path) as img:
            # Получаем текущее DPI
            dpi = img.info.get('dpi', (96, 96))
            dpi = max(dpi[0], 96)

            # Сохраняем исходные размеры
            original_size = img.size

            # Вычисляем новые размеры для целевого DPI, сохраняя соотношение сторон
            scale_factor = target_dpi / dpi
            new_width = int(img.width * scale_factor)
            new_height = int(img.height * scale_factor)

            # Проверяем, не превышает ли новый размер максимально допустимый
            if new_width > max_size[0] or new_height > max_size[1]:
                # Если превышает, уменьшаем, сохраняя соотношение сторон
                scale = min(max_size[0] / new_width, max_size[1] / new_height)
                new_width = int(new_width * scale)
                new_height = int(new_height * scale)

            new_size = (new_width, new_height)

            # Изменяем размер изображения
            img_resized = img.resize(new_size, Image.LANCZOS)

            # Устанавливаем новое DPI
            img_resized.info['dpi'] = (target_dpi, target_dpi)

            # Сохраняем стандартизированное изображение
            img_resized.save(standardized_path, dpi=(target_dpi, target_dpi))

        logger.info(f"Изображение успешно стандартизировано: {standardized_path}")
        return str(standardized_path), original_size, new_size

    except Exception as e:
        logger.error(f"Ошибка при стандартизации изображения {image_path}: {str(e)}")
        raise

def safe_get_mtime(file_path):
    try:
        return os.path.getmtime(file_path)
    except FileNotFoundError:
        logger.warning(f"Файл не найден: {file_path}")
        return None

async def process_uploaded_file(file: UploadFile):
    try:
        # Создаем временный файл
        temp_file_path = os.path.join(TEMP_DIR, file.filename)
        with open(temp_file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)

        # Стандартизируем изображение
        standardized_path, original_size, new_size = standardize_image(temp_file_path)

        # Перемещаем стандартизированное изображение в папку uploads
        final_path = os.path.join(UPLOAD_DIR, os.path.basename(standardized_path))
        os.rename(standardized_path, final_path)

        # Удаляем оригинальный файл
        os.remove(temp_file_path)

        # Вычисляем хэш файла
        file_hash = calculate_file_hash(final_path)

        # Получаем размер файла
        file_size = os.path.getsize(final_path)

        return {
            "filename": os.path.basename(final_path),
            "path": final_path,
            "original_size": original_size,
            "new_size": new_size,
            "hash": file_hash,
            "file_size": file_size,
            "mime_type": mimetypes.guess_type(final_path)[0] or 'application/octet-stream'
        }
    except Exception as e:
        logger.error(f"Ошибка при обработке файла {file.filename}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка при обработке файла: {str(e)}")



def archive_old_drawing(drawing_path):
    drawing_path = drawing_path.replace('static/', '').lstrip('/')
    full_path = os.path.join(os.getcwd(), STATIC_DIR, drawing_path)
    if os.path.exists(full_path):
        archive_dir = os.path.join(STATIC_DIR, "archived_drawings")
        if not os.path.exists(archive_dir):
            os.makedirs(archive_dir)
        archived_filename = f"archived_{os.path.basename(drawing_path)}"
        archived_path = os.path.join(archive_dir, archived_filename)
        shutil.move(full_path, archived_path)
        logger.info(f"Чертеж архивирован: {archived_path}")
        return f"archived_drawings/{archived_filename}"
    else:
        logger.warning(f"Чертеж не найден для архивации: {full_path}")
        return None



@app.get("/view_drawing/{order_id}")
async def view_drawing(request: Request, order_id: int, db: Session = Depends(get_db)):
    order = db.query(models.ProductionOrder).filter(models.ProductionOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")

    # Получаем только актуальные (не архивированные) чертежи
    current_drawings = db.query(models.Drawing, models.OrderDrawing.qr_code_path).join(models.OrderDrawing).filter(
        models.OrderDrawing.order_id == order_id,
        models.Drawing.archived_at == None
    ).all()

    drawing_info = []
    for drawing, qr_code_path in current_drawings:
        # Удаляем префикс "static/" из пути к файлу, если он есть
        file_path = drawing.file_path
        if file_path.startswith("static/"):
            file_path = file_path[7:]
        
        if qr_code_path and qr_code_path.startswith("static/"):
            qr_code_path = qr_code_path[7:]

        drawing_info.append({
            "path": file_path,
            "name": drawing.file_name,
            "qr_code_path": qr_code_path
        })

    logger.info(f"Drawing info: {drawing_info}")

    return templates.TemplateResponse("view_drawing.html", {
        "request": request,
        "order": order,
        "drawings": drawing_info
    })

@app.get("/edit_production_order/{order_id}")
async def edit_production_order(request: Request, order_id: int, db: Session = Depends(get_db)):
    order = db.query(models.ProductionOrder).filter(models.ProductionOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")

    # Загружаем связанные чертежи с дополнительной информацией
    order_drawings = db.query(models.OrderDrawing).filter(models.OrderDrawing.order_id == order_id).all()
    drawings_info = []

    for order_drawing in order_drawings:
        drawing = db.query(models.Drawing).filter(models.Drawing.id == order_drawing.drawing_id).first()
        if drawing and not drawing.archived_at:
            drawings_info.append({
                "id": drawing.id,
                "file_name": drawing.file_name,
                "file_path": drawing.file_path.replace('static/', ''),
                "qr_code_path": order_drawing.qr_code_path
            })

    return templates.TemplateResponse("production_order_form.html", {
        "request": request,
        "order": order,
        "drawings": drawings_info
    })

@app.get("/drawing_history/{order_id}")
async def drawing_history(request: Request, order_id: int, db: Session = Depends(get_db)):
    order = db.query(models.ProductionOrder).filter(models.ProductionOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")

    # Получаем актуальные чертежи
    current_drawings = db.query(models.Drawing, models.OrderDrawing.qr_code_path).join(models.OrderDrawing).filter(
        models.OrderDrawing.order_id == order_id,
        models.Drawing.archived_at == None
    ).all()

    # Получаем архивированные чертежи
    archived_drawings = db.query(models.Drawing, models.OrderDrawing.qr_code_path).join(models.OrderDrawing).filter(
        models.OrderDrawing.order_id == order_id,
        models.Drawing.archived_at != None
    ).all()

    def process_drawings(drawings):
        return [
            {
                "path": drawing.file_path[7:] if drawing.file_path.startswith("static/") else drawing.file_path,
                "name": drawing.file_name,
                "qr_code_path": qr_code_path[7:] if qr_code_path and qr_code_path.startswith("static/") else qr_code_path
            }
            for drawing, qr_code_path in drawings
        ]

    current_drawings_processed = process_drawings(current_drawings)
    archived_drawings_processed = process_drawings(archived_drawings)

    logger.info(f"Current drawings: {current_drawings_processed}")
    logger.info(f"Archived drawings: {archived_drawings_processed}")

    return templates.TemplateResponse("drawing_history.html", {
        "request": request,
        "order": order,
        "current_drawings": current_drawings_processed,
        "archived_drawings": archived_drawings_processed
    })

@app.get("/api/orders")
async def get_orders(db: Session = Depends(get_db)):
    orders = db.query(models.ProductionOrder).all()
    return [order.to_dict() for order in orders]


@app.post("/upload_drawing")
async def upload_drawing(
    file: UploadFile = File(...),
    order_id: int = Form(...),
    db: Session = Depends(get_db)
):
    try:
        # Вычисление хеша файла
        file_hash = await file_utils.calculate_file_hash(file)

        # Проверка существования чертежа с таким хешем
        existing_drawing = repository.get_drawing_by_hash(db, file_hash)
        if existing_drawing:
            # Если чертеж уже существует, обновляем время последнего использования
            repository.update_drawing_last_used(db, existing_drawing.id)
            file_path = existing_drawing.file_path
        else:
            # Если чертеж новый, сохраняем его
            file_path = file_utils.get_file_path(file_hash)
            await file_utils.save_file(file, file_path)

        # Получаем информацию о файле
        file_size = file_utils.get_file_size(file_path)
        mime_type = file_utils.get_mime_type(file.filename)

        # Создаем или получаем запись о чертеже
        drawing = repository.get_or_create_drawing(db, file_hash, file_path, file.filename, file_size, mime_type)

        # Связываем чертеж с заказом
        order_drawing = repository.create_order_drawing(db, order_id, drawing.id)

        return {"message": "Drawing uploaded successfully", "drawing_id": drawing.id, "order_drawing_id": order_drawing.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/order_drawings/{order_id}")
def get_order_drawings(order_id: int, db: Session = Depends(get_db)):
    drawings = repository.get_drawings_by_order(db, order_id)
    return {"drawings": [{"id": d.id, "file_name": d.file_name, "file_path": d.file_path} for d in drawings]}

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8443,
        ssl_keyfile="key.pem",
        ssl_certfile="cert.pem"
    )
