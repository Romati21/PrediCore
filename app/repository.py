from sqlalchemy.orm import Session
from app import models
import random
import string
from datetime import date
from typing import Union

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
    metal_delivery_date: str,  # Изменено на str
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
