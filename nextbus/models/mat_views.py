"""
Materialized views for the nextbus package.
"""
import functools

from sqlalchemy.dialects import postgresql as pg

from nextbus import db
from nextbus.models import utils
from nextbus.models.tables import (
    Region, AdminArea, District, Locality, StopArea, StopPoint,
    JourneyPattern, JourneyLink, Service, Operator, LocalOperator
)


def _select_natural_sort():
    stop_ind = db.select([StopPoint.short_ind.label("string")])
    service_line = db.select([Service.line.label("string")])
    other_num = db.select([db.func.generate_series(0, 100).cast(db.Text)
                           .label("string")])
    num = db.union(stop_ind, service_line, other_num).alias("num")

    regex = (
        db.func.regexp_matches(num.c.string, "0*(\\d+)|(\D+)", "g")
        .alias("r")
    )
    # Make a column alias with text array type
    r = db.column("r", type_=db.ARRAY(db.Text, dimensions=1))

    # If not numeric, convert to uppercase
    r_upper = db.func.upper(r[2])
    # Add number of digits to numbers so they are sorted naturally
    # eg 4294967296 -> 10 digits -> 2 digits so is converted to 2104294967296
    r_len = db.func.length(r[1]).cast(db.Text)
    r_len_len = db.func.length(r_len).cast(db.Text)
    r_concat = r_len.concat(r_len_len).concat(r[1])

    index = db.func.coalesce(r_upper, r_concat)
    index = db.func.convert_to(index, "SQL_ASCII")
    index = db.func.string_agg(index, "\\x00")
    index = db.func.coalesce(index, "")

    select_index = db.select([index]).select_from(regex)

    query = (
        db.select([num.c.string.label("string"), select_index.label("index")])
        .select_from(num)
    )

    # Set columns manually
    query.c.string.primary_key = True
    query.c.index.type = db.LargeBinary

    return query


def _tsvector_column(*columns):
    """ Creates an expression for tsvector values with weights from a number of
        columns.
    """
    vectors = []
    for column, weight in columns:
        tsvector = db.func.to_tsvector("english", column)
        if weight in ["A", "B", "C", "D"]:
            tsvector = db.func.setweight(tsvector, weight)
        elif weight is not None:
            raise ValueError("Each argument must be either a letter A-D "
                             "or None.")

        vectors.append(tsvector)

    # 'col1.concat(col2)' in SQLAlchemy translates to col1 || col2 in SQL
    return functools.reduce(lambda a, b: a.concat(b), vectors)


