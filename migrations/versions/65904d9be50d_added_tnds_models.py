"""added TNDS models

Revision ID: 65904d9be50d
Revises: ab6763ad82d3
Create Date: 2018-07-11 10:30:29.332725

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '65904d9be50d'
down_revision = 'ab6763ad82d3'
branch_labels = None
depends_on = None

# Enum types
direction = sa.Enum(
    'inbound', 'outbound', 'inboundAndOutbound', 'circular', 'clockwise',
    'antiClockwise', name='direction'
)
service_mode = sa.Enum('bus', 'metro', 'tram', name='service_mode')
stop_timing = sa.Enum('PPT', 'PTP', 'TIP', 'OTH', name='stop_timing')
bank_holiday = sa.Enum(
    'NewYearsDay', 'Jan2ndScotland', 'GoodFriday', 'EasterMonday', 'MayDay',
    'SpringBank', 'LateSummerBankHolidayNotScotland',
    'AugustBankHolidayScotland', 'ChristmasDay', 'BoxingDay',
    'ChristmasDayHoliday', 'BoxingDayHoliday', 'NewYearsDayHoliday',
    'ChristmasEve', 'NewYearsEve', name='bank_holiday'
)


def upgrade():
    op.create_table(
        'bank_holiday_date',
        sa.Column('name', bank_holiday, nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.PrimaryKeyConstraint('name', 'date')
    )
    op.create_table(
        'journey_section',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table(
        'operator',
        sa.Column('code', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('code')
    )
    op.create_table(
        'organisation',
        sa.Column('code', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('code')
    )
    op.create_table(
        'local_operator',
        sa.Column('code', sa.Text(), nullable=False),
        sa.Column('region_ref', sa.VARCHAR(length=2), nullable=False),
        sa.Column('operator_ref', sa.Text(), nullable=True),
        sa.Column('name', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['operator_ref'], ['operator.code'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['region_ref'], ['region.code'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('code', 'region_ref')
    )
    op.create_table(
        'operating_period',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('org_ref', sa.Text(), nullable=False),
        sa.Column('date_start', sa.Date(), nullable=False),
        sa.Column('date_end', sa.Date(), nullable=False),
        sa.Column('working', sa.Boolean(), nullable=False),
        sa.CheckConstraint('date_start <= date_end'),
        sa.ForeignKeyConstraint(['org_ref'], ['organisation.code'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table(
        'operating_date',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('org_ref', sa.Text(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('working', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['org_ref'], ['organisation.code'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table(
        'service',
        sa.Column('code', sa.Text(), nullable=False),
        sa.Column('origin', sa.Text(), nullable=False),
        sa.Column('destination', sa.Text(), nullable=False),
        sa.Column('local_operator_ref', sa.Text(), nullable=False),
        sa.Column('region_ref', sa.VARCHAR(length=2), nullable=False),
        sa.Column('mode', service_mode, nullable=False),
        sa.Column('direction', direction, nullable=False),
        sa.ForeignKeyConstraint(
            ['local_operator_ref', 'region_ref'],
            ['local_operator.code', 'local_operator.region_ref'],
            ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('code')
    )
    op.create_table(
        'journey_pattern',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=False),
        sa.Column('service_ref', sa.Text(), nullable=False),
        sa.Column('direction', direction, nullable=False),
        sa.Column('date_start', sa.Date(), nullable=False),
        sa.Column('date_end', sa.Date(), nullable=True),
        sa.CheckConstraint('date_start <= date_end'),
        sa.ForeignKeyConstraint(['service_ref'], ['service.code'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table(
        'service_line',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=False),
        sa.Column('name', sa.Text(), nullable=True),
        sa.Column('service_ref', sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(['service_ref'], ['service.code'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table(
        'journey_link',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=False),
        sa.Column('section_ref', sa.Integer(), nullable=False),
        sa.Column('stop_start', sa.VARCHAR(length=12), nullable=True),
        sa.Column('wait_start', sa.Interval(), nullable=False),
        sa.Column('timing_start', stop_timing, nullable=False),
        sa.Column('stopping_start', sa.Boolean(), nullable=False),
        sa.Column('stop_end', sa.VARCHAR(length=12), nullable=True),
        sa.Column('wait_end', sa.Interval(), nullable=False),
        sa.Column('timing_end', stop_timing, nullable=False),
        sa.Column('stopping_end', sa.Boolean(), nullable=False),
        sa.Column('run_time', sa.Interval(), nullable=False),
        sa.Column('direction', direction, nullable=True),
        sa.Column('route_direction', direction, nullable=True),
        sa.Column('sequence', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['section_ref'], ['journey_section.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['stop_end'], ['stop_point.atco_code'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['stop_start'], ['stop_point.atco_code'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('section_ref', 'sequence')
    )
    op.create_table(
        'journey',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=False),
        sa.Column('service_ref', sa.Text(), nullable=False),
        sa.Column('line_ref', sa.Integer(), nullable=False),
        sa.Column('pattern_ref', sa.Integer(), nullable=False),
        sa.Column('start_run', sa.Integer(), nullable=True),
        sa.Column('end_run', sa.Integer(), nullable=True),
        sa.Column('departure', sa.Time(), nullable=False),
        sa.Column('days', sa.Integer(), nullable=False),
        sa.Column('weeks', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['line_ref'], ['service_line.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['pattern_ref'], ['journey_pattern.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['service_ref'], ['service.code'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['start_run'], ['journey_link.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['end_run'], ['journey_link.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table(
        'journey_specific_link',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('journey_ref', sa.Integer(), nullable=False),
        sa.Column('link_ref', sa.Integer(), nullable=False),
        sa.Column('wait_start', sa.Interval(), nullable=True),
        sa.Column('stopping_start', sa.Boolean(), nullable=True),
        sa.Column('wait_end', sa.Interval(), nullable=True),
        sa.Column('stopping_end', sa.Boolean(), nullable=True),
        sa.Column('run_time', sa.Interval(), nullable=True),
        sa.ForeignKeyConstraint(['link_ref'], ['journey_link.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['journey_ref'], ['journey.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('journey_ref', 'link_ref')
    )
    op.create_table(
        'journey_sections',
        sa.Column('pattern_ref', sa.Integer(), nullable=False),
        sa.Column('section_ref', sa.Integer(), nullable=False),
        sa.Column('sequence', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['pattern_ref'], ['journey_pattern.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['section_ref'], ['journey_section.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('pattern_ref', 'section_ref'),
        sa.UniqueConstraint('pattern_ref', 'sequence')
    )
    op.create_table(
        'bank_holidays',
        sa.Column('name', bank_holiday, nullable=False),
        sa.Column('journey_ref', sa.Integer(), nullable=False),
        sa.Column('operational', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['journey_ref'], ['journey.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('name', 'journey_ref')
    )
    op.create_table(
        'organisations',
        sa.Column('org_ref', sa.Text(), nullable=False),
        sa.Column('journey_ref', sa.Integer(), nullable=False),
        sa.Column('operational', sa.Boolean(), nullable=False),
        sa.Column('working', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['journey_ref'], ['journey.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['org_ref'], ['organisation.code'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('org_ref', 'journey_ref')
    )
    op.create_table(
        'special_period',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('journey_ref', sa.Integer(), nullable=True),
        sa.Column('date_start', sa.Date(), nullable=True),
        sa.Column('date_end', sa.Date(), nullable=True),
        sa.Column('operational', sa.Boolean(), nullable=False),
        sa.CheckConstraint('date_start <= date_end'),
        sa.ForeignKeyConstraint(['journey_ref'], ['journey.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('special_period')
    op.drop_table('organisations')
    op.drop_table('bank_holidays')
    op.drop_table('journey_sections')
    op.drop_table('journey_specific_link')
    op.drop_table('journey')
    op.drop_table('journey_link')
    op.drop_table('service_line')
    op.drop_table('journey_pattern')
    op.drop_table('service')
    op.drop_table('operating_date')
    op.drop_table('operating_period')
    op.drop_table('local_operator')
    op.drop_table('organisation')
    op.drop_table('operator')
    op.drop_table('journey_section')
    op.drop_table('bank_holiday_date')

    bind = op.get_bind()
    bank_holiday.drop(bind)
    stop_timing.drop(bind)
    service_mode.drop(bind)
    direction.drop(bind)
