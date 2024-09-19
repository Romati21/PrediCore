"""sync_database_state

Revision ID: 5b58309a5231
Revises: 26881dbe1c75
Create Date: 2024-09-18 13:05:52.901464

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5b58309a5231'
down_revision: Union[str, None] = '26881dbe1c75'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE alembic_version SET version_num='26881dbe1c75'")



def downgrade() -> None:
    pass
