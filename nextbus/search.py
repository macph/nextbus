"""
Search functions for the nextbus package.
"""
import re
from nextbus import db
from nextbus import models

STOPS_LIMIT = 512
RESULT_COLUMNS = ['table_name', 'code', 'name', 'indicator', 'street',
                  'locality_name', 'district_name', 'admin_area',
                  'admin_area_name']


class PostcodeException(Exception):
    """ Raised if a postcode was identified but it doesn't exist. """
    def __init__(self, query, postcode):
        super(PostcodeException, self).__init__()
        self.query = query
        self.postcode = postcode

    def __str__(self):
        return ("Postcode '%s' from query %r does not exist."
                % (self.postcode, self.query))


def search_code(query):
    """ Queries stop points and postcodes to find an exact match, returning
        the model object, or False if no match is found.
    """
    regex_postcode = re.compile(r"^\s*([A-Za-z]{1,2}\d{1,2}[A-Za-z]?)"
                                r"\s*(\d[A-Za-z]{2})\s*$")
    postcode = regex_postcode.match(query)
    if postcode:
        # Search postcode; make all upper and remove spaces first
        outward, inward = postcode.group(1), postcode.group(2)
        q_psc = models.Postcode.query.filter(
            models.Postcode.index == (outward + inward).upper()
        ).one_or_none()
        if q_psc is not None:
            return q_psc
        else:
            raise PostcodeException(query, (outward + ' ' + inward).upper())

    # Search NaPTAN code & ATCO code first
    q_stop = models.StopPoint.query.filter(
        db.or_(models.StopPoint.naptan_code == query.lower(),
               models.StopPoint.atco_code == query.upper())
    ).one_or_none()
    if q_stop is not None:
        return q_stop

    # Neither a stop nor a postcode was found
    return False


def table_name_literal(model, name=None):
    """ Helper function to create column with name of table. Adds column
        name if one is specified.
    """
    col = db.literal_column("'%s'" % model.__tablename__)
    return col.label(name) if name else col


def _empty_col(column_name):
    """ Helper function to create a column with empty text and a label. """
    return db.literal_column("''").label(column_name)


def _fts_search_exists(tsquery):
    """ Does a PostgreSQL FTS search to check if matching entries exist. """
    admin_area = (
        db.session.query(
            models.AdminArea.code
        ).filter(db.func.to_tsvector('english', models.AdminArea.name)
                 .match(tsquery, postgresql_regconfig='english'))
    )
    district = (
        db.session.query(
            models.District.code
        ).filter(db.func.to_tsvector('english', models.District.name)
                 .match(tsquery, postgresql_regconfig='english'))
    )
    locality = (
        db.session.query(
            models.Locality.code
        ).outerjoin(models.Locality.stop_points)
        .filter(db.func.to_tsvector('english', models.Locality.name)
                .match(tsquery, postgresql_regconfig='english'),
                models.StopPoint.atco_code.isnot(None))
    )
    stop_area = (
        db.session.query(
            models.StopArea.code
        ).filter(db.func.to_tsvector('english', models.StopArea.name)
                 .match(tsquery, postgresql_regconfig='english'))
    )
    stop = (
        db.session.query(
            models.StopPoint.atco_code
        ).filter(
            db.or_(
                db.func.to_tsvector('english', models.StopPoint.name)
                .match(tsquery, postgresql_regconfig='english'),
                db.func.to_tsvector('english', models.StopPoint.street)
                .match(tsquery, postgresql_regconfig='english')
            )
        )
    )

    return admin_area.union_all(district, locality, stop_area, stop).all()


