from sqlalchemy import Column, Integer, String, Date
from app.database import Base
from datetime import date

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

class ProductionOrder(Base):
    __tablename__ = "production_orders"

    id = Column(Integer, primary_key=True, index=True)
    order_number = Column(String(6), unique=True, index=True)
    publication_date = Column(Date, default=date.today)
    drawing_designation = Column(String)
    drawing_link = Column(String)
    quantity = Column(Integer)
    desired_production_date = Column(String)
    required_material = Column(String)
    metal_delivery_date = Column(String)
    notes = Column(String)


# class Order(Base):
#     __tablename__ = "orders"

#     id = Column(Integer, primary_key=True, index=True)
#     order_id = Column(String, unique=True, index=True)
#     customer_name = Column(String)
#     product_name = Column(String)
#     quantity = Column(Integer)
