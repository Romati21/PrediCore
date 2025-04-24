#!/bin/sh

# Использование: ./restore_db.sh <commit_hash>

if [ $# -eq 0 ]; then
    echo "Usage: $0 <commit_hash>"
    exit 1
fi

COMMIT_HASH=$1
BACKUP_DIR="/media/E/postgres_backup"

# Получаем дату и время коммита
COMMIT_DATE=$(git show -s --format=%cd --date=format:'%Y%m%d_%H%M%S' $COMMIT_HASH)

# Находим ближайший бэкап перед коммитом
BACKUP_FILE=$(find $BACKUP_DIR -type f -name "qr_code_inventory_db_*.dump" | sort | awk -v date="$COMMIT_DATE" '$0 ~ date {print p} {p=$0}' | tail -n 1)

if [ -z "$BACKUP_FILE" ]; then
    echo "Backup file not found for commit $COMMIT_HASH"
    exit 1
fi

echo "Restoring from backup: $BACKUP_FILE"

# Восстанавливаем базу данных
pg_restore -U qr_code_inventory_user -h 192.168.122.91 -d qr_code_inventory_db -c "$BACKUP_FILE"

# Находим ревизию Alembic, ближайшую к дате коммита
ALEMBIC_REVISION=$(alembic history | awk -v date="$COMMIT_DATE" '$0 ~ date {print $1; exit}')

if [ -z "$ALEMBIC_REVISION" ]; then
    echo "Could not find Alembic revision for commit date. Using latest revision before or at commit date."
    ALEMBIC_REVISION=$(alembic history | awk -v date="$COMMIT_DATE" '$0 < date {print $1; exit}')
fi

echo "Upgrading Alembic to revision: $ALEMBIC_REVISION"

# Применяем миграции Alembic
alembic upgrade "$ALEMBIC_REVISION"

echo "Database restored to state at commit $COMMIT_HASH"
