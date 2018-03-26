"""
Search functions for the nextbus package.
"""
import collections
import re

from flask import current_app

from nextbus import db, models, ts_parser


REGEX_POSTCODE = re.compile(r"^\s*([A-Za-z]{1,2}\d{1,2}[A-Za-z]?)"
                            r"\s*(\d[A-Za-z]{2})\s*$")
MINIMUM_AREA_RANK = 0.5
MINIMUM_STOP_RANK = 0.25
LOCAL_LIMIT = 32
STOPS_LIMIT = 256


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
        the model object, or None if no match is found.
    """
    found = None
    postcode = REGEX_POSTCODE.match(query)
    if postcode:
        # Search postcode; make all upper and remove spaces first
        outward, inward = postcode.group(1), postcode.group(2)
        q_psc = (
            models.Postcode.query.options(db.load_only("text"))
            .filter(models.Postcode.index == (outward + inward).upper())
        ).one_or_none()
        if q_psc is not None:
            found = q_psc
        else:
            raise PostcodeException(query, (outward + " " + inward).upper())

    if not found:
        # Search NaPTAN code & ATCO code
        q_stop = (
            models.StopPoint.query.options(db.load_only("atco_code"))
            .filter(db.or_(models.StopPoint.naptan_code == query.lower(),
                           models.StopPoint.atco_code == query.upper()))
        ).one_or_none()
        if q_stop is not None:
            found = q_stop

    if found:
        current_app.logger.info("Search query %r returned exact match %r"
                                % (query, found))

    return found


def _empty_col(column_name, value=None):
    """ Helper function to create a literal column with a value (empty text by
        default) and a label.
    """
    text = "''" if value is None else str(value)
    return db.literal_column(text).label(column_name)


def _fts_search_exists(query_text):
    """ Does a PostgreSQL FTS search to check if matching entries exist. """
    def match_query(tsvector):
        return tsvector.match(query_text, postgresql_regconfig="english")

    admin_area = (
        db.session.query(models.AdminArea.code)
        .filter(match_query(models.AdminArea.tsv_name))
    )
    district = (
        db.session.query(models.District.code)
        .filter(match_query(models.District.tsv_name))
    )
    locality = (
        db.session.query(models.Locality.code)
        .outerjoin(models.Locality.stop_points)
        .filter(match_query(models.Locality.tsv_name),
                models.StopPoint.atco_code.isnot(None))
    )
    stop_area = (
        db.session.query(models.StopArea.code)
        .filter(match_query(models.StopArea.tsv_name))
    )
    stop = (
        db.session.query(models.StopPoint.atco_code)
        .filter(db.or_(
            match_query(models.StopPoint.tsv_both),
            match_query(models.StopPoint.tsv_name),
            match_query(models.StopPoint.tsv_street)
        ))
    )

    return admin_area.union(district, locality, stop_area, stop).all()


def _fts_search_all(query_text, rank_text=None, names_only=True):
    """ Does a PostgreSQL FTS search to find all stops and places matching
        query, returning a dictionary of lists with keys ``area``, ``locality``
        and ``stop`` and ordered by rank, name and indicator (if present).

        Columns:
        - ``table_name`` Name of the table this result comes from
        - ``code`` Primary key for row
        - ``name`` Name of area/locality/stop
        - ``indicator`` Indicator for stop point or number of stops for stop
        area; empty for other results
        - ``street`` Street stop point is on; empty for other results
        - ``locality_name`` Locality name for stop points and areas; empty for
        other results
        - ``district_name`` District name for localities and stops; empty for
        other results
        - ``admin_area`` Admin area code for filtering on search page
        - ``admin_area_name`` Name of admin area for filtering on search page
        - ``rank`` Search rank - in case of stop point this is the first
        non-zero rank

        With ``names_only`` set to true, each results table (except admin area)
        has a minimum rank such that only results with name or street that
        matches the query are included. For example, a stop with name matching
        'Westminster' will be included, but a stop within Westminster locality
        whose name does not match 'Westminster' will not be.
        - District: ``rank > 0.5``
        - Locality: ``rank > 0.5``
        - StopArea: ``rank > 0.5``
        - StopPoint: ``rank > 0.25``

        All rankings are done with weights 0.125, 0.25, 0.5 and 1.0 for ``D``
        to ``A`` respectively.
    """
    query_rank = query_text if rank_text is None else rank_text

    def ts_rank_func(tsvector):
        """ Creates an expression with the ``ts_rank`` function from a TSVector
            and a TSQuery made from the query text.
        """
        weights = "{0.125, 0.25, 0.5, 1.0}"
        tsquery = db.func.to_tsquery("english", query_rank)

        return db.func.ts_rank(weights, tsvector, tsquery)

    def match_query(tsvector):
        """ Creates a SQL expression from a TSVector that translates to
            ``tsvector @@ to_tsquery('english', query_text')``.
        """
        return tsvector.match(query_text, postgresql_regconfig="english")

    min_area_rank = MINIMUM_AREA_RANK if names_only else 0
    min_stop_rank = MINIMUM_STOP_RANK if names_only else 0

    rank_district = ts_rank_func(models.District.tsv_name)
    rank_local = ts_rank_func(models.Locality.tsv_name)
    rank_stop_area = ts_rank_func(models.StopArea.tsv_name)
    rank_stop_both = ts_rank_func(models.StopPoint.tsv_both)
    rank_stop_name = ts_rank_func(models.StopPoint.tsv_name)
    rank_stop_street = ts_rank_func(models.StopPoint.tsv_street)

    empty = db.session.query(
        _empty_col("table_name"),
        _empty_col("code"),
        _empty_col("name"),
        _empty_col("indicator"),
        _empty_col("street"),
        _empty_col("locality_name"),
        _empty_col("district_name"),
        _empty_col("admin_area"),
        _empty_col("admin_area_name"),
        _empty_col("rank", value=0)
    ).filter(db.false())

    # Repeating column names are skipped so the second set are given labels
    admin_area = db.session.query(
        models.table_name(models.AdminArea),
        models.AdminArea.code,
        models.AdminArea.name,
        _empty_col("indicator"),
        _empty_col("street"),
        _empty_col("locality_name"),
        _empty_col("district_name"),
        models.AdminArea.code.label("code_2"),
        models.AdminArea.name.label("name_2"),
        ts_rank_func(models.AdminArea.tsv_name)
    ).filter(match_query(models.AdminArea.tsv_name))

    district = (
        db.session.query(
            models.table_name(models.District),
            models.District.code,
            models.District.name,
            _empty_col("indicator"),
            _empty_col("street"),
            _empty_col("locality_name"),
            _empty_col("district_name"),
            models.AdminArea.code,
            models.AdminArea.name,
            rank_district
        ).select_from(models.District)
        .join(models.AdminArea,
              models.AdminArea.code == models.District.admin_area_ref)
        .filter(match_query(models.District.tsv_name),
                rank_district > min_area_rank)
    )

    # Subquery required to find associated stop points and filter out those
    # without any
    sub_locality = (
        db.session.query(
            models.Locality.code,
            models.Locality.name,
            models.Locality.district_ref,
            models.Locality.admin_area_ref,
            rank_local.label("rank")
        ).outerjoin(models.Locality.stop_points)
        .group_by(models.Locality.code)
        .filter(match_query(models.Locality.tsv_name),
                rank_local > min_area_rank,
                models.StopPoint.atco_code.isnot(None))
    ).subquery()

    locality = (
        db.session.query(
            models.table_name(models.Locality),
            sub_locality.c.code,
            sub_locality.c.name,
            _empty_col("indicator"),
            _empty_col("street"),
            _empty_col("locality_name"),
            db.func.coalesce(models.District.name, ""),
            models.AdminArea.code,
            models.AdminArea.name,
            sub_locality.c.rank
        ).select_from(sub_locality)
        .outerjoin(models.District,
                   models.District.code == sub_locality.c.district_ref)
        .join(models.AdminArea,
              models.AdminArea.code == sub_locality.c.admin_area_ref)
    )

    # Subquery required to count number of stops in stop area
    sub_stop_area = (
        db.session.query(
            models.StopArea.code,
            models.StopArea.name,
            models.StopArea.locality_ref,
            models.StopArea.admin_area_ref,
            models.StopArea.stop_count.label("ind"), #pylint: disable=E1101
            rank_stop_area.label("rank")
        ).join(models.StopArea.stop_points)
        .group_by(models.StopArea.code)
        .filter(match_query(models.StopArea.tsv_name),
                rank_stop_area > min_area_rank)
    ).subquery()

    stop_area = (
        db.session.query(
            models.table_name(models.StopArea),
            sub_stop_area.c.code,
            sub_stop_area.c.name,
            sub_stop_area.c.ind,
            _empty_col("street"),
            db.func.coalesce(models.Locality.name, ""),
            db.func.coalesce(models.District.name, ""),
            models.AdminArea.code,
            models.AdminArea.name,
            sub_stop_area.c.rank
        ).select_from(sub_stop_area)
        .outerjoin(models.Locality,
                   models.Locality.code == sub_stop_area.c.locality_ref)
        .outerjoin(models.District,
                   models.District.code == models.Locality.district_ref)
        .join(models.AdminArea,
              models.AdminArea.code == sub_stop_area.c.admin_area_ref)
    )

    # Reuse the stop area subquery to exclude stop points within areas that
    # have already been matched.
    # ts_rank evaluated in same order as WHERE clause; checks if rank for
    # 'tsv_both' is non zero, else check 'tsv_name' as so on.
    stop_point = (
        db.session.query(
            models.table_name(models.StopPoint),
            models.StopPoint.atco_code,
            models.StopPoint.name,
            models.StopPoint.short_ind,
            models.StopPoint.street,
            models.Locality.name,
            db.func.coalesce(models.District.name, ""),
            models.AdminArea.code,
            models.AdminArea.name,
            db.case([(rank_stop_both != 0, rank_stop_both),
                     (rank_stop_name != 0, rank_stop_name)],
                    else_=rank_stop_street)
        ).select_from(models.StopPoint)
        .outerjoin(sub_stop_area,
                   sub_stop_area.c.code == models.StopPoint.stop_area_ref)
        .join(models.Locality,
              models.Locality.code == models.StopPoint.locality_ref)
        .outerjoin(models.District,
                   models.District.code == models.Locality.district_ref)
        .join(models.AdminArea,
              models.AdminArea.code == models.Locality.admin_area_ref)
        .filter(
            db.or_(match_query(models.StopPoint.tsv_both),
                   match_query(models.StopPoint.tsv_name),
                   match_query(models.StopPoint.tsv_street)),
            db.or_(rank_stop_both > min_stop_rank,
                   rank_stop_name > min_stop_rank,
                   rank_stop_street > min_stop_rank),
            sub_stop_area.c.code.is_(None)
        )
    )

    return (
        empty.union_all(admin_area, district, locality, stop_area, stop_point)
        .order_by(db.desc("rank"), "name", "indicator").all()
    )


def search_exists(query):
    """ Searches for stop, postcodes and places that do exist, without
        information on areas, before redirecting to a search results page with
        the full data.

        :returns: Either a matching Postcode object, a matching StopPoint
        object, or a list of matching results.
        :raises ValueError: if a query without any words was submitted.
        :raises PostcodeException: if a query was identified as a postcode but
        it does not exist.
    """
    if not "".join(query.split()):
        raise ValueError("No suitable query was entered.")

    # Search stop points and postcodes for an exact match
    obj_matching = search_code(query)
    if obj_matching:
        return obj_matching

    # Else: do a full text search - format query string first
    tsquery, _ = ts_parser.parse(query)
    results = _fts_search_exists(tsquery)

    return results


def search_full(query):
    """ Searches for stops, postcodes and places, returning full data including
        area information.

        :param query: Query text returned from search form.
        :param raise_exception: Set to raise an exception when too many results
        are returned.
        :returns: Either a matching Postcode object, a matching StopPoint
        object, or a dictionary of result lists with keys ``area``,
        ``locality`` and ``stop``, ordered by rank, name and indicator.
        :raises ValueError: if a query without any words was submitted.
        :raises PostcodeException: if a query was identified as a postcode but
        it does not exist.
    """
    if not "".join(query.split()):
        raise ValueError("No suitable query was entered.")

    # Search stop points and postcodes for an exact match
    obj_matching = search_code(query)
    if obj_matching:
        return obj_matching

    # Else: do a full text search - format query string first
    results = _fts_search_all(*ts_parser.parse(query))

    dict_results = collections.defaultdict(list)
    for row in results:
        if row.table_name in ["admin_area", "district"]:
            dict_results["area"].append(row)
        elif row.table_name in ["stop_area", "stop_point"]:
            dict_results["stop"].append(row)
        elif row.table_name == "locality":
            dict_results["locality"].append(row)
        else:
            raise ValueError("Table name %s in row is not valid."
                             % row.table_name)

    current_app.logger.info(
        "Search query %r returned results %s" %
        (query, {k: len(v) for k, v in dict_results.items()})
    )

    # Results were already ordered in SQL query; no need to sort lists
    return dict_results
