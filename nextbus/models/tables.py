"""
Models for the nextbus database.
"""
from sqlalchemy.ext import hybrid

from nextbus import db, location
from nextbus.models import utils

MIN_GROUPED = 72
MAX_DIST = 500

# Can't load NaturalSort materialized view yet, so use alias here
_ns = db.table("natural_sort", db.column("string"), db.column("index"))


class ServiceMode(utils.BaseModel):
    """ Lookup table for service modes, eg bus and tram. """
    __tablename__ = "service_mode"

    id = db.Column(db.Integer, primary_key=True, autoincrement=False)
    name = db.Column(db.Text, nullable=False, unique=True)


class BankHoliday(utils.BaseModel):
    """ Lookup table for bank holidays. """
    __tablename__ = "bank_holiday"

    id = db.Column(db.Integer, primary_key=True, autoincrement=False)
    name = db.Column(db.Text, nullable=False, unique=True)

    dates = db.relationship("BankHolidayDate", backref="bank_holiday")


class Region(utils.BaseModel):
    """ NPTG region. """
    __tablename__ = "region"

    code = db.Column(db.VARCHAR(2), primary_key=True)
    name = db.Column(db.Text, nullable=False, index=True)
    modified = db.deferred(db.Column(db.DateTime))

    areas = db.relationship("AdminArea", backref="region", innerjoin=True,
                            order_by="AdminArea.name")
    services = db.relationship("Service", backref="region", innerjoin=True)

    def __repr__(self):
        return "<Region(%r)>" % self.code

    def list_areas(self):
        """ Queries a list of districts and areas (that do not contain any
            districts) within the region, sorted by name.
        """
        query_areas = (
            db.session.query(
                db.case([(District.code.is_(None),
                          utils.table_name(AdminArea))],
                        else_=utils.table_name(District)).label("table_name"),
                db.case([(District.code.is_(None), AdminArea.code)],
                        else_=District.code).label("code"),
                db.case([(District.code.is_(None), AdminArea.name)],
                        else_=District.name).label("name")
            ).select_from(AdminArea)
            .outerjoin(AdminArea.districts)
            .filter(AdminArea.region_ref == self.code)
            .order_by("name")
        )

        return query_areas.all()


class AdminArea(utils.BaseModel):
    """ NPTG administrative area. """
    __tablename__ = "admin_area"

    code = db.Column(db.VARCHAR(3), primary_key=True)
    name = db.Column(db.Text, nullable=False, index=True)
    atco_code = db.deferred(db.Column(db.VARCHAR(3), unique=True, nullable=False))
    region_ref = db.Column(
        db.VARCHAR(2),
        db.ForeignKey("region.code", ondelete="CASCADE"),
        nullable=False, index=True
    )
    is_live = db.deferred(db.Column(db.Boolean, default=True))
    modified = db.deferred(db.Column(db.DateTime))

    districts = db.relationship("District", backref="admin_area",
                                order_by="District.name")
    localities = db.relationship("Locality", backref="admin_area",
                                 innerjoin=True, order_by="Locality.name")
    postcodes = db.relationship("Postcode", backref="admin_area",
                                innerjoin=True, order_by="Postcode.text")
    stop_points = db.relationship(
        "StopPoint", backref="admin_area", innerjoin=True,
        order_by="StopPoint.name, StopPoint.ind_index"
    )
    stop_areas = db.relationship("StopArea", backref="admin_area",
                                 innerjoin=True, order_by="StopArea.name")
    services = db.relationship("Service", backref="admin_area")

    def __repr__(self):
        return "<AdminArea(%r)>" % self.code

    def list_localities(self):
        """ Queries all localities that do contain stops or stop areas. """
        locality_refs = db.session.query(StopPoint.locality_ref).subquery()
        query_local = (
            Locality.query
            .filter(Locality.admin_area_ref == self.code,
                    Locality.code.in_(locality_refs))
            .order_by(Locality.name)
        )

        return query_local.all()