def _fts_location_search_exists(tsquery_name, tsquery_location):
    """ Does a PostgreSQL FTS search on both names of stops/places and the
        areas they are located in to check if matching entries exist.
    """
    # Admin area not needed
    district = (
        db.session.query(
            models.District.code
        ).select_from(models.District)
        .join(models.AdminArea,
              models.AdminArea.code == models.District.admin_area_code)
        .filter(db.func.to_tsvector('english', models.District.name)
                .match(tsquery_name, postgresql_regconfig='english'),
                db.func.to_tsvector('english', models.AdminArea.name)
                .match(tsquery_location, postgresql_regconfig='english'))
    )
    locality = (
        db.session.query(
            models.Locality.code
        ).select_from(models.Locality)
        .outerjoin(models.Locality.stop_points)
        .outerjoin(models.District,
                   models.District.code == models.Locality.district_code)
        .join(models.AdminArea,
              models.AdminArea.code == models.Locality.admin_area_code)
        .filter(
            db.func.to_tsvector('english', models.Locality.name)
            .match(tsquery_name, postgresql_regconfig='english'),
            models.StopPoint.atco_code.isnot(None),
            db.or_(
                db.func.to_tsvector('english', models.District.name)
                .match(tsquery_location, postgresql_regconfig='english'),
                db.func.to_tsvector('english', models.AdminArea.name)
                .match(tsquery_location, postgresql_regconfig='english')
            )
        )
    )
    stop_area = (
        db.session.query(
            models.StopArea.code
        ).select_from(models.StopArea)
        .outerjoin(models.Locality,
                   models.Locality.code == models.StopArea.locality_code)
        .outerjoin(models.District,
                   models.District.code == models.Locality.district_code)
        .join(models.AdminArea,
              models.AdminArea.code == models.StopArea.admin_area_code)
        .filter(
            db.func.to_tsvector('english', models.StopArea.name)
            .match(tsquery_name, postgresql_regconfig='english'),
            db.or_(
                db.func.to_tsvector('english', models.Locality.name)
                .match(tsquery_location, postgresql_regconfig='english'),
                db.func.to_tsvector('english', models.District.name)
                .match(tsquery_location, postgresql_regconfig='english'),
                db.func.to_tsvector('english', models.AdminArea.name)
                .match(tsquery_location, postgresql_regconfig='english')
            )
        )
    )
    stop = (
        db.session.query(
            models.StopPoint.atco_code
        ).select_from(models.StopPoint)
        .join(models.Locality,
              models.Locality.code == models.StopPoint.locality_code)
        .outerjoin(models.District,
                   models.District.code == models.Locality.district_code)
        .join(models.AdminArea,
              models.AdminArea.code == models.StopPoint.admin_area_code)
        .filter(
            db.or_(
                db.func.to_tsvector('english', models.StopPoint.name)
                .match(tsquery_name, postgresql_regconfig='english'),
                db.func.to_tsvector('english', models.StopPoint.street)
                .match(tsquery_name, postgresql_regconfig='english')
            ),
            db.or_(
                db.func.to_tsvector('english', models.Locality.name)
                .match(tsquery_location, postgresql_regconfig='english'),
                db.func.to_tsvector('english', models.District.name)
                .match(tsquery_location, postgresql_regconfig='english'),
                db.func.to_tsvector('english', models.AdminArea.name)
                .match(tsquery_location, postgresql_regconfig='english')
            )
        )
    )

    return district.union_all(locality, stop_area, stop).all()


