from pydantic import BaseModel, EmailStr, Field, validator
from datetime import date, datetime, time
from enum import Enum
from typing import Optional

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

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
    # Уберем поле role отсюда, так как оно будет назначаться автоматически

    @validator('birth_date', pre=True)
    def parse_birth_date(cls, v):
        if isinstance(v, str):
            return date.fromisoformat(v)
        return v

    @validator('password')
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError('Пароль должен содержать не менее 8 символов')
        if not any(char.isdigit() for char in v):
            raise ValueError('Пароль должен содержать хотя бы одну цифру')
        if not any(char.isupper() for char in v):
            raise ValueError('Пароль должен содержать хотя бы одну заглавную букву')
        return v

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
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda dt: dt.isoformat(),
            date: lambda d: d.isoformat()
        }

class Shift(str, Enum):
    DAY = "День"
    NIGHT = "Ночь"

class UserBase(BaseModel):
    username: str
    full_name: str
    role: str

# class UserCreate(UserBase):
#     pass

class User(UserBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class MachineBase(BaseModel):
    name: str

class MachineCreate(MachineBase):
    pass

class Machine(MachineBase):
    id: int
    created_at: date
    updated_at: date

    class Config:
        from_attributes = True

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
        from_attributes = True

class OperationBase(BaseModel):
    name: str

class OperationCreate(OperationBase):
    pass

class Operation(OperationBase):
    id: int
    created_at: date
    updated_at: date

    class Config:
        from_attributes = True

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
        from_attributes = True

class ArchivedWorkLog(WorkLog):
    original_id: int
    archived_at: datetime

    class Config:
        from_attributes = True

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
        from_attributes = True

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
        from_attributes = True

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
        from_attributes = True

class ProductionOrderBase(BaseModel):
    order_number: str
    part_id: int
    quantity: int = Field(..., gt=0)
    desired_production_date_start: date
    desired_production_date_end: date
    required_material: str
    metal_delivery_date: Optional[str] = None
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
    metal_delivery_date: Optional[str] = None
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
        from_attributes = True

class ArchivedProductionOrder(ProductionOrder):
    original_id: int
    archived_at: datetime

    class Config:
        from_attributes = True

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
        from_attributes = True

class OrderDrawingBase(BaseModel):
    order_id: int
    drawing_id: int

class OrderDrawingCreate(OrderDrawingBase):
    pass

class OrderDrawing(OrderDrawingBase):
    id: int
    created_at: date

    class Config:
        from_attributes = True