class District(utils.BaseModel):
    """ NPTG district. """
    __tablename__ = "district"

    code = db.Column(db.VARCHAR(3), primary_key=True)
    name = db.Column(db.Text, nullable=False, index=True)
    admin_area_ref = db.Column(
        db.VARCHAR(3),
        db.ForeignKey("admin_area.code", ondelete="CASCADE"),
        nullable=False, index=True
    )
    modified = db.deferred(db.Column(db.DateTime))

    localities = db.relationship("Locality", backref="district",
                                 order_by="Locality.name")
    postcodes = db.relationship("Postcode", backref="district",
                                order_by="Postcode.text")

    def __repr__(self):
        return "<District(%r)>" % self.code

    def list_localities(self):
        """ Queries all localities that do contain stops or stop areas. """
        locality_refs = db.session.query(StopPoint.locality_ref).subquery()
        query_local = (
            Locality.query
            .filter(Locality.district_ref == self.code,
                    Locality.code.in_(locality_refs))
            .order_by(Locality.name)
        )

        return query_local.all()


class Locality(utils.BaseModel):
    """ NPTG locality. """
    __tablename__ = "locality"

    code = db.Column(db.VARCHAR(8), primary_key=True)
    name = db.Column(db.Text, nullable=False, index=True)
    parent_ref = db.deferred(db.Column(db.VARCHAR(8), index=True))
    admin_area_ref = db.Column(
        db.VARCHAR(3),
        db.ForeignKey("admin_area.code", ondelete="CASCADE"),
        nullable=False, index=True
    )
    district_ref = db.Column(db.VARCHAR(3),
                             db.ForeignKey("district.code", ondelete="CASCADE"),
                             index=True)
    latitude = db.deferred(db.Column(db.Float, nullable=False))
    longitude = db.deferred(db.Column(db.Float, nullable=False))
    easting = db.deferred(db.Column(db.Integer, nullable=False))
    northing = db.deferred(db.Column(db.Integer, nullable=False))
    modified = db.deferred(db.Column(db.DateTime))

    stop_points = db.relationship(
        "StopPoint", backref="locality", innerjoin=True,
        order_by="StopPoint.name, StopPoint.ind_index"
    )
    stop_areas = db.relationship("StopArea", backref="locality", innerjoin=True,
                                 order_by="StopArea.name")

    def __repr__(self):
        return "<Locality(%r)>" % self.code

    def list_stops(self, group_areas=True):
        """ Queries all stop areas and stop points (those not already in
            stop areas) within locality, ordered by name and indicator.

            :param group_areas: Consolidate stops into stop areas.
        """
        stops = (
            db.session.query(
                utils.table_name(StopPoint).label("table_name"),
                StopPoint.atco_code.label("code"),
                StopPoint.name.label("name"),
                StopPoint.short_ind.label("short_ind"),
                StopPoint.admin_area_ref.label("admin_area_ref"),
                StopPoint.stop_type.label("stop_type"),
                StopPoint.stop_area_ref.label("stop_area_ref")
            )
            .filter(StopPoint.locality_ref == self.code)
        )

        if group_areas:
            stops_not_areas = (
                stops
                .outerjoin(StopPoint.stop_area)
                .filter(db.or_(StopPoint.stop_area_ref.is_(None),
                               StopArea.locality_ref != self.code))
            )
            stop_areas = (
                db.session.query(
                    utils.table_name(StopArea).label("table_name"),
                    StopArea.code.label("code"),
                    StopArea.name.label("name"),
                    StopArea.stop_count.label("short_ind"),
                    StopArea.admin_area_ref.label("admin_area_ref"),
                    StopArea.stop_area_type.label("stop_type"),
                    db.literal_column("NULL").label("stop_area_ref")
                )
                .join(StopArea.stop_points)
                .group_by(StopArea.code)
                .filter(StopArea.locality_ref == self.code)
            )
            subquery = stops_not_areas.union(stop_areas).subquery()
            query = (
                db.session.query(subquery)
                .join(_ns, _ns.c.string == subquery.c.short_ind)
                .order_by(subquery.c.name, _ns.c.index)
            )

        else:
            query = stops.order_by(StopPoint.name, StopPoint.ind_index)

        return query.all()


