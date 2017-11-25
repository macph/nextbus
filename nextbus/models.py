"""
Models for the nextbus database.
"""
from nextbus import db

class Region(db.Model):
    """ NPTG region. """
    __tablename__ = 'region'

    code = db.Column(db.VARCHAR(2), primary_key=True)
    name = db.Column(db.Text, index=True)
    modified = db.Column(db.DateTime)

    areas = db.relationship('AdminArea', backref='region')

    def __repr__(self):
        return '<Region(%r, %r)>' % (self.code, self.name)


class AdminArea(db.Model):
    """ NPTG administrative area. """
    __tablename__ = 'admin_area'

    code = db.Column(db.VARCHAR(3), primary_key=True)
    name = db.Column(db.Text, index=True)
    atco_code = db.Column(db.VARCHAR(3), index=True, unique=True)
    region_code = db.Column(db.VARCHAR(2), db.ForeignKey('region.code'))
    modified = db.Column(db.DateTime)

    districts = db.relationship('District', backref='admin_area')
    localities = db.relationship('Locality', backref='admin_area')
    postcodes = db.relationship('Postcode', backref='admin_area')
    stop_points = db.relationship('StopPoint', backref='admin_area')
    stop_areas = db.relationship('StopArea', backref='admin_area')

    def __repr__(self):
        return '<AdminArea(%r, %r, %r)>' % (self.code, self.atco_code, self.name)


class District(db.Model):
    """ NPTG district. """
    __tablename__ = 'district'

    code = db.Column(db.VARCHAR(3), primary_key=True)
    name = db.Column(db.Text, index=True)
    admin_area_code = db.Column(db.VARCHAR(3), db.ForeignKey('admin_area.code'))
    modified = db.Column(db.DateTime)

    localities = db.relationship('Locality', backref='district')
    postcodes = db.relationship('Postcode', backref='district')

    def __repr__(self):
        return '<District(%r, %r)>' % (self.code, self.name)


class Locality(db.Model):
    """ NPTG locality. """
    __tablename__ = 'locality'

    code = db.Column(db.VARCHAR(7), primary_key=True)
    name = db.Column(db.Text, index=True)
    parent_code = db.Column(db.VARCHAR(7), db.ForeignKey('locality.code'))
    admin_area_code = db.Column(db.VARCHAR(3), db.ForeignKey('admin_area.code'))
    district_code = db.Column(db.VARCHAR(3), db.ForeignKey('district.code'))
    easting = db.Column(db.Integer)
    northing = db.Column(db.Integer)
    longitude = db.Column(db.Float)
    latitude = db.Column(db.Float)
    modified = db.Column(db.DateTime)

    stop_points = db.relationship('StopPoint', backref='locality')
    children = db.relationship('Locality', backref=db.backref('parent', remote_side=[code]))

    def __repr__(self):
        return '<Locality(%r, %r)>' % (self.code, self.name)


class StopPoint(db.Model):
    """ NaPTAN stop points, eg bus stops. """
    __tablename__ = 'stop_point'

    atco_code = db.Column(db.VARCHAR(12), primary_key=True)
    naptan_code = db.Column(db.VARCHAR(8), index=True, unique=True)
    common_name = db.Column(db.Text, index=True)
    short_name = db.Column(db.Text, index=True)
    landmark = db.Column(db.Text)
    street = db.Column(db.Text, index=True)
    crossing = db.Column(db.Text)
    indicator = db.Column(db.Text, index=True)
    short_ind = db.Column(db.Text, index=True)
    locality_code = db.Column(db.VARCHAR(7), db.ForeignKey('locality.code'))
    admin_area_code = db.Column(db.VARCHAR(3), db.ForeignKey('admin_area.code'))
    stop_area_code = db.Column(db.VARCHAR(10), db.ForeignKey('stop_area.code'))
    easting = db.Column(db.Integer)
    northing = db.Column(db.Integer)
    longitude = db.Column(db.Float)
    latitude = db.Column(db.Float)
    stop_type = db.Column(db.VARCHAR(3))
    bearing = db.Column(db.VARCHAR(1))
    modified = db.Column(db.DateTime)

    def __repr__(self):
        return '<StopPoint(%r, %r, %r)>' % (self.atco_code, self.naptan_code, self.common_name)


class StopArea(db.Model):
    """ NaPTAN stop areas, eg bus interchanges. """
    __tablename__ = 'stop_area'

    code = db.Column(db.VARCHAR(10), primary_key=True)
    name = db.Column(db.Text, index=True)
    admin_area_code = db.Column(db.VARCHAR(3), db.ForeignKey('admin_area.code'))
    stop_area_type = db.Column(db.VARCHAR(4))
    easting = db.Column(db.Integer)
    northing = db.Column(db.Integer)
    longitude = db.Column(db.Float)
    latitude = db.Column(db.Float)
    modified = db.Column(db.DateTime)

    stop_points = db.relationship('StopPoint', backref='stop_area')

    def __repr__(self):
        return '<StopArea(%r, %r)>' % (self.code, self.name)


class Postcode(db.Model):
    """ Postcodes with coordinates, derived from the NSPL data. """
    __tablename__ = 'postcode'
    postcode_regex = r"^([a-zA-Z]{1,2}\d{1,2}[a-zA-Z]?\s*\d{1}[a-zA-Z]{2})$"

    index = db.Column(db.VARCHAR(7), primary_key=True)
    text = db.Column(db.VARCHAR(8), index=True, unique=True)
    local_authority_code = db.Column(db.VARCHAR(9))
    admin_area_code = db.Column(db.VARCHAR(3), db.ForeignKey('admin_area.code'))
    district_code = db.Column(db.VARCHAR(3), db.ForeignKey('district.code'))
    easting = db.Column(db.Integer)
    northing = db.Column(db.Integer)
    longitude = db.Column(db.Float)
    latitude = db.Column(db.Float)

    def __repr__(self):
        return '<Postcode(%r, %r)>' % (self.index, self.text)
