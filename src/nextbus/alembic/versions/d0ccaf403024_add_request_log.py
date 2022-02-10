"""
add request log

Revision ID: d0ccaf403024
Revises: 0532364ab1d1
Create Date: 2021-10-06 09:42:47.569055

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd0ccaf403024'
down_revision = '0532364ab1d1'
branch_labels = None
depends_on = None

request_log = sa.table(
    "request_log",
    sa.column("id", sa.Integer),
    sa.column("last_called", sa.DateTime(timezone=True)),
    sa.column("call_count", sa.Integer)
)


def upgrade():
    op.create_table(
        'request_log',
        sa.Column('id', sa.Integer(), autoincrement=False, nullable=False),
        sa.Column('last_called', sa.DateTime(timezone=True), nullable=False),
        sa.Column('call_count', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.execute(
        request_log.insert()
        .values(id=1, last_called=sa.func.now(), call_count=0)
    )


def downgrade():
    op.drop_table('request_log')