class StopArea(utils.BaseModel):
    """ NaPTAN stop areas, eg bus interchanges. """
    __tablename__ = "stop_area"

    code = db.Column(db.VARCHAR(12), primary_key=True)
    name = db.Column(db.Text, nullable=False, index=True)
    admin_area_ref = db.Column(
        db.VARCHAR(3),
        db.ForeignKey("admin_area.code", ondelete="CASCADE"),
        nullable=False, index=True
    )
    locality_ref = db.Column(
        db.VARCHAR(8),
        db.ForeignKey("locality.code", ondelete="CASCADE"),
        index=True
    )
    stop_area_type = db.Column(db.VARCHAR(4), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    easting = db.deferred(db.Column(db.Integer, nullable=False))
    northing = db.deferred(db.Column(db.Integer, nullable=False))
    modified = db.deferred(db.Column(db.DateTime))

    stop_points = db.relationship(
        "StopPoint", backref="stop_area",
        order_by="StopPoint.name, StopPoint.ind_index"
    )

    def __repr__(self):
        return "<StopArea(%r)>" % self.code

    @hybrid.hybrid_property
    def stop_count(self):
        """ Counts number of stops in area using the ORM. """
        return len(self.stop_points)

    @stop_count.expression
    def stop_count(cls):
        """ ORM expression finding the number of associated stop points.
            Requires an inner join with stop points and grouped by stop area
            code.
        """
        return db.cast(db.func.count(cls.code), db.Text)

    def get_stops_lines(self):
        """ Queries all stops associated with a stop area, sorted naturally, and
            a list of services for every stop, also sorted naturally.
        """
        subquery_lines = (
            db.session.query(Service.line)
            .join(Service.patterns)
            .join(JourneyPattern.links)
            .filter(JourneyLink.stop_point_ref == StopPoint.atco_code)
            .group_by(Service.line)
            .order_by(Service.line_index)
        ).as_scalar()

        query_stops = (
            db.session.query(StopPoint, db.func.array(subquery_lines))
            .select_from(StopPoint)
            .filter(StopPoint.stop_area_ref == self.code)
            .order_by(StopPoint.name, StopPoint.ind_index)
        )

        return query_stops.all()


class StopPoint(utils.BaseModel):
    """ NaPTAN stop points, eg bus stops. """
    __tablename__ = "stop_point"

    atco_code = db.Column(db.VARCHAR(12), primary_key=True)
    naptan_code = db.Column(db.VARCHAR(9), index=True, unique=True, nullable=False)
    name = db.Column(db.Text, nullable=False, index=True)
    landmark = db.Column(db.Text)
    street = db.Column(db.Text)
    crossing = db.Column(db.Text)
    indicator = db.Column(db.Text, default="", nullable=False)
    short_ind = db.Column(db.Text, index=True, default="", nullable=False)
    locality_ref = db.Column(
        db.VARCHAR(8),
        db.ForeignKey("locality.code", ondelete="CASCADE"),
        nullable=False, index=True
    )
    admin_area_ref = db.Column(
        db.VARCHAR(3),
        db.ForeignKey("admin_area.code", ondelete="CASCADE"),
        nullable=False, index=True
    )
    stop_area_ref = db.Column(
        db.VARCHAR(12),
        db.ForeignKey("stop_area.code", ondelete="CASCADE"),
        index=True
    )
    stop_type = db.Column(db.VARCHAR(3), nullable=False)
    bearing = db.Column(db.VARCHAR(2))
    latitude = db.Column(db.Float, nullable=False, index=True)
    longitude = db.Column(db.Float, nullable=False, index=True)
    easting = db.deferred(db.Column(db.Integer, nullable=False))
    northing = db.deferred(db.Column(db.Integer, nullable=False))
    modified = db.deferred(db.Column(db.DateTime))

    # Access to index for natural sort - only need it for ordering queries
    ind_index = db.deferred(db.select([_ns.c.index])
                            .where(_ns.c.string == short_ind))

    _join_other = db.and_(
        db.foreign(stop_area_ref).isnot(None),
        db.remote(stop_area_ref) == db.foreign(stop_area_ref),
        db.remote(atco_code) != db.foreign(atco_code)
    )
    other_stops = db.relationship(
        "StopPoint",
        primaryjoin=_join_other,
        uselist=True,
        order_by="StopPoint.name, StopPoint.ind_index"
    )
    patterns = db.relationship(
        "JourneyLink",
        backref=db.backref("stops", uselist=True))
    services = db.relationship(
        "Service",
        secondary="join(JourneyLink, JourneyPattern, "
                  "JourneyLink.pattern_ref == JourneyPattern.id)",
        primaryjoin="JourneyLink.stop_point_ref == StopPoint.atco_code",
        secondaryjoin="Service.code == JourneyPattern.service_ref",
        backref=db.backref("stops", uselist=True),
        order_by="Service.line_index, Service.description"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Declared in case it needs to be defined for stops near a point
        distance = None

    def __repr__(self):
        if "atco_code" in self.__dict__:
            repr_text = "<StopPoint(atco_code=%r)>" % self.atco_code
        else:
            repr_text = "<StopPoint(naptan_code=%r)>" % self.naptan_code

        return repr_text

    @classmethod
    def within_box(cls, box):
        """ Finds all stop points within a box with latitude and longitude
            coordinates for each side.

            :param box: BoundingBox object with north, east, south and west
            attributes
            :returns: Unordered list of StopPoint objects
        """
        try:
            nearby_stops = cls.query.filter(
                db.between(StopPoint.latitude, box.south, box.north),
                db.between(StopPoint.longitude, box.west, box.east)
            ).all()
        except AttributeError:
            raise TypeError("Box %r is not a valid BoundingBox object." % box)

        return nearby_stops

    @classmethod
    def in_range(cls, latitude, longitude):
        """ Finds stop points in range of lat/long coordinates.

            Returns an ordered list of stop points and their distances from
            said coordinates.

            :param latitude: Latitude of centre point
            :param longitude: Longitude of centre point
            :returns: List of StopPoint objects with distance attribute added
            and sorted.
        """
        box = location.bounding_box(latitude, longitude, MAX_DIST)
        nearby_stops = cls.within_box(box)

        stops = []
        for stop in nearby_stops:
            dist = location.get_distance((latitude, longitude),
                                         (stop.latitude, stop.longitude))
            if dist < MAX_DIST:
                stop.distance = dist
                stops.append(stop)

        return sorted(stops, key=lambda s: s.distance)

    def to_geojson(self):
        """ Outputs stop point data in GeoJSON format.

            :returns: JSON-serializable dict.
        """
        title_ind = " (%s)" % self.indicator if self.indicator else ""
        geojson = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [self.longitude, self.latitude]
            },
            "properties": {
                "atcoCode": self.atco_code,
                "naptanCode": self.naptan_code,
                "title": self.name + title_ind,
                "name": self.name,
                "indicator": self.short_ind,
                "street": self.street,
                "bearing": self.bearing,
                "stopType": self.stop_type,
                "adminAreaRef": self.admin_area_ref,
            }
        }

        return geojson

    def get_services(self):
        """ Queries all services at this stop, returning a list including the
            directions of these services.
        """
        query_services = (
            db.session.query(
                Service,
                db.func.array_agg(JourneyPattern.direction.distinct()
                                  .label("directions"))
            )
            .join(Service.patterns)
            .join(JourneyPattern.links)
            .filter(JourneyLink.stop_point_ref == self.atco_code)
            .group_by(Service.code)
            .order_by(Service.line_index, Service.description)
        )

        return query_services.all()


