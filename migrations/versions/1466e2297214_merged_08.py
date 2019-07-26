"""
Squashed migrations for 0.8

- fk for region on journey pattern
- Added active property to stops
- modified constraints for operating and special periods
- modified fts weights
- added service pairs
- fixed services without operators

Revision ID: 1466e2297214
Revises: 2bf4c5301c63
Create Date: 2019-07-19 13:51:55.584119

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1466e2297214'
down_revision = '74069f6388f3'
branch_labels = None
depends_on = None


stop_area = sa.table(
    "stop_area",
    sa.column("code", sa.VARCHAR(12)),
    sa.column("active", sa.Boolean)
)
stop_point = sa.table(
    "stop_point",
    sa.column("atco_code", sa.VARCHAR(12)),
    sa.column("active", sa.Boolean)
)


def upgrade():
    op.create_foreign_key(op.f('journey_pattern_region_ref_fkey'), 'journey_pattern', 'region', ['region_ref'], ['code'], ondelete='CASCADE')

    op.add_column('stop_area', sa.Column('active', sa.Boolean(), nullable=True))
    op.add_column('stop_point', sa.Column('active', sa.Boolean(), nullable=True))
    op.execute(sa.update(stop_area).values(active=True))
    op.execute(sa.update(stop_point).values(active=True))
    op.alter_column('stop_area', 'active', nullable=False)
    op.alter_column('stop_point', 'active', nullable=False)
    op.create_index(op.f('ix_stop_area_active'), 'stop_area', ['active'], unique=False)
    op.create_index(op.f('ix_stop_point_active'), 'stop_point', ['active'], unique=False)

    op.drop_constraint('operating_period_check', 'operating_period')
    op.drop_constraint('special_period_check', 'special_period')
    op.alter_column('special_period', 'date_end', existing_type=sa.DATE(), nullable=False)
    op.alter_column('special_period', 'date_start', existing_type=sa.DATE(), nullable=False)

    op.create_table(
        'service_pair',
        sa.Column('id', sa.Integer(), autoincrement=False, nullable=False),
        sa.Column('service0', sa.Integer(), nullable=False),
        sa.Column('direction0', sa.Boolean(), nullable=False),
        sa.Column('count0', sa.Integer(), nullable=False),
        sa.Column('service1', sa.Integer(), nullable=False),
        sa.Column('direction1', sa.Boolean(), nullable=False),
        sa.Column('count1', sa.Integer(), nullable=False),
        sa.Column('similarity', sa.Float(), nullable=False),
        sa.CheckConstraint('service0 < service1'),
        sa.ForeignKeyConstraint(('service0',), ['service.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(('service1',), ['service.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_service_pair_direction0'), 'service_pair', ['direction0'], unique=False)
    op.create_index(op.f('ix_service_pair_direction1'), 'service_pair', ['direction1'], unique=False)
    op.create_index(op.f('ix_service_pair_service0'), 'service_pair', ['service0'], unique=False)
    op.create_index(op.f('ix_service_pair_service1'), 'service_pair', ['service1'], unique=False)

    op.execute("DROP MATERIALIZED VIEW fts;")
    op.execute("""
        CREATE MATERIALIZED VIEW fts AS
        SELECT 'region' AS table_name,
                CAST(region.code AS TEXT) AS code,
                region.name AS name,
                NULL AS short_ind,
                NULL AS street,
                NULL AS stop_type,
                NULL AS stop_area_ref,
                NULL AS locality_name,
                NULL AS district_name,
                NULL AS admin_area_ref,
                NULL AS admin_area_name,
                CAST(ARRAY[] AS TEXT[]) AS admin_areas,
                setweight(to_tsvector('english', region.name), 'A') AS vector
        FROM region
        WHERE region.code != 'GB'
        UNION ALL
        SELECT 'admin_area' AS table_name,
               CAST(admin_area.code AS TEXT) AS code,
               admin_area.name AS name,
               NULL AS short_ind,
               NULL AS street,
               NULL AS stop_type,
               NULL AS stop_area_ref,
               NULL AS locality_name,
               NULL AS district_name,
               admin_area.code AS admin_area_ref,
               admin_area.name AS admin_area_name,
               CAST(ARRAY[admin_area.code] AS TEXT[]) AS admin_areas,
               setweight(to_tsvector('english', admin_area.name), 'A') AS vector
        FROM admin_area
        WHERE admin_area.region_ref != 'GB'
        UNION ALL
        SELECT 'district' AS table_name,
               CAST(district.code AS TEXT) AS code,
               district.name AS name,
               NULL AS short_ind,
               NULL AS street,
               NULL AS stop_type,
               NULL AS stop_area_ref,
               NULL AS locality_name,
               NULL AS district_name,
               admin_area.code AS admin_area_ref,
               admin_area.name AS admin_area_name,
               CAST(ARRAY[admin_area.code] AS TEXT[]) AS admin_areas,
               setweight(to_tsvector('english', district.name), 'A') ||
               setweight(to_tsvector('english', admin_area.name), 'B') AS vector
        FROM district
             JOIN admin_area ON admin_area.code = district.admin_area_ref
        UNION ALL
        SELECT 'locality' AS table_name,
               CAST(locality.code AS TEXT) AS code,
               locality.name AS name,
               NULL AS short_ind,
               NULL AS street,
               NULL AS stop_type,
               NULL AS stop_area_ref,
               NULL AS locality_name,
               district.name AS district_name,
               admin_area.code AS admin_area_ref,
               admin_area.name AS admin_area_name,
               CAST(ARRAY[admin_area.code] AS TEXT[]) AS admin_areas,
               setweight(to_tsvector('english', locality.name), 'A') ||
               setweight(to_tsvector('english', coalesce(district.name, '')), 'C') ||
               setweight(to_tsvector('english', admin_area.name), 'C') AS vector
        FROM locality
             LEFT OUTER JOIN district ON district.code = locality.district_ref
             JOIN admin_area ON admin_area.code = locality.admin_area_ref
        WHERE EXISTS (
                  SELECT stop_point.atco_code
                  FROM stop_point
                  WHERE stop_point.locality_ref = locality.code
              )
        UNION ALL
        SELECT 'stop_area' AS table_name,
               CAST(stop_area.code AS TEXT) AS code,
               stop_area.name AS name,
               CAST(count(stop_point.atco_code) AS TEXT) AS short_ind,
               NULL AS street,
               stop_area.stop_area_type AS stop_type,
               NULL AS stop_area_ref,
               locality.name AS locality_name,
               district.name AS district_name,
               admin_area.code AS admin_area_ref,
               admin_area.name AS admin_area_name,
               CAST(ARRAY[admin_area.code] AS TEXT[]) AS admin_areas,
               setweight(to_tsvector('english', stop_area.name), 'B') ||
               setweight(to_tsvector('english', coalesce(locality.name, '')), 'C') ||
               setweight(to_tsvector('english', coalesce(district.name, '')), 'D') ||
               setweight(to_tsvector('english', admin_area.name), 'D') AS vector
        FROM stop_area
             JOIN stop_point ON stop_area.code = stop_point.stop_area_ref AND stop_point.active
             LEFT OUTER JOIN locality ON locality.code = stop_area.locality_ref
             LEFT OUTER JOIN district ON district.code = locality.district_ref
             JOIN admin_area ON admin_area.code = stop_area.admin_area_ref
        WHERE stop_area.active
        GROUP BY stop_area.code, locality.name, district.name, admin_area.code
        UNION ALL
        SELECT 'stop_point' AS table_name,
               CAST(stop_point.atco_code AS TEXT) AS code,
               stop_point.name AS name,
               stop_point.short_ind AS short_ind,
               stop_point.street AS street,
               stop_point.stop_type AS stop_type,
               stop_point.stop_area_ref AS stop_area_ref,
               locality.name AS locality_name,
               district.name AS district_name,
               admin_area.code AS admin_area_ref,
               admin_area.name AS admin_area_name,
               CAST(ARRAY[admin_area.code] AS TEXT[]) AS admin_areas,
               setweight(to_tsvector('english', stop_point.name), 'B') ||
               setweight(to_tsvector('english', stop_point.street), 'B') ||
               setweight(to_tsvector('english', locality.name), 'C') ||
               setweight(to_tsvector('english', coalesce(district.name, '')), 'D') ||
               setweight(to_tsvector('english', admin_area.name), 'D') AS vector
        FROM stop_point
             JOIN locality ON locality.code = stop_point.locality_ref
             LEFT OUTER JOIN district ON district.code = locality.district_ref
             JOIN admin_area ON admin_area.code = stop_point.admin_area_ref
        WHERE stop_point.active
        UNION ALL
        SELECT 'service' AS table_name,
               CAST(service.id AS TEXT) AS code,
               service.description AS name,
               service.line AS short_ind,
               NULL AS street,
               NULL AS stop_type,
               NULL AS stop_area_ref,
               NULL AS locality_name,
               NULL AS district_name,
               NULL AS admin_area_ref,
               NULL AS admin_area_name,
               CAST(array_agg(DISTINCT admin_area.code) AS TEXT[]) AS admin_areas,
               setweight(to_tsvector('english', service.line), 'B') ||
               setweight(to_tsvector('english', service.description), 'B') ||
               setweight(to_tsvector('english', coalesce(string_agg(DISTINCT operator.name, ' '), '')), 'C') ||
               setweight(to_tsvector('english', string_agg(DISTINCT locality.name, ' ')), 'C') ||
               setweight(to_tsvector('english', coalesce(string_agg(DISTINCT district.name, ' '), '')), 'D') ||
               setweight(to_tsvector('english', string_agg(DISTINCT admin_area.name, ' ')), 'D') AS vector
        FROM service
             JOIN journey_pattern ON journey_pattern.service_ref = service.id
             JOIN local_operator ON local_operator.code = journey_pattern.local_operator_ref AND
                                    local_operator.region_ref = journey_pattern.region_ref
             LEFT OUTER JOIN operator ON local_operator.operator_ref = operator.code
             JOIN journey_link ON journey_pattern.id = journey_link.pattern_ref
             JOIN stop_point ON journey_link.stop_point_ref = stop_point.atco_code AND stop_point.active
             JOIN locality ON stop_point.locality_ref = locality.code
             LEFT OUTER JOIN district ON locality.district_ref = district.code
             JOIN admin_area ON locality.admin_area_ref = admin_area.code
        GROUP BY service.id
        WITH NO DATA;
    """)
    op.create_index(op.f("ix_fts_table"), "fts", ["table_name"], unique=False)
    op.create_index(op.f("ix_fts_code"), "fts", ["code"], unique=False)
    op.create_index(op.f("ix_fts_unique"), "fts", ["table_name", "code"], unique=True)
    op.create_index(op.f("ix_fts_vector_gin"), "fts", ["vector"], unique=False, postgresql_using="gin")
    op.create_index(op.f("ix_fts_areas_gin"), "fts", ["admin_areas"], unique=False, postgresql_using="gin")


def downgrade():
    op.drop_index(op.f('ix_service_pair_service1'), table_name='service_pair')
    op.drop_index(op.f('ix_service_pair_service0'), table_name='service_pair')
    op.drop_index(op.f('ix_service_pair_direction1'), table_name='service_pair')
    op.drop_index(op.f('ix_service_pair_direction0'), table_name='service_pair')
    op.drop_table('service_pair')

    op.alter_column('special_period', 'date_start', existing_type=sa.DATE(), nullable=True)
    op.alter_column('special_period', 'date_end', existing_type=sa.DATE(), nullable=True)
    op.create_check_constraint('operating_period_check', 'operating_period', sa.column('date_start') <= sa.column('date_end'))
    op.create_check_constraint('special_period_check', 'special_period', sa.column('date_start') <= sa.column('date_end'))

    op.execute("DROP MATERIALIZED VIEW fts;")
    op.execute("""
        CREATE MATERIALIZED VIEW fts AS
        SELECT 'region' AS table_name,
                region.code AS code,
                region.name AS name,
                NULL AS short_ind,
                NULL AS street,
                NULL AS stop_type,
                NULL AS stop_area_ref,
                NULL AS locality_name,
                NULL AS district_name,
                NULL AS admin_area_ref,
                NULL AS admin_area_name,
                CAST(ARRAY[] AS TEXT[]) AS admin_areas,
                setweight(to_tsvector('english', region.name), 'A') AS vector
        FROM region
        WHERE region.code != 'GB'
        UNION ALL
        SELECT 'admin_area' AS table_name,
               admin_area.code AS code,
               admin_area.name AS name,
               NULL AS short_ind,
               NULL AS street,
               NULL AS stop_type,
               NULL AS stop_area_ref,
               NULL AS locality_name,
               NULL AS district_name,
               admin_area.code AS admin_area_ref,
               admin_area.name AS admin_area_name,
               ARRAY[admin_area.code] AS admin_areas,
               setweight(to_tsvector('english', admin_area.name), 'A') AS vector
        FROM admin_area
        WHERE admin_area.region_ref != 'GB'
        UNION ALL
        SELECT 'district' AS table_name,
               district.code AS code,
               district.name AS name,
               NULL AS short_ind,
               NULL AS street,
               NULL AS stop_type,
               NULL AS stop_area_ref,
               NULL AS locality_name,
               NULL AS district_name,
               admin_area.code AS admin_area_ref,
               admin_area.name AS admin_area_name,
               ARRAY[admin_area.code] AS admin_areas,
               setweight(to_tsvector('english', district.name), 'A') ||
               setweight(to_tsvector('english', admin_area.name), 'B') AS vector
        FROM district
             JOIN admin_area ON admin_area.code = district.admin_area_ref
        UNION ALL
        SELECT 'locality' AS table_name,
               locality.code AS code,
               locality.name AS name,
               NULL AS short_ind,
               NULL AS street,
               NULL AS stop_type,
               NULL AS stop_area_ref,
               NULL AS locality_name,
               district.name AS district_name,
               admin_area.code AS admin_area_ref,
               admin_area.name AS admin_area_name,
               ARRAY[admin_area.code] AS admin_areas,
               setweight(to_tsvector('english', locality.name), 'A') ||
               setweight(to_tsvector('english', coalesce(district.name, '')), 'B') ||
               setweight(to_tsvector('english', admin_area.name), 'B') AS vector
        FROM locality
             LEFT OUTER JOIN district ON district.code = locality.district_ref
             JOIN admin_area ON admin_area.code = locality.admin_area_ref
        WHERE EXISTS (
                  SELECT stop_point.atco_code
                  FROM stop_point
                  WHERE stop_point.locality_ref = locality.code
              )
        UNION ALL
        SELECT 'stop_area' AS table_name,
               stop_area.code AS code,
               stop_area.name AS name,
               CAST(count(stop_point.atco_code) AS TEXT) AS short_ind,
               NULL AS street,
               stop_area.stop_area_type AS stop_type,
               NULL AS stop_area_ref,
               locality.name AS locality_name,
               district.name AS district_name,
               admin_area.code AS admin_area_ref,
               admin_area.name AS admin_area_name,
               ARRAY[admin_area.code] AS admin_areas,
               setweight(to_tsvector('english', stop_area.name), 'A') ||
               setweight(to_tsvector('english', coalesce(locality.name, '')), 'C') ||
               setweight(to_tsvector('english', coalesce(district.name, '')), 'D') ||
               setweight(to_tsvector('english', admin_area.name), 'D') AS vector
        FROM stop_area
             LEFT OUTER JOIN stop_point ON stop_area.code = stop_point.stop_area_ref
             LEFT OUTER JOIN locality ON locality.code = stop_area.locality_ref
             LEFT OUTER JOIN district ON district.code = locality.district_ref
             JOIN admin_area ON admin_area.code = stop_area.admin_area_ref
        GROUP BY stop_area.code, locality.name, district.name, admin_area.code
        UNION ALL
        SELECT 'stop_point' AS table_name,
               stop_point.atco_code AS code,
               stop_point.name AS name,
               stop_point.short_ind AS short_ind,
               stop_point.street AS street,
               stop_point.stop_type AS stop_type,
               stop_point.stop_area_ref AS stop_area_ref,
               locality.name AS locality_name,
               district.name AS district_name,
               admin_area.code AS admin_area_ref,
               admin_area.name AS admin_area_name,
               ARRAY[admin_area.code] AS admin_areas,
               setweight(to_tsvector('english', stop_point.name), 'A') ||
               setweight(to_tsvector('english', stop_point.street), 'B') ||
               setweight(to_tsvector('english', locality.name), 'C') ||
               setweight(to_tsvector('english', coalesce(district.name, '')), 'D') ||
               setweight(to_tsvector('english', admin_area.name), 'D') AS vector
        FROM stop_point
             JOIN locality ON locality.code = stop_point.locality_ref
             LEFT OUTER JOIN district ON district.code = locality.district_ref
             JOIN admin_area ON admin_area.code = stop_point.admin_area_ref
        UNION ALL
        SELECT 'service' AS table_name,
               CAST(service.id AS TEXT) AS code,
               service.description AS name,
               service.line AS short_ind,
               NULL AS street,
               NULL AS stop_type,
               NULL AS stop_area_ref,
               NULL AS locality_name,
               NULL AS district_name,
               NULL AS admin_area_ref,
               NULL AS admin_area_name,
               array_agg(DISTINCT admin_area.code) AS admin_areas,
               setweight(to_tsvector('english', service.line), 'A') ||
               setweight(to_tsvector('english', service.description), 'A') ||
               setweight(to_tsvector('english', string_agg(DISTINCT operator.name, ' ')), 'B') ||
               setweight(to_tsvector('english', string_agg(DISTINCT locality.name, ' ')), 'C') ||
               setweight(to_tsvector('english', coalesce(string_agg(DISTINCT district.name, ' '), '')), 'D') ||
               setweight(to_tsvector('english', string_agg(DISTINCT admin_area.name, ' ')), 'D') AS vector
        FROM service
             JOIN journey_pattern ON journey_pattern.service_ref = service.id
             JOIN local_operator ON local_operator.code = journey_pattern.local_operator_ref AND
                                    local_operator.region_ref = journey_pattern.region_ref
             JOIN operator ON local_operator.operator_ref = operator.code
             JOIN journey_link ON journey_pattern.id = journey_link.pattern_ref
             JOIN stop_point ON journey_link.stop_point_ref = stop_point.atco_code
             JOIN locality ON stop_point.locality_ref = locality.code
             LEFT OUTER JOIN district ON locality.district_ref = district.code
             JOIN admin_area ON locality.admin_area_ref = admin_area.code
        GROUP BY service.id
        WITH NO DATA;
    """)
    op.create_index(op.f("ix_fts_table"), "fts", ["table_name"], unique=False)
    op.create_index(op.f("ix_fts_code"), "fts", ["code"], unique=False)
    op.create_index(op.f("ix_fts_unique"), "fts", ["table_name", "code"], unique=True)
    op.create_index(op.f("ix_fts_vector_gin"), "fts", ["vector"], unique=False, postgresql_using="gin")
    op.create_index(op.f("ix_fts_areas_gin"), "fts", ["admin_areas"], unique=False, postgresql_using="gin")

    op.drop_index(op.f('ix_stop_point_active'), table_name='stop_point')
    op.drop_index(op.f('ix_stop_area_active'), table_name='stop_point')
    op.drop_column('stop_point', 'active')
    op.drop_column('stop_area', 'active')

    op.drop_constraint(op.f('journey_pattern_region_ref_fkey'), 'journey_pattern', type_='foreignkey')
