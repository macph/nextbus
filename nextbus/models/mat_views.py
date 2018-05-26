"""
Materialized views for the nextbus package.
"""
import functools

from nextbus import db
from nextbus.models import utils
from nextbus.models.tables import (Region, AdminArea, District, Locality,
                                   StopArea, StopPoint)


def _select_fts_vectors():
    """ Helper function to create a query for the full text search materialized
        view.

        Core expressions are required, because the session has not been set up
        yet, though ORM models and attributes can still be used,
    """
    null = db.literal_column("NULL")

    def tsvector_column(*columns):
        """ Helper function to create an expression for tsvector values from a
            number of columns.
        """
        vectors = []
        for column, weight in columns:
            tsvector = db.func.to_tsvector("english", column)
            if weight in "ABCD" and len(weight) == 1:
                tsvector = db.func.setweight(tsvector, weight)
            elif weight is not None:
                raise ValueError("Each argument must be either a letter A-D "
                                 "or None.")

            vectors.append(tsvector)

        # 'col1.concat(col2)' in SQLAlchemy translates to col1 || col2 in SQL
        return functools.reduce(lambda a, b: a.concat(b), vectors)

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
            tsvector_column((Region.name, "A")).label("vector")
        ])
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
            tsvector_column((AdminArea.name, "A")).label("vector")
        ])
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
            tsvector_column((District.name, "A"),
                             (AdminArea.name, "B")).label("vector")
        ])
        .select_from(
            District.__table__
            .join(AdminArea, AdminArea.code == District.admin_area_ref)
        )
    )

    t_locality = (
        db.select([
            StopPoint.locality_ref.label("code")
        ])
        .group_by(StopPoint.locality_ref)
        .alias("locality_stops")
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
            tsvector_column((Locality.name, "A"),
                             (db.func.coalesce(District.name, ""), "B"),
                             (AdminArea.name, "B")).label("vector")
        ])
        .select_from(
            Locality.__table__
            .join(t_locality, t_locality.c.code == Locality.code)
            .outerjoin(District, District.code == Locality.district_ref)
            .join(AdminArea, AdminArea.code == Locality.admin_area_ref)
        )
    )

    t_area = (
        db.select([
            StopPoint.stop_area_ref.label("code"),
            db.cast(db.func.count(StopPoint.atco_code), db.Text).label("ind")
        ])
        .group_by(StopPoint.stop_area_ref)
        .alias("stop_count")
    )

    stop_area = (
        db.select([
            utils.table_name(StopArea).label("table_name"),
            StopArea.code.label("code"),
            StopArea.name.label("name"),
            t_area.c.ind.label("short_ind"),
            null.label("street"),
            StopArea.stop_area_type.label("stop_type"),
            null.label("stop_area_ref"),
            Locality.name.label("locality_name"),
            District.name.label("district_name"),
            AdminArea.code.label("admin_area_ref"),
            AdminArea.name.label("admin_area_name"),
            tsvector_column((StopArea.name, "A"),
                            (db.func.coalesce(Locality.name, ""), "C"),
                             (db.func.coalesce(District.name, ""), "D"),
                             (AdminArea.name, "D")).label("vector")
        ])
        .select_from(
            StopArea.__table__
            .join(t_area, t_area.c.code == StopArea.code)
            .outerjoin(Locality, Locality.code == StopArea.locality_ref)
            .outerjoin(District, District.code == Locality.district_ref)
            .join(AdminArea, AdminArea.code == StopArea.admin_area_ref)
        )
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
            tsvector_column((StopPoint.name, "A"),
                             (StopPoint.street, "B"),
                             (Locality.name, "C"),
                             (db.func.coalesce(District.name, ""), "D"),
                             (AdminArea.name, "D")).label("vector")
        ])
        .select_from(
            StopPoint.__table__
            .join(Locality, Locality.code == StopPoint.locality_ref)
            .outerjoin(District, District.code == Locality.district_ref)
            .join(AdminArea, AdminArea.code == StopPoint.admin_area_ref)
        )
    )

    queries = (region, admin_area, district, locality, stop_area, stop_point)

    return db.union_all(*queries)


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
        - ``vector`` The tsvector value to be searched over
        - ``rank`` Search rank - in case of stop point this is the first
        non-zero rank

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
    TYPE_NAMES = {
        "area": "Areas",
        "place": "Places",
        "stop": "Stops"
    }
    TYPES = {
        "area": {m.__tablename__ for m in [Region, AdminArea, District]},
        "place": {m.__tablename__ for m in [Locality]},
        "stop": {m.__tablename__ for m in [StopArea, StopPoint]}
    }

    MINIMUM_AREA_RANK = 0.5
    MINIMUM_STOP_RANK = 0.25
    WEIGHTS = "{0.125, 0.25, 0.5, 1.0}"

    __table__ = utils.create_materialized_view("fts", _select_fts_vectors())
    # Rank attribute left blank for search queries. See:
    # http://docs.sqlalchemy.org/en/latest/orm/mapped_sql_expr.html
    rank = db.query_expression()

    # Unique index for table_name + code required for concurrent refresh
    __table_args__ = (
        db.Index("ix_fts_name", "table_name"),
        db.Index("ix_fts_code", "code"),
        db.Index("ix_fts_unique", "table_name", "code", unique=True),
        db.Index("ix_fts_area", "admin_area_ref"),
        db.Index("ix_fts_gin", "tsvector", postgresql_using="gin")
    )

    def __repr__(self):
        return "<FTS(%s, %s)>" % (self.table_name, self.code)

    @classmethod
    def _match(cls, query):
        """ Full text search expression with a tsquery.

            :param query: String suitable for ``to_tsquery()`` function.
            :returns: Expression to be used in a query.
        """
        return cls.vector.match(query, postgresql_regconfig="english")

    @classmethod
    def _ts_rank(cls, query):
        """ Full text search rank expression with a tsquery.

            :param query: String suitable for ``to_tsquery()`` function.
            :returns: Expression to be used in a query.
        """
        tsquery = db.func.to_tsquery("english", query)

        return db.func.ts_rank(cls.WEIGHTS, cls.vector, tsquery)

    @classmethod
    def _match_query(cls, query, types=None, admin_areas=None):
        """ Creates an expression where tsvector values are matched with
            tsquery values created by the tsquery parser.

            :param query: A ParseResult object or a string.
            :param types: Iterable with values 'area', 'place' or 'stop'.
            :param admin_areas: List of administrative area codes to filter by.
            :returns: Query expression to be executed.
        """
        try:
            string = query.to_string()
            string_not = query.to_string(exclude_not=True)
        except AttributeError:
            string = string_not = query

        # Add rank value and exclude vector column
        rank = cls._ts_rank(string_not).label("rank")
        match = cls.query.options(db.with_expression(cls.rank, rank),
                                  db.defer(cls.vector))

        # Filter by table name if requested
        if types is not None:
            tables = []
            for type_ in types:
                if type_ not in cls.TYPES:
                    raise ValueError("Type %s is invalid. Set of types must "
                                     "only contain the values %s." %
                                     (type_, list(cls.TYPES.keys())))
                tables.extend(cls.TYPES[type_])
            if tables:
                match = match.filter(cls.table_name.in_(tables))

        # Filter by admin area code if requested
        if admin_areas is not None:
            match = match.filter(cls.admin_area_ref.in_(admin_areas),
                                 cls.admin_area_ref.isnot(None))

        # Finally, match the query
        match = match.filter(cls._match(string))

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

        match = cls._match_query(query, types, admin_areas).cte("match")
        match_b = match.alias("match_b")

        expression = (
            db.session.query(match)
            .outerjoin(match_b, match.c.stop_area_ref == match_b.c.code)
            .filter(match_b.c.code.is_(None))
        )

        if names_only:
            expression = expression.filter(db.or_(
                match.c.rank > cls.MINIMUM_AREA_RANK,
                db.and_(match.c.table_name == StopPoint.__tablename__,
                        match.c.rank > cls.MINIMUM_STOP_RANK)
            ))

        # Order by rank, name and indicator
        expression = expression.order_by(db.desc(match.c.rank), match.c.name,
                                         match.c.short_ind)

        return expression

    @classmethod
    def matching_types(cls, query, names_only=True):
        """ Finds all admin areas and table names covering matching results for
            a query.

            The areas and types are sorted into two sets, to be used for
            filtering.

            :param query: A ParseResult object or a string.
            :param names_only: Sets thresholds for search rankings such that
            only results that match the higher weighted lexemes are retained.
            :returns: A tuple with a dict of types and a dict  of tuples with
            administrative area references and names
        """
        try:
            string = query.to_string()
        except AttributeError:
            string = query

        # Search all types and admin areas
        match = cls._match_query(query).cte("match")

        expression = (
            db.session.query(match.c.table_name, match.c.admin_area_ref,
                             match.c.admin_area_name)
            .distinct(match.c.table_name, match.c.admin_area_ref)
        )

        if names_only:
            expression = expression.filter(db.or_(
                match.c.rank > cls.MINIMUM_AREA_RANK,
                db.and_(match.c.table_name == StopPoint.__tablename__,
                        match.c.rank > cls.MINIMUM_STOP_RANK)
            ))

        result = expression.all()
        # Sort results into separate sets and group tables into types
        tables = {row.table_name for row in result}
        s_areas = {(row.admin_area_ref, row.admin_area_name) for row in result
                   if row.admin_area_ref.isnot(None)}

        types = {t: cls.TYPE_NAMES[t] for t, set_ in cls.TYPES.items()
                 if tables & set_}
        areas = dict(s_areas)

        return types, areas
