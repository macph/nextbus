"""remove autoincrement

Revision ID: 7e108ad6890f
Revises: 8946edeca5f1
Create Date: 2018-12-04 16:09:07.520686

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7e108ad6890f'
down_revision = '8946edeca5f1'
branch_labels = None
depends_on = None


def create_sequence(operation, name, table, column):
    create_seq = "CREATE SEQUENCE %s OWNED BY %s"
    alter_seq = "ALTER SEQUENCE %s RESTART WITH %d"
    col_name = "%s.%s" % (table, column)

    max_ = op.get_bind().execute(sa.select([sa.func.max(sa.text(column))])
                                 .select_from(sa.text(table))).scalar()

    operation.execute(create_seq % (name, col_name))
    if max_ is not None:
        operation.execute(alter_seq % (name, max_ + 1))

    operation.alter_column(table, column, server_default=sa.text("nextval('%s'::regclass)" % name))


def drop_sequence(operation, name, table, column):
    drop_seq = "DROP SEQUENCE %s"

    op.alter_column(table, column, server_default=None)
    operation.execute(drop_seq % name)


def upgrade():
    drop_sequence(op, "journey_specific_link_id_seq", "journey_specific_link", "id")
    drop_sequence(op, "operating_date_id_seq", "operating_date", "id")
    drop_sequence(op, "operating_period_id_seq", "operating_period", "id")
    drop_sequence(op, "special_period_id_seq", "special_period", "id")


def downgrade():
    create_sequence(op, "special_period_id_seq", "special_period", "id")
    create_sequence(op, "operating_period_id_seq", "operating_period", "id")
    create_sequence(op, "operating_date_id_seq", "operating_date", "id")
    create_sequence(op, "journey_specific_link_id_seq", "journey_specific_link", "id")
