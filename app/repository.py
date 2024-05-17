from sqlalchemy.orm import Session
from app import models

def create_inventory(db: Session, batch_number: str, part_number: str, quantity: int):
    db_inventory = models.Inventory(batch_number=batch_number, part_number=part_number, quantity=quantity)
    db.add(db_inventory)
    db.commit()
    db.refresh(db_inventory)
    return db_inventory

def get_inventory(db: Session, skip: int = 0, limit: int = 20):
    return db.query(models.Inventory).offset(skip).limit(limit).all()
