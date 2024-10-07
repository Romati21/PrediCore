"""Add users and sessions

Revision ID: ebacd2c1eb97
Revises: e84b2e530c8e
Create Date: 2024-10-07 12:10:07.306895

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

userrole_enum = postgresql.ENUM('MASTER', 'ADJUSTER', 'WORKER', name='userrole', create_type=False)

# revision identifiers, used by Alembic
revision: str = 'ebacd2c1eb97'
down_revision: str = 'e84b2e530c8e'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # 1. Создание типа ENUM 'userrole' в базе данных
    userrole_enum.create(op.get_bind())

    # 2. Изменение существующей таблицы 'users' для использования типа 'userrole'
    op.execute("ALTER TABLE users ALTER COLUMN role TYPE userrole USING role::userrole")

    # 3. Создание таблицы 'user_sessions'
    op.create_table('user_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('token', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token')
    )
    op.create_index(op.f('ix_user_sessions_id'), 'user_sessions', ['id'], unique=False)

    # 4. Добавление колонок в таблицу 'users'
    op.add_column('users', sa.Column('birth_date', sa.Date(), nullable=False))
    op.add_column('users', sa.Column('password_hash', sa.String(length=255), nullable=False))
    op.add_column('users', sa.Column('email', sa.String(length=100), nullable=False))
    op.add_column('users', sa.Column('is_active', sa.Boolean(), nullable=True))
    op.add_column('users', sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True))

    # 5. Уникальное ограничение на колонку email
    op.create_unique_constraint(None, 'users', ['email'])


def downgrade() -> None:
    # Откат изменений типа ENUM и удаление типа 'userrole'
    op.drop_constraint(None, 'users', type_='unique')
    op.alter_column('users', 'role',
               existing_type=userrole_enum,
               type_=sa.VARCHAR(length=50),
               existing_nullable=False)

    userrole_enum.drop(op.get_bind())

    # Удаление колонок из таблицы 'users'
    op.drop_column('users', 'last_login_at')
    op.drop_column('users', 'is_active')
    op.drop_column('users', 'email')
    op.drop_column('users', 'password_hash')
    op.drop_column('users', 'birth_date')

    # Удаление индекса и таблицы 'user_sessions'
    op.drop_index(op.f('ix_user_sessions_id'), table_name='user_sessions')
    op.drop_table('user_sessions')
