from sqlalchemy import Column, Integer, String, Date
from sqlalchemy.types import TypeDecorator
from app.database import Base
from datetime import date, datetime
from sqlalchemy.sql import func
from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

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
    publication_date = Column(Date)
    drawing_designation = Column(String)
    drawing_link = Column(String, nullable=True)  # Убедитесь, что здесь стоит nullable=True
    quantity = Column(Integer)
    desired_production_date_start = Column(Date)
    desired_production_date_end = Column(Date)
    required_material = Column(String)
    metal_delivery_date = Column(String)
    notes = Column(String, nullable=True)

    # def update_drawing_link(self, new_link: str):
    #     self.drawing_link = new_link
