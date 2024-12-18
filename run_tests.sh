#!/bin/bash

# Проверка наличия .env файла
if [ ! -f .env ]; then
    echo "Error: .env file not found!"
    echo "Please create .env file based on .env.example"
    exit 1
fi

echo "Loading environment variables..."

# Загрузка переменных окружения
set -a
source .env
set +a

# Вывод для отладки
echo "Checking environment variables:"
echo "JWT_SECRET_KEY=${JWT_SECRET_KEY:0:10}..." # Показываем только первые 10 символов для безопасности
echo "DATABASE_URL is set: $([[ -n $DATABASE_URL ]] && echo 'Yes' || echo 'No')"
echo "ENVIRONMENT=${ENVIRONMENT}"

# Проверка критически важных переменных
if [ -z "$JWT_SECRET_KEY" ]; then
    echo "Error: JWT_SECRET_KEY not set in .env file!"
    exit 1
fi

if [ -z "$DATABASE_URL" ]; then
    echo "Error: DATABASE_URL not set in .env file!"
    exit 1
fi

# Активация виртуального окружения
if [ ! -d "venv_dev" ]; then
    echo "Error: venv_dev directory not found!"
    echo "Please create virtual environment first"
    exit 1
fi

echo "Activating virtual environment..."
source venv_dev/bin/activate

# Экспорт переменных явно для Python
export JWT_SECRET_KEY="$JWT_SECRET_KEY"
export DATABASE_URL="$DATABASE_URL"
export ENVIRONMENT="${ENVIRONMENT:-development}"

echo "Running tests..."
# Установка PYTHONPATH и запуск тестов
export PYTHONPATH=/media/D/cnc_base_dev
python -c "import os; print('Python sees JWT_SECRET_KEY:', bool(os.getenv('JWT_SECRET_KEY')))"
pytest tests/test_auth.py -v
