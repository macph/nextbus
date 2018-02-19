"""renamed foreign keys

Revision ID: 2f1d6aa8c56f
Revises: fbead75da60d
Create Date: 2018-02-19 10:42:52.407923

"""
from alembic import op
import sqlalchemy as sa
import sqlalchemy.sql as sql


# revision identifiers, used by Alembic.
revision = '2f1d6aa8c56f'
down_revision = 'fbead75da60d'
branch_labels = None
depends_on = None


# Temporary tables for data migrations between '_code' and '_ref' columns
temp_aa = sql.table('admin_area',
    sa.Column('region_code', sa.VARCHAR(2)),
    sa.Column('region_ref', sa.VARCHAR(2))
)

temp_d = sql.table('district',
    sa.Column('admin_area_code', sa.VARCHAR(3)),
    sa.Column('admin_area_ref', sa.VARCHAR(3))
)

temp_l = sql.table('locality',
    sa.Column('parent_code', sa.VARCHAR(8)),
    sa.Column('parent_ref', sa.VARCHAR(8)),
    sa.Column('district_code', sa.VARCHAR(3)),
    sa.Column('district_ref', sa.VARCHAR(3)),
    sa.Column('admin_area_code', sa.VARCHAR(3)),
    sa.Column('admin_area_ref', sa.VARCHAR(3))
)

temp_ps = sql.table('postcode',
    sa.Column('district_code', sa.VARCHAR(3)),
    sa.Column('district_ref', sa.VARCHAR(3)),
    sa.Column('admin_area_code', sa.VARCHAR(3)),
    sa.Column('admin_area_ref', sa.VARCHAR(3))
)

temp_sa = sql.table('stop_area',
    sa.Column('locality_code', sa.VARCHAR(8)),
    sa.Column('locality_ref', sa.VARCHAR(8)),
    sa.Column('admin_area_code', sa.VARCHAR(3)),
    sa.Column('admin_area_ref', sa.VARCHAR(3))
)

temp_sp = sql.table('stop_point',
    sa.Column('stop_area_code', sa.VARCHAR(12)),
    sa.Column('stop_area_ref', sa.VARCHAR(12)),
    sa.Column('locality_code', sa.VARCHAR(8)),
    sa.Column('locality_ref', sa.VARCHAR(8)),
    sa.Column('admin_area_code', sa.VARCHAR(3)),
    sa.Column('admin_area_ref', sa.VARCHAR(3))
)


