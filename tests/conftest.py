import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.database import Base, get_db
from app.main import app, scheduler
from app.models import User
from app.auth.auth import get_password_hash
import asyncio
import nest_asyncio
from datetime import datetime
import pytz

# Инициализируем event loop для тестов
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

# Применяем nest_asyncio для решения проблем с event loop
nest_asyncio.apply()

# Отключаем планировщик для тестов
if scheduler._eventloop:
    scheduler.shutdown()
scheduler._eventloop = loop
scheduler.shutdown()

# Используем существующую тестовую базу данных PostgreSQL
SQLALCHEMY_DATABASE_URL = "postgresql://qr_code_inventory_user:nbvjirF9291@192.168.122.192/qr_code_inventory_db_unit"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    echo=True  # Enable SQL logging for debugging
)

TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False  # Prevent expired object issues
)

def setup_database():
    # Import all models here to ensure they are registered with the Base
    from app.models import (
        User, UserSession, RevokedToken, Machine, Part, Operation,
        WorkLog, ArchivedWorkLog, SetupInfo, OperationDetails,
        WorkLogNotes, Drawing, OrderDrawing, ProductionOrder,
        ArchivedProductionOrder
    )
    
    # Drop existing tables
    Base.metadata.drop_all(bind=engine)
    
    # Create all tables
    Base.metadata.create_all(bind=engine)

@pytest.fixture(scope="function")
def db_session():
    # Create fresh tables for each test
    setup_database()
    
    # Create a new session
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        # Clean up tables after test
        Base.metadata.drop_all(bind=engine)

@pytest.fixture(autouse=True)
def clean_db(db_session):
    """Очищает базу данных перед каждым тестом"""
    # Сначала удаляем сессии, так как они ссылаются на пользователей
    db_session.execute(text("DELETE FROM user_sessions"))
    # Затем удаляем пользователей
    db_session.execute(text("DELETE FROM users"))
    db_session.commit()

@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass  # Don't close here, let db_session fixture handle it
            
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

@pytest.fixture(scope="function")
def test_user(db_session):
    user = User(
        username="testuser",
        email="test@example.com",
        password_hash=get_password_hash("testpassword"),
        full_name="Test User",
        role="WORKER",
        birth_date=datetime.now(pytz.utc).date()
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user

@pytest.fixture(scope="function")
def test_admin(db_session):
    admin = User(
        username="admin",
        email="admin@example.com",
        password_hash=get_password_hash("adminpassword"),
        full_name="Admin User",
        role="ADMIN",
        birth_date=datetime.now(pytz.utc).date()
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin

@pytest.fixture(scope="function")
def auth_headers(client, test_user):
    response = client.post(
        "/login",
        data={
            "username": "testuser",
            "password": "testpassword"
        }
    )
    cookies = response.cookies
    return {"Cookie": f"access_token={cookies.get('access_token')}; refresh_token={cookies.get('refresh_token')}"}
