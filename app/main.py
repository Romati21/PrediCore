from fastapi import FastAPI, Depends, HTTPException, Request, Form
from sqlalchemy.orm import Session
from app import models, repository
from app.database import SessionLocal, engine
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from datetime import date, datetime
from pydantic import BaseModel
from pathlib import Path
import qrcode
from PIL import Image, ImageDraw, ImageFont
import io, base64, re, random, string, logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

    qr = qrcode.QRCode(version=1, box_size=10, border=5, error_correction=qrcode.constants.ERROR_CORRECT_H)
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
    img.save("qr_code_with_text.png")
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
    drawing_link: str = Form(...),
    quantity: int = Form(...),
    desired_production_date_start: str = Form(...),  # Изменено на str
    desired_production_date_end: str = Form(...),    # Изменено на str
    required_material: str = Form(...),
    publication_date=date.today(),  # Устанавливаем текущую дату
    metal_delivery_date: str = Form(...),
    notes: str = Form(...),
    db: Session = Depends(get_db)
):
    date_format = "%d.%m.%Y"
    try:
        desired_production_date_start_parsed = datetime.strptime(desired_production_date_start, date_format).date()
        desired_production_date_end_parsed = datetime.strptime(desired_production_date_end, date_format).date()
        # Оставляем metal_delivery_date как строку
    except ValueError as e:
        return {"error": f"Ошибка формата даты. Используйте {date_format}"}  # Возвращаем ошибку

    # Генерируем order_number
    order_number = generate_order_number(drawing_designation, db)

    production_order = repository.create_production_order(
        db=db,
        order_number=order_number,
        drawing_designation=drawing_designation,
        drawing_link=drawing_link,
        quantity=quantity,
        desired_production_date_start=desired_production_date_start_parsed,
        desired_production_date_end=desired_production_date_end_parsed,
        required_material=required_material,
        metal_delivery_date=metal_delivery_date,  # Передаем как строку
        notes=notes
    )
    return RedirectResponse(url="/production_order_form", status_code=303)

@app.get("/production_orders", response_class=HTMLResponse)
async def show_production_orders(request: Request, db: Session = Depends(get_db)):
    orders = repository.get_production_orders(db)
    return templates.TemplateResponse("production_orders.html", {"request": request, "orders": orders})

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8443,
        ssl_keyfile="key.pem",
        ssl_certfile="cert.pem"
    )