def upgrade():
    op.add_column('admin_area', sa.Column('region_ref', sa.VARCHAR(length=2), nullable=True))
    op.create_index(op.f('ix_admin_area_region_ref'), 'admin_area', ['region_ref'], unique=False)
    op.drop_index('ix_admin_area_region_code', table_name='admin_area')
    op.drop_constraint('admin_area_region_code_fkey', 'admin_area', type_='foreignkey')
    op.create_foreign_key('admin_area_region_ref_fkey', 'admin_area', 'region', ['region_ref'], ['code'], ondelete='CASCADE')
    op.execute(sa.update(temp_aa).values(region_ref=temp_aa.c.region_code))
    op.alter_column('admin_area', 'region_ref', existing_type=sa.VARCHAR(length=2), nullable=False)
    op.drop_column('admin_area', 'region_code')

    op.add_column('district', sa.Column('admin_area_ref', sa.VARCHAR(length=3), nullable=True))
    op.create_index(op.f('ix_district_admin_area_ref'), 'district', ['admin_area_ref'], unique=False)
    op.drop_index('ix_district_admin_area_code', table_name='district')
    op.drop_constraint('district_admin_area_code_fkey', 'district', type_='foreignkey')
    op.create_foreign_key('district_admin_area_ref_fkey', 'district', 'admin_area', ['admin_area_ref'], ['code'], ondelete='CASCADE')
    op.execute(sa.update(temp_d).values(admin_area_ref=temp_d.c.admin_area_code))
    op.alter_column('district', 'admin_area_ref', existing_type=sa.VARCHAR(length=3), nullable=False)
    op.drop_column('district', 'admin_area_code')

    op.add_column('locality', sa.Column('admin_area_ref', sa.VARCHAR(length=3), nullable=True))
    op.add_column('locality', sa.Column('district_ref', sa.VARCHAR(length=3), nullable=True))
    op.add_column('locality', sa.Column('parent_ref', sa.VARCHAR(length=8), nullable=True))
    op.create_index(op.f('ix_locality_admin_area_ref'), 'locality', ['admin_area_ref'], unique=False)
    op.create_index(op.f('ix_locality_district_ref'), 'locality', ['district_ref'], unique=False)
    op.create_index(op.f('ix_locality_parent_ref'), 'locality', ['parent_ref'], unique=False)
    op.drop_index('ix_locality_admin_area_code', table_name='locality')
    op.drop_index('ix_locality_district_code', table_name='locality')
    op.drop_index('ix_locality_parent_code', table_name='locality')
    op.drop_constraint('locality_district_code_fkey', 'locality', type_='foreignkey')
    op.drop_constraint('locality_admin_area_code_fkey', 'locality', type_='foreignkey')
    op.create_foreign_key('locality_admin_area_ref_fkey', 'locality', 'admin_area', ['admin_area_ref'], ['code'],
                          ondelete='CASCADE')
    op.create_foreign_key('locality_district_ref_fkey', 'locality', 'district', ['district_ref'], ['code'],
                          ondelete='CASCADE')
    op.execute(sa.update(temp_l).values(
        parent_ref=temp_l.c.parent_code, district_ref=temp_l.c.district_code,
        admin_area_ref=temp_l.c.admin_area_code
    ))
    op.alter_column('locality', 'admin_area_ref', existing_type=sa.VARCHAR(length=3), nullable=False)
    op.drop_column('locality', 'district_code')
    op.drop_column('locality', 'parent_code')
    op.drop_column('locality', 'admin_area_code')

    op.add_column('postcode', sa.Column('admin_area_ref', sa.VARCHAR(length=3), nullable=True))
    op.add_column('postcode', sa.Column('district_ref', sa.VARCHAR(length=3), nullable=True))
    op.create_index(op.f('ix_postcode_admin_area_ref'), 'postcode', ['admin_area_ref'], unique=False)
    op.create_index(op.f('ix_postcode_district_ref'), 'postcode', ['district_ref'], unique=False)
    op.drop_index('ix_postcode_admin_area_code', table_name='postcode')
    op.drop_index('ix_postcode_district_code', table_name='postcode')
    op.drop_constraint('postcode_district_code_fkey', 'postcode', type_='foreignkey')
    op.drop_constraint('postcode_admin_area_code_fkey', 'postcode', type_='foreignkey')
    op.create_foreign_key('postcode_district_ref_fkey', 'postcode', 'district', ['district_ref'], ['code'],
                          ondelete='CASCADE')
    op.create_foreign_key('postcode_admin_area_ref_fkey', 'postcode', 'admin_area', ['admin_area_ref'], ['code'],
                          ondelete='CASCADE')
    op.execute(sa.update(temp_ps).values(
        district_ref=temp_ps.c.district_code, admin_area_ref=temp_ps.c.admin_area_code
    ))
    op.alter_column('postcode', 'admin_area_ref', existing_type=sa.VARCHAR(length=3), nullable=False)
    op.drop_column('postcode', 'district_code')
    op.drop_column('postcode', 'admin_area_code')

    op.add_column('stop_area', sa.Column('admin_area_ref', sa.VARCHAR(length=3), nullable=True))
    op.add_column('stop_area', sa.Column('locality_ref', sa.VARCHAR(length=8), nullable=True))
    op.create_index(op.f('ix_stop_area_admin_area_ref'), 'stop_area', ['admin_area_ref'], unique=False)
    op.create_index(op.f('ix_stop_area_locality_ref'), 'stop_area', ['locality_ref'], unique=False)
    op.drop_index('ix_stop_area_admin_area_code', table_name='stop_area')
    op.drop_index('ix_stop_area_locality_code', table_name='stop_area')
    op.drop_constraint('stop_area_locality_code_fkey', 'stop_area', type_='foreignkey')
    op.drop_constraint('stop_area_admin_area_code_fkey', 'stop_area', type_='foreignkey')
    op.create_foreign_key('stop_area_admin_area_ref_fkey', 'stop_area', 'admin_area', ['admin_area_ref'], ['code'],
                          ondelete='CASCADE')
    op.create_foreign_key('stop_area_locality_ref_fkey', 'stop_area', 'locality', ['locality_ref'], ['code'],
                          ondelete='CASCADE')
    op.execute(sa.update(temp_sa).values(
        locality_ref=temp_sa.c.locality_code, admin_area_ref=temp_sa.c.admin_area_code
    ))
    op.alter_column('stop_area', 'admin_area_ref', existing_type=sa.VARCHAR(length=3), nullable=False)
    op.drop_column('stop_area', 'admin_area_code')
    op.drop_column('stop_area', 'locality_code')

    op.add_column('stop_point', sa.Column('admin_area_ref', sa.VARCHAR(length=3), nullable=True))
    op.add_column('stop_point', sa.Column('locality_ref', sa.VARCHAR(length=8), nullable=True))
    op.add_column('stop_point', sa.Column('stop_area_ref', sa.VARCHAR(length=12), nullable=True))
    op.create_index(op.f('ix_stop_point_admin_area_ref'), 'stop_point', ['admin_area_ref'], unique=False)
    op.create_index(op.f('ix_stop_point_locality_ref'), 'stop_point', ['locality_ref'], unique=False)
    op.create_index(op.f('ix_stop_point_stop_area_ref'), 'stop_point', ['stop_area_ref'], unique=False)
    op.drop_index('ix_stop_point_admin_area_code', table_name='stop_point')
    op.drop_index('ix_stop_point_locality_code', table_name='stop_point')
    op.drop_index('ix_stop_point_stop_area_code', table_name='stop_point')
    op.drop_constraint('stop_point_locality_code_fkey', 'stop_point', type_='foreignkey')
    op.drop_constraint('stop_point_stop_area_code_fkey', 'stop_point', type_='foreignkey')
    op.drop_constraint('stop_point_admin_area_code_fkey', 'stop_point', type_='foreignkey')
    op.create_foreign_key('stop_point_stop_area_ref_fkey', 'stop_point', 'stop_area', ['stop_area_ref'], ['code'],
                          ondelete='CASCADE')
    op.create_foreign_key('stop_point_admin_area_ref_fkey', 'stop_point', 'admin_area', ['admin_area_ref'], ['code'],
                          ondelete='CASCADE')
    op.create_foreign_key('stop_point_locality_ref_fkey', 'stop_point', 'locality', ['locality_ref'], ['code'],
                          ondelete='CASCADE')
    op.execute(sa.update(temp_sp).values(
        stop_area_ref=temp_sp.c.stop_area_code, locality_ref=temp_sp.c.locality_code, 
        admin_area_ref=temp_sp.c.admin_area_code
    ))
    op.alter_column('stop_point', 'locality_ref', existing_type=sa.VARCHAR(length=8), nullable=False)
    op.alter_column('stop_point', 'admin_area_ref', existing_type=sa.VARCHAR(length=3), nullable=False)
    op.drop_column('stop_point', 'admin_area_code')
    op.drop_column('stop_point', 'stop_area_code')
    op.drop_column('stop_point', 'locality_code')


