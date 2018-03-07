"""
Update tsvector column values after populating databases for full text search.
"""
import functools

from nextbus import db, models
from nextbus.populate import database_session, logger


def _concat_tsvector(*columns):
    """ Helper function to create an expression from concatenating TSVector
        values with weights.

        Each argument is a tuple of length 2, for each column and weight.
    """
    tsv = []
    try:
        for col, weight in columns:
            if weight is None:
                tsv.append(db.func.to_tsvector("english", col))
            elif weight in "ABCD":
                tsv.append(db.func.setweight(
                    db.func.to_tsvector("english", col), weight
                ))
            else:
                raise ValueError("Weight for a TSVector must be a letter A-D.")
    except TypeError as err:
        raise TypeError("Each argument must be a tuple of length 2.") from err

    # 'col1.concat(col2)' in SQLAlchemy translates to col1 || col2 in SQL
    sql_concat = lambda a, b: a.concat(b)

    return functools.reduce(sql_concat, tsv)


def update_nptg_tsvector():
    """ Update the TSVector columns for regions, areas, districts and
        localities.

        District and admin area names are weighted equally.
    """
    region_tsv = db.session.query(
        models.Region.code,
        _concat_tsvector((models.Region.name, "A")).label("tsv_name")
    ).subquery()

    admin_area_tsv = db.session.query(
        models.AdminArea.code,
        _concat_tsvector((models.AdminArea.name, None)).label("tsv_name")
    ).subquery()

    district_tsv = (
        db.session.query(
            models.District.code,
            _concat_tsvector((models.District.name, "A"),
                             (models.AdminArea.name, "B")).label("tsv_name")
        ).select_from(models.District)
        .join(models.AdminArea,
              models.AdminArea.code == models.District.admin_area_ref)
    ).subquery()

    locality_tsv = (
        db.session.query(
            models.Locality.code,
            _concat_tsvector((models.Locality.name, "A"),
                             (db.func.coalesce(models.District.name, ""), "B"),
                             (models.AdminArea.name, "B")).label("tsv_name")
        ).select_from(models.Locality)
        .outerjoin(models.District,
                   models.District.code == models.Locality.district_ref)
        .join(models.AdminArea,
              models.AdminArea.code == models.Locality.admin_area_ref)
    ).subquery()

    region = models.Region.__table__
    admin_area = models.AdminArea.__table__
    district = models.District.__table__
    locality = models.Locality.__table__

    with database_session():
        logger.info("Updating NPTG TSVector columns for full text search")
        db.session.execute(region.update()
                           .values(tsv_name=region_tsv.c.tsv_name)
                           .where(region_tsv.c.code == region.c.code))
        db.session.execute(admin_area.update()
                           .values(tsv_name=admin_area_tsv.c.tsv_name)
                           .where(admin_area_tsv.c.code == admin_area.c.code))
        db.session.execute(district.update()
                           .values(tsv_name=district_tsv.c.tsv_name)
                           .where(district_tsv.c.code == district.c.code))
        db.session.execute(locality.update()
                           .values(tsv_name=locality_tsv.c.tsv_name)
                           .where(locality_tsv.c.code == locality.c.code))


def update_naptan_tsvector():
    """ Update the TSVector columns for stop points and stop areas with names
        from their localities, districts and admin areas.

        Localities, districts and admin areas are weighted equally for both
        stop areas and stop points so they are ordered properly in search
        results.
    """
    stop_area = models.StopArea.__table__
    stop_point = models.StopPoint.__table__

    stop_area_tsv = (
        db.session.query(
            models.StopArea.code,
            _concat_tsvector((models.StopArea.name, "A"),
                             (db.func.coalesce(models.Locality.name, ""), "C"),
                             (db.func.coalesce(models.District.name, ""), "D"),
                             (models.AdminArea.name, "D")).label("tsv_name")
        ).select_from(models.StopArea)
        .outerjoin(models.Locality,
                   models.Locality.code == models.StopArea.locality_ref)
        .outerjoin(models.District,
                   models.District.code == models.Locality.district_ref)
        .join(models.AdminArea,
              models.AdminArea.code == models.StopArea.admin_area_ref)
    ).subquery()

    # Need 3 TSVector columns: one for name, one for street, one for both such
    # that a search query with a NOT operator will not exclude results from
    # both columns.
    # If name and streets are equal, the 'tsv_both' column will be null.
    stop_point_tsv = (
        db.session.query(
            models.StopPoint.atco_code,
            db.case(
                [(models.StopPoint.name == models.StopPoint.street, None)],
                else_=_concat_tsvector((models.StopPoint.name, "A"),
                                       (models.StopPoint.street, "B"),
                                       (models.Locality.name, "C"),
                                       (db.func.coalesce(models.District.name,
                                                         ""), "D"),
                                       (models.AdminArea.name, "D"))
            ).label("tsv_both"),
            _concat_tsvector((models.StopPoint.name, "A"),
                             (models.Locality.name, "C"),
                             (db.func.coalesce(models.District.name, ""), "D"),
                             (models.AdminArea.name, "D")).label("tsv_name"),
            _concat_tsvector((models.StopPoint.street, "B"),
                             (models.Locality.name, "C"),
                             (db.func.coalesce(models.District.name, ""), "D"),
                             (models.AdminArea.name, "D")).label("tsv_street")
        ).select_from(models.StopPoint)
        .join(models.Locality,
              models.Locality.code == models.StopPoint.locality_ref)
        .outerjoin(models.District,
                   models.District.code == models.Locality.district_ref)
        .join(models.AdminArea,
              models.AdminArea.code == models.StopPoint.admin_area_ref)
    ).subquery()

    with database_session():
        logger.info("Updating NaPTAN TSVector columns for full text search")
        db.session.execute(stop_area.update()
                           .values(tsv_name=stop_area_tsv.c.tsv_name)
                           .where(stop_area_tsv.c.code == stop_area.c.code))
        db.session.execute(stop_point.update()
                           .values(tsv_both=stop_point_tsv.c.tsv_both,
                                   tsv_name=stop_point_tsv.c.tsv_name,
                                   tsv_street=stop_point_tsv.c.tsv_street)
                           .where(stop_point_tsv.c.atco_code
                                  == stop_point.c.atco_code))
