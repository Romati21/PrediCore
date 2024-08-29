from pydantic import BaseModel, validator
from datetime import date, datetime
from typing import Optional, List

class ProductionOrderCreate(BaseModel):
    drawing_designation: str
    quantity: int
    desired_production_date_start: date
    desired_production_date_end: date
    required_material: str
    metal_delivery_date: Optional[str] = None
    notes: Optional[str] = None

    @validator('desired_production_date_start', 'desired_production_date_end', pre=True)
    def parse_date(cls, value):
        if isinstance(value, str):
            return datetime.strptime(value, "%d.%m.%Y").date()
        return value

class ProductionOrderUpdate(BaseModel):
    drawing_file: Optional[str]
