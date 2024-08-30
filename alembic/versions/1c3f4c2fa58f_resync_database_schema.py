from typing import Sequence, Union
from sqlalchemy import exc, text
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector
from sqlalchemy import inspect
from sqlalchemy.exc import NoSuchTableError, OperationalError

# revision identifiers, used by Alembic.
revision: str = '1c3f4c2fa58f'
down_revision: Union[str, None] = '833565f12ada'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade():
    inspector = inspect(op.get_bind())

    def create_table_if_not_exists(table_name, *args, **kwargs):
        if not inspector.has_table(table_name):
            op.create_table(table_name, *args, **kwargs)
        else:
            print(f"Таблица {table_name} уже существует.")

    def add_column_if_not_exists(table_name, column):
        try:
            columns = [c['name'] for c in inspector.get_columns(table_name)]
            if column.name not in columns:
                op.add_column(table_name, column)
                print(f"Столбец {column.name} добавлен в таблицу {table_name}.")
            else:
                print(f"Столбец {column.name} уже существует в таблице {table_name}.")
        except NoSuchTableError:
            print(f"Таблица {table_name} не существует.")
        except OperationalError as e:
            print(f"Ошибка при добавлении столбца {column.name}: {str(e)}")

    def create_index_if_not_exists(index_name, table_name, columns, unique=False):
        try:
            op.create_index(op.f(index_name), table_name, columns, unique=unique)
            print(f"Индекс {index_name} создан для таблицы {table_name}.")
        except exc.OperationalError:
            print(f"Индекс {index_name} уже существует или не может быть создан.")

    # Создание таблицы 'drawings' (если она еще не существует)
    create_table_if_not_exists(
        'drawings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('hash', sa.String(length=64), nullable=False),
        sa.Column('file_path', sa.String(length=255), nullable=False),
        sa.Column('file_name', sa.String(length=255), nullable=False),
        sa.Column('file_size', sa.BigInteger(), nullable=False),
        sa.Column('mime_type', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('last_used_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('version', sa.Integer(), server_default='1', nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('hash')
    )

    # Добавление столбца 'archived_at' (если он еще не существует)
    add_column_if_not_exists('drawings', sa.Column('archived_at', sa.TIMESTAMP(timezone=True), nullable=True))

    # Создание индекса для поля hash
    create_index_if_not_exists('idx_drawings_hash', 'drawings', ['hash'], unique=False)

    # Создание таблицы order_drawings
    create_table_if_not_exists(
        'order_drawings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('drawing_id', sa.Integer(), nullable=False),
        sa.Column('qr_code_path', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['drawing_id'], ['drawings.id'], ),
        sa.ForeignKeyConstraint(['order_id'], ['production_orders.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Создание индекса для поля order_id
    create_index_if_not_exists('idx_order_drawings_order_id', 'order_drawings', ['order_id'], unique=False)

def downgrade():
    # Здесь можно добавить логику отката изменений, если это необходимо
    pass
