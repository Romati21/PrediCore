from sqlalchemy.orm import Session
from app import models
import random
import string
from datetime import date
from typing import Union
from datetime import datetime

def generate_unique_id(db: Session):
    while True:
        unique_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        if not db.query(models.Order).filter(models.Order.order_id == unique_id).first():
            return unique_id

def create_order(db: Session, order_number: str, customer_name: str, product_name: str, quantity: int):
    print(f"Creating order with parameters: order_number={order_number}, customer_name={customer_name}, product_name={product_name}, quantity={quantity}")
    db_order = models.Order(order_id=order_number, customer_name=customer_name, product_name=product_name, quantity=quantity)
    db.add(db_order)
    try:
        db.commit()
        print("Order saved successfully")
    except Exception as e:
        db.rollback()
        print(f"Error saving order: {e}")
    db.refresh(db_order)
    return db_order

def create_inventory(db: Session, batch_number: str, part_number: str, quantity: int):
    db_inventory = models.Inventory(batch_number=batch_number, part_number=part_number, quantity=quantity)
    db.add(db_inventory)
    db.commit()
    db.refresh(db_inventory)
    return db_inventory

def get_inventory(db: Session, skip: int = 0, limit: int = 20):
    return db.query(models.Inventory).offset(skip).limit(limit).all()

def generate_unique_order_number(db: Session):
    while True:
        order_number = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        if not db.query(models.ProductionOrder).filter(models.ProductionOrder.order_number == order_number).first():
            return order_number

def create_production_order(
    db: Session,
    order_number: str,
    drawing_designation: str,
    drawing_link: str,
    quantity: int,
    desired_production_date_start: date,
    desired_production_date_end: date,
    required_material: str,
    metal_delivery_date: str,
    notes: str
):
    db_order = models.ProductionOrder(
        order_number=order_number,
        drawing_designation=drawing_designation,
        drawing_link=drawing_link,
        quantity=quantity,
        desired_production_date_start=desired_production_date_start,
        desired_production_date_end=desired_production_date_end,
        required_material=required_material,
        metal_delivery_date=metal_delivery_date,
        notes=notes
    )
    db.add(db_order)
    db.commit()
    db.refresh(db_order)
    return db_order

def get_production_orders(db: Session, skip: int = 0, limit: int = 20):
    return db.query(models.ProductionOrder).offset(skip).limit(limit).all()



def create_drawing(db: Session, hash: str, file_path: str, file_name: str, file_size: int, mime_type: str):
    db_drawing = models.Drawing(
        hash=hash,
        file_path=file_path,
        file_name=file_name,
        file_size=file_size,
        mime_type=mime_type
    )
    db.add(db_drawing)
    db.commit()
    db.refresh(db_drawing)
    return db_drawing

def get_drawing_by_hash(db: Session, hash: str):
    return db.query(models.Drawing).filter(models.Drawing.hash == hash).first()

def update_drawing_last_used(db: Session, drawing_id: int):
    db.query(models.Drawing).filter(models.Drawing.id == drawing_id).update({"last_used_at": datetime.utcnow()})
    db.commit()

def create_order_drawing(db: Session, order_id: int, drawing_id: int, qr_code_path: str = None):
    db_order_drawing = models.OrderDrawing(
        order_id=order_id,
        drawing_id=drawing_id,
        qr_code_path=qr_code_path
    )
    db.add(db_order_drawing)
    db.commit()
    db.refresh(db_order_drawing)
    return db_order_drawing

def get_order_drawings(db: Session, order_id: int):
    return db.query(models.OrderDrawing).filter(models.OrderDrawing.order_id == order_id).all()
