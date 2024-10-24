from sqlalchemy import Column, Integer, String, DateTime, Date, Time, Boolean, ForeignKey, Enum, CheckConstraint, SmallInteger, Index
from sqlalchemy.orm import Session
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base
from passlib.hash import bcrypt  # Для хэширования паролей
import enum
from datetime import date, datetime, timedelta
import logging

Base = declarative_base()

class Shift(enum.Enum):
    DAY = "День"
    NIGHT = "Ночь"

class UserRole(enum.Enum):
    ADMIN = "Администратор"
    MASTER = "Мастер"
    ADJUSTER = "Наладчик"
    WORKER = "Рабочий"

    def __str__(self):
        return self.value

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(100), nullable=False)
    birth_date = Column(Date, nullable=False)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.WORKER)
    email = Column(String(100), unique=True, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    otp = Column(String, nullable=True)  # Добавляем поле для хранения OTP
    failed_login_attempts = Column(Integer, default=0)
    last_failed_login = Column(DateTime(timezone=True))
    is_locked = Column(Boolean, default=False)
    lock_expiry = Column(DateTime(timezone=True))

    # Хэширование пароля
    def set_password(self, password: str):
        self.password_hash = bcrypt.hash(password)

    # Проверка пароля
    def check_password(self, password: str) -> bool:
        return bcrypt.verify(password, self.password_hash)

class RevokedToken(Base):
    __tablename__ = "revoked_tokens"

    id = Column(Integer, primary_key=True, index=True)
    jti = Column(String(36), unique=True, nullable=False)
    session_id = Column(Integer, ForeignKey("user_sessions.id"), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_by_user_id = Column(Integer, ForeignKey("users.id"))
    reason = Column(String(255))
    token_type = Column(String(20))

    session = relationship("UserSession", back_populates="revoked_tokens")
    revoked_by = relationship("User")

    __table_args__ = (
        Index('idx_expires_at', 'expires_at'),  # Индекс для быстрой очистки
        Index('idx_session_token_type', 'session_id', 'token_type'),  # Составной индекс
    )

class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    ip_address = Column(String(45), nullable=False)
    user_agent = Column(String(255))
    last_activity = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_active = Column(Boolean, default=True)
    access_token_jti = Column(String(36), unique=True)
    refresh_token_jti = Column(String(36), unique=True)

    user = relationship("User", back_populates="sessions")
    revoked_tokens = relationship("RevokedToken", back_populates="session", cascade="all, delete-orphan")

    async def revoke_tokens(self, db: Session, revoked_by_user: User, reason: str):
    # """Отзыв всех токенов сессии"""
        try:
            current_time = datetime.utcnow()

            logging.info(f"Attempting to revoke tokens for session {self.id}")

            if self.access_token_jti:
                logging.info(f"Revoking access token {self.access_token_jti}")
                revoked_access = RevokedToken(
                    jti=self.access_token_jti,
                    session_id=self.id,
                    revoked_at=current_time,
                    expires_at=current_time + timedelta(minutes=30),
                    revoked_by_user_id=revoked_by_user.id,
                    reason=reason,
                    token_type="access"
                )
                db.add(revoked_access)

            if self.refresh_token_jti:
                logging.info(f"Revoking refresh token {self.refresh_token_jti}")
                revoked_refresh = RevokedToken(
                    jti=self.refresh_token_jti,
                    session_id=self.id,
                    revoked_at=current_time,
                    expires_at=current_time + timedelta(days=7),
                    revoked_by_user_id=revoked_by_user.id,
                    reason=reason,
                    token_type="refresh"
                )
                db.add(revoked_refresh)

            self.is_active = False
            logging.info(f"Setting session {self.id} as inactive")

            try:
                db.commit()
                logging.info(f"Successfully revoked tokens for session {self.id}")
            except Exception as commit_error:
                logging.error(f"Error during commit: {str(commit_error)}")
                db.rollback()
                raise

        except Exception as e:
            logging.error(f"Error in revoke_tokens: {str(e)}")
            db.rollback()
            raise
User.sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")

class Machine(Base):
    __tablename__ = "machines"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

class Part(Base):
    __tablename__ = "parts"

    id = Column(Integer, primary_key=True, index=True)
    number = Column(String(50), unique=True, nullable=False)
    name = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

class Operation(Base):
    __tablename__ = "operations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

class WorkLog(Base):
    __tablename__ = "work_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    date = Column(Date, nullable=False)
    shift = Column(Enum(Shift), nullable=False)
    machine_id = Column(Integer, ForeignKey('machines.id'), nullable=False)
    part_id = Column(Integer, ForeignKey('parts.id'), nullable=False)
    operation_id = Column(Integer, ForeignKey('operations.id'), nullable=False)
    operation_time = Column(Integer, nullable=False)  # в секундах
    adjuster_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    operator_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    produced_quantity = Column(Integer, nullable=False)
    order_number = Column(String(50), ForeignKey('production_orders.order_number'), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    is_archived = Column(Boolean, default=False, nullable=False)
    is_deleted = Column(Boolean, default=False, nullable=False)

    user = relationship("User", foreign_keys=[user_id])
    machine = relationship("Machine")
    part = relationship("Part")
    operation = relationship("Operation")
    adjuster = relationship("User", foreign_keys=[adjuster_id])
    operator = relationship("User", foreign_keys=[operator_id])
    production_order = relationship("ProductionOrder")

    __table_args__ = (
        CheckConstraint('produced_quantity > 0', name='check_produced_quantity_positive'),
    )

class ArchivedWorkLog(Base):
    __tablename__ = "archived_work_logs"

    id = Column(Integer, primary_key=True, index=True)
    original_id = Column(Integer, nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    user_id = Column(Integer, nullable=False)
    date = Column(Date, nullable=False)
    shift = Column(Enum(Shift), nullable=False)
    machine_id = Column(Integer, nullable=False)
    part_id = Column(Integer, nullable=False)
    operation_id = Column(Integer, nullable=False)
    operation_time = Column(Integer, nullable=False)
    adjuster_id = Column(Integer, nullable=False)
    operator_id = Column(Integer, nullable=False)
    produced_quantity = Column(Integer, nullable=False)
    order_number = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)
    archived_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    is_deleted = Column(Boolean, default=False, nullable=False)

class SetupInfo(Base):
    __tablename__ = "setup_info"

    id = Column(Integer, primary_key=True, index=True)
    work_log_id = Column(Integer, ForeignKey('work_logs.id'), unique=True, nullable=False)
    setup_start = Column(Time, nullable=True)
    setup_end = Column(Time, nullable=True)
    setups_count = Column(SmallInteger, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    work_log = relationship("WorkLog", back_populates="setup_info")

WorkLog.setup_info = relationship("SetupInfo", back_populates="work_log", uselist=False)

class OperationDetails(Base):
    __tablename__ = "operation_details"

    id = Column(Integer, primary_key=True, index=True)
    work_log_id = Column(Integer, ForeignKey('work_logs.id'), unique=True, nullable=False)
    next_operation_zinc = Column(Boolean, nullable=False)
    next_operation_cnc = Column(Boolean, nullable=False)
    parts_per_operation = Column(SmallInteger, nullable=False)
    estimated_quantity = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    work_log = relationship("WorkLog", back_populates="operation_details")

WorkLog.operation_details = relationship("OperationDetails", back_populates="work_log", uselist=False)

class WorkLogNotes(Base):
    __tablename__ = "work_log_notes"

    id = Column(Integer, primary_key=True, index=True)
    work_log_id = Column(Integer, ForeignKey('work_logs.id'), unique=True, nullable=False)
    note = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    work_log = relationship("WorkLog", back_populates="notes")

WorkLog.notes = relationship("WorkLogNotes", back_populates="work_log", uselist=False)

class Drawing(Base):
    __tablename__ = "drawings"

    id = Column(Integer, primary_key=True, index=True)
    hash = Column(String(64), unique=True, nullable=False, index=True)
    file_path = Column(String(255), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_size = Column(Integer, nullable=False)
    mime_type = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_used_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    version = Column(SmallInteger, nullable=False, server_default='1')
    archived_at = Column(DateTime(timezone=True), nullable=True)

class OrderDrawing(Base):
    __tablename__ = "order_drawings"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey('production_orders.id'), nullable=False, index=True)
    drawing_id = Column(Integer, ForeignKey('drawings.id'), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    order = relationship("ProductionOrder", back_populates="drawings")
    drawing = relationship("Drawing")

class ProductionOrder(Base):
    __tablename__ = "production_orders"

    id = Column(Integer, primary_key=True, index=True)
    order_number = Column(String(50), unique=True, index=True)
    publication_date = Column(Date, nullable=False)
    part_id = Column(Integer, ForeignKey('parts.id'), nullable=False)
    quantity = Column(Integer, nullable=False)
    desired_production_date_start = Column(Date, nullable=False)
    desired_production_date_end = Column(Date, nullable=False)
    required_material = Column(String(100), nullable=False)
    metal_delivery_date = Column(String(50), nullable=True)
    notes = Column(String, nullable=True)
    drawing_link = Column(String(255), nullable=True)
    archived_drawings = Column(String, nullable=True)
    qr_code_path = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    is_deleted = Column(Boolean, default=False, nullable=False)

    drawings = relationship("OrderDrawing", back_populates="order")
    part = relationship("Part")
    work_logs = relationship("WorkLog", back_populates="production_order")

    __table_args__ = (
        CheckConstraint('quantity > 0', name='check_quantity_positive'),
        CheckConstraint('desired_production_date_end >= desired_production_date_start', name='check_date_range'),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "order_number": self.order_number,
            "publication_date": self.publication_date.isoformat() if self.publication_date else None,
            "part_number": self.part.number if self.part else None,
            "drawing_link": self.drawing_link,
            "quantity": self.quantity,
            "desired_production_date_start": self.desired_production_date_start.isoformat() if self.desired_production_date_start else None,
            "desired_production_date_end": self.desired_production_date_end.isoformat() if self.desired_production_date_end else None,
            "required_material": self.required_material,
            "metal_delivery_date": self.metal_delivery_date if self.metal_delivery_date else None,
            "notes": self.notes,
            "qr_code_path": self.qr_code_path
        }

class ArchivedProductionOrder(Base):
    __tablename__ = "archived_production_orders"

    id = Column(Integer, primary_key=True, index=True)
    original_id = Column(Integer, nullable=False)
    order_number = Column(String(50), unique=True, index=True)
    publication_date = Column(Date, nullable=False)
    part_id = Column(Integer, nullable=False)
    quantity = Column(Integer, nullable=False)
    desired_production_date_start = Column(Date, nullable=False)
    desired_production_date_end = Column(Date, nullable=False)
    required_material = Column(String(100), nullable=False)
    metal_delivery_date = Column(String(50), nullable=True)
    notes = Column(String, nullable=True)
    drawing_link = Column(String(255), nullable=True)
    archived_drawings = Column(String, nullable=True)
    qr_code_path = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)
    archived_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    is_deleted = Column(Boolean, default=False, nullable=False)

OrderDrawing.order = relationship("ProductionOrder", back_populates="drawings")
