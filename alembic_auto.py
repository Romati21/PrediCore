import subprocess
import sys
from datetime import datetime
from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine
from alembic import command

# Используем ваш URL базы данных
DATABASE_URL = "postgresql://qr_code_inventory_user:nbvjirF9291@192.168.122.192:5432/qr_code_inventory_db"

def run_command(command):
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    output, error = process.communicate()
    return output.decode(), error.decode(), process.returncode

def check_and_update_db():
    alembic_cfg = Config("alembic.ini")
    script = ScriptDirectory.from_config(alembic_cfg)
    
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        context = MigrationContext.configure(conn)
        current_rev = context.get_current_revision()
        head_rev = script.get_current_head()
        
        if current_rev != head_rev:
            print("Database is not up to date. Updating...")
            command.upgrade(alembic_cfg, "head")
            print("Database updated successfully.")
        else:
            print("Database is up to date.")

def main():
    # Сначала проверяем и обновляем базу данных
    check_and_update_db()

    # Генерация описания изменений
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    description = f"Auto-generated migration {timestamp}"

    # Проверка наличия изменений и создание миграции
    output, error, code = run_command(f"alembic revision --autogenerate -m '{description}'")
    if "No changes in schema detected" in output:
        print("No changes detected.")
        return

    if code != 0:
        print(f"Error creating migration: {error}")
        sys.exit(1)

    print("Migration created successfully.")

    # Применение миграции
    output, error, code = run_command("alembic upgrade head")
    if code != 0:
        print(f"Error applying migration: {error}")
        sys.exit(1)

    print("Migration applied successfully.")

if __name__ == "__main__":
    main()
