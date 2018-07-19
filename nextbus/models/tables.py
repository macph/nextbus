"""
Models for the nextbus database.
"""
from sqlalchemy.ext import hybrid

from nextbus import db, location
from nextbus.models import types, utils

MIN_GROUPED = 72
MAX_DIST = 500


class Region(utils.BaseModel):
    """ NPTG region. """
    __tablename__ = "region"

    code = db.Column(db.VARCHAR(2), primary_key=True)
    name = db.Column(db.Text, index=True, nullable=False)
    modified = db.deferred(db.Column(db.DateTime))

    areas = db.relationship("AdminArea", backref="region", innerjoin=True,
                            order_by="AdminArea.name")

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
    name = db.Column(db.Text, index=True, nullable=False)
    atco_code = db.deferred(db.Column(db.VARCHAR(3), unique=True, nullable=False))
    region_ref = db.Column(db.VARCHAR(2),
                           db.ForeignKey("region.code", ondelete="CASCADE"),
                           index=True, nullable=False)
    is_live = db.deferred(db.Column(db.Boolean, default=True))
    modified = db.deferred(db.Column(db.DateTime))

    districts = db.relationship("District", backref="admin_area", order_by="District.name")
    localities = db.relationship("Locality", backref="admin_area", innerjoin=True,
                                 order_by="Locality.name")
    postcodes = db.relationship("Postcode", backref="admin_area", innerjoin=True,
                                order_by="Postcode.text")
    stop_points = db.relationship("StopPoint", backref="admin_area", innerjoin=True,
                                  order_by="StopPoint.name, StopPoint.short_ind")
    stop_areas = db.relationship("StopArea", backref="admin_area", innerjoin=True,
                                 order_by="StopArea.name")

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
    name = db.Column(db.Text, index=True, nullable=False)
    admin_area_ref = db.Column(db.VARCHAR(3),
                               db.ForeignKey("admin_area.code", ondelete="CASCADE"),
                               index=True, nullable=False)
    modified = db.deferred(db.Column(db.DateTime))

    localities = db.relationship("Locality", backref="district", order_by="Locality.name")
    postcodes = db.relationship("Postcode", backref="district", order_by="Postcode.text")

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

    # TODO: Fix self-referential foreign key constraints deferring.
    code = db.Column(db.VARCHAR(8), primary_key=True)
    name = db.Column(db.Text, index=True, nullable=False)
    parent_ref = db.deferred(db.Column(db.VARCHAR(8), index=True))
    admin_area_ref = db.Column(db.VARCHAR(3),
                               db.ForeignKey("admin_area.code", ondelete="CASCADE"),
                               index=True, nullable=False)
    district_ref = db.Column(db.VARCHAR(3),
                             db.ForeignKey("district.code", ondelete="CASCADE"),
                             index=True)
    latitude = db.deferred(db.Column(db.Float, nullable=False))
    longitude = db.deferred(db.Column(db.Float, nullable=False))
    easting = db.deferred(db.Column(db.Integer, nullable=False))
    northing = db.deferred(db.Column(db.Integer, nullable=False))
    modified = db.deferred(db.Column(db.DateTime))

    stop_points = db.relationship("StopPoint", backref="locality", innerjoin=True,
                                  order_by="StopPoint.name, StopPoint.short_ind")
    stop_areas = db.relationship("StopArea", backref="locality", innerjoin=True,
                                 order_by="StopArea.name")
    # children = db.relationship("Locality", backref=db.backref("parent", remote_side=[code]),
    #                            order_by="Locality.name")

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
                    StopArea.stop_count.label("short_ind"), #pylint: disable=E1101
                    StopArea.admin_area_ref.label("admin_area_ref"),
                    StopArea.stop_area_type.label("stop_type"),
                    db.literal_column("NULL").label("stop_area_ref")
                )
                .join(StopArea.stop_points)
                .group_by(StopArea.code)
                .filter(StopArea.locality_ref == self.code)
            )
            query = stops_not_areas.union(stop_areas)

        else:
            query = stops

        return query.order_by("name", "short_ind").all()


