"""
Models for the nextbus database.
"""
import sqlalchemy.dialects.postgresql as pg_sql
from sqlalchemy.ext import hybrid

from nextbus import db, location


MIN_GROUPED = 72
MAX_DIST = 500


def table_name(model):
    """ Returns column with literal name of model table. """
    return db.literal_column("'%s'" % model.__tablename__)


class BaseMixin(object):
    """ Adds functionality to the SQLAlchemy model class. """
    __table__ = None

    def _asdict(self):
        """ Returns a dictionary of currently loaded columns in a model object.
            Any deferred columns or relationships will not be included.
        """
        return {attr: value for attr, value in self.__dict__.items()
                if attr in self.__table__.columns}


class Region(db.Model):
    """ NPTG region. """
    __tablename__ = "region"

    code = db.Column(db.VARCHAR(2), primary_key=True)
    name = db.Column(db.Text, index=True, nullable=False)
    modified = db.deferred(db.Column(db.DateTime))
    tsv_name = db.deferred(db.Column(pg_sql.TSVECTOR))

    areas = db.relationship("AdminArea", backref="region", innerjoin=True,
                            order_by="AdminArea.name")

    __table_args__ = (
        db.Index("ix_region_tsvector_name", "tsv_name", postgresql_using="gin"),
    )

    def __repr__(self):
        return "<Region(%r)>" % self.code

    def list_areas(self):
        """ Queries a list of districts and areas (that do not contain any
            districts) within the region, sorted by name.
        """
        query_areas = (
            db.session.query(
                db.case([(District.code.is_(None), table_name(AdminArea))],
                        else_=table_name(District)).label("table"),
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


class AdminArea(db.Model):
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
    tsv_name = db.deferred(db.Column(pg_sql.TSVECTOR))

    districts = db.relationship("District", backref="admin_area", order_by="District.name")
    localities = db.relationship("Locality", backref="admin_area", innerjoin=True,
                                 order_by="Locality.name")
    postcodes = db.relationship("Postcode", backref="admin_area", innerjoin=True,
                                order_by="Postcode.text")
    stop_points = db.relationship("StopPoint", backref="admin_area", innerjoin=True,
                                  order_by="StopPoint.name, StopPoint.short_ind")
    stop_areas = db.relationship("StopArea", backref="admin_area", innerjoin=True,
                                 order_by="StopArea.name")

    __table_args__ = (
        db.Index("ix_admin_area_tsvector_name", "tsv_name", postgresql_using="gin"),
    )

    def __repr__(self):
        return "<AdminArea(%r)>" % self.code

    def list_localities(self):
        """ Queries all localities that do contain stops or stop areas. """
        query_local = (
            Locality.query
            .distinct(Locality.code, Locality.name)
            .join(Locality.stop_points)
            .filter(Locality.admin_area_ref == self.code)
            .order_by(Locality.name)
        )

        return query_local.all()


class District(db.Model):
    """ NPTG district. """
    __tablename__ = "district"

    code = db.Column(db.VARCHAR(3), primary_key=True)
    name = db.Column(db.Text, index=True, nullable=False)
    admin_area_ref = db.Column(db.VARCHAR(3),
                               db.ForeignKey("admin_area.code", ondelete="CASCADE"),
                               index=True, nullable=False)
    modified = db.deferred(db.Column(db.DateTime))
    tsv_name = db.deferred(db.Column(pg_sql.TSVECTOR))

    localities = db.relationship("Locality", backref="district", order_by="Locality.name")
    postcodes = db.relationship("Postcode", backref="district", order_by="Postcode.text")

    __table_args__ = (
        db.Index("ix_district_tsvector_name", "tsv_name", postgresql_using="gin"),
    )

    def __repr__(self):
        return "<District(%r)>" % self.code

    def list_localities(self):
        """ Queries all localities that do contain stops or stop areas. """
        query_local = (
            Locality.query
            .distinct(Locality.code, Locality.name)
            .join(Locality.stop_points)
            .filter(Locality.district_ref == self.code)
            .order_by(Locality.name)
        )

        return query_local.all()


class Locality(db.Model):
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
    tsv_name = db.deferred(db.Column(pg_sql.TSVECTOR))

    stop_points = db.relationship("StopPoint", backref="locality", innerjoin=True,
                                  order_by="StopPoint.name, StopPoint.short_ind")
    stop_areas = db.relationship("StopArea", backref="locality", innerjoin=True,
                                 order_by="StopArea.name")
    # children = db.relationship("Locality", backref=db.backref("parent", remote_side=[code]),
    #                            order_by="Locality.name")

    __table_args__ = (
        db.Index("ix_locality_tsvector_name", "tsv_name", postgresql_using="gin"),
    )

    def __repr__(self):
        return "<Locality(%r)>" % self.code

    def list_stops(self, group_areas=True):
        """ Queries all stop areas and stop points (those not already in
            stop areas) within locality, ordered by name and indicator.

            :param group_areas: Consolidate stops into stop areas.
        """
        stops = (
            db.session.query(
                table_name(StopPoint).label("table"),
                StopPoint.atco_code.label("code"),
                StopPoint.name.label("name"),
                StopPoint.short_ind.label("short_ind"),
                StopPoint.admin_area_ref.label("admin_area_ref"),
                StopPoint.stop_type.label("stop_type")
            )
            .outerjoin(StopPoint.stop_area)
            .filter(StopPoint.locality_ref == self.code)
        )

        if group_areas:
            stops_not_areas = stops.filter(
                db.or_(StopPoint.stop_area_ref.is_(None),
                       StopArea.locality_ref != self.code)
            )
            stop_areas = (
                db.session.query(
                    table_name(StopArea).label("table"),
                    StopArea.code.label("code"),
                    StopArea.name.label("name"),
                    StopArea.stop_count.label("short_ind"), #pylint: disable=E1101
                    StopArea.admin_area_ref.label("admin_area_ref"),
                    StopArea.stop_area_type.label("stop_type")
                )
                .join(StopArea.stop_points)
                .group_by(StopArea.code)
                .filter(StopArea.locality_ref == self.code)
            )
            query = stops_not_areas.union(stop_areas)

        else:
            query = stops

        return query.order_by("name", "short_ind").all()


class StopArea(BaseMixin, db.Model):
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
    tsv_name = db.deferred(db.Column(pg_sql.TSVECTOR))

    stop_points = db.relationship("StopPoint", backref="stop_area",
                                  order_by="StopPoint.name, StopPoint.short_ind")

    __table_args__ = (
        db.Index("ix_stop_area_tsvector_name", "tsv_name", postgresql_using="gin"),
    )

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


class StopPoint(BaseMixin, db.Model):
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
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    easting = db.deferred(db.Column(db.Integer, nullable=False))
    northing = db.deferred(db.Column(db.Integer, nullable=False))
    modified = db.deferred(db.Column(db.DateTime))
    tsv_both = db.deferred(db.Column(pg_sql.TSVECTOR))
    tsv_name = db.deferred(db.Column(pg_sql.TSVECTOR))
    tsv_street = db.deferred(db.Column(pg_sql.TSVECTOR))

    __table_args__ = (
        db.Index("ix_stop_point_tsvector_both", "tsv_both", postgresql_using="gin"),
        db.Index("ix_stop_point_tsvector_name", "tsv_name", postgresql_using="gin"),
        db.Index("ix_stop_point_tsvector_street", "tsv_street", postgresql_using="gin"),
    )

    def __repr__(self):
        if "atco_code" in self.__dict__:
            repr_text = "<StopPoint(atco_code=%r)>" % self.atco_code
        else:
            repr_text = "<StopPoint(naptan_code=%r)>" % self.naptan_code

        return repr_text

    @classmethod
    def in_range(cls, coord):
        """ Finds stop points in range of lat/long coordinates.

            Returns an ordered list of stop points and their distances from
            said coordinates.

            :param coord: Latitude and longitude as tuple of two floats.
            :returns: List of tuples (stop, distance from coord), sorted by the
            latter value.
        """
        lat_0, long_0, lat_1, long_1 = location.bounding_box(coord, MAX_DIST)
        nearby_stops = cls.query.filter(
            db.between(StopPoint.latitude, lat_0, lat_1),
            db.between(StopPoint.longitude, long_0, long_1)
        ).all()

        stops = []
        for stop in nearby_stops:
            dist = location.get_dist(coord, (stop.latitude, stop.longitude))
            if dist < MAX_DIST:
                stops.append((stop, dist))

        return sorted(stops, key=lambda s: s[1])


class Postcode(db.Model):
    """ Postcodes with coordinates, derived from the NSPL data. """
    __tablename__ = "postcode"
    postcode_regex = r"^([a-zA-Z]{1,2}\d{1,2}[a-zA-Z]?\s*\d{1}[a-zA-Z]{2})$"

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
        return StopPoint.in_range((self.latitude, self.longitude))
