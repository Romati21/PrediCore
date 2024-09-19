"""empty_migration

Revision ID: aa03f5e92c32
Revises: 
Create Date: 2024-09-19 14:16:12.018987

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'aa03f5e92c32'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Здесь мы добавим создание таблицы alembic_version
    op.create_table(
        'alembic_version',
        sa.Column('version_num', sa.String(32), nullable=False),
        sa.PrimaryKeyConstraint('version_num')
    )
    op.execute("INSERT INTO alembic_version (version_num) VALUES ('aa03f5e92c32')")

def downgrade():
    op.drop_table('alembic_version')
