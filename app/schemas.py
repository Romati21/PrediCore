from pydantic import BaseModel
from datetime import date
from typing import Optional

class ProductionOrderCreate(BaseModel):
    order_number: str
    drawing_designation: str
    drawing_link: str
    quantity: int
    desired_production_date_start: date
    desired_production_date_end: date
    required_material: str
    metal_delivery_date: Optional[date]
    notes: Optional[str]

class ProductionOrderUpdate(BaseModel):
    drawing_file: Optional[str]
