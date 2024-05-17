from sqlalchemy import Column, Integer, String
from app.database import Base

class Inventory(Base):
    __tablename__ = "inventory"

    id = Column(Integer, primary_key=True, index=True)
    batch_number = Column(String, index=True)
    part_number = Column(String, index=True)
    quantity = Column(Integer)
