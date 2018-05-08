"""replaced tsvector columns with mat view

Revision ID: f88d5245a532
Revises: 295e6c3d42b9
Create Date: 2018-05-09 20:13:44.952092

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'f88d5245a532'
down_revision = '295e6c3d42b9'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_index('ix_region_tsvector_name', table_name='region')
    op.drop_column('region', 'tsv_name')

    op.drop_index('ix_admin_area_tsvector_name', table_name='admin_area')
    op.drop_column('admin_area', 'tsv_name')

    op.drop_index('ix_district_tsvector_name', table_name='district')
    op.drop_column('district', 'tsv_name')

    op.drop_index('ix_locality_tsvector_name', table_name='locality')
    op.drop_column('locality', 'tsv_name')

    op.drop_index('ix_stop_area_tsvector_name', table_name='stop_area')
    op.drop_column('stop_area', 'tsv_name')

    op.drop_index('ix_stop_point_tsvector_street', table_name='stop_point')
    op.drop_index('ix_stop_point_tsvector_name', table_name='stop_point')
    op.drop_index('ix_stop_point_tsvector_both', table_name='stop_point')
    op.drop_column('stop_point', 'tsv_street')
    op.drop_column('stop_point', 'tsv_name')
    op.drop_column('stop_point', 'tsv_both')

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
        WITH NO DATA;
    """)
    op.create_index(op.f('ix_fts_table'), 'fts', ['table_name'], unique=False)
    op.create_index(op.f('ix_fts_code'), 'fts', ['code'], unique=False)
    op.create_index(op.f('ix_fts_unique'), 'fts', ['table_name', 'code'], unique=True)
    op.create_index(op.f('ix_fts_area'), 'fts', ['admin_area_ref'], unique=False)
    op.create_index(op.f('ix_fts_vector_gin'), 'fts', ['vector'], unique=False, postgresql_using='gin')


def downgrade():
    op.drop_index(op.f('ix_fts_vector_gin'), table_name='fts')
    op.drop_index(op.f('ix_fts_area'), table_name='fts')
    op.drop_index(op.f('ix_fts_unique'), table_name='fts')
    op.drop_index(op.f('ix_fts_code'), table_name='fts')
    op.drop_index(op.f('ix_fts_table'), table_name='fts')
    op.execute("DROP MATERIALIZED VIEW IF EXISTS fts")

    op.add_column('stop_point', sa.Column('tsv_both', postgresql.TSVECTOR(), nullable=True))
    op.add_column('stop_point', sa.Column('tsv_name', postgresql.TSVECTOR(), nullable=True))
    op.add_column('stop_point', sa.Column('tsv_street', postgresql.TSVECTOR(), nullable=True))
    op.create_index('ix_stop_point_tsvector_both', 'stop_point', ['tsv_both'], unique=False, postgresql_using='gin')
    op.create_index('ix_stop_point_tsvector_name', 'stop_point', ['tsv_name'], unique=False, postgresql_using='gin')
    op.create_index('ix_stop_point_tsvector_street', 'stop_point', ['tsv_street'], unique=False, postgresql_using='gin')

    op.add_column('stop_area', sa.Column('tsv_name', postgresql.TSVECTOR(), nullable=True))
    op.create_index('ix_stop_area_tsvector_name', 'stop_area', ['tsv_name'], unique=False, postgresql_using='gin')

    op.add_column('locality', sa.Column('tsv_name', postgresql.TSVECTOR(), nullable=True))
    op.create_index('ix_locality_tsvector_name', 'locality', ['tsv_name'], unique=False, postgresql_using='gin')

    op.add_column('admin_area', sa.Column('tsv_name', postgresql.TSVECTOR(), nullable=True))
    op.create_index('ix_admin_area_tsvector_name', 'admin_area', ['tsv_name'], unique=False, postgresql_using='gin')

    op.add_column('district', sa.Column('tsv_name', postgresql.TSVECTOR(), nullable=True))
    op.create_index('ix_district_tsvector_name', 'district', ['tsv_name'], unique=False, postgresql_using='gin')

    op.add_column('region', sa.Column('tsv_name', postgresql.TSVECTOR(), nullable=True))
    op.create_index('ix_region_tsvector_name', 'region', ['tsv_name'], unique=False, postgresql_using='gin')
