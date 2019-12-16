"""
moved to derived models

Revision ID: 0d7fbd9b8750
Revises: 39ac82acfedc
Create Date: 2019-12-15 14:27:43.453654

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0d7fbd9b8750'
down_revision = '39ac82acfedc'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("DROP MATERIALIZED VIEW natural_sort;")
    op.execute("DROP MATERIALIZED VIEW fts;")

    op.create_table(
        'fts',
        sa.Column('table_name', sa.Text(), nullable=False),
        sa.Column('code', sa.Text(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('indicator', sa.Text(), nullable=True),
        sa.Column('street', sa.Text(), nullable=True),
        sa.Column('stop_type', sa.Text(), nullable=True),
        sa.Column('stop_area_ref', sa.Text(), nullable=True),
        sa.Column('locality_name', sa.Text(), nullable=True),
        sa.Column('district_name', sa.Text(), nullable=True),
        sa.Column('admin_area_ref', sa.VARCHAR(length=3), nullable=True),
        sa.Column('admin_area_name', sa.Text(), nullable=True),
        sa.Column('admin_areas', sa.ARRAY(sa.Text(), dimensions=1), nullable=False),
        sa.Column('vector', postgresql.TSVECTOR(), nullable=False),
        sa.PrimaryKeyConstraint('table_name', 'code')
    )
    op.create_index('ix_fts_areas_gin', 'fts', ['admin_areas'], unique=False, postgresql_using='gin')
    op.create_index(op.f('ix_fts_code'), 'fts', ['code'], unique=False)
    op.create_index(op.f('ix_fts_table_name'), 'fts', ['table_name'], unique=False)
    op.create_index('ix_fts_unique', 'fts', ['table_name', 'code'], unique=True)
    op.create_index('ix_fts_vector_gin', 'fts', ['vector'], unique=False, postgresql_using='gin')

    op.create_table(
        'natural_sort',
        sa.Column('string', sa.Text(), nullable=False),
        sa.Column('index', sa.LargeBinary(), nullable=True),
        sa.PrimaryKeyConstraint('string')
    )
    op.create_index(op.f('ix_natural_sort_index'), 'natural_sort', ['index'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_natural_sort_index'), table_name='natural_sort')
    op.drop_table('natural_sort')
    op.drop_index('ix_fts_vector_gin', table_name='fts')
    op.drop_index('ix_fts_unique', table_name='fts')
    op.drop_index(op.f('ix_fts_table_name'), table_name='fts')
    op.drop_index(op.f('ix_fts_code'), table_name='fts')
    op.drop_index('ix_fts_areas_gin', table_name='fts')
    op.drop_table('fts')

    op.execute("""
        CREATE MATERIALIZED VIEW fts AS
        SELECT 'region' AS table_name,
                CAST(region.code AS TEXT) AS code,
                region.name AS name,
                NULL AS indicator,
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
               NULL AS indicator,
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
               NULL AS indicator,
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
               NULL AS indicator,
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
               CAST(count(stop_point.atco_code) AS TEXT) AS indicator,
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
               stop_point.short_ind AS indicator,
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
               service.code AS code,
               service.short_description AS name,
               service.line AS indicator,
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

    op.execute("""
        CREATE MATERIALIZED VIEW natural_sort AS
            SELECT num.string AS string,
                   (SELECT coalesce(string_agg(convert_to(coalesce(
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
    """)
    op.create_index(op.f("ix_natural_sort_string"), "natural_sort", ["string"], unique=True)
    op.create_index(op.f("ix_natural_sort_index"), "natural_sort", ["index"], unique=False)
