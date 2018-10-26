"""added natural sort mat view

Revision ID: db2857ad5cdc
Revises: 059c8f0da3b3
Create Date: 2018-11-03 15:01:46.679393

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'db2857ad5cdc'
down_revision = '059c8f0da3b3'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('''
            CREATE MATERIALIZED VIEW natural_sort AS
                SELECT num.string AS string,
                       (
                           SELECT coalesce(string_agg(convert_to(coalesce(
                                      upper(r[2]),
                                      CAST(length(r[1]) AS TEXT) ||
                                      CAST(length(CAST(length(r[1]) AS TEXT)) AS TEXT) ||
                                      r[1]
                                  ), 'SQL_ASCII'), '\\x00'), '')
                             FROM regexp_matches(num.string, '0*(\\d+)|(\\D+)', 'g') AS r
                       ) AS index
                  FROM (
                           SELECT stop_point.short_ind AS string FROM stop_point
                           UNION
                           SELECT service.line AS string FROM service
                           UNION
                           SELECT CAST(generate_series(0, 100) AS TEXT) AS string
                       ) AS num
            WITH NO DATA;
        ''')
    op.create_index(op.f('ix_natural_sort_string'), 'natural_sort', ['string'],
                    unique=True)
    op.create_index(op.f('ix_natural_sort_index'), 'natural_sort', ['index'],
                    unique=False)


def downgrade():
    op.execute("DROP MATERIALIZED VIEW natural_sort")
