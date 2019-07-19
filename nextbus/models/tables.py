"""
Models for the nextbus database.
"""
import re

import sqlalchemy.dialects.postgresql as pg

from nextbus import db, location
from nextbus.models import utils

MIN_GROUPED = 72
MAX_DIST = 500

# Aliases for tables or views not yet defined
_natural_sort = db.table("natural_sort", db.column("string"),
                         db.column("index"))
_stop_point = db.table("stop_point", db.column("atco_code"),
                       db.column("stop_area_ref"), db.column("active"))
_service = db.table("service", db.column("id"), db.column("line"))
_pattern = db.table("journey_pattern", db.column("id"),
                    db.column("service_ref"))
_link = db.table("journey_link", db.column("pattern_ref"),
                 db.column("stop_point_ref"))


class ServiceMode(db.Model):
    """ Lookup table for service modes, eg bus and tram. """
    __tablename__ = "service_mode"

    id = db.Column(db.Integer, primary_key=True, autoincrement=False)
    name = db.Column(db.Text, nullable=False, unique=True)


@db.event.listens_for(ServiceMode.__table__, "after_create")
def _insert_service_modes(target, connection, **kw):
    """ Inserts service mode IDs and names after creating lookup table. """
    statement = target.insert().values([
        {"id": 1, "name": "bus"},
        {"id": 2, "name": "coach"},
        {"id": 3, "name": "tram"},
        {"id": 4, "name": "metro"},
        {"id": 5, "name": "underground"}
    ])
    connection.execute(statement)


class BankHoliday(db.Model):
    """ Lookup table for bank holidays. """
    __tablename__ = "bank_holiday"

    id = db.Column(db.Integer, primary_key=True, autoincrement=False)
    name = db.Column(db.Text, nullable=False, unique=True)

    dates = db.relationship("BankHolidayDate", backref="bank_holiday",
                            innerjoin=True, lazy="raise")


@db.event.listens_for(BankHoliday.__table__, "after_create")
def _insert_bank_holidays(target, connection, **kw):
    """ Inserts bank holiday IDs and names after creating lookup table. """
    statement = target.insert().values([
        {"id": 1, "name": "NewYearsDay"},
        {"id": 2, "name": "Jan2ndScotland"},
        {"id": 3, "name": "GoodFriday"},
        {"id": 4, "name": "EasterMonday"},
        {"id": 5, "name": "MayDay"},
        {"id": 6, "name": "SpringBank"},
        {"id": 7, "name": "LateSummerBankHolidayNotScotland"},
        {"id": 8, "name": "AugustBankHolidayScotland"},
        {"id": 9, "name": "ChristmasDay"},
        {"id": 10, "name": "BoxingDay"},
        {"id": 11, "name": "ChristmasDayHoliday"},
        {"id": 12, "name": "BoxingDayHoliday"},
        {"id": 13, "name": "NewYearsDayHoliday"},
        {"id": 14, "name": "ChristmasEve"},
        {"id": 15, "name": "NewYearsEve"},
    ])
    connection.execute(statement)


class BankHolidayDate(db.Model):
    """ Bank holiday dates. """
    __tablename__ = "bank_holiday_date"

    holiday_ref = db.Column(
        db.Integer,
        db.ForeignKey("bank_holiday.id"),
        primary_key=True, index=True
    )
    date = db.Column(db.Date, primary_key=True)


