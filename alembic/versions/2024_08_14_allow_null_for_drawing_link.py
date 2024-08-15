"""Allow null for drawing_link

Revision ID: new_revision_id
Revises: 06fcc36d480d
Create Date: 2023-08-14 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '4fe103c285a8'
down_revision = '06fcc36d480d'
branch_labels = None
depends_on = None

def upgrade():
    op.alter_column('production_orders', 'drawing_link',
               existing_type=sa.VARCHAR(),
               nullable=True)

def downgrade():
    op.alter_column('production_orders', 'drawing_link',
               existing_type=sa.VARCHAR(),
               nullable=False)