class Postcode(utils.BaseModel):
    """ Postcodes with coordinates, derived from the NSPL data. """
    __tablename__ = "postcode"

    index = db.Column(db.VARCHAR(7), primary_key=True)
    text = db.Column(db.VARCHAR(8), index=True, unique=True, nullable=False)
    admin_area_ref = db.Column(
        db.VARCHAR(3),
        db.ForeignKey("admin_area.code", ondelete="CASCADE"),
        nullable=False, index=True
    )
    district_ref = db.Column(
        db.VARCHAR(3),
        db.ForeignKey("district.code", ondelete="CASCADE"),
        index=True
    )
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    easting = db.deferred(db.Column(db.Integer, nullable=False))
    northing = db.deferred(db.Column(db.Integer, nullable=False))

    def __repr__(self):
        if "index" in self.__dict__:
            repr_text = "<Postcode(index=%r)>" % self.index
        else:
            repr_text = "<Postcode(text=%r)>" % self.text

        return repr_text

    def stops_in_range(self):
        """ Returns a list of all stop points within range. """
        return StopPoint.in_range(self.latitude, self.longitude)


class Operator(utils.BaseModel):
    """ Bus/metro service operator. """
    __tablename__ = "operator"

    code = db.Column(db.Text, primary_key=True)

    local_codes = db.relationship("LocalOperator",
                                  order_by="LocalOperator.code",
                                  backref="operator")