@db.event.listens_for(BankHolidayDate.__table__, "after_create")
def _insert_bank_holiday_dates(target, connection, **kw):
    """ Inserts bank holiday dates after creating table. """
    statement = target.insert().values([
        {"holiday_ref": 13, "date": "2017-01-02"},
        {"holiday_ref": 2, "date": "2017-01-02"},
        {"holiday_ref": 3, "date": "2017-04-14"},
        {"holiday_ref": 4, "date": "2017-04-17"},
        {"holiday_ref": 5, "date": "2017-05-01"},
        {"holiday_ref": 6, "date": "2017-05-29"},
        {"holiday_ref": 8, "date": "2017-08-05"},
        {"holiday_ref": 7, "date": "2017-08-28"},
        {"holiday_ref": 9, "date": "2017-12-25"},
        {"holiday_ref": 10, "date": "2017-12-26"},
        {"holiday_ref": 1, "date": "2018-01-01"},
        {"holiday_ref": 2, "date": "2018-01-02"},
        {"holiday_ref": 3, "date": "2018-03-30"},
        {"holiday_ref": 4, "date": "2018-04-02"},
        {"holiday_ref": 5, "date": "2018-05-07"},
        {"holiday_ref": 6, "date": "2018-05-28"},
        {"holiday_ref": 8, "date": "2018-08-06"},
        {"holiday_ref": 7, "date": "2018-08-27"},
        {"holiday_ref": 9, "date": "2018-12-25"},
        {"holiday_ref": 10, "date": "2018-12-26"},
        {"holiday_ref": 1, "date": "2019-01-01"},
        {"holiday_ref": 2, "date": "2019-01-02"},
        {"holiday_ref": 3, "date": "2019-04-19"},
        {"holiday_ref": 4, "date": "2019-04-22"},
        {"holiday_ref": 5, "date": "2019-05-06"},
        {"holiday_ref": 6, "date": "2019-05-27"},
        {"holiday_ref": 8, "date": "2019-08-05"},
        {"holiday_ref": 7, "date": "2019-08-26"},
        {"holiday_ref": 9, "date": "2019-12-25"},
        {"holiday_ref": 10, "date": "2019-12-26"},
    ])
    connection.execute(statement)


class Region(db.Model):
    """ NPTG region. """
    __tablename__ = "region"

    code = db.Column(db.VARCHAR(2), primary_key=True)
    name = db.Column(db.Text, nullable=False, index=True)
    modified = db.deferred(db.Column(db.DateTime))

    areas = db.relationship("AdminArea", backref="region", innerjoin=True,
                            order_by="AdminArea.name", lazy="raise")
    patterns = db.relationship("JourneyPattern", backref="region",
                               innerjoin=True, lazy="raise")

    def __repr__(self):
        return "<Region(%r)>" % self.code


class AdminArea(db.Model):
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
                                order_by="District.name", lazy="raise")
    localities = db.relationship("Locality", backref="admin_area",
                                 innerjoin=True, order_by="Locality.name",
                                 lazy="raise")
    postcodes = db.relationship("Postcode", backref="admin_area",
                                innerjoin=True, order_by="Postcode.text",
                                lazy="raise")
    stop_points = db.relationship(
        "StopPoint", backref="admin_area", innerjoin=True,
        order_by="StopPoint.name, StopPoint.ind_index", lazy="raise"
    )
    stop_areas = db.relationship("StopArea", backref="admin_area",
                                 innerjoin=True, order_by="StopArea.name",
                                 lazy="raise")

    def __repr__(self):
        return "<AdminArea(%r)>" % self.code

    def list_localities(self):
        """ Queries all localities containing active stops. """
        query_local = (
            Locality.query
            .filter(Locality.admin_area_ref == self.code,
                    Locality.stop_points.any(StopPoint.active))
            .order_by(Locality.name)
        )

        return query_local.all()


class District(db.Model):
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
                                 order_by="Locality.name", lazy="raise")
    postcodes = db.relationship("Postcode", backref="district",
                                order_by="Postcode.text", lazy="raise")

    def __repr__(self):
        return "<District(%r)>" % self.code

    def list_localities(self):
        """ Queries all localities containing active stops. """
        query_local = (
            Locality.query
            .filter(Locality.district_ref == self.code,
                    Locality.stop_points.any(StopPoint.active))
            .order_by(Locality.name)
        )

        return query_local.all()