def _select_fts_vectors():
    """ Helper function to create a query for the full text search materialized
        view.

        Core expressions are required, because the session has not been set up
        yet, though ORM models and attributes can still be used.
    """
    null = db.literal_column("NULL")

    region = (
        db.select([
            utils.table_name(Region).label("table_name"),
            Region.code.label("code"),
            Region.name.label("name"),
            null.label("short_ind"),
            null.label("street"),
            null.label("stop_type"),
            null.label("stop_area_ref"),
            null.label("locality_name"),
            null.label("district_name"),
            null.label("admin_area_ref"),
            null.label("admin_area_name"),
            db.cast(pg.array([]), pg.ARRAY(db.Text)).label("admin_areas"),
            _tsvector_column((Region.name, "A")).label("vector")
        ])
        .where(Region.code != 'GB')
    )

    admin_area = (
        db.select([
            utils.table_name(AdminArea).label("table_name"),
            AdminArea.code.label("code"),
            AdminArea.name.label("name"),
            null.label("short_ind"),
            null.label("street"),
            null.label("stop_type"),
            null.label("stop_area_ref"),
            null.label("locality_name"),
            null.label("district_name"),
            AdminArea.code.label("admin_area_ref"),
            AdminArea.name.label("admin_area_name"),
            pg.array([AdminArea.code]).label("admin_areas"),
            _tsvector_column((AdminArea.name, "A")).label("vector")
        ])
        .where(AdminArea.region_ref != 'GB')
    )

    district = (
        db.select([
            utils.table_name(District).label("table_name"),
            District.code.label("code"),
            District.name.label("name"),
            null.label("short_ind"),
            null.label("street"),
            null.label("stop_type"),
            null.label("stop_area_ref"),
            null.label("locality_name"),
            null.label("district_name"),
            AdminArea.code.label("admin_area_ref"),
            AdminArea.name.label("admin_area_name"),
            pg.array([AdminArea.code]).label("admin_areas"),
            _tsvector_column(
                (District.name, "A"),
                (AdminArea.name, "B")
            ).label("vector")
        ])
        .select_from(
            District.__table__
            .join(AdminArea, AdminArea.code == District.admin_area_ref)
        )
    )

    locality = (
        db.select([
            utils.table_name(Locality).label("table_name"),
            Locality.code.label("code"),
            Locality.name.label("name"),
            null.label("short_ind"),
            null.label("street"),
            null.label("stop_type"),
            null.label("stop_area_ref"),
            null.label("locality_name"),
            District.name.label("district_name"),
            AdminArea.code.label("admin_area_ref"),
            AdminArea.name.label("admin_area_name"),
            pg.array([AdminArea.code]).label("admin_areas"),
            _tsvector_column(
                (Locality.name, "A"),
                (db.func.coalesce(District.name, ""), "B"),
                (AdminArea.name, "B")
            ).label("vector")
        ])
        .select_from(
            Locality.__table__
            .outerjoin(District, District.code == Locality.district_ref)
            .join(AdminArea, AdminArea.code == Locality.admin_area_ref)
        )
        .where(db.exists([StopPoint.atco_code])
               .where(StopPoint.locality_ref == Locality.code))
    )

    stop_area = (
        db.select([
            utils.table_name(StopArea).label("table_name"),
            StopArea.code.label("code"),
            StopArea.name.label("name"),
            db.cast(db.func.count(StopPoint.atco_code), db.Text)
            .label("short_ind"),
            null.label("street"),
            StopArea.stop_area_type.label("stop_type"),
            null.label("stop_area_ref"),
            Locality.name.label("locality_name"),
            District.name.label("district_name"),
            AdminArea.code.label("admin_area_ref"),
            AdminArea.name.label("admin_area_name"),
            pg.array([AdminArea.code]).label("admin_areas"),
            _tsvector_column(
                (StopArea.name, "A"),
                (db.func.coalesce(Locality.name, ""), "C"),
                (db.func.coalesce(District.name, ""), "D"),
                (AdminArea.name, "D")
            ).label("vector")
        ])
        .select_from(
            StopArea.__table__
            .outerjoin(StopPoint, StopArea.code == StopPoint.stop_area_ref)
            .outerjoin(Locality, Locality.code == StopArea.locality_ref)
            .outerjoin(District, District.code == Locality.district_ref)
            .join(AdminArea, AdminArea.code == StopArea.admin_area_ref)
        )
        .group_by(StopArea.code, Locality.name, District.name, AdminArea.code)
    )

    stop_point = (
        db.select([
            utils.table_name(StopPoint).label("table_name"),
            StopPoint.atco_code.label("code"),
            StopPoint.name.label("name"),
            StopPoint.short_ind.label("short_ind"),
            StopPoint.street.label("street"),
            StopPoint.stop_type.label("stop_type"),
            StopPoint.stop_area_ref.label("stop_area_ref"),
            Locality.name.label("locality_name"),
            District.name.label("district_name"),
            AdminArea.code.label("admin_area_ref"),
            AdminArea.name.label("admin_area_name"),
            pg.array([AdminArea.code]).label("admin_areas"),
            _tsvector_column(
                (StopPoint.name, "A"),
                (StopPoint.street, "B"),
                (Locality.name, "C"),
                (db.func.coalesce(District.name, ""), "D"),
                (AdminArea.name, "D")
            ).label("vector")
        ])
        .select_from(
            StopPoint.__table__
            .join(Locality, Locality.code == StopPoint.locality_ref)
            .outerjoin(District, District.code == Locality.district_ref)
            .join(AdminArea, AdminArea.code == StopPoint.admin_area_ref)
        )
    )

    service = (
        db.select([
            utils.table_name(Service).label("table_name"),
            db.cast(Service.id, db.Text).label("code"),
            Service.description.label("name"),
            Service.line.label("short_ind"),
            null.label("street"),
            null.label("stop_type"),
            null.label("stop_area_ref"),
            null.label("locality_name"),
            null.label("district_name"),
            null.label("admin_area_ref"),
            null.label("admin_area_name"),
            db.func.array_agg(db.distinct(AdminArea.code)).label("admin_areas"),
            _tsvector_column(
                (Service.line, "A"),
                (Service.description, "A"),
                (db.func.string_agg(db.distinct(Operator.name), " "), "B"),
                (db.func.string_agg(db.distinct(Locality.name), " "), "C"),
                (db.func.coalesce(
                    db.func.string_agg(db.distinct(District.name), " "),
                    ""
                ), "D"),
                (db.func.string_agg(db.distinct(AdminArea.name), " "), "D")
            ).label("vector")
        ])
        .select_from(
            Service.__table__
            .join(JourneyPattern, Service.id == JourneyPattern.service_ref)
            .join(LocalOperator,
                  (JourneyPattern.local_operator_ref == LocalOperator.code) &
                  (JourneyPattern.region_ref == LocalOperator.region_ref))
            .join(Operator, LocalOperator.operator_ref == Operator.code)
            .join(JourneyLink, JourneyPattern.id == JourneyLink.pattern_ref)
            .join(StopPoint, JourneyLink.stop_point_ref == StopPoint.atco_code)
            .join(Locality, StopPoint.locality_ref == Locality.code)
            .outerjoin(District, Locality.district_ref == District.code)
            .join(AdminArea, Locality.admin_area_ref == AdminArea.code)
        )
        .group_by(Service.id)
    )

    return db.union_all(region, admin_area, district, locality, stop_area,
                        stop_point, service)


