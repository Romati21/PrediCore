"""sync_database_state

Revision ID: 24c58374da3a
Revises: aa5d7a8933ea
Create Date: 2024-08-26 13:51:45.404616

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '24c58374da3a'
down_revision: Union[str, None] = 'aa5d7a8933ea'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE alembic_version SET version_num='aa5d7a8933ea'")


def downgrade() -> None:
    pass
