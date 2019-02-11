"""use noc dataset for operator data

Revision ID: 2355305e6972
Revises: be39987fc563
Create Date: 2019-02-11 11:32:50.942131

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2355305e6972'
down_revision = 'be39987fc563'
branch_labels = None
depends_on = None


local_operator = sa.table(
    "local_operator",
    sa.column("code", type_=sa.Text),
    sa.column("region_ref", type_=sa.VARCHAR(2)),
    sa.column("name", type_=sa.Text)
)
operator = sa.table(
    "operator",
    sa.column("code", type_=sa.Text),
    sa.column("name", type_=sa.Text),
    sa.column("region_ref", type_=sa.VARCHAR(2)),
    sa.column("mode", type_=sa.Integer)
)
service = sa.table(
    "service",
    sa.column("id", type_=sa.Integer),
    sa.column("mode", type_=sa.Integer)
)
service_mode = sa.table(
    "service_mode",
    sa.column("id", type_=sa.Integer),
    sa.column("name", type_=sa.Text)
)


def upgrade():
    op.execute("DROP MATERIALIZED VIEW fts;")

    op.execute(service_mode.update().where(service_mode.c.id == 2).values({"name": "coach"}))
    op.execute(service_mode.insert().values([
        {"id": 4, "name": "metro"},
        {"id": 5, "name": "underground"}
    ]))
    op.execute(service.update().where(service.c.mode == 2).values({"mode": 4}))

    op.execute(operator.update().where(operator.c.name.is_(None)).values({"name": ""}))
    op.alter_column('operator', 'name', existing_type=sa.TEXT(), nullable=False)

    op.add_column('operator', sa.Column('region_ref', sa.VARCHAR(length=2), nullable=True))
    op.add_column('operator', sa.Column('mode', sa.Integer(), nullable=True))
    op.execute(operator.update().values({"mode": 1, "region_ref": "GB"}))
    op.alter_column('operator', 'region_ref', existing_type=sa.VARCHAR(2), nullable=False)
    op.alter_column('operator', 'mode', existing_type=sa.INTEGER(), nullable=False)

    op.add_column('operator', sa.Column('licence_name', sa.Text(), nullable=True))
    op.add_column('operator', sa.Column('email', sa.Text(), nullable=True))
    op.add_column('operator', sa.Column('address', sa.Text(), nullable=True))
    op.add_column('operator', sa.Column('website', sa.Text(), nullable=True))
    op.add_column('operator', sa.Column('twitter', sa.Text(), nullable=True))

    op.create_index(op.f('ix_operator_mode'), 'operator', ['mode'], unique=False)
    op.create_index(op.f('ix_operator_region_ref'), 'operator', ['region_ref'], unique=False)
    op.create_foreign_key(op.f("operator_region_ref_fkey"), 'operator', 'region',
                          ['region_ref'], ['code'], ondelete='CASCADE')
    op.create_foreign_key(op.f("operator_service_mode_fkey"), 'operator', 'service_mode',
                          ['mode'], ['id'])

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
    op.create_index(op.f('ix_fts_table'), 'fts', ['table_name'], unique=False)
    op.create_index(op.f('ix_fts_code'), 'fts', ['code'], unique=False)
    op.create_index(op.f('ix_fts_unique'), 'fts', ['table_name', 'code'], unique=True)
    op.create_index(op.f('ix_fts_vector_gin'), 'fts', ['vector'], unique=False, postgresql_using='gin')
    op.create_index(op.f('ix_fts_areas_gin'), 'fts', ['admin_areas'], unique=False, postgresql_using='gin')


def downgrade():
    op.execute("DROP MATERIALIZED VIEW fts;")

    op.drop_constraint(op.f("operator_region_ref_fkey"), 'operator', type_='foreignkey')
    op.drop_constraint(op.f("operator_service_mode_fkey"), 'operator', type_='foreignkey')
    op.drop_index(op.f('ix_operator_region_ref'), table_name='operator')
    op.drop_index(op.f('ix_operator_mode'), table_name='operator')

    op.drop_column('operator', 'twitter')
    op.drop_column('operator', 'website')
    op.drop_column('operator', 'address')
    op.drop_column('operator', 'email')
    op.drop_column('operator', 'licence_name')
    op.drop_column('operator', 'mode')
    op.drop_column('operator', 'region_ref')

    op.alter_column('operator', 'name', existing_type=sa.TEXT(), nullable=True)

    op.execute(service.update().where(service.c.mode == 2).values({"mode": 1}))
    op.execute(service.update().where(service.c.mode > 3).values({"mode": 2}))
    op.execute(service_mode.delete().where(service_mode.c.id > 3))
    op.execute(service_mode.update().where(service_mode.c.id == 2).values({"name": "metro"}))

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
               setweight(to_tsvector('english', string_agg(DISTINCT local_operator.name, ' ')), 'B') ||
               setweight(to_tsvector('english', string_agg(DISTINCT locality.name, ' ')), 'C') ||
               setweight(to_tsvector('english', coalesce(string_agg(DISTINCT district.name, ' '), '')), 'D') ||
               setweight(to_tsvector('english', string_agg(DISTINCT admin_area.name, ' ')), 'D') AS vector
        FROM service
             JOIN journey_pattern ON journey_pattern.service_ref = service.id
             JOIN local_operator ON local_operator.code = journey_pattern.local_operator_ref AND
                                    local_operator.region_ref = journey_pattern.region_ref
             JOIN journey_link ON journey_pattern.id = journey_link.pattern_ref
             JOIN stop_point ON journey_link.stop_point_ref = stop_point.atco_code
             JOIN locality ON stop_point.locality_ref = locality.code
             LEFT OUTER JOIN district ON locality.district_ref = district.code
             JOIN admin_area ON locality.admin_area_ref = admin_area.code
        GROUP BY service.id
        WITH NO DATA;
    """)
    op.create_index(op.f('ix_fts_table'), 'fts', ['table_name'], unique=False)
    op.create_index(op.f('ix_fts_code'), 'fts', ['code'], unique=False)
    op.create_index(op.f('ix_fts_unique'), 'fts', ['table_name', 'code'], unique=True)
    op.create_index(op.f('ix_fts_vector_gin'), 'fts', ['vector'], unique=False, postgresql_using='gin')
    op.create_index(op.f('ix_fts_areas_gin'), 'fts', ['admin_areas'], unique=False, postgresql_using='gin')