class Locality(db.Model):
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
    latitude = db.deferred(db.Column(db.Float, nullable=False),
                           group="coordinates")
    longitude = db.deferred(db.Column(db.Float, nullable=False),
                            group="coordinates")
    easting = db.deferred(db.Column(db.Integer, nullable=False))
    northing = db.deferred(db.Column(db.Integer, nullable=False))
    modified = db.deferred(db.Column(db.DateTime))

    stop_points = db.relationship(
        "StopPoint", order_by="StopPoint.name, StopPoint.ind_index",
        back_populates="locality", lazy="raise"
    )
    stop_areas = db.relationship("StopArea", backref="locality",
                                 order_by="StopArea.name", lazy="raise")

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
                StopArea.code.label("stop_area_ref")
            )
            .select_from(StopPoint)
            .outerjoin(
                StopArea,
                (StopPoint.stop_area_ref == StopArea.code) & StopArea.active
            )
            .filter(StopPoint.locality_ref == self.code, StopPoint.active)
        )

        if group_areas:
            stops_outside_areas = stops.filter(
                StopPoint.stop_area_ref.is_(None) |
                db.not_(StopArea.active) |
                (StopArea.locality_ref != self.code)
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
                .filter(StopArea.locality_ref == self.code, StopArea.active)
            )
            subquery = stops_outside_areas.union(stop_areas).subquery()
            query = (
                db.session.query(subquery)
                .join(_natural_sort,
                      _natural_sort.c.string == subquery.c.short_ind)
                .order_by(subquery.c.name, _natural_sort.c.index)
            )
        else:
            query = stops.order_by(StopPoint.name, StopPoint.ind_index)

        return query.all()


class StopArea(db.Model):
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
    active = db.Column(db.Boolean, nullable=False, index=True)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    easting = db.deferred(db.Column(db.Integer, nullable=False))
    northing = db.deferred(db.Column(db.Integer, nullable=False))
    modified = db.deferred(db.Column(db.DateTime))

    # Number of stop points associated with this stop area
    stop_count = db.deferred(
        db.select([db.cast(db.func.count(), db.Text)])
        .where((_stop_point.c.stop_area_ref == code) & _stop_point.c.active)
    )

    stop_points = db.relationship(
        "StopPoint", backref="stop_area",
        order_by="StopPoint.name, StopPoint.ind_index", lazy="raise"
    )

    def __repr__(self):
        return "<StopArea(%r)>" % self.code


def _array_lines(code):
    """ Create subquery for an distinct and ordered array of all lines serving a
        stop.
    """
    subquery = (
        db.select([_service.c.line])
        .select_from(
            _service
            .join(_pattern, _pattern.c.service_ref == _service.c.id)
            .join(_link, _link.c.pattern_ref == _pattern.c.id)
        )
        .where(_link.c.stop_point_ref == code)
        .group_by(_service.c.line)
        .order_by(db.select([_natural_sort.c.index])
                  .where(_natural_sort.c.string == _service.c.line))
        .as_scalar()
    )

    return db.func.array(subquery)


