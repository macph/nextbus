"""merged migrations for 0.6

Revision ID: ab6763ad82d3
Revises:
Create Date: 2018-05-27 10:09:20.074300

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "ab6763ad82d3"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "region",
        sa.Column("code", sa.VARCHAR(length=2), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("modified", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("code")
    )
    op.create_index(op.f("ix_region_name"), "region", ["name"], unique=False)

    op.create_table(
        "admin_area",
        sa.Column("code", sa.VARCHAR(length=3), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("atco_code", sa.VARCHAR(length=3), nullable=False),
        sa.Column("region_ref", sa.VARCHAR(length=2), nullable=False),
        sa.Column("is_live", sa.Boolean(), nullable=True),
        sa.Column("modified", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["region_ref"], ["region.code"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("code"),
        sa.UniqueConstraint("atco_code")
    )
    op.create_index(op.f("ix_admin_area_name"), "admin_area", ["name"], unique=False)
    op.create_index(op.f("ix_admin_area_region_ref"), "admin_area", ["region_ref"], unique=False)

    op.create_table(
        "district",
        sa.Column("code", sa.VARCHAR(length=3), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("admin_area_ref", sa.VARCHAR(length=3), nullable=False),
        sa.Column("modified", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["admin_area_ref"], ["admin_area.code"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("code")
    )
    op.create_index(op.f("ix_district_admin_area_ref"), "district", ["admin_area_ref"], unique=False)
    op.create_index(op.f("ix_district_name"), "district", ["name"], unique=False)

    op.create_table(
        "locality",
        sa.Column("code", sa.VARCHAR(length=8), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("parent_ref", sa.VARCHAR(length=8), nullable=True),
        sa.Column("admin_area_ref", sa.VARCHAR(length=3), nullable=False),
        sa.Column("district_ref", sa.VARCHAR(length=3), nullable=True),
        sa.Column("easting", sa.Integer(), nullable=False),
        sa.Column("northing", sa.Integer(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("modified", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["admin_area_ref"], ["admin_area.code"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["district_ref"], ["district.code"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("code")
    )
    op.create_index(op.f("ix_locality_admin_area_ref"), "locality", ["admin_area_ref"], unique=False)
    op.create_index(op.f("ix_locality_district_ref"), "locality", ["district_ref"], unique=False)
    op.create_index(op.f("ix_locality_name"), "locality", ["name"], unique=False)
    op.create_index(op.f("ix_locality_parent_ref"), "locality", ["parent_ref"], unique=False)

    op.create_table(
        "postcode",
        sa.Column("index", sa.VARCHAR(length=7), nullable=False),
        sa.Column("text", sa.VARCHAR(length=8), nullable=False),
        sa.Column("admin_area_ref", sa.VARCHAR(length=3), nullable=False),
        sa.Column("district_ref", sa.VARCHAR(length=3), nullable=True),
        sa.Column("easting", sa.Integer(), nullable=False),
        sa.Column("northing", sa.Integer(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["admin_area_ref"], ["admin_area.code"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["district_ref"], ["district.code"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("index")
    )
    op.create_index(op.f("ix_postcode_admin_area_ref"), "postcode", ["admin_area_ref"], unique=False)
    op.create_index(op.f("ix_postcode_district_ref"), "postcode", ["district_ref"], unique=False)
    op.create_index(op.f("ix_postcode_text"), "postcode", ["text"], unique=True)

    op.create_table(
        "stop_area",
        sa.Column("code", sa.VARCHAR(length=12), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("admin_area_ref", sa.VARCHAR(length=3), nullable=False),
        sa.Column("locality_ref", sa.VARCHAR(length=8), nullable=True),
        sa.Column("stop_area_type", sa.VARCHAR(length=4), nullable=False),
        sa.Column("easting", sa.Integer(), nullable=False),
        sa.Column("northing", sa.Integer(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("modified", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["admin_area_ref"], ["admin_area.code"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["locality_ref"], ["locality.code"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("code")
    )
    op.create_index(op.f("ix_stop_area_admin_area_ref"), "stop_area", ["admin_area_ref"], unique=False)
    op.create_index(op.f("ix_stop_area_locality_ref"), "stop_area", ["locality_ref"], unique=False)
    op.create_index(op.f("ix_stop_area_name"), "stop_area", ["name"], unique=False)

    op.create_table(
        "stop_point",
        sa.Column("atco_code", sa.VARCHAR(length=12), nullable=False),
        sa.Column("naptan_code", sa.VARCHAR(length=9), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("landmark", sa.Text(), nullable=True),
        sa.Column("street", sa.Text(), nullable=True),
        sa.Column("crossing", sa.Text(), nullable=True),
        sa.Column("indicator", sa.Text(), server_default="", nullable=False),
        sa.Column("short_ind", sa.Text(), server_default="", nullable=False),
        sa.Column("locality_ref", sa.VARCHAR(length=8), nullable=False),
        sa.Column("admin_area_ref", sa.VARCHAR(length=3), nullable=False),
        sa.Column("stop_area_ref", sa.VARCHAR(length=12), nullable=True),
        sa.Column("easting", sa.Integer(), nullable=False),
        sa.Column("northing", sa.Integer(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("stop_type", sa.VARCHAR(length=3), nullable=False),
        sa.Column("bearing", sa.VARCHAR(length=2), nullable=True),
        sa.Column("modified", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["admin_area_ref"], ["admin_area.code"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["locality_ref"], ["locality.code"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["stop_area_ref"], ["stop_area.code"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("atco_code")
    )
    op.create_index(op.f("ix_stop_point_name"), "stop_point", ["name"], unique=False)
    op.create_index(op.f("ix_stop_point_admin_area_ref"), "stop_point", ["admin_area_ref"], unique=False)
    op.create_index(op.f("ix_stop_point_locality_ref"), "stop_point", ["locality_ref"], unique=False)
    op.create_index(op.f("ix_stop_point_naptan_code"), "stop_point", ["naptan_code"], unique=True)
    op.create_index(op.f("ix_stop_point_short_ind"), "stop_point", ["short_ind"], unique=False)
    op.create_index(op.f("ix_stop_point_stop_area_ref"), "stop_point", ["stop_area_ref"], unique=False)
    op.create_index(op.f("ix_stop_point_latitude"), "stop_point", ["latitude"], unique=False)
    op.create_index(op.f("ix_stop_point_longitude"), "stop_point", ["longitude"], unique=False)

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
    op.create_index(op.f("ix_fts_table"), "fts", ["table_name"], unique=False)
    op.create_index(op.f("ix_fts_code"), "fts", ["code"], unique=False)
    op.create_index(op.f("ix_fts_unique"), "fts", ["table_name", "code"], unique=True)
    op.create_index(op.f("ix_fts_area"), "fts", ["admin_area_ref"], unique=False)
    op.create_index(op.f("ix_fts_vector_gin"), "fts", ["vector"], unique=False, postgresql_using="gin")


def downgrade():
    op.execute("DROP MATERIALIZED VIEW IF EXISTS fts")

    op.drop_table("stop_point")
    op.drop_table("stop_area")
    op.drop_table("postcode")
    op.drop_table("locality")
    op.drop_table("district")
    op.drop_table("admin_area")
    op.drop_table("region")
