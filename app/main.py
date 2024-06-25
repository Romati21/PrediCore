from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from app import models, repository
from app.database import SessionLocal, engine
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi import Request, Form
import qrcode
# uvicorn app.main:app --reload

models.Base.metadata.create_all(bind=engine)

app = FastAPI()
templates = Jinja2Templates(directory="templates")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def generate_qr_code(data: str, filename: str):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill='black', back_color='white')
    img.save(filename)

@app.get("/", response_class=HTMLResponse)
async def read_form(request: Request):
    return templates.TemplateResponse("form.html", {"request": request})

@app.post("/submit")
async def submit_data(batch_number: str = Form(...), part_number: str = Form(...), quantity: int = Form(...), db: Session = Depends(get_db)):
    inventory_item = repository.create_inventory(db, batch_number, part_number, quantity)
    data = f"Партия: {batch_number}, Деталь: {part_number}, Количество: {quantity}"
    qr_filename = f"static/qr_codes/qr_{inventory_item.id}.png"
    generate_qr_code(data, qr_filename)
    return {"Успех": "Данные добавлены и QR-код сгенерирован"}

@app.get("/data", response_class=HTMLResponse)
async def show_data(request: Request, db: Session = Depends(get_db)):
    inventory = repository.get_inventory(db)
    return templates.TemplateResponse("data.html", {"request": request, "data": inventory})
