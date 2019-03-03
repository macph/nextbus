"""
Squashed data migrations for 0.7

Revision ID: 74069f6388f3
Revises: d26cde7b1d28
Create Date: 2019-03-03 15:24:11.180723

"""
import datetime as dt

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '74069f6388f3'
down_revision = 'ab6763ad82d3'
branch_labels = None
depends_on = None


# Insert data for lookup tables
bank_holiday_data = [
    {"id": 1, "name": "NewYearsDay"},
    {"id": 2, "name": "Jan2ndScotland"},
    {"id": 3, "name": "GoodFriday"},
    {"id": 4, "name": "EasterMonday"},
    {"id": 5, "name": "MayDay"},
    {"id": 6, "name": "SpringBank"},
    {"id": 7, "name": "LateSummerBankHolidayNotScotland"},
    {"id": 8, "name": "AugustBankHolidayScotland"},
    {"id": 9, "name": "ChristmasDay"},
    {"id": 10, "name": "BoxingDay"},
    {"id": 11, "name": "ChristmasDayHoliday"},
    {"id": 12, "name": "BoxingDayHoliday"},
    {"id": 13, "name": "NewYearsDayHoliday"},
    {"id": 14, "name": "ChristmasEve"},
    {"id": 15, "name": "NewYearsEve"},
]
mode_data = [
    {"id": 1, "name": "bus"},
    {"id": 2, "name": "coach"},
    {"id": 3, "name": "tram"},
    {"id": 4, "name": "metro"},
    {"id": 5, "name": "underground"}
]
# Insert data for bank holidays
date_f = "%Y-%m-%d"
bank_holiday_dates = [
    {"holiday_ref": 13, "date": "2017-01-02"},
    {"holiday_ref": 2, "date": "2017-01-02"},
    {"holiday_ref": 3, "date": "2017-04-14"},
    {"holiday_ref": 4, "date": "2017-04-17"},
    {"holiday_ref": 5, "date": "2017-05-01"},
    {"holiday_ref": 6, "date": "2017-05-29"},
    {"holiday_ref": 8, "date": "2017-08-05"},
    {"holiday_ref": 7, "date": "2017-08-28"},
    {"holiday_ref": 9, "date": "2017-12-25"},
    {"holiday_ref": 10, "date": "2017-12-26"},
    {"holiday_ref": 1, "date": "2018-01-01"},
    {"holiday_ref": 2, "date": "2018-01-02"},
    {"holiday_ref": 3, "date": "2018-03-30"},
    {"holiday_ref": 4, "date": "2018-04-02"},
    {"holiday_ref": 5, "date": "2018-05-07"},
    {"holiday_ref": 6, "date": "2018-05-28"},
    {"holiday_ref": 8, "date": "2018-08-06"},
    {"holiday_ref": 7, "date": "2018-08-27"},
    {"holiday_ref": 9, "date": "2018-12-25"},
    {"holiday_ref": 10, "date": "2018-12-26"},
    {"holiday_ref": 1, "date": "2019-01-01"},
    {"holiday_ref": 2, "date": "2019-01-02"},
    {"holiday_ref": 3, "date": "2019-04-19"},
    {"holiday_ref": 4, "date": "2019-04-22"},
    {"holiday_ref": 5, "date": "2019-05-06"},
    {"holiday_ref": 6, "date": "2019-05-27"},
    {"holiday_ref": 8, "date": "2019-08-05"},
    {"holiday_ref": 7, "date": "2019-08-26"},
    {"holiday_ref": 9, "date": "2019-12-25"},
    {"holiday_ref": 10, "date": "2019-12-26"},
]