def _fts_search_all(tsquery):
    """ Does a PostgreSQL FTS search to find all stops and places matching
        query, returning table with specific columns.
    """
    empty_query = db.session.query(
        *tuple(_empty_col(c) for c in RESULT_COLUMNS)
    ).filter(db.false())

    admin_area = (
        db.session.query(
            table_name_literal(models.AdminArea),
            models.AdminArea.code,
            models.AdminArea.name,
            _empty_col('indicator'),
            _empty_col('street'),
            _empty_col('locality_name'),
            _empty_col('district_name'),
            models.AdminArea.code.label('admin_area'),
            models.AdminArea.name.label('admin_area_name')
        ).filter(db.func.to_tsvector('english', models.AdminArea.name)
                 .match(tsquery, postgresql_regconfig='english'))
    )
    district = (
        db.session.query(
            table_name_literal(models.District),
            models.District.code,
            models.District.name,
            _empty_col('indicator'),
            _empty_col('street'),
            _empty_col('locality_name'),
            _empty_col('district_name'),
            models.AdminArea.code.label('admin_area'),
            models.AdminArea.name.label('admin_area_name')
        ).select_from(models.District)
        .join(models.AdminArea,
              models.AdminArea.code == models.District.admin_area_code)
        .filter(db.func.to_tsvector('english', models.District.name)
                .match(tsquery, postgresql_regconfig='english'))
    )
    sub_locality = (
        db.session.query(
            models.Locality.code,
            models.Locality.name,
            models.Locality.district_code,
            models.Locality.admin_area_code
        ).outerjoin(models.Locality.stop_points)
        .group_by(models.Locality.code)
        .filter(db.func.to_tsvector('english', models.Locality.name)
                .match(tsquery, postgresql_regconfig='english'),
                models.StopPoint.atco_code.isnot(None))
    ).subquery()
    locality = (
        db.session.query(
            table_name_literal(models.Locality),
            sub_locality.c.code,
            sub_locality.c.name,
            _empty_col('indicator'),
            _empty_col('street'),
            _empty_col('locality_name'),
            db.func.coalesce(models.District.name.label('district_name'), ''),
            models.AdminArea.code.label('admin_area'),
            models.AdminArea.name.label('admin_area_name')
        ).select_from(sub_locality)
        .outerjoin(models.District,
                   models.District.code == sub_locality.c.district_code)
        .join(models.AdminArea,
              models.AdminArea.code == sub_locality.c.admin_area_code)
    )
    # Subquery required to count number of stops in stop area and group by stop
    # area code before joining with locality and admin area
    sub_stop_area = (
        db.session.query(
            models.StopArea.code.label('code'),
            models.StopArea.name.label('name'),
            models.StopArea.locality_code.label('locality_code'),
            models.StopArea.admin_area_code.label('admin_area_code'),
            db.cast(db.func.count(models.StopArea.code), db.Text).label('ind'),
        ).join(models.StopArea.stop_points)
        .group_by(models.StopArea.code)
        .filter(db.func.to_tsvector('english', models.StopArea.name)
                .match(tsquery, postgresql_regconfig='english'))
    ).subquery()
    stop_area = (
        db.session.query(
            table_name_literal(models.StopArea),
            sub_stop_area.c.code,
            sub_stop_area.c.name,
            sub_stop_area.c.ind,
            _empty_col('street'),
            db.func.coalesce(models.Locality.name.label('locality_name'), ''),
            db.func.coalesce(models.District.name.label('district_name'), ''),
            models.AdminArea.code.label('admin_area'),
            models.AdminArea.name.label('admin_area_name')
        ).select_from(sub_stop_area)
        .outerjoin(models.Locality,
                   models.Locality.code == sub_stop_area.c.locality_code)
        .outerjoin(models.District,
                   models.District.code == models.Locality.district_code)
        .join(models.AdminArea,
              models.AdminArea.code == sub_stop_area.c.admin_area_code)
    )
    stop = (
        db.session.query(
            table_name_literal(models.StopPoint),
            models.StopPoint.atco_code,
            models.StopPoint.name,
            models.StopPoint.short_ind,
            models.StopPoint.street,
            models.Locality.name.label('locality_name'),
            db.func.coalesce(models.District.name.label('district_name'), ''),
            models.AdminArea.code.label('admin_area'),
            models.AdminArea.name.label('admin_area_name')
        ).select_from(models.StopPoint)
        .outerjoin(models.StopArea,
                   models.StopArea.code == models.StopPoint.stop_area_code)
        .join(models.Locality,
              models.Locality.code == models.StopPoint.locality_code)
        .outerjoin(models.District,
                   models.District.code == models.Locality.district_code)
        .join(models.AdminArea,
              models.AdminArea.code == models.Locality.admin_area_code)
        # Include stops with name or street matching query but exclude these
        # within areas that have already been found - prevent duplicates
        .filter(
            db.or_(
                db.func.to_tsvector('english', models.StopPoint.name)
                .match(tsquery, postgresql_regconfig='english'),
                db.func.to_tsvector('english', models.StopPoint.street)
                .match(tsquery, postgresql_regconfig='english')
            ),
            db.not_(
                db.and_(
                    models.StopPoint.stop_area_code.isnot(None),
                    db.func.to_tsvector('english', models.StopArea.name)
                    .match(tsquery, postgresql_regconfig='english')
                )
            )
        )
    )

    return empty_query.union_all(admin_area, district, locality, stop_area,
                                 stop).all()