class StopPoint(db.Model):
    """ NaPTAN stop points, eg bus stops. """
    __tablename__ = "stop_point"

    atco_code = db.Column(db.VARCHAR(12), primary_key=True)
    naptan_code = db.Column(db.VARCHAR(9), index=True, unique=True,
                            nullable=False)
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
    active = db.Column(db.Boolean, nullable=False, index=True)
    bearing = db.Column(db.VARCHAR(2))
    latitude = db.Column(db.Float, nullable=False, index=True)
    longitude = db.Column(db.Float, nullable=False, index=True)
    easting = db.deferred(db.Column(db.Integer, nullable=False))
    northing = db.deferred(db.Column(db.Integer, nullable=False))
    modified = db.deferred(db.Column(db.DateTime))

    # Access to index for natural sort - only need it for ordering queries
    ind_index = db.deferred(db.select([_natural_sort.c.index])
                            .where(_natural_sort.c.string == short_ind))
    # Distinct list of lines serving this stop
    lines = db.deferred(_array_lines(atco_code))

    locality = db.relationship("Locality", uselist=False,
                               back_populates="stop_points", lazy="raise")
    other_stops = db.relationship(
        "StopPoint",
        primaryjoin=(
            db.foreign(stop_area_ref).isnot(None) &
            (db.remote(stop_area_ref) == db.foreign(stop_area_ref)) &
            (db.remote(atco_code) != db.foreign(atco_code)) &
            db.remote(active)
        ),
        uselist=True,
        order_by="StopPoint.name, StopPoint.ind_index",
        lazy="raise"
    )
    links = db.relationship("JourneyLink", backref="stop_point", lazy="raise")

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

    @property
    def long_name(self):
        if self.indicator:
            return "%s (%s)" % (self.name, self.indicator)
        else:
            return self.name

    @classmethod
    def within_box(cls, box, *options, active_only=True):
        """ Finds all stop points within a box with latitude and longitude
            coordinates for each side.

            :param box: BoundingBox object with north, east, south and west
            attributes
            :param options: Options for loading model instances, eg load_only
            :param active_only: Active stops only
            :returns: Unordered list of StopPoint objects
        """
        query = cls.query
        if options:
            query = query.options(*options)
        if active_only:
            query = query.filter(cls.active)
        try:
            nearby_stops = query.filter(
                db.between(cls.latitude, box.south, box.north),
                db.between(cls.longitude, box.west, box.east)
            )
        except AttributeError:
            raise TypeError("Box %r is not a valid BoundingBox object." % box)

        return nearby_stops.all()

    @classmethod
    def in_range(cls, latitude, longitude, *options, active_only=True):
        """ Finds stop points in range of lat/long coordinates.

            Returns an ordered list of stop points and their distances from
            said coordinates.

            :param latitude: Latitude of centre point
            :param longitude: Longitude of centre point
            :param options: Options for loading model instances, eg load_only
            :param active_only: Active stops only
            :returns: List of StopPoint objects with distance attribute added
            and sorted.
        """
        box = location.bounding_box(latitude, longitude, MAX_DIST)
        nearby_stops = cls.within_box(box, *options, active_only=active_only)

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
        geojson = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [self.longitude, self.latitude]
            },
            "properties": {
                "atcoCode": self.atco_code,
                "smsCode": self.naptan_code,
                "title": self.long_name,
                "name": self.name,
                "indicator": self.short_ind,
                "street": self.street,
                "bearing": self.bearing,
                "stopType": self.stop_type,
                "locality": self.locality.name,
                "adminAreaRef": self.admin_area_ref,
            }
        }

        return geojson

    def get_services(self):
        """ Queries and returns two datasets for services and operators at this
            stoplist including the origin and destination of these services,
            grouped by service ID and direction. Services are also checked for
            whether they terminate at this stop or not. Operators are returned
            as a dict of local operator codes and operator names.
        """
        # Checks if associated link is not last in sequence
        link = db.aliased(JourneyLink)
        next_link = (
            db.session.query(link.id)
            .filter(link.pattern_ref == JourneyLink.pattern_ref,
                    link.sequence == JourneyLink.sequence + 1)
            .as_scalar()
        )

        # Give service instance name in keyed tuple object
        service = db.aliased(Service, name="service")
        operator = pg.array((
            LocalOperator.code,
            db.func.coalesce(Operator.name, LocalOperator.name)
        ))
        query_services = (
            db.session.query(
                service,
                JourneyPattern.direction,
                db.func.string_agg(JourneyPattern.origin.distinct(), ' / ')
                .label("origin"),
                db.func.string_agg(JourneyPattern.destination.distinct(), ' / ')
                .label("destination"),
                (db.func.count(next_link) == 0).label("terminates"),
                pg.array_agg(db.distinct(operator)).label("operators")
            )
            .join(service.patterns)
            .join(JourneyPattern.links)
            .join(JourneyPattern.local_operator)
            .outerjoin(LocalOperator.operator)
            .filter(JourneyLink.stop_point_ref == self.atco_code)
            .group_by(service.id, JourneyPattern.direction)
            .order_by(service.line_index, service.description,
                      JourneyPattern.direction)
        )

        services = query_services.all()
        operators = {}
        for sv in services:
            operators.update(sv.operators)

        return services, operators

    def to_full_json(self):
        """ Produces full data for stop point in JSON format, including services
            and locality data.
        """
        services, operators = self.get_services()
        json = {
            "atcoCode": self.atco_code,
            "smsCode": self.naptan_code,
            "title": self.long_name,
            "name": self.name,
            "indicator": self.short_ind,
            "street": self.street,
            "crossing": self.crossing,
            "landmark": self.landmark,
            "bearing": self.bearing,
            "stopType": self.stop_type,
            "adminAreaRef": self.admin_area_ref,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "active": self.active,
            "adminArea": {
                "code": self.admin_area.code,
                "name": self.admin_area.name,
            },
            "district": {
                "code": self.locality.district.code,
                "name": self.locality.district.name,
            } if self.locality.district is not None else None,
            "locality": {
                "code": self.locality.code,
                "name": self.locality.name,
            },
            "services": [{
                "id": s.service.id,
                "description": s.service.description,
                "line": s.service.line,
                "direction": "inbound" if s.direction else "outbound",
                "reverse": s.direction,
                "origin": s.origin,
                "destination": s.destination,
                "terminates": s.terminates,
                "operatorCodes": list(operators)
            } for s in services],
            "operators": [{
                "code": code, "name": name
            } for code, name in operators.items()]
        }

        return json


