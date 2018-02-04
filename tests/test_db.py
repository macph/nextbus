"""
Testing the populate module.
"""
import os
import datetime
import unittest

import psycopg2
import sqlalchemy

from nextbus import db, create_app, models


REGION = {
    "code": "Y",
    "name": "Yorkshire",
    "modified": datetime.datetime.now()
}
ADMIN_AREA = {
    "code": "099",
    "name": "South Yorkshire",
    "atco_code": "370",
    "region_code": "Y",
    "is_live": True,
    "modified": datetime.datetime.now()
}
DISTRICT = {
    "code": "263",
    "name": "Sheffield",
    "admin_area_code": "099",
    "modified": datetime.datetime.now()
}
LOCALITY = {
    "code": "E0030518",
    "name": "Sharrow Vale",
    "parent_code": None,
    "admin_area_code": "099",
    "district_code": "263",
    "easting": 433540,
    "northing": 385740,
    "longitude": -1.497413,
    "latitude": 53.36747,
    "modified": datetime.datetime.now()
}
STOP_AREA = {
    "code": "370G100809",
    "name": "Psalter Lane - Bagshot Street",
    "admin_area_code": "099",
    "locality_code": "E0030518",
    "stop_area_type": "GPBS",
    "easting": 433794,
    "northing": 385561,
    "longitude": -1.49361482816,
    "latitude": 53.36584531963,
    "modified": datetime.datetime.now()
}
STOP_POINT = {
    "atco_code": "370020602",
    "naptan_code": "37020602",
    "name": "Cherry Tree Road",
    "landmark": "20602",
    "street": "Psalter Lane",
    "crossing": "Cherry Tree Road",
    "indicator": "adj",
    "short_ind": "adj",
    "locality_code": "E0030518",
    "admin_area_code": "099",
    "stop_area_code": "370G100809",
    "easting": 433780,
    "northing": 385542,
    "longitude": -1.49382723113,
    "latitude": 53.36567543456,
    "stop_type": "BCT",
    "bearing": "SW",
    "modified": datetime.datetime.now()
}


class BaseDBTests(unittest.TestCase):
    """ Base class for testing with the app and database """
    ENV_VAR = "TEST_DATABASE_URI"

    @classmethod
    def setUpClass(cls):
        # set up app
        cls.app = create_app(config_obj="default_config.TestConfig")
        new_uri = os.environ.get(cls.ENV_VAR)
        if new_uri:
            cls.app.config["SQLALCHEMY_DATABASE_URI"] = new_uri

    @classmethod
    def tearDownClass(cls):
        del cls.app

    @classmethod
    def create_tables(cls):
        """ Creates tables in database from models """
        with cls.app.app_context():
            db.create_all()

    @classmethod
    def drop_tables(cls):
        """ Drops all tables from database """
        with cls.app.app_context():
            # close any connections
            db.session.remove()
            db.drop_all()

    @staticmethod
    def model_as_dict(model_object):
        """ Get all columns and values from a model object as a dict. """
        model = model_object.__class__
        columns = [c.key for c in model.__table__.columns]
        return {c: getattr(model_object, c) for c in columns}


class ModelTests(BaseDBTests):
    """ Testing creation of model objects and querying them """

    def setUp(self):
        self.create_tables()
    
    def tearDown(self):
        self.drop_tables()

    def test_create_region(self):
        with self.app.app_context():
            region = models.Region(**REGION)
            db.session.add(region)
            db.session.commit()

            regions = models.Region.query.all()
            queried_attrs = self.model_as_dict(regions[0])
            self.assertEqual(REGION, queried_attrs)

    def test_create_multiple(self):
        with self.app.app_context():
            objects = [
                models.Region(**REGION),
                models.AdminArea(**ADMIN_AREA),
                models.District(**DISTRICT),
                models.Locality(**LOCALITY)
            ]
            db.session.add_all(objects)
            db.session.commit()

            locality = models.Locality.query.filter(
                models.Locality.name == "Sharrow Vale"
            ).one()
            queried_attrs = self.model_as_dict(locality)
            self.assertEqual(LOCALITY, queried_attrs)

    def test_foreign_key(self):
        with self.app.app_context(),\
                self.assertRaisesRegex(sqlalchemy.exc.IntegrityError,
                                       "foreign key"):
            # Set district code to one that doesn't exist
            new_area = ADMIN_AREA.copy()
            new_area['region_code'] = "L"
            objects = [
                models.Region(**REGION),
                models.AdminArea(**new_area)
            ]
            db.session.add_all(objects)
            db.session.commit()


class RelationshipTests(BaseDBTests):
    """ Testing relations between different models """

    @classmethod
    def setUpClass(cls):
        super(RelationshipTests, cls).setUpClass()
        cls.create_tables()
        with cls.app.app_context():
            objects = [
                models.Region(**REGION),
                models.AdminArea(**ADMIN_AREA),
                models.District(**DISTRICT),
                models.Locality(**LOCALITY)
            ]
            db.session.add_all(objects)
            db.session.commit()

    @classmethod
    def tearDownClass(cls):
        cls.drop_tables()
        super(RelationshipTests, cls).tearDownClass()

    def test_region_areas(self):
        with self.app.app_context():
            region = models.Region.query.filter_by(code="Y").one()
            admin_area = models.AdminArea.query.filter_by(code="099").one()
            region_areas = region.areas
            self.assertEqual(admin_area, region_areas[0])

    def test_area_region(self):
        with self.app.app_context():
            region = models.Region.query.filter_by(code="Y").one()
            admin_area = models.AdminArea.query.filter_by(code="099").one()
            self.assertEqual(region, admin_area.region)
