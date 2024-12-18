#!/bin/bash

# Проверка наличия .env файла
if [ ! -f .env ]; then
    echo "Error: .env file not found!"
    echo "Please create .env file based on .env.example"
    exit 1
fi

# Загрузка переменных окружения
set -a
source .env
set +a

# Проверка критически важных переменных
if [ -z "$JWT_SECRET_KEY" ]; then
    echo "Error: JWT_SECRET_KEY not set in .env file!"
    exit 1
fi

if [ -z "$DATABASE_URL" ]; then
    echo "Error: DATABASE_URL not set in .env file!"
    exit 1
fi

cd /media/D/cnc_base_dev

# Активация виртуального окружения
if [ ! -d "venv_dev" ]; then
    echo "Error: venv_dev directory not found!"
    echo "Please create virtual environment first"
    exit 1
fi

source venv_dev/bin/activate

# Проверка SSL сертификатов
if [ ! -f "key.pem" ] || [ ! -f "cert.pem" ]; then
    echo "Warning: SSL certificates not found!"
    echo "Running without SSL..."
    uvicorn app.main:app --host 0.0.0.0 --port 8343
else
    uvicorn app.main:app --host 0.0.0.0 --port 8343 --ssl-keyfile key.pem --ssl-certfile cert.pem
fi
