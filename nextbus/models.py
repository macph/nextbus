"""
Models for the nextbus database.
"""
from nextbus import db


MIN_GROUPED = 72


class Region(db.Model):
    """ NPTG region. """
    __tablename__ = 'region'

    code = db.Column(db.VARCHAR(2), primary_key=True)
    name = db.Column(db.Text, index=True)
    modified = db.Column(db.DateTime)

    areas = db.relationship('AdminArea', backref='region', order_by='AdminArea.name')

    __table_args__ = (
        db.Index('ix_region_gin_name', db.text("to_tsvector('english', name)"),
                 postgresql_using='gin'),
    )

    def __repr__(self):
        return '<Region(%r, %r)>' % (self.code, self.name)


class AdminArea(db.Model):
    """ NPTG administrative area. """
    __tablename__ = 'admin_area'

    code = db.Column(db.VARCHAR(3), primary_key=True)
    name = db.Column(db.Text, index=True)
    atco_code = db.Column(db.VARCHAR(3), unique=True)
    region_code = db.Column(db.VARCHAR(2),
                            db.ForeignKey('region.code', ondelete='CASCADE'), index=True)
    is_live = db.Column(db.Boolean, default=True)
    modified = db.Column(db.DateTime)

    districts = db.relationship('District', backref='admin_area', order_by='District.name')
    localities = db.relationship('Locality', backref='admin_area', order_by='Locality.name')
    postcodes = db.relationship('Postcode', backref='admin_area', order_by='Postcode.text')
    stop_points = db.relationship('StopPoint', backref='admin_area',
                                  order_by='StopPoint.common_name, StopPoint.short_ind')
    stop_areas = db.relationship('StopArea', backref='admin_area', order_by='StopArea.name')

    __table_args__ = (
        db.Index('ix_admin_area_gin_name', db.text("to_tsvector('english', name)"),
                 postgresql_using='gin'),
    )

    def __repr__(self):
        return '<AdminArea(%r, %r, %r)>' % (self.code, self.atco_code, self.name)


class District(db.Model):
    """ NPTG district. """
    __tablename__ = 'district'

    code = db.Column(db.VARCHAR(3), primary_key=True)
    name = db.Column(db.Text, index=True)
    admin_area_code = db.Column(db.VARCHAR(3),
                                db.ForeignKey('admin_area.code', ondelete='CASCADE'), index=True)
    modified = db.Column(db.DateTime)

    localities = db.relationship('Locality', backref='district', order_by='Locality.name')
    postcodes = db.relationship('Postcode', backref='district', order_by='Postcode.text')

    __table_args__ = (
        db.Index('ix_district_gin_name', db.text("to_tsvector('english', name)"),
                 postgresql_using='gin'),
    )

    def __repr__(self):
        return '<District(%r, %r)>' % (self.code, self.name)


class Locality(db.Model):
    """ NPTG locality. """
    __tablename__ = 'locality'

    # TODO: Fix self-referential foreign keys deferring.
    code = db.Column(db.VARCHAR(8), primary_key=True)
    name = db.Column(db.Text, index=True)
    parent_code = db.Column(db.VARCHAR(8), index=True)
    admin_area_code = db.Column(db.VARCHAR(3),
                                db.ForeignKey('admin_area.code', ondelete='CASCADE'), index=True)
    district_code = db.Column(db.VARCHAR(3),
                              db.ForeignKey('district.code', ondelete='CASCADE'), index=True)
    easting = db.Column(db.Integer)
    northing = db.Column(db.Integer)
    longitude = db.Column(db.Float)
    latitude = db.Column(db.Float)
    modified = db.Column(db.DateTime)

    stop_points = db.relationship('StopPoint', backref='locality',
                                  order_by='StopPoint.common_name, StopPoint.short_ind')
    stop_areas = db.relationship('StopArea', backref='locality', order_by='StopArea.name')
    # children = db.relationship('Locality', backref=db.backref('parent', remote_side=[code]),
    #                            order_by='Locality.name')

    __table_args__ = (
        db.Index('ix_locality_gin_name', db.text("to_tsvector('english', name)"),
                 postgresql_using='gin'),
    )

    def __repr__(self):
        return '<Locality(%r, %r)>' % (self.code, self.name)


