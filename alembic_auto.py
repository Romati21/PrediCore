import subprocess
import sys
from datetime import datetime

def run_command(command):
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    output, error = process.communicate()
    return output.decode(), error.decode(), process.returncode

def main():
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