class NaturalSort(utils.MaterializedView):
    """ Sorts indicators and lines naturally via a join with this view. """
    __table__ = utils.create_mat_view("natural_sort", _select_natural_sort())

    __table_args__ = (
        db.Index("ix_natural_sort_string", "string", unique=True),
        db.Index("ix_natural_sort_index", "index")
    )


class FTS(utils.MaterializedView):
    """ Materialized view for full text searching.

        Columns:
        - ``table_name`` Name of the table this row comes from
        - ``code`` Primary key for row
        - ``name`` Name of area/locality/stop
        - ``short_ind`` Indicator for stop point or number of stops for stop
        area; empty for other results
        - ``street`` Street stop point is on; empty for other results
        - ``stop_type`` Type of stop or area
        - ``locality_name`` Locality name for stop points and areas; empty for
        other results
        - ``district_name`` District name for localities and stops; empty for
        other results
        - ``admin_area_ref`` Admin area code for filtering on search page
        - ``admin_area_name`` Name of admin area for filtering on search page
        - ``admin_areas`` Array of admin area refs to filter with
        - ``vector`` The tsvector value to be searched over

        A threshold for rankings can be set such that only results with name
        or street that matches the query are included. For example, a stop with
        name matching 'Westminster' will be included, but a stop within
        Westminster locality whose name does not match 'Westminster' will not.
        - District: ``rank > 0.5``
        - Locality: ``rank > 0.5``
        - StopArea: ``rank > 0.5``
        - StopPoint: ``rank > 0.25``

        All rankings are done with weights 0.125, 0.25, 0.5 and 1.0 for ``D``
        to ``A`` respectively.
    """
    __table__ = utils.create_mat_view("fts", _select_fts_vectors())

    # Unique index for table_name + code required for concurrent refresh
    __table_args__ = (
        db.Index("ix_fts_table", "table_name"),
        db.Index("ix_fts_code", "code"),
        db.Index("ix_fts_unique", "table_name", "code", unique=True),
        db.Index("ix_fts_vector_gin", "tsvector", postgresql_using="gin"),
        db.Index("ix_fts_areas_gin", "admin_areas", postgresql_using="gin")
    )

    TYPES = {"area": "Areas", "place": "Places", "stop": "Stops",
             "service": "Services"}
    TYPE_TABLES = {"area": {"region", "admin_area", "district"},
                   "place": {"locality"}, "stop": {"stop_area", "stop_point"},
                   "service": {"service"}}

    MINIMUM_AREA_RANK = 0.5
    MINIMUM_STOP_RANK = 0.25
    WEIGHTS = "{0.125, 0.25, 0.5, 1.0}"

    def __repr__(self):
        return "<FTS(%s, %s)>" % (self.table_name, self.code)

    @classmethod
    def match(cls, query):
        """ Full text search expression with a tsquery.

            :param query: String suitable for ``to_tsquery()`` function.
            :returns: Expression to be used in a query.
        """
        return cls.vector.match(query, postgresql_regconfig="english")

    @classmethod
    def ts_rank(cls, query):
        """ Full text search rank expression with a tsquery.

            :param query: String suitable for ``to_tsquery()`` function.
            :returns: Expression to be used in a query.
        """
        tsquery = db.func.to_tsquery("english", query)

        return db.func.ts_rank(cls.WEIGHTS, cls.vector, tsquery)

    @classmethod
    def _apply_filters(cls, match, types=None, areas=None, rank=None):
        """ Apply filters to a search expression if they are specified.

            :param match: The original query expression
            :param types: Types, ie 'stop', 'place' and 'area' to filter by
            :param areas: Administrative area codes to filter by
            :param rank: Rank function used to filter results above a threshold
            set by ``MINIMUM_AREA_RANK`` and ``MINIMUM_STOP_RANK``.
            :returns: Query expression with added filters, if any
        """
        if types and set(types) - cls.TYPES.keys():
            raise ValueError("Invalid values for type parameter.")

        if types:
            tables = []
            for type_ in types:
                tables.extend(cls.TYPE_TABLES[type_])
            match = match.filter(cls.table_name.in_(tables))

        if areas:
            match = match.filter(cls.admin_areas.overlap(areas))

        if rank is not None:
            match = match.filter(
                (cls.table_name == StopPoint.__tablename__) &
                (rank > cls.MINIMUM_STOP_RANK) |
                (rank > cls.MINIMUM_AREA_RANK)
            )

        return match

    @classmethod
    def search(cls, query, types=None, admin_areas=None, names_only=True):
        """ Creates an expression for searching queries, excluding stop points
            within areas that already match and results of low rank.

            :param query: A ParseResult object or a string.
            :param types: Set with values 'area', 'place' or 'stop'.
            :param admin_areas: List of administrative area codes to filter by.
            :param names_only: Sets thresholds for search rankings such that
            only results that match the higher weighted lexemes are retained.
            :returns: Query expression to be executed.
        """
        try:
            string = query.to_string()
            string_not = query.to_string(defined=True)
        except AttributeError:
            string = string_not = query

        fts_sa = db.aliased(cls)
        rank = cls.ts_rank(string_not)
        # Defer vector and admin areas, and order by rank, name and indicator
        match = (
            cls.query
            .options(db.defer(cls.vector), db.defer(cls.admin_areas))
            .outerjoin(NaturalSort, cls.short_ind == NaturalSort.string)
            .filter(
                cls.match(string),
                # Ignore stops whose stop areas already match
                ~db.exists().where(
                    fts_sa.match(string) &
                    (fts_sa.code == cls.stop_area_ref)
                )
            )
            .order_by(db.desc(rank), cls.name, NaturalSort.index)
        )
        # Add filters for rank, types or admin area
        match = cls._apply_filters(match, types, admin_areas,
                                   rank if names_only else None)

        return match

    @classmethod
    def matching_types(cls, query, admin_areas=None, names_only=True):
        """ Finds all admin areas and table names covering matching results for
            a query.

            The areas and types are sorted into two sets, to be used for
            filtering.

            :param query: A ParseResult object or a string.
            :param admin_areas: Filter by admin areas to get matching types
            :param names_only: Sets thresholds for search rankings such that
            only results that match the higher weighted lexemes are retained.
            :returns: A tuple with a dict of types and a dict with
            administrative area references and names
        """
        try:
            string = query.to_string()
            string_not = query.to_string(defined=True)
        except AttributeError:
            string = string_not = query

        expr = (
            db.session.query(
                pg.array_agg(db.distinct(cls.table_name)).label("tables"),
                pg.array_agg(db.distinct(
                    pg.array([AdminArea.code, AdminArea.name])
                )).label("areas")
            )
            .select_from(db.func.unnest(cls.admin_areas).alias("unnest_areas"))
            .join(AdminArea, db.column("unnest_areas") == AdminArea.code)
            .filter(cls.match(string))
        )
        if names_only:
            expr = cls._apply_filters(expr, rank=cls.ts_rank(string_not))

        # All data should have been aggregated into one row
        result = expr.one()

        if result.tables is not None:
            tables = set(result.tables)
            if admin_areas:
                tables &= set(admin_areas)
            types = {t: n for t, n in cls.TYPES.items()
                     if tables & cls.TYPE_TABLES[t]}
        else:
            types = {}

        if result.areas is not None:
            areas = dict(result.areas)
        else:
            areas = {}

        return types, areas