class LocalOperator(utils.BaseModel):
    """ Operator codes within regions for each operator. """
    __tablename__ = "local_operator"

    code = db.Column(db.Text, primary_key=True)
    region_ref = db.Column(
        db.VARCHAR(2),
        db.ForeignKey("region.code", ondelete="CASCADE"),
        primary_key=True, index=True
    )
    operator_ref = db.Column(
        db.Text,
        db.ForeignKey("operator.code", ondelete="CASCADE"),
        index=True
    )
    name = db.Column(db.Text, nullable=True)

    services = db.relationship("Service", backref="local_operator")


class Service(utils.BaseModel):
    """ Service group. """
    __tablename__ = "service"

    code = db.Column(db.Text, primary_key=True)
    line = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text, nullable=False)
    local_operator_ref = db.Column(db.Text, nullable=False)
    region_ref = db.Column(
        db.VARCHAR(2),
        db.ForeignKey("region.code", ondelete="CASCADE"),
        nullable=False, index=True
    )
    admin_area_ref = db.Column(
        db.VARCHAR(3),
        db.ForeignKey("admin_area.code", ondelete="CASCADE"),
        nullable=True, index=True
    )
    mode = db.Column(
        db.Integer,
        db.ForeignKey("service_mode.id"),
        nullable=False, index=True
    )

    # Access to index for natural sort
    line_index = db.deferred(db.select([_ns.c.index])
                             .where(_ns.c.string == line))

    __table_args__ = (
        db.ForeignKeyConstraint(
            ["local_operator_ref", "region_ref"],
            ["local_operator.code", "local_operator.region_ref"],
            ondelete="CASCADE"
        ),
        db.Index("ix_service_local_operator_ref_region_ref",
                 "local_operator_ref", "region_ref")
    )

    patterns = db.relationship("JourneyPattern", backref="service")

    def has_mirror(self, selected=None):
        """ Checks directions for all patterns for a service and return the
            right one.
        """
        set_dir = {p.direction for p in self.patterns}
        if set_dir == {True, False}:
            reverse = bool(selected) if selected is not None else False
            has_mirror = True
        else:
            reverse = set_dir.pop()
            has_mirror = False

        return reverse, has_mirror


