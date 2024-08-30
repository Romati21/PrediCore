from pydantic import BaseModel, validator
from datetime import date, datetime
from typing import Optional, List

class ProductionOrderCreate(BaseModel):
    order_number: str
    drawing_designation: str
    quantity: int
    desired_production_date_start: date
    desired_production_date_end: date
    required_material: str
    metal_delivery_date: Optional[str] = None
    notes: Optional[str] = None
    publication_date: date

    @validator('desired_production_date_start', 'desired_production_date_end', 'publication_date', pre=True)
    def parse_date(cls, value):
        if isinstance(value, str):
            return datetime.strptime(value, "%d.%m.%Y").date()
        return value

class ProductionOrderUpdate(BaseModel):
    drawing_file: Optional[str]
    order_number: Optional[str]
    drawing_designation: Optional[str]
    quantity: Optional[int]
    desired_production_date_start: Optional[date]
    desired_production_date_end: Optional[date]
    required_material: Optional[str]
    metal_delivery_date: Optional[str]
    notes: Optional[str]

    @validator('desired_production_date_start', 'desired_production_date_end', pre=True)
    def parse_date(cls, value):
        if isinstance(value, str):
            return datetime.strptime(value, "%d.%m.%Y").date()
        return value
