"""Merge heads

Revision ID: 41153c4da03a
Revises: 890dc02d87fa, b5330111209d
Create Date: 2024-10-07 10:01:47.366795

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '41153c4da03a'
down_revision: Union[str, None] = ('890dc02d87fa', 'b5330111209d')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