class Postcode(db.Model):
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
            repr_text = "index=%r" % self.index
        else:
            repr_text = "text=%r" % self.text

        return "<Postcode(%s)>" % repr_text

    def stops_in_range(self, *options):
        """ Returns a list of all stop points within range.

            :param options: Options for loading model instances, eg load_only
            :returns: List of StopPoint objects with distance attribute added
            and sorted.
        """
        return StopPoint.in_range(self.latitude, self.longitude, *options)


class Operator(db.Model):
    """ Bus/metro service operator. """
    __tablename__ = "operator"

    SPLIT_ADDRESS = re.compile(r"\s*,\s*")

    code = db.Column(db.Text, primary_key=True)
    region_ref = db.Column(
        db.VARCHAR(2),
        db.ForeignKey("region.code", ondelete="CASCADE"),
        nullable=False, index=True
    )
    name = db.Column(db.Text, nullable=False)
    mode = db.Column(
        db.Integer,
        db.ForeignKey("service_mode.id"),
        nullable=False, index=True
    )
    licence_name = db.deferred(db.Column(db.Text, nullable=True))
    email = db.deferred(db.Column(db.Text), group="contacts")
    address = db.deferred(db.Column(db.Text), group="contacts")
    website = db.deferred(db.Column(db.Text), group="contacts")
    twitter = db.deferred(db.Column(db.Text), group="contacts")

    local_codes = db.relationship(
        "LocalOperator",
        backref=db.backref("operator", innerjoin=True, uselist=False),
        order_by="LocalOperator.code",
        lazy="raise"
    )
    patterns = db.relationship(
        "JourneyPattern",
        backref=db.backref("operator", innerjoin=True, viewonly=True,
                           uselist=False),
        secondary="local_operator",
        viewonly=True,
        lazy="raise"
    )

    @property
    def split_address(self):
        if "address" not in db.inspect(self).unloaded:
            return self.SPLIT_ADDRESS.split(self.address)
        else:
            return None


class LocalOperator(db.Model):
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

    patterns = db.relationship(
        "JourneyPattern",
        backref=db.backref("local_operator", innerjoin=True, uselist=False,
                           viewonly=True),
        viewonly=True,
        lazy="raise"
    )