def downgrade():
    op.add_column('stop_point', sa.Column('locality_code', sa.VARCHAR(length=8), autoincrement=False, nullable=True))
    op.add_column('stop_point', sa.Column('stop_area_code', sa.VARCHAR(length=12), autoincrement=False, nullable=True))
    op.add_column('stop_point', sa.Column('admin_area_code', sa.VARCHAR(length=3), autoincrement=False, nullable=True))
    op.drop_constraint('stop_point_admin_area_ref_fkey', 'stop_point', type_='foreignkey')
    op.drop_constraint('stop_point_stop_area_ref_fkey', 'stop_point', type_='foreignkey')
    op.drop_constraint('stop_point_locality_ref_fkey', 'stop_point', type_='foreignkey')
    op.create_foreign_key('stop_point_admin_area_code_fkey', 'stop_point', 'admin_area', ['admin_area_code'], ['code'], ondelete='CASCADE')
    op.create_foreign_key('stop_point_stop_area_code_fkey', 'stop_point', 'stop_area', ['stop_area_code'], ['code'], ondelete='CASCADE')
    op.create_foreign_key('stop_point_locality_code_fkey', 'stop_point', 'locality', ['locality_code'], ['code'], ondelete='CASCADE')
    op.create_index('ix_stop_point_stop_area_code', 'stop_point', ['stop_area_code'], unique=False)
    op.create_index('ix_stop_point_locality_code', 'stop_point', ['locality_code'], unique=False)
    op.create_index('ix_stop_point_admin_area_code', 'stop_point', ['admin_area_code'], unique=False)
    op.drop_index(op.f('ix_stop_point_stop_area_ref'), table_name='stop_point')
    op.drop_index(op.f('ix_stop_point_locality_ref'), table_name='stop_point')
    op.drop_index(op.f('ix_stop_point_admin_area_ref'), table_name='stop_point')
    op.execute(sa.update(temp_sp).values(
        stop_area_code=temp_sp.c.stop_area_ref, locality_code=temp_sp.c.locality_ref,
        admin_area_code=temp_sp.c.admin_area_ref
    ))
    op.alter_column('stop_point', 'locality_code', existing_type=sa.VARCHAR(length=8), nullable=False)
    op.alter_column('stop_point', 'admin_area_code', existing_type=sa.VARCHAR(length=3), nullable=False)
    op.drop_column('stop_point', 'stop_area_ref')
    op.drop_column('stop_point', 'locality_ref')
    op.drop_column('stop_point', 'admin_area_ref')

    op.add_column('stop_area', sa.Column('locality_code', sa.VARCHAR(length=8), autoincrement=False, nullable=True))
    op.add_column('stop_area', sa.Column('admin_area_code', sa.VARCHAR(length=3), autoincrement=False, nullable=True))
    op.drop_constraint('stop_area_admin_area_ref_fkey', 'stop_area', type_='foreignkey')
    op.drop_constraint('stop_area_locality_ref_fkey', 'stop_area', type_='foreignkey')
    op.create_foreign_key('stop_area_admin_area_code_fkey', 'stop_area', 'admin_area', ['admin_area_code'], ['code'], ondelete='CASCADE')
    op.create_foreign_key('stop_area_locality_code_fkey', 'stop_area', 'locality', ['locality_code'], ['code'], ondelete='CASCADE')
    op.create_index('ix_stop_area_locality_code', 'stop_area', ['locality_code'], unique=False)
    op.create_index('ix_stop_area_admin_area_code', 'stop_area', ['admin_area_code'], unique=False)
    op.drop_index(op.f('ix_stop_area_locality_ref'), table_name='stop_area')
    op.drop_index(op.f('ix_stop_area_admin_area_ref'), table_name='stop_area')
    op.execute(sa.update(temp_sa).values(
        locality_code=temp_sa.c.locality_ref, admin_area_code=temp_sa.c.admin_area_ref
    ))
    op.alter_column('stop_area', 'admin_area_code', existing_type=sa.VARCHAR(length=3), nullable=False)
    op.drop_column('stop_area', 'locality_ref')
    op.drop_column('stop_area', 'admin_area_ref')

    op.add_column('postcode', sa.Column('admin_area_code', sa.VARCHAR(length=3), autoincrement=False, nullable=True))
    op.add_column('postcode', sa.Column('district_code', sa.VARCHAR(length=3), autoincrement=False, nullable=True))
    op.drop_constraint('postcode_district_ref_fkey', 'postcode', type_='foreignkey')
    op.drop_constraint('postcode_admin_area_ref_fkey', 'postcode', type_='foreignkey')
    op.create_foreign_key('postcode_admin_area_code_fkey', 'postcode', 'admin_area', ['admin_area_code'], ['code'], ondelete='CASCADE')
    op.create_foreign_key('postcode_district_code_fkey', 'postcode', 'district', ['district_code'], ['code'], ondelete='CASCADE')
    op.create_index('ix_postcode_district_code', 'postcode', ['district_code'], unique=False)
    op.create_index('ix_postcode_admin_area_code', 'postcode', ['admin_area_code'], unique=False)
    op.drop_index(op.f('ix_postcode_district_ref'), table_name='postcode')
    op.drop_index(op.f('ix_postcode_admin_area_ref'), table_name='postcode')
    op.execute(sa.update(temp_ps).values(
        district_code=temp_ps.c.district_ref, admin_area_code=temp_ps.c.admin_area_ref
    ))
    op.alter_column('postcode', 'admin_area_code', existing_type=sa.VARCHAR(length=3), nullable=False)
    op.drop_column('postcode', 'district_ref')
    op.drop_column('postcode', 'admin_area_ref')

    op.add_column('locality', sa.Column('admin_area_code', sa.VARCHAR(length=3), autoincrement=False, nullable=True))
    op.add_column('locality', sa.Column('parent_code', sa.VARCHAR(length=8), autoincrement=False, nullable=True))
    op.add_column('locality', sa.Column('district_code', sa.VARCHAR(length=3), autoincrement=False, nullable=True))
    op.drop_constraint('locality_district_ref_fkey', 'locality', type_='foreignkey')
    op.drop_constraint('locality_admin_area_ref_fkey', 'locality', type_='foreignkey')
    op.create_foreign_key('locality_admin_area_code_fkey', 'locality', 'admin_area', ['admin_area_code'], ['code'], ondelete='CASCADE')
    op.create_foreign_key('locality_district_code_fkey', 'locality', 'district', ['district_code'], ['code'], ondelete='CASCADE')
    op.create_index('ix_locality_parent_code', 'locality', ['parent_code'], unique=False)
    op.create_index('ix_locality_district_code', 'locality', ['district_code'], unique=False)
    op.create_index('ix_locality_admin_area_code', 'locality', ['admin_area_code'], unique=False)
    op.drop_index(op.f('ix_locality_parent_ref'), table_name='locality')
    op.drop_index(op.f('ix_locality_district_ref'), table_name='locality')
    op.drop_index(op.f('ix_locality_admin_area_ref'), table_name='locality')
    op.execute(sa.update(temp_l).values(
        parent_code=temp_l.c.parent_ref, district_code=temp_l.c.district_ref,
        admin_area_code=temp_l.c.admin_area_ref
    ))
    op.alter_column('locality', 'admin_area_code', existing_type=sa.VARCHAR(length=3), nullable=False)
    op.drop_column('locality', 'parent_ref')
    op.drop_column('locality', 'district_ref')
    op.drop_column('locality', 'admin_area_ref')

    op.add_column('district', sa.Column('admin_area_code', sa.VARCHAR(length=3), autoincrement=False, nullable=True))
    op.drop_constraint('district_admin_area_ref_fkey', 'district', type_='foreignkey')
    op.create_foreign_key('district_admin_area_code_fkey', 'district', 'admin_area', ['admin_area_code'], ['code'], ondelete='CASCADE')
    op.create_index('ix_district_admin_area_code', 'district', ['admin_area_code'], unique=False)
    op.drop_index(op.f('ix_district_admin_area_ref'), table_name='district')
    op.execute(sa.update(temp_d).values(admin_area_code=temp_d.c.admin_area_ref))
    op.alter_column('district', 'admin_area_code', existing_type=sa.VARCHAR(length=3), nullable=False)
    op.drop_column('district', 'admin_area_ref')

    op.add_column('admin_area', sa.Column('region_code', sa.VARCHAR(length=2), autoincrement=False, nullable=True))
    op.drop_constraint('admin_area_region_ref_fkey', 'admin_area', type_='foreignkey')
    op.create_foreign_key('admin_area_region_code_fkey', 'admin_area', 'region', ['region_code'], ['code'], ondelete='CASCADE')
    op.create_index('ix_admin_area_region_code', 'admin_area', ['region_code'], unique=False)
    op.drop_index(op.f('ix_admin_area_region_ref'), table_name='admin_area')
    op.execute(sa.update(temp_aa).values(region_code=temp_aa.c.region_ref))
    op.alter_column('admin_area', 'region_code', existing_type=sa.VARCHAR(length=2), nullable=False)
    op.drop_column('admin_area', 'region_ref')
