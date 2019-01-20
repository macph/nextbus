"""added notes to journeys

Revision ID: 9cb95e84cf3e
Revises: 7e108ad6890f
Create Date: 2019-01-19 09:08:26.924086

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9cb95e84cf3e'
down_revision = '7e108ad6890f'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('journey', sa.Column('note_code', sa.Text(), nullable=True))
    op.add_column('journey', sa.Column('note_text', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('journey', 'note_text')
    op.drop_column('journey', 'note_code')
