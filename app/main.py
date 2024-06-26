import uvicorn
from fastapi import FastAPI, Depends, HTTPException, Request, Form
from sqlalchemy.orm import Session
from app import models, repository
from app.database import SessionLocal, engine
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles


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

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8443,
        ssl_keyfile="key.pem",
        ssl_certfile="cert.pem"
    )
