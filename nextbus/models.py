"""
Models for the nextbus database.
"""
from nextbus import db


class Region(db.Model):
    """ NPTG region. """
    __tablename__ = 'Regions'
    region_code = db.Column(db.VARCHAR(2), primary_key=True)
    region_name = db.Column(db.Text)
    country = db.Column(db.Text)
    areas = db.relationship('AdminArea', backref='region')

    def __repr__(self):
        return f'<Region({self.region_code!r}, {self.region_name!r})>'


class AdminArea(db.Model):
    """ NPTG administrative area. """
    __tablename__ = 'AdminAreas'
    admin_area_code = db.Column(db.VARCHAR(3), primary_key=True)
    region_code = db.Column(db.VARCHAR(2), db.ForeignKey('Regions.region_code'))
    atco_area_code = db.Column(db.VARCHAR(3), index=True, unique=True)
    area_name = db.Column(db.Text)
    area_short_name = db.Column(db.Text)
    districts = db.relationship('District', backref='admin_area')
    localities = db.relationship('Locality', backref='admin_area')
    postcodes = db.relationship('Postcode', backref='admin_area')
    stop_points = db.relationship('StopPoint', backref='admin_area')
    stop_areas = db.relationship('StopArea', backref='admin_area')

    def __repr__(self):
        return f'<Area({self.admin_area_code!r}, {self.atco_area_code!r}, {self.area_name!r})>'


class District(db.Model):
    """ NPTG district. """
    __tablename__ = 'Districts'
    nptg_district_code = db.Column(db.VARCHAR(3), primary_key=True)
    admin_area_code = db.Column(db.VARCHAR(3), db.ForeignKey('AdminAreas.admin_area_code'))
    district_name = db.Column(db.Text)
    localities = db.relationship('Locality', backref='district')

    def __repr__(self):
        return f'<District({self.nptg_district_code!r}, {self.district_name!r})>'


class Locality(db.Model):
    """ NPTG locality. """
    __tablename__ = 'Localities'
    nptg_locality_code = db.Column(db.VARCHAR(7), primary_key=True)
    locality_name = db.Column(db.Text)
    admin_area_code = db.Column(db.VARCHAR(3), db.ForeignKey('AdminAreas.admin_area_code'))
    nptg_district_code = db.Column(db.VARCHAR(3), db.ForeignKey('Districts.nptg_district_code'))
    easting = db.Column(db.Integer)
    northing = db.Column(db.Integer)
    longitude = db.Column(db.Float)
    latitude = db.Column(db.Float)

    def __repr__(self):
        return f'<Locality({self.nptg_locality_code!r}, {self.locality_name!r})>'


class Postcode(db.Model):
    """ Postcode data. """
    __tablename__ = 'Postcodes'
    """ Postcodes with coordinates, derived from the NSPL data. """
    postcode_regex = r"^([a-zA-Z]{1,2}\d{1,2}[a-zA-Z]?\s*\d{1}[a-zA-Z]{2})$"

    postcode = db.Column(db.VARCHAR(8), primary_key=True)
    postcode_2 = db.Column(db.VARCHAR(7), unique=True)
    local_authority_code = db.Column(db.VARCHAR(9))
    admin_area_code = db.Column(db.VARCHAR(3), db.ForeignKey('AdminAreas.admin_area_code'))
    easting = db.Column(db.Integer)
    northing = db.Column(db.Integer)
    longitude = db.Column(db.Float)
    latitude = db.Column(db.Float)

    def __repr__(self):
        return f'<Postcode({self.postcode!r})>'

    @property
    def outward(self):
        """ The first part of a postcode, eg 'SW1A' in 'SW1A 0AA'."""
        return self.postcode.split(' ')[0]

    @outward.setter
    def outward(self, value):
        raise AttributeError("Cannot set 'outward' as %s; the property is read"
                             "-only." % value)

    @property
    def inward(self):
        """ The second part of a postcode, eg '0AA' in 'SW1A 0AA'."""
        return self.postcode.split(' ')[1]

    @inward.setter
    def inward(self, value):
        raise AttributeError("Cannot set 'inward' as %s; the property is read-"
                             "only." % value)


class StopPoint(db.Model):
    """ NaPTAN stop points, eg bus stops. """
    __tablename__ = 'StopPoints'
    atco_code = db.Column(db.VARCHAR(12), primary_key=True)
    naptan_code = db.Column(db.VARCHAR(8), index=True, unique=True)
    desc_common = db.Column(db.Text)
    desc_short = db.Column(db.Text)
    desc_landmark = db.Column(db.Text)
    desc_street = db.Column(db.Text)
    desc_crossing = db.Column(db.Text)
    desc_indicator = db.Column(db.Text)
    nptg_locality_code = db.Column(db.VARCHAR(7), db.ForeignKey('Localities.nptg_locality_code'))
    suburb = db.Column(db.Text)
    town = db.Column(db.Text)
    easting = db.Column(db.Integer)
    northing = db.Column(db.Integer)
    longitude = db.Column(db.Float)
    latitude = db.Column(db.Float)
    stop_type = db.Column(db.VARCHAR(3))
    bearing = db.Column(db.VARCHAR(1))
    stop_area_code = db.Column(db.VARCHAR(10), db.ForeignKey('StopAreas.stop_area_code'))
    admin_area_code = db.Column(db.VARCHAR(3), db.ForeignKey('AdminAreas.admin_area_code'))

    def __repr__(self):
        return f'<StopPoint({self.atco_code!r}, {self.naptan_code!r}, {self.desc_short!r})>'


class StopArea(db.Model):
    """ NaPTAN stop areas, eg bus interchanges. """
    __tablename__ = 'StopAreas'
    stop_area_code = db.Column(db.VARCHAR(10), primary_key=True)
    stop_area_name = db.Column(db.Text)
    admin_area_code = db.Column(db.VARCHAR(3), db.ForeignKey('AdminAreas.admin_area_code'))
    stop_area_type = db.Column(db.VARCHAR(4))
    easting = db.Column(db.Integer)
    northing = db.Column(db.Integer)
    longitude = db.Column(db.Float)
    latitude = db.Column(db.Float)
    stop_points = db.relationship('StopPoint', backref='stop_area')

    def __repr__(self):
        return f'<StopArea({self.stop_area_code!r}, {self.stop_area_name!r})>'