class StopArea(db.Model):
    """ NaPTAN stop areas, eg bus interchanges. """
    __tablename__ = 'stop_area'

    code = db.Column(db.VARCHAR(12), primary_key=True)
    name = db.Column(db.Text, index=True)
    admin_area_code = db.Column(db.VARCHAR(3),
                                db.ForeignKey('admin_area.code', ondelete='CASCADE'), index=True)
    locality_code = db.Column(db.VARCHAR(8),
                              db.ForeignKey('locality.code', ondelete='CASCADE'), index=True)
    stop_area_type = db.Column(db.VARCHAR(4))
    easting = db.Column(db.Integer)
    northing = db.Column(db.Integer)
    longitude = db.Column(db.Float)
    latitude = db.Column(db.Float)
    modified = db.Column(db.DateTime)

    stop_points = db.relationship('StopPoint', backref='stop_area',
                                  order_by='StopPoint.common_name, StopPoint.short_ind')

    __table_args__ = (
        db.Index('ix_stop_area_gin_name', db.text("to_tsvector('english', name)"),
                 postgresql_using='gin'),
    )

    def __repr__(self):
        return '<StopArea(%r, %r)>' % (self.code, self.name)


class StopPoint(db.Model):
    """ NaPTAN stop points, eg bus stops. """
    __tablename__ = 'stop_point'
    _text = {'E': 'east', 'N': 'north', 'NE': 'northeast', 'NW': 'northwest',
             'S': 'south', 'SE': 'southeast', 'SW': 'southwest', 'W': 'west'}

    atco_code = db.Column(db.VARCHAR(12), primary_key=True)
    naptan_code = db.Column(db.VARCHAR(9), index=True, unique=True)
    common_name = db.Column(db.Text, index=True)
    short_name = db.Column(db.Text)
    landmark = db.Column(db.Text)
    street = db.Column(db.Text)
    crossing = db.Column(db.Text)
    indicator = db.Column(db.Text)
    short_ind = db.Column(db.Text, index=True)
    locality_code = db.Column(db.VARCHAR(8),
                              db.ForeignKey('locality.code', ondelete='CASCADE'), index=True)
    admin_area_code = db.Column(db.VARCHAR(3),
                                db.ForeignKey('admin_area.code', ondelete='CASCADE'), index=True)
    stop_area_code = db.Column(db.VARCHAR(12),
                               db.ForeignKey('stop_area.code', ondelete='CASCADE'), index=True)
    easting = db.Column(db.Integer)
    northing = db.Column(db.Integer)
    longitude = db.Column(db.Float)
    latitude = db.Column(db.Float)
    stop_type = db.Column(db.VARCHAR(3))
    bearing = db.Column(db.VARCHAR(2))
    modified = db.Column(db.DateTime)

    __table_args__ = (
        db.Index('ix_stop_point_gin_common_name',
                 db.text("to_tsvector('english', common_name)"),
                 postgresql_using='gin'),
        db.Index('ix_stop_point_gin_street',
                 db.text("to_tsvector('english', street)"),
                 postgresql_using='gin'),
    )

    def __repr__(self):
        return '<StopPoint(%r, %r, %r)>' % (self.atco_code, self.naptan_code, self.common_name)

    @property
    def direction(self):
        """ Prints bearing in full (eg 'NW' returns 'northwest'). """
        return self._text.get(self.bearing.upper())

    def serialise(self):
        """ Pass stop data in serialised form. """
        attrs = [
            'atco_code',
            'common_name',
            'indicator',
            'short_ind',
            'latitude',
            'longitude'
        ]

        return {i: getattr(self, i) for i in attrs}


class Postcode(db.Model):
    """ Postcodes with coordinates, derived from the NSPL data. """
    __tablename__ = 'postcode'
    postcode_regex = r"^([a-zA-Z]{1,2}\d{1,2}[a-zA-Z]?\s*\d{1}[a-zA-Z]{2})$"

    index = db.Column(db.VARCHAR(7), primary_key=True)
    text = db.Column(db.VARCHAR(8), index=True, unique=True)
    local_authority_code = db.Column(db.VARCHAR(9))
    admin_area_code = db.Column(db.VARCHAR(3),
                                db.ForeignKey('admin_area.code', ondelete='CASCADE'), index=True)
    district_code = db.Column(db.VARCHAR(3),
                              db.ForeignKey('district.code', ondelete='CASCADE'), index=True)
    easting = db.Column(db.Integer)
    northing = db.Column(db.Integer)
    longitude = db.Column(db.Float)
    latitude = db.Column(db.Float)

    def __repr__(self):
        return '<Postcode(%r, %r)>' % (self.index, self.text)
