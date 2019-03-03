"""made description nonnull

Revision ID: 74069f6388f3
Revises: d26cde7b1d28
Create Date: 2019-03-03 15:24:11.180723

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '74069f6388f3'
down_revision = 'd26cde7b1d28'
branch_labels = None
depends_on = None


service = sa.table(
    'service',
    sa.column('id', sa.Integer()),
    sa.column('description', sa.Text())
)


def upgrade():
    op.execute(
        service.update()
        .values({'description': ''})
        .where(service.c.description.is_(None))
    )
    op.alter_column('service', 'description', existing_type=sa.TEXT(), nullable=False)


def downgrade():
    op.alter_column('service', 'description', existing_type=sa.TEXT(), nullable=True)
    op.execute(
        service.update()
        .values({'description': None})
        .where(service.c.description == '')
    )
