from fastapi import FastAPI, Depends, HTTPException, Request, Form
from sqlalchemy.orm import Session
from app import models, repository
from app.database import SessionLocal, engine
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from datetime import date
from pydantic import BaseModel
import qrcode
import io
import base64

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
async def read_form(request: Request):
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

@app.get("/production_order_form", response_class=HTMLResponse)
async def production_order_form(request: Request):
    return templates.TemplateResponse("production_order_form.html", {"request": request})

@app.post("/submit_production_order")
async def submit_production_order(
    drawing_designation: str = Form(...),
    drawing_link: str = Form(...),
    quantity: int = Form(...),
    desired_production_date: str = Form(...),
    required_material: str = Form(...),
    metal_delivery_date: str = Form(...),
    notes: str = Form(...),
    db: Session = Depends(get_db)
):
    production_order = repository.create_production_order(
        db, drawing_designation, drawing_link, quantity,
        desired_production_date, required_material, metal_delivery_date, notes
    )
    return {"success": "Заказ-наряд создан", "order_number": production_order.order_number}

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