def _fts_location_search_all(tsquery_name, tsquery_location):
    """ Does a PostgreSQL FTS search to find all stops and places matching
        query, returning table with specific columns.
    """
    empty_query = db.session.query(
        *tuple(_empty_col(c) for c in RESULT_COLUMNS)
    ).filter(db.false())
    # Admin area not needed
    district = (
        db.session.query(
            table_name_literal(models.District),
            models.District.code,
            models.District.name,
            _empty_col('indicator'),
            _empty_col('street'),
            _empty_col('locality_name'),
            _empty_col('district_name'),
            models.AdminArea.code.label('admin_area'),
            models.AdminArea.name.label('admin_area_name')
        ).select_from(models.District)
        .join(models.AdminArea,
              models.AdminArea.code == models.District.admin_area_code)
        .filter(db.func.to_tsvector('english', models.District.name)
                .match(tsquery_name, postgresql_regconfig='english'),
                db.func.to_tsvector('english', models.AdminArea.name)
                .match(tsquery_location, postgresql_regconfig='english'))
    )
    sub_locality = (
        db.session.query(
            models.Locality.code,
            models.Locality.name,
            models.Locality.district_code,
            models.Locality.admin_area_code
        ).outerjoin(models.Locality.stop_points)
        .group_by(models.Locality.code)
        .filter(db.func.to_tsvector('english', models.Locality.name)
                .match(tsquery_name, postgresql_regconfig='english'),
                models.StopPoint.atco_code.isnot(None))
    ).subquery()
    locality = (
        db.session.query(
            table_name_literal(models.Locality),
            sub_locality.c.code,
            sub_locality.c.name,
            _empty_col('indicator'),
            _empty_col('street'),
            _empty_col('locality_name'),
            db.func.coalesce(models.District.name.label('district_name'), ''),
            models.AdminArea.code.label('admin_area'),
            models.AdminArea.name.label('admin_area_name')
        ).select_from(sub_locality)
        .outerjoin(models.District,
                   models.District.code == sub_locality.c.district_code)
        .join(models.AdminArea,
              models.AdminArea.code == sub_locality.c.admin_area_code)
        .filter(db.or_(
            db.func.to_tsvector('english', models.District.name)
            .match(tsquery_location, postgresql_regconfig='english'),
            db.func.to_tsvector('english', models.AdminArea.name)
            .match(tsquery_location, postgresql_regconfig='english')
        ))
    )
    # Subquery required to count number of stops in stop area and group by stop
    # area code before joining with locality and admin area
    sub_stop_area = (
        db.session.query(
            models.StopArea.code.label('code'),
            models.StopArea.name.label('name'),
            models.StopArea.locality_code.label('locality_code'),
            models.StopArea.admin_area_code.label('admin_area_code'),
            db.cast(db.func.count(models.StopArea.code), db.Text).label('ind'),
        ).join(models.StopArea.stop_points)
        .group_by(models.StopArea.code)
        .filter(db.func.to_tsvector('english', models.StopArea.name)
                .match(tsquery_name, postgresql_regconfig='english'))
    ).subquery()
    stop_area = (
        db.session.query(
            table_name_literal(models.StopArea),
            sub_stop_area.c.code,
            sub_stop_area.c.name,
            sub_stop_area.c.ind,
            _empty_col('street'),
            db.func.coalesce(models.Locality.name.label('locality_name'), ''),
            db.func.coalesce(models.District.name.label('district_name'), ''),
            models.AdminArea.code.label('admin_area'),
            models.AdminArea.name.label('admin_area_name')
        ).select_from(sub_stop_area)
        .outerjoin(models.Locality,
                   models.Locality.code == sub_stop_area.c.locality_code)
        .outerjoin(models.District,
                   models.District.code == models.Locality.district_code)
        .join(models.AdminArea,
              models.AdminArea.code == sub_stop_area.c.admin_area_code)
        .filter(db.or_(
            db.func.to_tsvector('english', models.Locality.name)
            .match(tsquery_location, postgresql_regconfig='english'),
            db.func.to_tsvector('english', models.District.name)
            .match(tsquery_location, postgresql_regconfig='english'),
            db.func.to_tsvector('english', models.AdminArea.name)
            .match(tsquery_location, postgresql_regconfig='english')
        ))
    )
    stop = (
        db.session.query(
            table_name_literal(models.StopPoint),
            models.StopPoint.atco_code,
            models.StopPoint.name,
            models.StopPoint.short_ind,
            models.StopPoint.street,
            models.Locality.name.label('locality_name'),
            db.func.coalesce(models.District.name.label('district_name'), ''),
            models.AdminArea.code.label('admin_area'),
            models.AdminArea.name.label('admin_area_name')
        ).select_from(models.StopPoint)
        .outerjoin(models.StopArea,
                   models.StopArea.code == models.StopPoint.stop_area_code)
        .join(models.Locality,
              models.Locality.code == models.StopPoint.locality_code)
        .outerjoin(models.District,
                   models.District.code == models.Locality.district_code)
        .join(models.AdminArea,
              models.AdminArea.code == models.Locality.admin_area_code)
        # Include stops with name or street matching query but exclude these
        # within areas that have already been found - prevent duplicates
        .filter(
            db.or_(
                db.func.to_tsvector('english', models.StopPoint.name)
                .match(tsquery_name, postgresql_regconfig='english'),
                db.func.to_tsvector('english', models.StopPoint.street)
                .match(tsquery_name, postgresql_regconfig='english')
            ),
            db.not_(
                db.and_(
                    models.StopPoint.stop_area_code.isnot(None),
                    db.func.to_tsvector('english', models.StopArea.name)
                    .match(tsquery_name, postgresql_regconfig='english')
                )
            ),
            db.or_(
                db.func.to_tsvector('english', models.Locality.name)
                .match(tsquery_location, postgresql_regconfig='english'),
                db.func.to_tsvector('english', models.District.name)
                .match(tsquery_location, postgresql_regconfig='english'),
                db.func.to_tsvector('english', models.AdminArea.name)
                .match(tsquery_location, postgresql_regconfig='english')
            )
        )
    )

    return empty_query.union_all(district, locality, stop_area, stop).all()