class StopArea(utils.BaseModel):
    """ NaPTAN stop areas, eg bus interchanges. """
    __tablename__ = "stop_area"

    code = db.Column(db.VARCHAR(12), primary_key=True)
    name = db.Column(db.Text, index=True, nullable=False)
    admin_area_ref = db.Column(db.VARCHAR(3),
                               db.ForeignKey("admin_area.code", ondelete="CASCADE"),
                               index=True, nullable=False)
    locality_ref = db.Column(db.VARCHAR(8),
                             db.ForeignKey("locality.code", ondelete="CASCADE"),
                             index=True)
    stop_area_type = db.Column(db.VARCHAR(4), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    easting = db.deferred(db.Column(db.Integer, nullable=False))
    northing = db.deferred(db.Column(db.Integer, nullable=False))
    modified = db.deferred(db.Column(db.DateTime))

    stop_points = db.relationship("StopPoint", backref="stop_area",
                                  order_by="StopPoint.name, StopPoint.short_ind")

    def __repr__(self):
        return "<StopArea(%r)>" % self.code

    @hybrid.hybrid_property
    def stop_count(self):
        """ Counts number of stops in area using the ORM. """
        return len(self.stop_points)

    @stop_count.expression
    def stop_count(cls): # pylint: disable=E0213
        """ ORM expression finding the number of associated stop points.
            Requires an inner join with stop points and grouped by stop area
            code.
        """
        return db.cast(db.func.count(cls.code), db.Text)


class StopPoint(utils.BaseModel):
    """ NaPTAN stop points, eg bus stops. """
    __tablename__ = "stop_point"

    atco_code = db.Column(db.VARCHAR(12), primary_key=True)
    naptan_code = db.Column(db.VARCHAR(9), index=True, unique=True, nullable=False)
    name = db.Column(db.Text, index=True, nullable=False)
    landmark = db.Column(db.Text)
    street = db.Column(db.Text)
    crossing = db.Column(db.Text)
    indicator = db.Column(db.Text, default="", nullable=False)
    short_ind = db.Column(db.Text, index=True, default="", nullable=False)
    locality_ref = db.Column(db.VARCHAR(8),
                             db.ForeignKey("locality.code", ondelete="CASCADE"),
                             index=True, nullable=False)
    admin_area_ref = db.Column(db.VARCHAR(3),
                               db.ForeignKey("admin_area.code", ondelete="CASCADE"),
                               index=True, nullable=False)
    stop_area_ref = db.Column(db.VARCHAR(12),
                              db.ForeignKey("stop_area.code", ondelete="CASCADE"),
                              index=True)
    stop_type = db.Column(db.VARCHAR(3), nullable=False)
    bearing = db.Column(db.VARCHAR(2))
    latitude = db.Column(db.Float, nullable=False, index=True)
    longitude = db.Column(db.Float, nullable=False, index=True)
    easting = db.deferred(db.Column(db.Integer, nullable=False))
    northing = db.deferred(db.Column(db.Integer, nullable=False))
    modified = db.deferred(db.Column(db.DateTime))

    _join_other = db.and_(
        db.foreign(stop_area_ref).isnot(None),
        db.remote(stop_area_ref) == db.foreign(stop_area_ref),
        db.remote(atco_code) != db.foreign(atco_code)
    )
    other_stops = db.relationship("StopPoint", primaryjoin=_join_other, uselist=True,
                                  order_by="StopPoint.name, StopPoint.short_ind")

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


class Postcode(utils.BaseModel):
    """ Postcodes with coordinates, derived from the NSPL data. """
    __tablename__ = "postcode"

    index = db.Column(db.VARCHAR(7), primary_key=True)
    text = db.Column(db.VARCHAR(8), index=True, unique=True, nullable=False)
    admin_area_ref = db.Column(db.VARCHAR(3),
                               db.ForeignKey("admin_area.code", ondelete="CASCADE"),
                               index=True, nullable=False)
    district_ref = db.Column(db.VARCHAR(3),
                             db.ForeignKey("district.code", ondelete="CASCADE"),
                             index=True)
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

    # local_codes = db.relationship("LocalOperator",
    #                               order_by="LocalOperator.code",
    #                               backref="operator")


class LocalOperator(utils.BaseModel):
    """ Operator codes within regions for each operator. """
    __tablename__ = "local_operator"

    code = db.Column(db.Text, primary_key=True)
    region_ref = db.Column(
        db.VARCHAR(2),
        db.ForeignKey("region.code", ondelete="CASCADE"),
        primary_key=True
    )
    operator_ref = db.Column(
        db.Text,
        db.ForeignKey("operator.code", ondelete="CASCADE"),
        nullable=False
    )
    name = db.Column(db.Text, nullable=True)


class Service(utils.BaseModel):
    """ Service group. """
    __tablename__ = "service"

    code = db.Column(db.Text, primary_key=True)
    origin = db.Column(db.Text, nullable=False)
    destination = db.Column(db.Text, nullable=False)
    date_start = db.Column(db.Date, nullable=False)
    date_end = db.Column(db.Date)
    local_operator_ref = db.Column(db.Text, nullable=False)
    region_ref = db.Column(db.VARCHAR(2), nullable=False)
    mode = db.Column(
        db.Enum(types.ServiceMode, name="service_mode",
                values_callable=types.enum_values),
        nullable=False
    )
    direction = db.Column(
        db.Enum(types.Direction, name="direction",
                values_callable=types.enum_values),
        nullable=False
    )
    # add classification and availability?
    modified = db.deferred(db.Column(db.DateTime))

    # operator = db.relationship("Operator", secondary="LocalOperator",
    #                            uselist=False)
    # lines = db.relationship("ServiceLine", backref="service", order_by="name")

    __table_args__ = (
        db.ForeignKeyConstraint(
            ["local_operator_ref", "region_ref"],
            ["local_operator.code", "local_operator.region_ref"],
            ondelete="CASCADE"
        ),
        db.CheckConstraint("date_start <= date_end")
    )


class ServiceLine(utils.BaseModel):
    """ Line label for a service. """
    __tablename__ = "service_line"

    id = db.Column(db.Text, primary_key=True)
    name = db.Column(db.Text)
    service_ref = db.Column(
        db.Text,
        db.ForeignKey("service.code", ondelete="CASCADE"),
        nullable=False,
        index=True
    )


# Add JourneyPatternInterchange?


class JourneyPattern(utils.BaseModel):
    """ Sequences of timing links. """
    __tablename__ = "journey_pattern"

    id = db.Column(db.Text, primary_key=True)
    service_ref = db.Column(
        db.Text,
        db.ForeignKey("service.code", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    direction = db.Column(
        db.Enum(types.Direction, name="direction",
                values_callable=types.enum_values),
        nullable=False
    )
    modified = db.deferred(db.Column(db.DateTime))

    # sections = db.relationship("JourneySection", secondary="JourneySections",
    #                            back_populates="patterns",
    #                            order_by="JourneySections.sequence")
    # links = db.relationship(
    #     "JourneyLink",
    #     primaryjoin="JourneyPattern.id == JourneySections.pattern_ref",
    #     secondary="join(JourneySections, JourneySection, "
    #               "JourneySections.section_ref == JourneySection.id",
    #     secondaryjoin="JourneySection.id == JourneyLink.section_ref",
    #     back_populates="patterns",
    #     order_by="JourneySections.sequence, sequence"
    # )


class JourneySections(utils.BaseModel):
    """ Sequences of journey sections for a pattern. """
    __tablename__ = "journey_sections"

    pattern_ref = db.Column(
        db.Text,
        db.ForeignKey("journey_pattern.id", ondelete="CASCADE"),
        primary_key=True,
        index=True
    )
    section_ref = db.Column(
        db.Text,
        db.ForeignKey("journey_section.id", ondelete="CASCADE"),
        primary_key=True,
        index=True
    )
    sequence = db.Column(db.Integer, nullable=False, index=True)

    __table_args__ = (
        db.UniqueConstraint("pattern_ref", "sequence"),
    )


class JourneySection(utils.BaseModel):
    """ Sequences of journey timing links. """
    __tablename__ = "journey_section"

    id = db.Column(db.Text, primary_key=True)

    # sections = db.relationship("JourneyPattern", secondary="JourneySections",
    #                            back_populates="sections")
    # links = db.relationship("JourneyLink", backref="section",
    #                         order_by="JourneyLink.sequence")


class JourneyLink(utils.BaseModel):
    """ Link between two stops with timing. """
    __tablename__ = "journey_link"

    id = db.Column(db.Integer, primary_key=True)
    section_ref = db.Column(
        db.Text,
        db.ForeignKey("journey_section.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    stop_start = db.Column(
        db.VARCHAR(12),
        db.ForeignKey("stop_point.atco_code", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    wait_start = db.Column(db.Interval, nullable=False)
    timing_start = db.Column(
        db.Enum(types.StopTiming, name="stop_timing",
                values_callable=types.enum_values),
        nullable=False
    )
    stopping_start = db.Column(db.Boolean, nullable=False)
    stop_end = db.Column(
        db.VARCHAR(12),
        db.ForeignKey("stop_point.atco_code", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    wait_end = db.Column(db.Interval, nullable=False)
    timing_end = db.Column(
        db.Enum(types.StopTiming, name="stop_timing",
                values_callable=types.enum_values),
        nullable=False
    )
    stopping_end = db.Column(db.Boolean, nullable=False)
    run_time = db.Column(db.Interval, nullable=False)
    direction = db.Column(
        db.Enum(types.Direction, name="direction",
                values_callable=types.enum_values)
    )
    # Direction for associated RouteLink
    route_direction = db.Column(
        db.Enum(types.Direction, name="direction",
                values_callable=types.enum_values),
        nullable=False
    )
    sequence = db.Column(db.Integer, index=True)

    # patterns = db.relationship(
    #     "JourneyPattern",
    #     primaryjoin="JourneySection.id == JourneyLink.section_ref",
    #     secondary="join(JourneySection, JourneySections, "
    #               "JourneySection.id == JourneySections.section_ref",
    #     secondaryjoin="JourneyPattern.id == JourneySections.pattern_ref",
    #     back_populates="links"
    # )

    __table_args__ = (
        db.UniqueConstraint("section_ref", "sequence"),
    )


class Journey(utils.BaseModel):
    """ Individual vehicle journey for a service. """
    __tablename__ = "journey"

    code = db.Column(db.Text, primary_key=True)
    service_ref = db.Column(
        db.Text,
        db.ForeignKey("service.code", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    line_ref = db.Column(
        db.Text,
        db.ForeignKey("service_line.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    pattern_ref = db.Column(
        db.Text,
        db.ForeignKey("journey_pattern.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    departure = db.Column(db.Time, nullable=False)
    # Add frequency?
    # Use bitwise operators for ISO day of week (1-7) and week of month (0-4)
    days = db.Column(db.Integer, db.CheckConstraint("days < 256"),
                     nullable=False)
    weeks = db.Column(db.Integer, db.CheckConstraint("weeks < 32"))

    # organisations = db.relationship("Organisation", secondary="Organisations",
    #                                 back_populates="journeys")
    # holidays = db.relationship("Holiday", secondary="Holidays",
    #                            back_populates="journeys")
    # holiday_dates = db.relationship(
    #     "BankHolidayDate", secondary="BankHolidays",
    #     secondaryjoin="BankHolidays.name == BankHolidayDate.name"
    # )
    # special_days = db.relationship("SpecialDay", backref="journey")


class Organisation(utils.BaseModel):
    """ Organisation with operating and non-operating periods. """
    __tablename__ = "organisation"

    code = db.Column(db.Text, primary_key=True)

    # periods = db.relationship("OperatingPeriod", backref="organisation")
    # excluded = db.relationship("OperatingDate", backref="organisation")
    # journeys = db.relationship("Journey", secondary="Organisations",
    #                            back_populates="organisations")


class Organisations(utils.BaseModel):
    """ Associated table for journeys and organisations. """
    __tablename__ = "organisations"

    org_ref = db.Column(
        db.Text,
        db.ForeignKey("organisation.code", ondelete="CASCADE"),
        primary_key=True
    )
    journey_ref = db.Column(
        db.Text,
        db.ForeignKey("journey.code", ondelete="CASCADE"),
        primary_key=True
    )
    operational = db.Column(db.Boolean, nullable=False)
    working = db.Column(db.Boolean, nullable=False)


class OperatingDate(utils.BaseModel):
    """ Dates to be excluded from operating periods. As they are not related
        to operating periods they will have higher priority.
    """
    __tablename__ = "operating_date"

    id = db.Column(db.Integer, primary_key=True)
    org_ref = db.Column(
        db.Text,
        db.ForeignKey("organisation.code", ondelete="CASCADE"),
        nullable=False
    )
    date = db.Column(db.Date, nullable=False)
    working = db.Column(db.Boolean, nullable=False)


class OperatingPeriod(utils.BaseModel):
    """ List of operating periods. """
    __tablename__ = "operating_period"

    id = db.Column(db.Integer, primary_key=True)
    org_ref = db.Column(
        db.Text,
        db.ForeignKey("organisation.code", ondelete="CASCADE"),
        nullable=False
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

    id = db.Column(db.Integer, primary_key=True)
    journey_ref = db.Column(
        db.Text,
        db.ForeignKey("journey.code", ondelete="CASCADE"),
    )
    date_start = db.Column(db.Date)
    date_end = db.Column(db.Date)
    operational = db.Column(db.Boolean, nullable=False)

    __table_args__ = (
        db.CheckConstraint("date_start <= date_end"),
        db.UniqueConstraint("journey_ref", "date_start", "date_end")
    )


class BankHolidayDate(utils.BaseModel):
    """ Bank holiday dates. """
    __tablename__ = "bank_holiday_date"

    name = db.Column(
        db.Enum(types.BankHoliday, name="bank_holiday",
                values_callable=types.enum_values),
        primary_key=True
    )
    date = db.Column(db.Date, primary_key=True)


class BankHolidays(utils.BaseModel):
    """ Bank holidays associated with journeys """
    __tablename__ = "bank_holidays"

    name = db.Column(
        db.Enum(types.BankHoliday, name="bank_holiday",
                values_callable=types.enum_values),
        primary_key=True
    )
    journey_ref = db.Column(
        db.Text,
        db.ForeignKey("journey.code", ondelete="CASCADE"),
        primary_key=True
    )
    operational = db.Column(db.Boolean)