class Service(db.Model):
    """ Service group. """
    __tablename__ = "service"

    id = db.Column(db.Integer, primary_key=True, autoincrement=False)
    code = db.Column(db.Text)
    line = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text, nullable=False)
    mode = db.Column(
        db.Integer,
        db.ForeignKey("service_mode.id"),
        nullable=False, index=True
    )

    # Access to index for natural sort
    line_index = db.deferred(db.select([_natural_sort.c.index])
                             .where(_natural_sort.c.string == line))
    # Get mode name for service
    mode_name = db.deferred(db.select([ServiceMode.name])
                            .where(ServiceMode.id == mode))

    patterns = db.relationship("JourneyPattern", backref="service",
                               innerjoin=True, lazy="raise")
    operators = db.relationship(
        "Operator",
        backref=db.backref("services", uselist=True, viewonly=True,
                           order_by="Service.line_index, Service.description"),
        primaryjoin="Service.id == JourneyPattern.service_ref",
        secondary="join(JourneyPattern, LocalOperator, "
                  "(JourneyPattern.local_operator_ref == LocalOperator.code) & "
                  "(JourneyPattern.region_ref == LocalOperator.region_ref))",
        secondaryjoin="LocalOperator.operator_ref == Operator.code",
        order_by="Operator.name",
        viewonly=True,
        lazy="raise"
    )
    regions = db.relationship(
        "Region",
        backref=db.backref("services", uselist=True,
                           order_by="Service.line_index, Service.description"),
        primaryjoin="Service.id == JourneyPattern.service_ref",
        secondary="journey_pattern",
        secondaryjoin="JourneyPattern.region_ref == Region.code",
        order_by="Region.name",
        lazy="raise"
    )

    def has_mirror(self, selected=None):
        """ Checks directions for all patterns for a service and return the
            right one.

            :param selected: Direction initially selected.
            :returns: New direction based on initial direction or new one if
            no mirror exists, and boolean indicating a mirror exists.
        """
        set_dir = {p.direction for p in self.patterns}
        if set_dir == {True, False}:
            reverse = bool(selected) if selected is not None else False
            has_mirror = True
        else:
            reverse = set_dir.pop()
            has_mirror = False

        return reverse, has_mirror

    def similar(self, direction=None, threshold=None):
        """ Find all services sharing stops with this service in a direction.

            :param direction: Service direction, or None to include both.
            :param threshold: Minimum similarity value, or None to include all.
        """
        id_ = db.bindparam("id", self.id)
        similar0 = (
            db.session.query(ServicePair.service0.label("id"),
                             ServicePair.direction0.label("direction"))
            .filter(ServicePair.service1 == id_)
        )
        similar1 = (
            db.session.query(ServicePair.service1.label("id"),
                             ServicePair.direction1.label("direction"))
            .filter(ServicePair.service0 == id_)
        )

        if direction is not None:
            dir_ = db.bindparam("dir", direction)
            similar0 = similar0.filter(ServicePair.direction1 == dir_)
            similar1 = similar1.filter(ServicePair.direction0 == dir_)

        if threshold is not None:
            value = db.bindparam("threshold", threshold)
            similar0 = similar0.filter(ServicePair.similarity > value)
            similar1 = similar1.filter(ServicePair.similarity > value)

        service = db.aliased(self, name="service")
        similar = db.union_all(similar0, similar1).alias()

        return (
            db.session.query(
                service,
                JourneyPattern.direction,
                db.func.string_agg(JourneyPattern.origin.distinct(), ' / ')
                .label("origin"),
                db.func.string_agg(JourneyPattern.destination.distinct(), ' / ')
                .label("destination")
            )
            .join(similar, similar.c.id == service.id)
            .join(JourneyPattern,
                  (service.id == JourneyPattern.service_ref) &
                  (similar.c.direction == JourneyPattern.direction))
            .group_by(service, similar.c.direction, JourneyPattern.direction)
            .order_by(service.line_index, service.description,
                      similar.c.direction)
            .all()
        )


class ServicePair(db.Model):
    """ Pairs of services sharing stops, used to find similar services. """
    __tablename__ = "service_pair"

    id = db.Column(db.Integer, primary_key=True, autoincrement=False)
    service0 = db.Column(db.Integer,
                         db.ForeignKey("service.id", ondelete="CASCADE"),
                         nullable=False, index=True)
    direction0 = db.Column(db.Boolean, nullable=False, index=True)
    count0 = db.Column(db.Integer, nullable=False)
    service1 = db.Column(db.Integer,
                         db.ForeignKey("service.id", ondelete="CASCADE"),
                         nullable=False, index=True)
    direction1 = db.Column(db.Boolean, nullable=False, index=True)
    count1 = db.Column(db.Integer, nullable=False)
    similarity = db.Column(db.Float, nullable=False)

    __table_args__ = (
        db.CheckConstraint("service0 < service1"),
    )


