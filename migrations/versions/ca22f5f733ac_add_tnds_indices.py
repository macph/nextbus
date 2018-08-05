"""add tnds indices

Revision ID: ca22f5f733ac
Revises: 65904d9be50d
Create Date: 2018-07-19 13:54:30.480758

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ca22f5f733ac'
down_revision = '65904d9be50d'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(op.f('ix_journey_pattern_ref'), 'journey', ['pattern_ref'], unique=False)
    op.create_index(op.f('ix_journey_service_ref'), 'journey', ['service_ref'], unique=False)
    op.create_index(op.f('ix_journey_link_sequence'), 'journey_link', ['sequence'], unique=False)
    op.create_index(op.f('ix_journey_link_pattern_ref'), 'journey_link', ['pattern_ref'], unique=False)
    op.create_index(op.f('ix_journey_link_stop_point_ref'), 'journey_link', ['stop_point_ref'], unique=False)
    op.create_index(op.f('ix_journey_pattern_service_ref'), 'journey_pattern', ['service_ref'], unique=False)
    op.create_index(op.f('ix_journey_specific_link_journey_ref'), 'journey_specific_link', ['journey_ref'], unique=False)
    op.create_index(op.f('ix_journey_specific_link_link_ref'), 'journey_specific_link', ['link_ref'], unique=False)
    op.create_index(op.f('ix_bank_holiday_date_holiday_ref'), 'bank_holiday_date', ['holiday_ref'], unique=False)
    op.create_index(op.f('ix_bank_holidays_holiday_ref'), 'bank_holidays', ['holiday_ref'], unique=False)
    op.create_index(op.f('ix_bank_holidays_journey_ref'), 'bank_holidays', ['journey_ref'], unique=False)
    op.create_index(op.f('ix_journey_end_run'), 'journey', ['end_run'], unique=False)
    op.create_index(op.f('ix_journey_start_run'), 'journey', ['start_run'], unique=False)
    op.create_index(op.f('ix_journey_pattern_direction'), 'journey_pattern', ['direction'], unique=False)
    op.create_index(op.f('ix_local_operator_operator_ref'), 'local_operator', ['operator_ref'], unique=False)
    op.create_index(op.f('ix_local_operator_region_ref'), 'local_operator', ['region_ref'], unique=False)
    op.create_index(op.f('ix_operating_date_org_ref'), 'operating_date', ['org_ref'], unique=False)
    op.create_index(op.f('ix_operating_period_org_ref'), 'operating_period', ['org_ref'], unique=False)
    op.create_index(op.f('ix_organisations_journey_ref'), 'organisations', ['journey_ref'], unique=False)
    op.create_index(op.f('ix_organisations_org_ref'), 'organisations', ['org_ref'], unique=False)
    op.create_index(op.f('ix_service_mode'), 'service', ['mode'], unique=False)
    op.create_index(op.f('ix_service_region_ref'), 'service', ['region_ref'], unique=False)
    op.create_index(op.f('ix_service_local_operator_ref_region_ref'), 'service', ['local_operator_ref', 'region_ref'], unique=False)
    op.create_index(op.f('ix_service_admin_area_ref'), 'service', ['admin_area_ref'], unique=False)
    op.create_index(op.f('ix_special_period_journey_ref'), 'special_period', ['journey_ref'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_special_period_journey_ref'), table_name='special_period')
    op.drop_index(op.f('ix_service_admin_area_ref'), table_name='service')
    op.drop_index(op.f('ix_service_local_operator_ref_region_ref'), table_name='service')
    op.drop_index(op.f('ix_service_region_ref'), table_name='service')
    op.drop_index(op.f('ix_service_mode'), table_name='service')
    op.drop_index(op.f('ix_organisations_org_ref'), table_name='organisations')
    op.drop_index(op.f('ix_organisations_journey_ref'), table_name='organisations')
    op.drop_index(op.f('ix_operating_period_org_ref'), table_name='operating_period')
    op.drop_index(op.f('ix_operating_date_org_ref'), table_name='operating_date')
    op.drop_index(op.f('ix_local_operator_region_ref'), table_name='local_operator')
    op.drop_index(op.f('ix_local_operator_operator_ref'), table_name='local_operator')
    op.drop_index(op.f('ix_journey_pattern_direction'), table_name='journey_pattern')
    op.drop_index(op.f('ix_journey_start_run'), table_name='journey')
    op.drop_index(op.f('ix_journey_end_run'), table_name='journey')
    op.drop_index(op.f('ix_bank_holidays_journey_ref'), table_name='bank_holidays')
    op.drop_index(op.f('ix_bank_holidays_holiday_ref'), table_name='bank_holidays')
    op.drop_index(op.f('ix_bank_holiday_date_holiday_ref'), table_name='bank_holiday_date')
    op.drop_index(op.f('ix_journey_specific_link_link_ref'), table_name='journey_specific_link')
    op.drop_index(op.f('ix_journey_specific_link_journey_ref'), table_name='journey_specific_link')
    op.drop_index(op.f('ix_journey_pattern_service_ref'), table_name='journey_pattern')
    op.drop_index(op.f('ix_journey_link_stop_point_ref'), table_name='journey_link')
    op.drop_index(op.f('ix_journey_link_pattern_ref'), table_name='journey_link')
    op.drop_index(op.f('ix_journey_link_sequence'), table_name='journey_link')
    op.drop_index(op.f('ix_journey_service_ref'), table_name='journey')
    op.drop_index(op.f('ix_journey_pattern_ref'), table_name='journey')