class JourneyPattern(utils.BaseModel):
    """ Sequences of timing links. """
    __tablename__ = "journey_pattern"

    id = db.Column(db.Integer, primary_key=True, autoincrement=False)
    origin = db.Column(db.Text, nullable=False)
    destination = db.Column(db.Text, nullable=False)
    service_ref = db.Column(
        db.Text,
        db.ForeignKey("service.code", ondelete="CASCADE"),
        nullable=False, index=True
    )
    direction = db.Column(db.Boolean, nullable=False, index=True)
    date_start = db.Column(db.Date, nullable=False)
    date_end = db.Column(db.Date)

    __table_args__ = (
        db.CheckConstraint("date_start <= date_end"),
    )

    links = db.relationship("JourneyLink", backref="pattern",
                            order_by="JourneyLink.sequence")


class JourneyLink(utils.BaseModel):
    """ Stop with timing and journey info..

        Each stop has the following fields:
        - ATCO code for stop as foreign key
        - Whether this is a timing info point (expected to be timetabled)
        - Whether this is a principal point (services must stop here)
        - Whether the bus stops or passes by
    """
    __tablename__ = "journey_link"

    id = db.Column(db.Integer, primary_key=True, autoincrement=False)
    pattern_ref = db.Column(
        db.Integer,
        db.ForeignKey("journey_pattern.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    stop_point_ref = db.Column(
        db.VARCHAR(12),
        db.ForeignKey("stop_point.atco_code", ondelete="CASCADE"),
        nullable=True, index=True
    )
    run_time = db.Column(db.Interval, nullable=True)
    wait_arrive = db.Column(db.Interval, nullable=True)
    wait_leave = db.Column(db.Interval, nullable=True)
    timing_point = db.Column(db.Boolean, nullable=False)
    principal_point = db.Column(db.Boolean, nullable=False)
    stopping = db.Column(db.Boolean, nullable=False)
    sequence = db.Column(db.Integer, index=True)

    __table_args__ = (
        db.UniqueConstraint("pattern_ref", "sequence"),
        db.CheckConstraint("run_time IS NOT NULL AND wait_arrive IS NOT NULL "
                           "OR wait_leave IS NOT NULL")
    )


class JourneySpecificLink(utils.BaseModel):
    """ Journey timing link for a specific journey. """
    __tablename__ = "journey_specific_link"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    journey_ref = db.Column(
        db.Integer,
        db.ForeignKey("journey.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    link_ref = db.Column(
        db.Integer,
        db.ForeignKey("journey_link.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    run_time = db.Column(db.Interval, nullable=True)
    wait_arrive = db.Column(db.Interval, nullable=True)
    wait_leave = db.Column(db.Interval, nullable=True)
    stopping = db.Column(db.Boolean, nullable=True)

    __table_args__ = (
        db.UniqueConstraint("journey_ref", "link_ref"),
    )


class Journey(utils.BaseModel):
    """ Individual vehicle journey for a service. """
    __tablename__ = "journey"

    id = db.Column(db.Integer, primary_key=True, autoincrement=False)
    pattern_ref = db.Column(
        db.Integer,
        db.ForeignKey("journey_pattern.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    start_run = db.Column(
        db.Integer,
        db.ForeignKey("journey_link.id", ondelete="CASCADE"),
        nullable=True, index=True
    )
    end_run = db.Column(
        db.Integer,
        db.ForeignKey("journey_link.id", ondelete="CASCADE"),
        nullable=True, index=True
    )
    departure = db.Column(db.Time, nullable=False)
    # Add frequency?
    # Use bitwise operators for ISO day of week (1-7) and week of month (0-4)
    days = db.Column(db.SmallInteger, db.CheckConstraint("days < 256"),
                     nullable=False)
    weeks = db.Column(db.SmallInteger, db.CheckConstraint("weeks < 32"))

    holidays = db.relationship(
        "BankHoliday", secondary="bank_holidays",
        secondaryjoin="BankHolidays.holidays"
                      ".op('&')(literal(1).op('<<')(BankHoliday.id)) > 0",
        viewonly=True
    )
    holiday_dates = db.relationship(
        "BankHolidayDate",
        secondary="join(BankHolidays, BankHoliday, "
                  "BankHolidays.holidays"
                  ".op('&')(literal(1).op('<<')(BankHoliday.id)) > 0)",
        primaryjoin="Journey.id == BankHolidays.journey_ref",
        secondaryjoin="BankHoliday.id == BankHolidayDate.holiday_ref",
        viewonly=True
    )
    special_days = db.relationship("SpecialPeriod", backref="journey")


class Organisation(utils.BaseModel):
    """ Organisation with operating and non-operating periods. """
    __tablename__ = "organisation"

    code = db.Column(db.Text, primary_key=True)

    periods = db.relationship("OperatingPeriod", backref="organisation")
    excluded = db.relationship("OperatingDate", backref="organisation")
    journeys = db.relationship("Journey", secondary="organisations",
                               backref="organisations")


class Organisations(utils.BaseModel):
    """ Associated table for journeys and organisations. """
    __tablename__ = "organisations"

    org_ref = db.Column(
        db.Text,
        db.ForeignKey("organisation.code", ondelete="CASCADE"),
        primary_key=True, index=True
    )
    journey_ref = db.Column(
        db.Integer,
        db.ForeignKey("journey.id", ondelete="CASCADE"),
        primary_key=True, index=True
    )
    operational = db.Column(db.Boolean, nullable=False)
    working = db.Column(db.Boolean, nullable=False)


class OperatingDate(utils.BaseModel):
    """ Dates to be excluded from operating periods. As they are not related
        to operating periods they will have higher priority.
    """
    __tablename__ = "operating_date"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    org_ref = db.Column(
        db.Text,
        db.ForeignKey("organisation.code", ondelete="CASCADE"),
        nullable=False, index=True
    )
    date = db.Column(db.Date, nullable=False)
    working = db.Column(db.Boolean, nullable=False)


class OperatingPeriod(utils.BaseModel):
    """ List of operating periods. """
    __tablename__ = "operating_period"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    org_ref = db.Column(
        db.Text,
        db.ForeignKey("organisation.code", ondelete="CASCADE"),
        nullable=False, index=True
    )
    date_start = db.Column(db.Date, nullable=False)
    date_end = db.Column(db.Date, nullable=False)
    working = db.Column(db.Boolean, nullable=False)

    __table_args__ = (
        db.CheckConstraint("date_start <= date_end"),
    )


class SpecialPeriod(utils.BaseModel):
    """ Special days specified by journeys. """
    __tablename__ = "special_period"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    journey_ref = db.Column(
        db.Integer,
        db.ForeignKey("journey.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    date_start = db.Column(db.Date)
    date_end = db.Column(db.Date)
    operational = db.Column(db.Boolean, nullable=False)

    __table_args__ = (
        db.CheckConstraint("date_start <= date_end"),
    )


class BankHolidayDate(utils.BaseModel):
    """ Bank holiday dates. """
    __tablename__ = "bank_holiday_date"

    holiday_ref = db.Column(
        db.Integer,
        db.ForeignKey("bank_holiday.id"),
        primary_key=True, index=True
    )
    date = db.Column(db.Date, primary_key=True)


class BankHolidays(utils.BaseModel):
    """ Bank holidays associated with journeys """
    __tablename__ = "bank_holidays"

    holidays = db.Column(db.Integer, index=True, primary_key=True,
                         autoincrement=False)
    journey_ref = db.Column(
        db.Integer,
        db.ForeignKey("journey.id", ondelete="CASCADE"),
        primary_key=True, index=True
    )
    operational = db.Column(db.Boolean)