def search_exists(query, parser=None, raise_exception=True):
    """ Searches for stop, postcodes and places that do exist, without
        information on areas, before redirecting to a search results page with
        the full data.

        :param parser: Parser to use when searching for all results with
        PostgreSQL's full text search.
        :param raise_exception: Set to raise an exception when too many results
        are returned.
    """
    if not ''.join(query.split()):
        raise ValueError("No suitable query was entered.")

    # Search stop points and postcodes for an exact match
    object_match = search_code(query)
    if object_match:
        return object_match

    # Else: do a full text search - format query string first
    result = parser(query) if parser else query
    # If the 'at' operator is used, a tuple is returned
    if isinstance(result, tuple):
        s_query, l_query = result
        results = _fts_location_search_exists(s_query, l_query)
    else:
        s_query = result
        results = _fts_search_exists(s_query)

    return results


def search_full(query, parser=None, raise_exception=True):
    """ Searches for stops, postcodes and places, returning full data including
        area information.

        :param parser: Parser to use when searching for all results with
        PostgreSQL's full text search.
        :param raise_exception: Set to raise an exception when too many results
        are returned.
    """
    if not ''.join(query.split()):
        raise ValueError("No suitable query was entered.")

    # Search stop points and postcodes for an exact match
    obj = search_code(query)
    if obj:
        return obj

    # Else: do a full text search - format query string first
    result = parser(query) if parser else query
    # If the 'at' operator is used, a tuple is returned but we only need to
    # find the names of stops or places
    if isinstance(result, tuple):
        s_query, l_query = result
        results = _fts_location_search_all(s_query, l_query)
    else:
        s_query = result
        results = _fts_search_all(s_query)

    return results
