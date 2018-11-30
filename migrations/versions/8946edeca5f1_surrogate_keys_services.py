"""surrogate keys services

Revision ID: 8946edeca5f1
Revises: e5510a1cd76f
Create Date: 2018-11-29 13:43:30.098760

"""
from alembic import op
import sqlalchemy as sa
import sqlalchemy.sql as sql


# revision identifiers, used by Alembic.
revision = '8946edeca5f1'
down_revision = 'e5510a1cd76f'
branch_labels = None
depends_on = None


temp_lo = sql.table('local_operator',
    sa.Column('operator_ref', sa.Text()),
    sa.Column('name', sa.Text()),
)


temp_o = sql.table('operator',
    sa.Column('code', sa.Text()),
    sa.Column('name', sa.Text()),
)


def upgrade():
    op.execute("DROP MATERIALIZED VIEW fts;")

    op.drop_constraint('journey_pattern_service_ref_fkey', 'journey_pattern', type_='foreignkey')

    op.add_column('service', sa.Column('id', sa.Integer(), autoincrement=False, nullable=False))
    op.drop_constraint('service_pkey', 'service')
    op.create_primary_key('service_pkey', 'service', ['id'])
    op.alter_column('service', 'code', existing_type=sa.Text(), nullable=True)
    op.alter_column('service', 'description', existing_type=sa.Text(), nullable=True)

    op.drop_index('ix_service_local_operator_ref_region_ref', table_name='service')
    op.drop_index('ix_service_region_ref', table_name='service')
    op.drop_constraint('service_region_ref_fkey', 'service', type_='foreignkey')
    op.drop_constraint('service_local_operator_ref_fkey', 'service', type_='foreignkey')
    op.drop_constraint('service_admin_area_ref_fkey', 'service', type_='foreignkey')
    op.drop_column('service', 'local_operator_ref')
    op.drop_column('service', 'region_ref')
    op.drop_column('service', 'admin_area_ref')

    op.add_column('operator', sa.Column('name', sa.Text(), nullable=True))
    op_name = (
        sa.select([temp_lo.c.name]).select_from(temp_lo)
        .where(temp_lo.c.operator_ref == temp_o.c.code)
        .order_by(sa.desc(temp_lo.c.name)).limit(1)
        .as_scalar()
    )
    op.execute(temp_o.update().values(name=op_name))

    op.drop_constraint('journey_pattern_check', 'journey_pattern', type_='check')
    op.alter_column('journey_pattern', 'service_ref', type_=sa.Integer(), existing_nullable=False, postgresql_using="service_ref::INT")
    op.create_foreign_key('journey_pattern_service_ref_fkey', 'journey_pattern', 'service', ['service_ref'], ['id'], ondelete='CASCADE')

    op.add_column('journey_pattern', sa.Column('local_operator_ref', sa.Text(), nullable=False))
    op.add_column('journey_pattern', sa.Column('region_ref', sa.VARCHAR(length=2), nullable=False))
    op.create_foreign_key('journey_pattern_local_operator_ref_fkey', 'journey_pattern', 'local_operator', ['local_operator_ref', 'region_ref'], ['code', 'region_ref'], ondelete='CASCADE')
    op.create_index(op.f('ix_journey_pattern_local_operator_ref'), 'journey_pattern', ['local_operator_ref'], unique=False)
    op.create_index(op.f('ix_journey_pattern_region_ref'), 'journey_pattern', ['region_ref'], unique=False)
    op.create_index(op.f('ix_journey_pattern_local_operator_ref_region_ref'), 'journey_pattern', ['local_operator_ref', 'region_ref'], unique=False)

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
                   setweight(to_tsvector('english', region.name), 'A') AS vector
              FROM region
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
                   setweight(to_tsvector('english', admin_area.name), 'A') AS vector
              FROM admin_area
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
                   setweight(to_tsvector('english', locality.name), 'A') ||
                   setweight(to_tsvector('english', coalesce(district.name, '')), 'B') ||
                   setweight(to_tsvector('english', admin_area.name), 'B') AS vector
              FROM locality
                   JOIN (
                       SELECT stop_point.locality_ref AS code
                         FROM stop_point
                     GROUP BY stop_point.locality_ref
                   ) AS locality_stops ON locality_stops.code = locality.code
                   LEFT OUTER JOIN district ON district.code = locality.district_ref
                   JOIN admin_area ON admin_area.code = locality.admin_area_ref
            UNION ALL
            SELECT 'stop_area' AS table_name,
                   stop_area.code AS code,
                   stop_area.name AS name,
                   stop_count.ind AS short_ind,
                   NULL AS street,
                   stop_area.stop_area_type AS stop_type,
                   NULL AS stop_area_ref,
                   locality.name AS locality_name,
                   district.name AS district_name,
                   admin_area.code AS admin_area_ref,
                   admin_area.name AS admin_area_name,
                   setweight(to_tsvector('english', stop_area.name), 'A') ||
                   setweight(to_tsvector('english', coalesce(locality.name, '')), 'C') ||
                   setweight(to_tsvector('english', coalesce(district.name, '')), 'D') ||
                   setweight(to_tsvector('english', admin_area.name), 'D') AS vector
              FROM stop_area
                   JOIN (
                       SELECT stop_point.stop_area_ref AS code,
                              CAST(count(stop_point.atco_code) AS TEXT) AS ind
                         FROM stop_point
                     GROUP BY stop_point.stop_area_ref
                   ) AS stop_count ON stop_count.code = stop_area.code
                   LEFT OUTER JOIN locality ON locality.code = stop_area.locality_ref
                   LEFT OUTER JOIN district ON district.code = locality.district_ref
                   JOIN admin_area ON admin_area.code = stop_area.admin_area_ref
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
                   service.id::TEXT AS code,
                   service.description AS name,
                   service.line AS short_ind,
                   NULL AS street,
                   NULL AS stop_type,
                   NULL AS stop_area_ref,
                   NULL AS locality_name,
                   NULL AS district_name,
                   NULL AS admin_area_ref,
                   NULL AS admin_area_name,
                   setweight(to_tsvector('english', service.line), 'A') ||
                   setweight(to_tsvector('english', service.description), 'A') ||
                   setweight(to_tsvector('english', operator_names.operators), 'B') ||
                   setweight(to_tsvector('english', area_names.localities), 'C') ||
                   setweight(to_tsvector('english', area_names.districts), 'D') ||
                   setweight(to_tsvector('english', area_names.admin_areas), 'D') AS vector
              FROM service
                   JOIN (
                       SELECT service.id AS id,
                              string_agg(DISTINCT locality.name, ' ') AS localities,
                              string_agg(DISTINCT coalesce(district.name, ''), ' ') AS districts,
                              string_agg(DISTINCT admin_area.name, ' ') AS admin_areas
                         FROM service
                              INNER JOIN journey_pattern ON journey_pattern.service_ref = service.id
                              INNER JOIN journey_link ON journey_link.pattern_ref = journey_pattern.id
                              INNER JOIN stop_point ON stop_point.atco_code = journey_link.stop_point_ref
                              INNER JOIN locality ON locality.code = stop_point.locality_ref
                              LEFT OUTER JOIN district ON district.code = locality.district_ref
                              INNER JOIN admin_area ON admin_area.code = locality.admin_area_ref
                     GROUP BY service.id
                   ) AS area_names ON area_names.id = service.id
                   JOIN (
                       SELECT service.id AS id,
                              string_agg(DISTINCT local_operator.name, ' ') AS operators
                         FROM service
                              INNER JOIN journey_pattern ON journey_pattern.service_ref = service.id
                              INNER JOIN local_operator ON local_operator.code = journey_pattern.local_operator_ref AND local_operator.region_ref = journey_pattern.region_ref
                       GROUP BY service.id
                   ) AS operator_names ON operator_names.id = service.id
        WITH NO DATA;
    """)
    op.create_index(op.f('ix_fts_table'), 'fts', ['table_name'], unique=False)
    op.create_index(op.f('ix_fts_code'), 'fts', ['code'], unique=False)
    op.create_index(op.f('ix_fts_unique'), 'fts', ['table_name', 'code'],
                    unique=True)
    op.create_index(op.f('ix_fts_area'), 'fts', ['admin_area_ref'],
                    unique=False)
    op.create_index(op.f('ix_fts_vector_gin'), 'fts', ['vector'], unique=False,
                    postgresql_using='gin')


def downgrade():
    op.execute("DROP MATERIALIZED VIEW fts;")

    op.drop_constraint('journey_pattern_service_ref_fkey', 'journey_pattern', type_='foreignkey')

    op.add_column('service', sa.Column('admin_area_ref', sa.VARCHAR(length=3), autoincrement=False, nullable=True))
    op.add_column('service', sa.Column('region_ref', sa.VARCHAR(length=2), autoincrement=False, nullable=False))
    op.add_column('service', sa.Column('local_operator_ref', sa.Text(), autoincrement=False, nullable=False))
    op.create_foreign_key('service_admin_area_ref_fkey', 'service', 'admin_area', ['admin_area_ref'], ['code'], ondelete='CASCADE')
    op.create_foreign_key('service_local_operator_ref_fkey', 'service', 'local_operator', ['local_operator_ref', 'region_ref'], ['code', 'region_ref'], ondelete='CASCADE')
    op.create_foreign_key('service_region_ref_fkey', 'service', 'region', ['region_ref'], ['code'], ondelete='CASCADE')
    op.create_index('ix_service_admin_area_ref', 'service', ['admin_area_ref'], unique=False)
    op.create_index('ix_service_region_ref', 'service', ['region_ref'], unique=False)
    op.create_index('ix_service_local_operator_ref_region_ref', 'service', ['local_operator_ref', 'region_ref'], unique=False)

    op.alter_column('service', 'description', existing_type=sa.Text(), nullable=False)
    op.alter_column('service', 'code', existing_type=sa.Text(), nullable=False)
    op.drop_constraint('service_pkey', 'service')
    op.create_primary_key('service_pkey', 'service', ['code'])
    op.drop_column('service', 'id')

    op.drop_column('operator', 'name')

    op.drop_index('ix_journey_pattern_local_operator_ref_region_ref', table_name='journey_pattern')
    op.drop_index(op.f('ix_journey_pattern_region_ref'), table_name='journey_pattern')
    op.drop_index(op.f('ix_journey_pattern_local_operator_ref'), table_name='journey_pattern')
    op.drop_column('journey_pattern', 'region_ref')
    op.drop_column('journey_pattern', 'local_operator_ref')

    op.alter_column('journey_pattern', 'service_ref', type_=sa.Text(), existing_nullable=False, postgresql_using="service_ref::TEXT")
    op.create_foreign_key('journey_pattern_service_ref_fkey', 'journey_pattern', 'service', ['service_ref'], ['code'], ondelete='CASCADE')
    op.create_check_constraint('journey_pattern_check', 'journey_pattern', 'date_start <= date_end')

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
                   setweight(to_tsvector('english', region.name), 'A') AS vector
              FROM region
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
                   setweight(to_tsvector('english', admin_area.name), 'A') AS vector
              FROM admin_area
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
                   setweight(to_tsvector('english', locality.name), 'A') ||
                   setweight(to_tsvector('english', coalesce(district.name, '')), 'B') ||
                   setweight(to_tsvector('english', admin_area.name), 'B') AS vector
              FROM locality
                   JOIN (
                       SELECT stop_point.locality_ref AS code
                         FROM stop_point
                     GROUP BY stop_point.locality_ref
                   ) AS locality_stops ON locality_stops.code = locality.code
                   LEFT OUTER JOIN district ON district.code = locality.district_ref
                   JOIN admin_area ON admin_area.code = locality.admin_area_ref
            UNION ALL
            SELECT 'stop_area' AS table_name,
                   stop_area.code AS code,
                   stop_area.name AS name,
                   stop_count.ind AS short_ind,
                   NULL AS street,
                   stop_area.stop_area_type AS stop_type,
                   NULL AS stop_area_ref,
                   locality.name AS locality_name,
                   district.name AS district_name,
                   admin_area.code AS admin_area_ref,
                   admin_area.name AS admin_area_name,
                   setweight(to_tsvector('english', stop_area.name), 'A') ||
                   setweight(to_tsvector('english', coalesce(locality.name, '')), 'C') ||
                   setweight(to_tsvector('english', coalesce(district.name, '')), 'D') ||
                   setweight(to_tsvector('english', admin_area.name), 'D') AS vector
              FROM stop_area
                   JOIN (
                       SELECT stop_point.stop_area_ref AS code,
                              CAST(count(stop_point.atco_code) AS TEXT) AS ind
                         FROM stop_point
                     GROUP BY stop_point.stop_area_ref
                   ) AS stop_count ON stop_count.code = stop_area.code
                   LEFT OUTER JOIN locality ON locality.code = stop_area.locality_ref
                   LEFT OUTER JOIN district ON district.code = locality.district_ref
                   JOIN admin_area ON admin_area.code = stop_area.admin_area_ref
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
                   service.code AS code,
                   service.description AS name,
                   service.line AS short_ind,
                   NULL AS street,
                   NULL AS stop_type,
                   NULL AS stop_area_ref,
                   NULL AS locality_name,
                   NULL AS district_name,
                   admin_area.code AS admin_area_ref,
                   admin_area.name AS admin_area_name,
                   setweight(to_tsvector('english', service.line), 'A') ||
                   setweight(to_tsvector('english', service.description), 'A') ||
                   setweight(to_tsvector('english', area_names.localities), 'C') ||
                   setweight(to_tsvector('english', area_names.districts), 'D') ||
                   setweight(to_tsvector('english', area_names.admin_areas), 'D') AS vector
              FROM service
                   JOIN (
                       SELECT service.code AS code,
                              string_agg(DISTINCT locality.name, ' ') AS localities,
                              string_agg(DISTINCT coalesce(district.name, ''), ' ') AS districts,
                              string_agg(DISTINCT admin_area.name, ' ') AS admin_areas
                         FROM service
                              INNER JOIN journey_pattern ON journey_pattern.service_ref = service.code
                              INNER JOIN journey_link ON journey_link.pattern_ref = journey_pattern.id
                              INNER JOIN stop_point ON stop_point.atco_code = journey_link.stop_point_ref
                              INNER JOIN locality ON locality.code = stop_point.locality_ref
                              LEFT OUTER JOIN district ON district.code = locality.district_ref
                              INNER JOIN admin_area ON admin_area.code = locality.admin_area_ref
                     GROUP BY service.code
                   ) AS area_names ON area_names.code = service.code
                   LEFT OUTER JOIN admin_area ON admin_area.code = service.admin_area_ref
        WITH NO DATA;
    """)
    op.create_index(op.f('ix_fts_table'), 'fts', ['table_name'], unique=False)
    op.create_index(op.f('ix_fts_code'), 'fts', ['code'], unique=False)
    op.create_index(op.f('ix_fts_unique'), 'fts', ['table_name', 'code'],
                    unique=True)
    op.create_index(op.f('ix_fts_area'), 'fts', ['admin_area_ref'],
                    unique=False)
    op.create_index(op.f('ix_fts_vector_gin'), 'fts', ['vector'], unique=False,
                    postgresql_using='gin')
