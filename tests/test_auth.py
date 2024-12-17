import pytest
from datetime import datetime, timedelta, timezone
import time
from app.models import User, UserSession
from app.auth.auth import ACCESS_TOKEN_EXPIRE_MINUTES

@pytest.fixture(autouse=True)
def clean_users_table(db_session):
    db_session.query(User).delete()
    db_session.commit()

def test_register_user(client, db_session):
    response = client.post(
        "/register",
        data={
            "username": "newuser",
            "password": "NewPassword123",
            "email": "new@example.com",
            "full_name": "New User",
            "birth_date": "1990-01-01"
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "newuser"
    assert data["email"] == "new@example.com"

def test_login_success(client, test_user, db_session):
    # Verify test user exists in database
    from app.models import User
    user = db_session.query(User).filter(User.username == "testuser").first()
    assert user is not None, "Test user not found in database"
    
    # Override the client's IP address with a valid one for testing
    client.headers["X-Real-IP"] = "127.0.0.1"
    
    response = client.post(
        "/login",
        data={
            "username": "testuser",
            "password": "testpassword"
        },
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Real-IP": "127.0.0.1"  # Set a valid IP address
        }
    )
    
    # Print response for debugging
    print(f"Response status: {response.status_code}")
    print(f"Response body: {response.json()}")
    
    assert response.status_code == 200
    assert response.json()["success"] == True
    assert "access_token" in response.cookies
    assert "refresh_token" in response.cookies

def test_login_wrong_password(client, test_user):
    response = client.post(
        "/login",
        data={
            "username": "testuser",
            "password": "wrongpassword"
        }
    )
    assert response.status_code == 400

def test_token_refresh(client, test_user, auth_headers):
    # Ждем немного, чтобы токен приблизился к истечению
    time.sleep(1)
    
    response = client.get("/api/auth-test", headers=auth_headers)
    assert response.status_code == 200
    
    # Проверяем, что токены в куках
    assert "access_token" in response.cookies
    assert "refresh_token" in response.cookies

def test_session_management(client, test_user, db_session):
    # Создаем несколько сессий
    for i in range(3):
        response = client.post(
            "/login",
            data={
                "username": "testuser",
                "password": "testpassword"
            }
        )
        assert response.status_code == 200
    
    # Проверяем количество активных сессий
    active_sessions = db_session.query(UserSession).filter(
        UserSession.user_id == test_user.id,
        UserSession.is_active == True
    ).count()
    
    assert active_sessions == 3

def test_session_limit(client, test_user, db_session):
    # Пытаемся создать больше сессий, чем разрешено (MAX_ACTIVE_SESSIONS = 5)
    for i in range(6):
        response = client.post(
            "/login",
            data={
                "username": "testuser",
                "password": "testpassword"
            }
        )
        if i < 5:
            assert response.status_code == 200
        else:
            assert response.status_code == 200
            assert "too_many_sessions" in response.json()["status"]

def test_logout(client, test_user, auth_headers):
    # Сначала проверяем, что мы авторизованы
    response = client.get("/api/auth-test", headers=auth_headers)
    assert response.status_code == 200
    
    # Выходим из системы
    response = client.post("/logout", headers=auth_headers)
    assert response.status_code == 200
    
    # Проверяем, что старые токены больше не работают
    response = client.get("/api/auth-test", headers=auth_headers)
    assert response.status_code == 401

def test_admin_access(client, test_admin):
    # Логинимся как админ
    response = client.post(
        "/login",
        data={
            "username": "admin",
            "password": "adminpassword"
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    assert response.status_code == 200
    cookies = response.cookies
    headers = {
        "Cookie": f"access_token={cookies.get('access_token')}; refresh_token={cookies.get('refresh_token')}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    # Проверяем доступ к админской странице
    response = client.get("/admin/users", headers=headers)
    assert response.status_code == 200

def test_worker_no_admin_access(client, test_user, auth_headers):
    # Пытаемся получить доступ к админской странице как обычный пользователь
    response = client.get("/admin/users", headers=auth_headers)
    assert response.status_code == 403
