"""
service unique code

Revision ID: 4b9d79774675
Revises: 1466e2297214
Create Date: 2019-08-19 10:49:08.588979

"""
from alembic import op
import sqlalchemy as sa
import sqlalchemy.dialects.postgresql as sa_pg


# revision identifiers, used by Alembic.
revision = '4b9d79774675'
down_revision = '1466e2297214'
branch_labels = None
depends_on = None


pattern = sa.table(
    "journey_pattern",
    sa.column("id", sa.Integer),
    sa.column("service_ref", sa.Integer),
    sa.column("direction", sa.Boolean),
    sa.column("origin", sa.Text),
    sa.column("destination", sa.Text)
)
service = sa.table(
    "service",
    sa.column("id", sa.Integer),
    sa.column("code", sa.Text),
    sa.column("line", sa.Text),
    sa.column("description", sa.Text),
    sa.column("short_description", sa.Text),
    sa.column("filename", sa.Text)
)


def fill_description():
    delimiter = sa.bindparam("delimiter", " – ")
    separator = sa.bindparam("separator", " / ")
    origin = sa.func.string_agg(
        sa.distinct(pattern.c.origin),
        sa_pg.aggregate_order_by(separator, pattern.c.origin)
    )
    destination = sa.func.string_agg(
        sa.distinct(pattern.c.origin),
        sa_pg.aggregate_order_by(separator, pattern.c.origin)
    )
    query = (
        sa.select([
            service.c.id.label("id"),
            (origin + delimiter + destination).label("description")
        ])
        .where(
            (service.c.description == "") &
            (service.c.id == pattern.c.service_ref) &
            ~pattern.c.direction
        )
        .group_by(service.c.id)
        .alias("fill_dest")
    )

    return query


def new_codes():
    delimiter = sa.bindparam("delimiter", " – ")
    places = sa.func.regexp_split_to_array(
        sa.func.trim(sa.func.regexp_replace(service.c.description, r"\((.*)\)", " ")),
        delimiter
    )
    places.type = sa.ARRAY(sa.Text, dimensions=1)

    s0 = sa.select([
        service.c.id,
        places.label("places"),
        service.c.line
    ]).alias("s0")

    length = sa.func.array_length(s0.c.places, 1)
    short_desc = sa.case(
        [(length == 1, s0.c.places[1])],
        else_=s0.c.places[1] + delimiter + s0.c.places[length]
    )

    s1 = sa.select([
        s0.c.id,
        short_desc.label("short_desc"),
        s0.c.line
    ]).alias("s1")

    line = sa.func.regexp_replace(sa.func.lower(s1.c.line), r"[^A-Za-z0-9\.]+", "-", "g")
    desc = sa.func.regexp_replace(sa.func.lower(s1.c.short_desc), r"[^A-Za-z0-9\.]+", "-", "g")
    code = sa.case(
        [(sa.func.length(line) <= 5, line + "-" + desc)],
        else_=line
    )

    s2 = sa.select([
        s1.c.id,
        s1.c.short_desc,
        code.label("code")
    ]).alias("s2")

    row_num = sa.func.row_number().over(partition_by=s2.c.code, order_by=s2.c.id)
    with_row_num = s2.c.code + "-" + sa.cast(row_num, sa.Text)
    new_code = sa.case([(row_num == 1, s2.c.code)], else_=with_row_num)

    query = sa.select([
        s2.c.id.label("id"),
        s2.c.short_desc.label("short_description"),
        new_code.label("code")
    ]).alias("dest_codes")

    return query


def upgrade():
    op.add_column('service', sa.Column('short_description', sa.Text(), nullable=True))
    op.add_column('service', sa.Column('filename', sa.Text(), nullable=True))

    fill_desc = fill_description()
    op.execute(
        sa.update(service)
        .values(description=fill_desc.c.description)
        .where(service.c.id == fill_desc.c.id)
    )
    service_codes = new_codes()
    op.execute(
        sa.update(service)
        .values(
            code=service_codes.c.code,
            short_description=service_codes.c.short_description,
            filename=service.c.code
        )
        .where(service.c.id == service_codes.c.id)
    )

    op.alter_column('service', 'short_description', nullable=False)
    op.create_index(op.f('ix_service_code'), 'service', ['code'], unique=True)

    op.execute("DROP MATERIALIZED VIEW fts;")
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


def downgrade():
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

    op.drop_index(op.f('ix_service_code'), table_name='service')
    op.execute(service.update().values(code=service.c.filename))
    op.drop_column('service', 'filename')
    op.drop_column('service', 'short_description')