class JourneyPattern(db.Model):
    """ Sequences of timing links. """
    __tablename__ = "journey_pattern"

    id = db.Column(db.Integer, primary_key=True, autoincrement=False)
    origin = db.Column(db.Text, nullable=False)
    destination = db.Column(db.Text, nullable=False)

    service_ref = db.Column(
        db.Integer,
        db.ForeignKey("service.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    local_operator_ref = db.Column(db.Text, nullable=False, index=True)
    region_ref = db.Column(
        db.VARCHAR(2),
        db.ForeignKey("region.code", ondelete="CASCADE"),
        nullable=False, index=True
    )

    direction = db.Column(db.Boolean, nullable=False, index=True)
    date_start = db.Column(db.Date, nullable=False)
    date_end = db.Column(db.Date)

    __table_args__ = (
        db.CheckConstraint("date_start <= date_end"),
        db.ForeignKeyConstraint(
            ["local_operator_ref", "region_ref"],
            ["local_operator.code", "local_operator.region_ref"],
            ondelete="CASCADE"
        ),
        db.Index("ix_journey_pattern_local_operator_ref_region_ref",
                 "local_operator_ref", "region_ref")
    )

    links = db.relationship("JourneyLink", backref="pattern", innerjoin=True,
                            order_by="JourneyLink.sequence", lazy="raise")
    journeys = db.relationship("Journey", backref="pattern", innerjoin=True,
                               lazy="raise")


class JourneyLink(db.Model):
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


class JourneySpecificLink(db.Model):
    """ Journey timing link for a specific journey. """
    __tablename__ = "journey_specific_link"

    id = db.Column(db.Integer, primary_key=True, autoincrement=False)
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


class Journey(db.Model):
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
    note_code = db.Column(db.Text)
    note_text = db.Column(db.Text)

    holiday_dates = db.relationship(
        "BankHolidayDate", secondary="bank_holidays",
        secondaryjoin="BankHolidays.holidays.op('&')("
                      "literal(1).op('<<')(BankHolidayDate.holiday_ref)"
                      ") > 0",
        viewonly=True,
        lazy="raise"
    )
    special_days = db.relationship("SpecialPeriod", backref="journey",
                                   lazy="raise")


class Organisation(db.Model):
    """ Organisation with operating and non-operating periods. """
    __tablename__ = "organisation"

    code = db.Column(db.Text, primary_key=True)

    periods = db.relationship("OperatingPeriod", backref="organisation",
                              lazy="raise")
    excluded = db.relationship("ExcludedDate", backref="organisation",
                               lazy="raise")
    journeys = db.relationship("Journey", secondary="organisations",
                               backref="organisations", lazy="raise")


class Organisations(db.Model):
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


class ExcludedDate(db.Model):
    """ Dates to be excluded from operating periods. """
    __tablename__ = "excluded_date"

    id = db.Column(db.Integer, primary_key=True, autoincrement=False)
    org_ref = db.Column(
        db.Text,
        db.ForeignKey("organisation.code", ondelete="CASCADE"),
        nullable=False, index=True
    )
    date = db.Column(db.Date, nullable=False)
    working = db.Column(db.Boolean, nullable=False)


class OperatingPeriod(db.Model):
    """ List of operating periods. """
    __tablename__ = "operating_period"

    id = db.Column(db.Integer, primary_key=True, autoincrement=False)
    org_ref = db.Column(
        db.Text,
        db.ForeignKey("organisation.code", ondelete="CASCADE"),
        nullable=False, index=True
    )
    date_start = db.Column(db.Date, nullable=False)
    date_end = db.Column(db.Date, nullable=True)
    working = db.Column(db.Boolean, nullable=False)


class SpecialPeriod(db.Model):
    """ Special days specified by journeys. """
    __tablename__ = "special_period"

    id = db.Column(db.Integer, primary_key=True, autoincrement=False)
    journey_ref = db.Column(
        db.Integer,
        db.ForeignKey("journey.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    date_start = db.Column(db.Date, nullable=False)
    date_end = db.Column(db.Date, nullable=False)
    operational = db.Column(db.Boolean, nullable=False)


class BankHolidays(db.Model):
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
