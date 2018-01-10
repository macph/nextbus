"""
Search functions for the nextbus package.
"""
import re
from nextbus import db
from nextbus import models

SEARCH_LIMIT = 2048


class PostcodeException(Exception):
    """ Raised if a postcode was identified but it doesn't exist. """
    def __init__(self, query, postcode):
        super(PostcodeException, self).__init__()
        self.query = query
        self.postcode = postcode

    def __str__(self):
        return ("Postcode '%s' from query %r does not exist."
                % (self.postcode, self.query))


class LimitException(Exception):
    """ Raised if a search query returns too many results """
    def __init__(self, query, count):
        super(LimitException, self).__init__()
        self.query = query
        self.count = count

    def __str__(self):
        return ("Search result %r returned too many results (%d)"
                % (self.query, self.count))


def _check_code(query):
    """ Queries stop points and postcodes to find an exact match, returning
        the model object, or None if no match is found.
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


def _table_col(model):
    """ Helper function to create column with name of table. """
    return db.literal_column("'%s'" % model.__tablename__)


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
    object_match = _check_code(query)
    if object_match:
        return object_match

    # Else: do a full text search - format query string first
    s_query = parser(query) if parser else query

    admin_area = (
        db.session.query(
            models.AdminArea.code.label('code')
        ).filter(db.func.to_tsvector('english', models.AdminArea.name)
                 .match(s_query, postgresql_regconfig='english'))
    )
    district = (
        db.session.query(
            models.District.code.label('code')
        ).filter(db.func.to_tsvector('english', models.District.name)
                 .match(s_query, postgresql_regconfig='english'))
    )
    locality = (
        db.session.query(
            models.Locality.code.label('code')
        ).outerjoin(models.Locality.stop_points)
        .filter(db.func.to_tsvector('english', models.Locality.name)
                .match(s_query, postgresql_regconfig='english'),
                models.StopPoint.atco_code.isnot(None))
    )
    stop_area = (
        db.session.query(
            models.StopArea.code.label('code')
        ).filter(db.func.to_tsvector('english', models.StopArea.name)
                 .match(s_query, postgresql_regconfig='english'))
    )
    stop = (
        db.session.query(
            models.StopPoint.atco_code.label('code')
        ).filter(
            db.or_(
                db.func.to_tsvector('english', models.StopPoint.name)
                .match(s_query, postgresql_regconfig='english'),
                db.func.to_tsvector('english', models.StopPoint.street)
                .match(s_query, postgresql_regconfig='english')
            )
        )
    )
    search = admin_area.union_all(district, locality, stop_area, stop)

    results = search.all()
    if raise_exception and len(results) > SEARCH_LIMIT:
        raise LimitException(s_query, len(results))

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
    obj = _check_code(query)
    if obj:
        return obj

    # Else: do a full text search - format query string first
    s_query = parser(query) if parser else query
    empty_col = db.literal_column("''")

    admin_area = (
        db.session.query(
            _table_col(models.AdminArea).label('table_name'),
            models.AdminArea.code.label('code'),
            models.AdminArea.name.label('name'),
            empty_col.label('indicator'),
            empty_col.label('street'),
            empty_col.label('locality_name'),
            models.AdminArea.code.label('admin_area'),
            models.AdminArea.name.label('admin_area_name')
        ).filter(db.func.to_tsvector('english', models.AdminArea.name)
                 .match(s_query, postgresql_regconfig='english'))
    )
    district = (
        db.session.query(
            _table_col(models.District).label('table_name'),
            models.District.code.label('code'),
            models.District.name.label('name'),
            empty_col.label('indicator'),
            empty_col.label('street'),
            empty_col.label('locality_name'),
            models.AdminArea.code.label('admin_area'),
            models.AdminArea.name.label('admin_area_name')
        ).select_from(models.District)
        .join(models.AdminArea,
              models.AdminArea.code == models.District.admin_area_code)
        .filter(db.func.to_tsvector('english', models.District.name)
                .match(s_query, postgresql_regconfig='english'))
    )
    sub_locality = (
        db.session.query(
            models.Locality.code,
            models.Locality.name,
            models.Locality.admin_area_code
        ).outerjoin(models.Locality.stop_points)
        .group_by(models.Locality.code)
        .filter(db.func.to_tsvector('english', models.Locality.name)
                .match(s_query, postgresql_regconfig='english'),
                models.StopPoint.atco_code.isnot(None))
    ).subquery()
    locality = (
        db.session.query(
            _table_col(models.Locality).label('table_name'),
            sub_locality.c.code.label('code'),
            sub_locality.c.name.label('name'),
            empty_col.label('indicator'),
            empty_col.label('street'),
            empty_col.label('locality_name'),
            models.AdminArea.code.label('admin_area'),
            models.AdminArea.name.label('admin_area_name')
        ).select_from(sub_locality)
        .join(models.AdminArea,
              models.AdminArea.code == sub_locality.c.admin_area_code)
    )
    # Subquery required to count number of stops in stop area and group by stop
    # area code before joining with locality and admin area
    sub_stop_area = (
        db.session.query(
            models.StopArea.code.label('code'),
            models.StopArea.name.label('name'),
            models.StopArea.admin_area_code.label('admin_area'),
            models.StopArea.locality_code.label('locality'),
            db.cast(db.func.count(models.StopArea.code), db.Text).label('ind'),
        ).join(models.StopArea.stop_points)
        .group_by(models.StopArea.code)
        .filter(db.func.to_tsvector('english', models.StopArea.name)
                .match(s_query, postgresql_regconfig='english'))
    ).subquery()
    stop_area = (
        db.session.query(
            _table_col(models.StopArea).label('table_name'),
            sub_stop_area.c.code.label('code'),
            sub_stop_area.c.name.label('name'),
            sub_stop_area.c.ind.label('indicator'),
            empty_col.label('street'),
            db.func.coalesce(models.Locality.name.label('locality_name'), ''),
            models.AdminArea.code.label('admin_area'),
            models.AdminArea.name.label('admin_area_name')
        ).select_from(sub_stop_area)
        .outerjoin(models.Locality,
                   models.Locality.code == sub_stop_area.c.locality)
        .join(models.AdminArea,
              models.AdminArea.code == sub_stop_area.c.admin_area)
    )
    stop = (
        db.session.query(
            _table_col(models.StopPoint).label('table_name'),
            models.StopPoint.atco_code.label('code'),
            models.StopPoint.name.label('name'),
            models.StopPoint.short_ind.label('indicator'),
            models.StopPoint.street.label('street'),
            models.Locality.name.label('locality_name'),
            models.AdminArea.code.label('admin_area'),
            models.AdminArea.name.label('admin_area_name')
        ).select_from(models.StopPoint)
        .outerjoin(models.StopArea,
                   models.StopArea.code == models.StopPoint.stop_area_code)
        .join(models.Locality,
              models.Locality.code == models.StopPoint.locality_code)
        .join(models.AdminArea,
              models.AdminArea.code == models.Locality.admin_area_code)
        # Include stops with name or street matching query but exclude these
        # within areas that have already been found - prevent duplicates
        .filter(
            db.or_(
                db.func.to_tsvector('english', models.StopPoint.name)
                .match(s_query, postgresql_regconfig='english'),
                db.func.to_tsvector('english', models.StopPoint.street)
                .match(s_query, postgresql_regconfig='english')
            ),
            db.not_(
                db.and_(
                    models.StopPoint.stop_area_code.isnot(None),
                    db.func.to_tsvector('english', models.StopArea.name)
                    .match(s_query, postgresql_regconfig='english')
                )
            )
        )
    )
    search = admin_area.union_all(district, locality, stop_area, stop)

    results = search.all()
    if raise_exception and len(results) > SEARCH_LIMIT:
        raise LimitException(s_query, len(results))

    return results
