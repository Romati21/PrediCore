import re
import requests
from bs4 import BeautifulSoup

def find_drawing_link(order_url, drawing_number, session):
    """
    Находит ссылку на чертеж по его номеру в заказе.

    Args:
        order_url: URL страницы с заказом.
        drawing_number: Номер чертежа (например, "КИ 124.01.02").
        session: Объект сессии requests для поддержания авторизации.

    Returns:
        Ссылка на чертеж или None, если ссылка не найдена.
    """
    try:
        response = session.get(order_url)
        response.raise_for_status()  # Проверяем на ошибки HTTP
        order_html = response.text
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при получении страницы заказа: {e}")
        return None

    # Находим блок с ссылкой на оконцеватель, используя BeautifulSoup
    soup = BeautifulSoup(order_html, 'html.parser')
    link_element = soup.find('div', class_='field-name-field-nodelinks').find('a')
    if link_element:
        drawing_link = link_element['href']
        return drawing_link
    else:
        return None

# URL страницы с заказом
order_url = "http://192.168.0.26/?q=omts/2024/zakaz-komplektuyushchih-k-zn-1312" 

# Данные для входа (замените на ваши)
username = "Романов"
password = "nbvjirF9291"

# URL страницы входа
login_url = "http://192.168.0.26/user/login"  # Проверьте URL для входа

# Создаем сессию requests
session = requests.Session()

# Авторизуемся на сайте
try:
    response = session.get(login_url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    form_build_id = soup.find('input', {'name': 'form_build_id'})['value']
    login_data = {
        'name': username,
        'pass': password,
        'form_build_id': form_build_id,
        'form_id': 'user_login_block',
        'op': 'Войти'
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
    }
    
    response = session.post(login_url, data=login_data, headers=headers, allow_redirects=True)
    response.raise_for_status()

    # Проверяем, что авторизация прошла успешно
    if "Выйти" in response.text:
        print("Авторизация прошла успешно.")
        
        # Используем find_drawing_link для получения ссылки на чертеж
        drawing_number = "КИ 124.01.02"  # Укажите нужный номер чертежа
        drawing_link = find_drawing_link(order_url, drawing_number, session)
        if drawing_link:
            print(f"Ссылка на чертеж: {drawing_link}")
        else:
            print("Ссылка на чертеж не найдена.")
    else:
        print("Ошибка авторизации.")
        print(response.text)  # Выводим ответ сервера для отладки
except requests.exceptions.RequestException as e:
    print(f"Ошибка при авторизации: {e}")