def upgrade():
    bank_holiday = op.create_table(
        "bank_holiday",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name")
    )
    op.bulk_insert(bank_holiday, bank_holiday_data)

    service_mode = op.create_table(
        "service_mode",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name")
    )
    op.bulk_insert(service_mode, mode_data)

    bh_dates = op.create_table(
        "bank_holiday_date",
        sa.Column("holiday_ref", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(["holiday_ref"], ["bank_holiday.id"]),
        sa.PrimaryKeyConstraint("holiday_ref", "date")
    )
    op.create_index(op.f("ix_bank_holiday_date_holiday_ref"), "bank_holiday_date", ["holiday_ref"], unique=False)
    op.bulk_insert(bh_dates, [
        {"holiday_ref": d["holiday_ref"], "date": dt.datetime.strptime(d["date"], date_f)}
        for d in bank_holiday_dates
    ])

    op.create_table(
        "operator",
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("region_ref", sa.VARCHAR(length=2), nullable=False),
        sa.Column("mode", sa.Integer(), nullable=False),
        sa.Column("licence_name", sa.Text(), nullable=True),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("website", sa.Text(), nullable=True),
        sa.Column("twitter", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["region_ref"], ["region.code"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["mode"], ["service_mode.id"]),
        sa.PrimaryKeyConstraint("code")
    )
    op.create_index(op.f("ix_operator_mode"), "operator", ["mode"], unique=False)
    op.create_index(op.f("ix_operator_region_ref"), "operator", ["region_ref"], unique=False)

    op.create_table(
        "organisation",
        sa.Column("code", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("code")
    )
    op.create_table(
        "local_operator",
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("region_ref", sa.VARCHAR(length=2), nullable=False),
        sa.Column("operator_ref", sa.Text(), nullable=True),
        sa.Column("name", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["operator_ref"], ["operator.code"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["region_ref"], ["region.code"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("code", "region_ref")
    )
    op.create_index(op.f("ix_local_operator_operator_ref"), "local_operator", ["operator_ref"], unique=False)
    op.create_index(op.f("ix_local_operator_region_ref"), "local_operator", ["region_ref"], unique=False)

    op.create_table(
        "operating_period",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("org_ref", sa.Text(), nullable=False),
        sa.Column("date_start", sa.Date(), nullable=False),
        sa.Column("date_end", sa.Date(), nullable=True),
        sa.Column("working", sa.Boolean(), nullable=False),
        sa.CheckConstraint("date_start <= date_end"),
        sa.ForeignKeyConstraint(["org_ref"], ["organisation.code"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id")
    )
    op.create_index(op.f("ix_operating_period_org_ref"), "operating_period", ["org_ref"], unique=False)

    op.create_table(
        "excluded_date",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("org_ref", sa.Text(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("working", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["org_ref"], ["organisation.code"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id")
    )
    op.create_index(op.f("ix_excluded_date_org_ref"), "excluded_date", ["org_ref"], unique=False)

    op.create_table(
        "service",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("code", sa.Text(), nullable=True),
        sa.Column("line", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("mode", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["mode"], ["service_mode.id"]),
        sa.PrimaryKeyConstraint("id")
    )
    op.create_index(op.f("ix_service_mode"), "service", ["mode"], unique=False)

    op.create_table(
        "journey_pattern",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("origin", sa.Text(), nullable=False),
        sa.Column("destination", sa.Text(), nullable=False),
        sa.Column("service_ref", sa.Integer(), nullable=False),
        sa.Column("local_operator_ref", sa.Text(), nullable=False),
        sa.Column("region_ref", sa.Text(), nullable=False),
        sa.Column("direction", sa.Boolean(), nullable=False),
        sa.Column("date_start", sa.Date(), nullable=False),
        sa.Column("date_end", sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(["service_ref"], ["service.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["local_operator_ref", "region_ref"],
            ["local_operator.code", "local_operator.region_ref"],
            ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id")
    )
    op.create_index(op.f("ix_journey_pattern_service_ref"), "journey_pattern", ["service_ref"], unique=False)
    op.create_index(op.f("ix_journey_pattern_direction"), "journey_pattern", ["direction"], unique=False)
    op.create_index(op.f("ix_journey_pattern_local_operator_ref"), "journey_pattern", ["local_operator_ref"], unique=False)
    op.create_index(op.f("ix_journey_pattern_region_ref"), "journey_pattern", ["region_ref"], unique=False)
    op.create_index(op.f("ix_journey_pattern_local_operator_ref_region_ref"), "journey_pattern", ["local_operator_ref", "region_ref"], unique=False)

    op.create_table(
        "journey_link",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=False),
        sa.Column("pattern_ref", sa.Integer(), nullable=False),
        sa.Column("stop_point_ref", sa.VARCHAR(length=12), nullable=True),
        sa.Column("run_time", sa.Interval(), nullable=True),
        sa.Column("wait_arrive", sa.Interval(), nullable=True),
        sa.Column("wait_leave", sa.Interval(), nullable=True),
        sa.Column("timing_point", sa.Boolean(), nullable=False),
        sa.Column("principal_point", sa.Boolean(), nullable=False),
        sa.Column("stopping", sa.Boolean(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["pattern_ref"], ["journey_pattern.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["stop_point_ref"], ["stop_point.atco_code"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("pattern_ref", "sequence"),
        sa.CheckConstraint("run_time IS NOT NULL AND wait_arrive IS NOT NULL OR wait_leave IS NOT NULL")
    )
    op.create_index(op.f("ix_journey_link_sequence"), "journey_link", ["sequence"], unique=False)
    op.create_index(op.f("ix_journey_link_pattern_ref"), "journey_link", ["pattern_ref"], unique=False)
    op.create_index(op.f("ix_journey_link_stop_point_ref"), "journey_link", ["stop_point_ref"], unique=False)

    op.create_table(
        "journey",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=False),
        sa.Column("pattern_ref", sa.Integer(), nullable=False),
        sa.Column("start_run", sa.Integer(), nullable=True),
        sa.Column("end_run", sa.Integer(), nullable=True),
        sa.Column("departure", sa.Time(), nullable=False),
        sa.Column("days", sa.SmallInteger(), nullable=False),
        sa.Column("weeks", sa.SmallInteger(), nullable=True),
        sa.Column("note_code", sa.Text(), nullable=True),
        sa.Column("note_text", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["pattern_ref"], ["journey_pattern.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["start_run"], ["journey_link.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["end_run"], ["journey_link.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id")
    )
    op.create_index(op.f("ix_journey_pattern_ref"), "journey", ["pattern_ref"], unique=False)
    op.create_index(op.f("ix_journey_end_run"), "journey", ["end_run"], unique=False)
    op.create_index(op.f("ix_journey_start_run"), "journey", ["start_run"], unique=False)

    op.create_table(
        "journey_specific_link",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("journey_ref", sa.Integer(), nullable=False),
        sa.Column("link_ref", sa.Integer(), nullable=False),
        sa.Column("run_time", sa.Interval(), nullable=True),
        sa.Column("wait_arrive", sa.Interval(), nullable=True),
        sa.Column("wait_leave", sa.Interval(), nullable=True),
        sa.Column("stopping", sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(["link_ref"], ["journey_link.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["journey_ref"], ["journey.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("journey_ref", "link_ref")
    )
    op.create_index(op.f("ix_journey_specific_link_journey_ref"), "journey_specific_link", ["journey_ref"], unique=False)
    op.create_index(op.f("ix_journey_specific_link_link_ref"), "journey_specific_link", ["link_ref"], unique=False)

    op.create_table(
        "bank_holidays",
        sa.Column("holidays", sa.Integer(), nullable=False),
        sa.Column("journey_ref", sa.Integer(), nullable=False),
        sa.Column("operational", sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(["journey_ref"], ["journey.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("holidays", "journey_ref")
    )
    op.create_index(op.f("ix_bank_holidays_holidays"), "bank_holidays", ["holidays"], unique=False)
    op.create_index(op.f("ix_bank_holidays_journey_ref"), "bank_holidays", ["journey_ref"], unique=False)

    op.create_table(
        "organisations",
        sa.Column("org_ref", sa.Text(), nullable=False),
        sa.Column("journey_ref", sa.Integer(), nullable=False),
        sa.Column("operational", sa.Boolean(), nullable=False),
        sa.Column("working", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["journey_ref"], ["journey.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_ref"], ["organisation.code"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("org_ref", "journey_ref")
    )
    op.create_index(op.f("ix_organisations_journey_ref"), "organisations", ["journey_ref"], unique=False)
    op.create_index(op.f("ix_organisations_org_ref"), "organisations", ["org_ref"], unique=False)

    op.create_table(
        "special_period",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("journey_ref", sa.Integer(), nullable=False),
        sa.Column("date_start", sa.Date(), nullable=True),
        sa.Column("date_end", sa.Date(), nullable=True),
        sa.Column("operational", sa.Boolean(), nullable=False),
        sa.CheckConstraint("date_start <= date_end"),
        sa.ForeignKeyConstraint(["journey_ref"], ["journey.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id")
    )
    op.create_index(op.f("ix_special_period_journey_ref"), "special_period", ["journey_ref"], unique=False)

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
    op.create_index(op.f("ix_natural_sort_string"), "natural_sort", ["string"],
                    unique=True)
    op.create_index(op.f("ix_natural_sort_index"), "natural_sort", ["index"],
                    unique=False)


def downgrade():
    op.execute("DROP MATERIALIZED VIEW natural_sort;")
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
        WITH NO DATA;
    """)
    op.create_index(op.f("ix_fts_table"), "fts", ["table_name"], unique=False)
    op.create_index(op.f("ix_fts_code"), "fts", ["code"], unique=False)
    op.create_index(op.f("ix_fts_unique"), "fts", ["table_name", "code"], unique=True)
    op.create_index(op.f("ix_fts_area"), "fts", ["admin_area_ref"], unique=False)
    op.create_index(op.f("ix_fts_vector_gin"), "fts", ["vector"], unique=False, postgresql_using="gin")

    op.drop_table("special_period")
    op.drop_table("organisations")
    op.drop_table("bank_holidays")
    op.drop_table("journey_specific_link")
    op.drop_table("journey")
    op.drop_table("journey_link")
    op.drop_table("journey_pattern")
    op.drop_table("service")
    op.drop_table("excluded_date")
    op.drop_table("operating_period")
    op.drop_table("local_operator")
    op.drop_table("organisation")
    op.drop_table("operator")
    op.drop_table("bank_holiday_date")
    op.drop_table("service_mode")
    op.drop_table("bank_holiday")
