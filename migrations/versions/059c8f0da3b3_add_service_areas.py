"""add service areas

Revision ID: 059c8f0da3b3
Revises: 036f99050836
Create Date: 2018-10-25 14:45:03.938326

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '059c8f0da3b3'
down_revision = '036f99050836'
branch_labels = None
depends_on = None


def upgrade():
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


def downgrade():
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
                SELECT DISTINCT ON (service.code)
                       'service' AS table_name,
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
                       setweight(to_tsvector('english', coalesce(admin_area.name, '')), 'B') AS vector
                  FROM service
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
