from sqlalchemy import Column, Integer, String, BigInteger, ForeignKey, TIMESTAMP, Date
from sqlalchemy.types import TypeDecorator
from app.database import Base
from datetime import date, datetime
from sqlalchemy.sql import func
from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.ext.declarative import declarative_base


Base = declarative_base()

class Drawing(Base):
    __tablename__ = "drawings"

    id = Column(Integer, primary_key=True, index=True)
    hash = Column(String(64), unique=True, nullable=False, index=True)
    file_path = Column(String(255), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_size = Column(BigInteger, nullable=False)
    mime_type = Column(String(100), nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    last_used_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    version = Column(Integer, nullable=False, server_default='1')
    archived_at = Column(TIMESTAMP(timezone=True), nullable=True)

class OrderDrawing(Base):
    __tablename__ = "order_drawings"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey('production_orders.id'), nullable=False, index=True)
    drawing_id = Column(Integer, ForeignKey('drawings.id'), nullable=False)
    qr_code_path = Column(String(255), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    order = relationship("ProductionOrder", back_populates="drawings")

class Inventory(Base):
    __tablename__ = "inventory"

    id = Column(Integer, primary_key=True, index=True)
    batch_number = Column(String, index=True)
    part_number = Column(String, index=True)
    quantity = Column(Integer)


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    order_number = Column(String, unique=True, index=True)
    customer_name = Column(String)
    product_name = Column(String)
    quantity = Column(Integer)

class FlexibleDate(TypeDecorator):
    impl = String

    def process_bind_param(self, value, dialect):
        if isinstance(value, date):
            return value.strftime("%d.%m.%Y")
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            try:
                return datetime.strptime(value, "%d.%m.%Y").date()
            except ValueError:
                return value
        return None

# class ProductionOrder(Base):
#     __tablename__ = "production_orders"

#     id = Column(Integer, primary_key=True, index=True)
#     order_number = Column(String, unique=True, index=True)
#     publication_date = Column(Date, default=date.today)  # Добавьте publication_date
#     drawing_designation = Column(String)
#     drawing_link = Column(String)
#     quantity = Column(Integer)
#     desired_production_date_start = Column(Date)
#     desired_production_date_end = Column(Date)
#     required_material = Column(String)
#     metal_delivery_date = Column(String) 
#     notes = Column(String)


class ProductionOrder(Base):
    __tablename__ = "production_orders"

    id = Column(Integer, primary_key=True, index=True)
    order_number = Column(String, unique=True, index=True)
    publication_date = Column(Date, nullable=False)
    drawing_designation = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False)
    desired_production_date_start = Column(Date, nullable=False)
    desired_production_date_end = Column(Date, nullable=False)
    required_material = Column(String, nullable=False)
    metal_delivery_date = Column(String)
    notes = Column(String, nullable=True)
    drawing_link = Column(String, nullable=True)
    archived_drawings = Column(String, nullable=True)
    drawings = relationship("OrderDrawing", back_populates="order")

    def to_dict(self):
        return {
            "id": self.id,
            "order_number": self.order_number,
            "publication_date": self.publication_date.isoformat() if self.publication_date else None,
            "drawing_designation": self.drawing_designation,
            "drawing_link": self.drawing_link,
            "quantity": self.quantity,
            "desired_production_date_start": self.desired_production_date_start.isoformat() if self.desired_production_date_start else None,
            "desired_production_date_end": self.desired_production_date_end.isoformat() if self.desired_production_date_end else None,
            "required_material": self.required_material,
            "metal_delivery_date": self.metal_delivery_date,
            "notes": self.notes
        }

# Добавим обратную связь в модель OrderDrawing
OrderDrawing.order = relationship("ProductionOrder", back_populates="drawings")
