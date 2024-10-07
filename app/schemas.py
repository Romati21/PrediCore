from pydantic import BaseModel, EmailStr
from datetime import date
from enum import Enum
from typing import Optional


class UserRole(str, Enum):
    MASTER = "Мастер"
    ADJUSTER = "Наладчик"
    WORKER = "Рабочий"

# Схема для регистрации новых пользователей, без роли
class UserCreate(BaseModel):
    full_name: str
    birth_date: date
    username: str
    email: EmailStr
    password: str

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    birth_date: Optional[date] = None
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None

# Схема для назначения роли администратором
class UserRoleUpdate(BaseModel):
    role: UserRole

class User(BaseModel):
    id: int
    full_name: str
    birth_date: date
    username: str
    email: EmailStr
    is_active: bool
    role: UserRole
    last_login_at: Optional[date]

    class Config:
        orm_mode = True

class Shift(str, Enum):
    DAY = "День"
    NIGHT = "Ночь"

class UserBase(BaseModel):
    username: str
    full_name: str
    role: str

class UserCreate(UserBase):
    pass

class User(UserBase):
    id: int
    created_at: date
    updated_at: date

    class Config:
        orm_mode = True

class MachineBase(BaseModel):
    name: str

class MachineCreate(MachineBase):
    pass

class Machine(MachineBase):
    id: int
    created_at: date
    updated_at: date

    class Config:
        orm_mode = True

class PartBase(BaseModel):
    number: str
    name: Optional[str] = None

class PartCreate(PartBase):
    pass

class Part(PartBase):
    id: int
    created_at: date
    updated_at: date

    class Config:
        orm_mode = True

class OperationBase(BaseModel):
    name: str

class OperationCreate(OperationBase):
    pass

class Operation(OperationBase):
    id: int
    created_at: date
    updated_at: date

    class Config:
        orm_mode = True

class WorkLogBase(BaseModel):
    user_id: int
    date: date
    shift: Shift
    machine_id: int
    part_id: int
    operation_id: int
    operation_time: int
    adjuster_id: int
    operator_id: int
    produced_quantity: int = Field(..., gt=0)
    order_number: str

class WorkLogCreate(WorkLogBase):
    pass

class WorkLog(WorkLogBase):
    id: int
    timestamp: date
    created_at: date
    updated_at: date

    class Config:
        orm_mode = True

class ArchivedWorkLog(WorkLog):
    original_id: int
    archived_at: datetime

    class Config:
        orm_mode = True

class SetupInfoBase(BaseModel):
    work_log_id: int
    setup_start: Optional[time] = None
    setup_end: Optional[time] = None
    setups_count: int = Field(..., ge=0)

class SetupInfoCreate(SetupInfoBase):
    pass

class SetupInfo(SetupInfoBase):
    id: int
    created_at: date
    updated_at: date

    class Config:
        orm_mode = True

class OperationDetailsBase(BaseModel):
    work_log_id: int
    next_operation_zinc: bool
    next_operation_cnc: bool
    parts_per_operation: int = Field(..., gt=0)
    estimated_quantity: int = Field(..., ge=0)

class OperationDetailsCreate(OperationDetailsBase):
    pass

class OperationDetails(OperationDetailsBase):
    id: int
    created_at: date
    updated_at: date

    class Config:
        orm_mode = True

class WorkLogNotesBase(BaseModel):
    work_log_id: int
    note: Optional[str] = None

class WorkLogNotesCreate(WorkLogNotesBase):
    pass

class WorkLogNotes(WorkLogNotesBase):
    id: int
    created_at: date
    updated_at: date

    class Config:
        orm_mode = True

class ProductionOrderBase(BaseModel):
    order_number: str
    part_id: int
    quantity: int = Field(..., gt=0)
    desired_production_date_start: date
    desired_production_date_end: date
    required_material: str
    metal_delivery_date: Optional[date] = None
    notes: Optional[str] = None

class ProductionOrderCreate(ProductionOrderBase):
    publication_date: date

    @validator('desired_production_date_end')
    def end_date_after_start_date(cls, v, values, **kwargs):
        if 'desired_production_date_start' in values and v < values['desired_production_date_start']:
            raise ValueError('end date must not be earlier than start date')
        return v

class ProductionOrderUpdate(BaseModel):
    part_id: Optional[int] = None
    quantity: Optional[int] = Field(None, gt=0)
    desired_production_date_start: Optional[date] = None
    desired_production_date_end: Optional[date] = None
    required_material: Optional[str] = None
    metal_delivery_date: Optional[date] = None
    notes: Optional[str] = None

    @validator('desired_production_date_end')
    def end_date_after_start_date(cls, v, values, **kwargs):
        if 'desired_production_date_start' in values and v and v < values['desired_production_date_start']:
            raise ValueError('end date must not be earlier than start date')
        return v

class ProductionOrder(ProductionOrderBase):
    id: int
    publication_date: date
    drawing_link: Optional[str] = None
    archived_drawings: Optional[str] = None
    qr_code_path: Optional[str] = None
    created_at: date
    updated_at: date

    class Config:
        orm_mode = True

class ArchivedProductionOrder(ProductionOrder):
    original_id: int
    archived_at: datetime

    class Config:
        orm_mode = True

class DrawingBase(BaseModel):
    hash: str
    file_path: str
    file_name: str
    file_size: int
    mime_type: str

class DrawingCreate(DrawingBase):
    pass

class Drawing(DrawingBase):
    id: int
    created_at: date
    last_used_at: date
    version: int
    archived_at: Optional[date] = None

    class Config:
        orm_mode = True

class OrderDrawingBase(BaseModel):
    order_id: int
    drawing_id: int

class OrderDrawingCreate(OrderDrawingBase):
    pass

class OrderDrawing(OrderDrawingBase):
    id: int
    created_at: date

    class Config:
        orm_mode = True
