"""resync_database_schema

Revision ID: 1c3f4c2fa58f
Revises: 833565f12ada
Create Date: 2024-08-27 13:49:27.448236

"""
from typing import Sequence, Union
from sqlalchemy import exc
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1c3f4c2fa58f'
down_revision: Union[str, None] = '833565f12ada'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None



def upgrade():
    # Создание таблицы drawings
    try:
        op.create_table(
            'drawings',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('hash', sa.String(length=64), nullable=False),
            sa.Column('file_path', sa.String(length=255), nullable=False),
            sa.Column('file_name', sa.String(length=255), nullable=False),
            sa.Column('file_size', sa.BigInteger(), nullable=False),
            sa.Column('mime_type', sa.String(length=100), nullable=False),
            sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('last_used_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('hash')
        )
    except exc.OperationalError:
        pass

    # Создание индекса для поля hash
    try:
        op.create_index(op.f('idx_drawings_hash'), 'drawings', ['hash'], unique=False)
    except exc.OperationalError:
        pass

    # Создание таблицы order_drawings
    try:
        op.create_table(
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
    except exc.OperationalError:
        pass

    # Создание индекса для поля order_id
    try:
        op.create_index(op.f('idx_order_drawings_order_id'), 'order_drawings', ['order_id'], unique=False)
    except exc.OperationalError:
        pass

    # Добавление поля archived_at в таблицу drawings
    try:
        op.add_column('drawings', sa.Column('archived_at', sa.TIMESTAMP(timezone=True), nullable=True))
    except exc.OperationalError:
        pass
