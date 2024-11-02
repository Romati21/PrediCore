"""Добавил DateTime для UserSession++

Revision ID: 2c4482fb4bb1
Revises: 3e35231bccd5
Create Date: 2024-03-21 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime, timezone

revision = '2c4482fb4bb1'
down_revision = '3e35231bccd5'
branch_labels = None
depends_on = None

def upgrade():
    # 1. Добавляем колонку как nullable
    op.add_column('user_sessions', 
        sa.Column('updated_at', 
                  sa.DateTime(timezone=True), 
                  nullable=True)
    )
    
    # 2. Создаем временную функцию для установки значения по умолчанию
    op.execute("""
        CREATE OR REPLACE FUNCTION set_updated_at()
        RETURNS VOID AS $$
        BEGIN
            UPDATE user_sessions 
            SET updated_at = COALESCE(created_at, CURRENT_TIMESTAMP) 
            WHERE updated_at IS NULL;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # 3. Выполняем обновление
    op.execute("SELECT set_updated_at();")
    
    # 4. Удаляем временную функцию
    op.execute("DROP FUNCTION set_updated_at();")
    
    # 5. Делаем колонку NOT NULL
    op.alter_column('user_sessions', 'updated_at',
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text('CURRENT_TIMESTAMP')
    )

def downgrade():
    # 1. Сначала делаем колонку nullable
    op.alter_column('user_sessions', 'updated_at',
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
        server_default=None
    )
    
    # 2. Затем удаляем её
    op.drop_column('user_sessions', 'updated_at')
