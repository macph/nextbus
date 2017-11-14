"""
Models for the nextbus database.
"""
from nextbus import db


class Region(db.Model):
    """ NPTG region. """
    __tablename__ = 'Regions'

    id = db.Column(db.Integer, primary_key=True)
    region_code = db.Column(db.VARCHAR(2), index=True, unique=True)
    region_name = db.Column(db.Text, index=True)
    last_modified = db.Column(db.DateTime)

    areas = db.relationship('AdminArea', backref='region')

    def __repr__(self):
        return '<Region(%r, %r)>' % (self.region_code, self.region_name)


class AdminArea(db.Model):
    """ NPTG administrative area. """
    __tablename__ = 'AdminAreas'

    id = db.Column(db.Integer, primary_key=True)
    admin_area_code = db.Column(db.VARCHAR(3), index=True, unique=True)
    region_code = db.Column(db.VARCHAR(2), db.ForeignKey('Regions.region_code'))
    atco_area_code = db.Column(db.VARCHAR(3), index=True, unique=True)
    area_name = db.Column(db.Text, index=True)
    last_modified = db.Column(db.DateTime)

    districts = db.relationship('District', backref='admin_area')
    localities = db.relationship('Locality', backref='admin_area')
    postcodes = db.relationship('Postcode', backref='admin_area')
    stop_points = db.relationship('StopPoint', backref='admin_area')
    stop_areas = db.relationship('StopArea', backref='admin_area')

    def __repr__(self):
        return '<Area(%r, %r, %r)>' % (self.admin_area_code, self.atco_area_code, self.area_name)


class District(db.Model):
    """ NPTG district. """
    __tablename__ = 'Districts'

    id = db.Column(db.Integer, primary_key=True)
    district_code = db.Column(db.VARCHAR(3), index=True, unique=True)
    admin_area_code = db.Column(db.VARCHAR(3), db.ForeignKey('AdminAreas.admin_area_code'))
    district_name = db.Column(db.Text, index=True)
    last_modified = db.Column(db.DateTime)

    localities = db.relationship('Locality', backref='district')
    postcodes = db.relationship('Postcode', backref='district')

    def __repr__(self):
        return '<District(%r, %r)>' % (self.district_code, self.district_name)


class Locality(db.Model):
    """ NPTG locality. """
    __tablename__ = 'Localities'

    id = db.Column(db.Integer, primary_key=True)
    locality_code = db.Column(db.VARCHAR(7), index=True, unique=True)
    locality_name = db.Column(db.Text, index=True)
    admin_area_code = db.Column(db.VARCHAR(3), db.ForeignKey('AdminAreas.admin_area_code'))
    district_code = db.Column(db.VARCHAR(3), db.ForeignKey('Districts.district_code'))
    easting = db.Column(db.Integer)
    northing = db.Column(db.Integer)
    longitude = db.Column(db.Float)
    latitude = db.Column(db.Float)
    last_modified = db.Column(db.DateTime)

    stop_points = db.relationship('StopPoint', backref='locality')

    def __repr__(self):
        return '<Locality(%r, %r)>' % (self.locality_code, self.locality_name)


class StopPoint(db.Model):
    """ NaPTAN stop points, eg bus stops. """
    __tablename__ = 'StopPoints'

    id = db.Column(db.Integer, primary_key=True)
    atco_code = db.Column(db.VARCHAR(12), index=True, unique=True)
    naptan_code = db.Column(db.VARCHAR(8), index=True, unique=True)
    desc_common = db.Column(db.Text, index=True)
    desc_short = db.Column(db.Text, index=True)
    desc_landmark = db.Column(db.Text)
    desc_street = db.Column(db.Text, index=True)
    desc_crossing = db.Column(db.Text)
    desc_indicator = db.Column(db.Text, index=True)
    desc_short_ind = db.Column(db.Text, index=True)
    locality_code = db.Column(db.VARCHAR(7), db.ForeignKey('Localities.locality_code'))
    easting = db.Column(db.Integer)
    northing = db.Column(db.Integer)
    longitude = db.Column(db.Float)
    latitude = db.Column(db.Float)
    stop_type = db.Column(db.VARCHAR(3))
    bearing = db.Column(db.VARCHAR(1))
    stop_area_code = db.Column(db.VARCHAR(10), db.ForeignKey('StopAreas.stop_area_code'))
    admin_area_code = db.Column(db.VARCHAR(3), db.ForeignKey('AdminAreas.admin_area_code'))
    last_modified = db.Column(db.DateTime)

    def __repr__(self):
        return '<StopPoint(%r, %r, %r)>' % (self.atco_code, self.naptan_code, self.desc_common)


class StopArea(db.Model):
    """ NaPTAN stop areas, eg bus interchanges. """
    __tablename__ = 'StopAreas'

    id = db.Column(db.Integer, primary_key=True)
    stop_area_code = db.Column(db.VARCHAR(10), index=True, unique=True)
    stop_area_name = db.Column(db.Text, index=True)
    admin_area_code = db.Column(db.VARCHAR(3), db.ForeignKey('AdminAreas.admin_area_code'))
    stop_area_type = db.Column(db.VARCHAR(4))
    easting = db.Column(db.Integer)
    northing = db.Column(db.Integer)
    longitude = db.Column(db.Float)
    latitude = db.Column(db.Float)
    last_modified = db.Column(db.DateTime)

    stop_points = db.relationship('StopPoint', backref='stop_area')

    def __repr__(self):
        return '<StopArea(%r, %r)>' % (self.stop_area_code, self.stop_area_name)


class Postcode(db.Model):
    """ Postcodes with coordinates, derived from the NSPL data. """
    __tablename__ = 'Postcodes'
    postcode_regex = r"^([a-zA-Z]{1,2}\d{1,2}[a-zA-Z]?\s*\d{1}[a-zA-Z]{2})$"

    id = db.Column(db.Integer, primary_key=True)
    postcode = db.Column(db.VARCHAR(8), index=True, unique=True)
    postcode_2 = db.Column(db.VARCHAR(7), index=True, unique=True)
    local_authority_code = db.Column(db.VARCHAR(9))
    admin_area_code = db.Column(db.VARCHAR(3), db.ForeignKey('AdminAreas.admin_area_code'))
    district_code = db.Column(db.VARCHAR(3), db.ForeignKey('Districts.district_code'))
    easting = db.Column(db.Integer)
    northing = db.Column(db.Integer)
    longitude = db.Column(db.Float)
    latitude = db.Column(db.Float)

    def __repr__(self):
        return '<Postcode(%r)>' % self.postcode
