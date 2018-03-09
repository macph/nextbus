"""
Testing database models.
"""
import unittest

import sqlalchemy

from nextbus import db, models
import utils


class ModelTests(utils.BaseAppTests):
    """ Testing creation of model objects and querying them """

    def setUp(self):
        self.create_tables()
    
    def tearDown(self):
        self.drop_tables()

    def test_create_region(self):
        region = models.Region(**utils.REGION)
        db.session.add(region)
        db.session.commit()

        regions = models.Region.query.all()
        queried_attrs = self.model_as_dict(regions[0])
        self.assertEqual(utils.REGION, queried_attrs)

    def test_create_multiple(self):
        objects = [
            models.Region(**utils.REGION),
            models.AdminArea(**utils.ADMIN_AREA),
            models.District(**utils.DISTRICT),
            models.Locality(**utils.LOCALITY)
        ]
        db.session.add_all(objects)
        db.session.commit()

        locality = models.Locality.query.filter(
            models.Locality.name == "Sharrow Vale"
        ).one()
        queried_attrs = self.model_as_dict(locality)
        self.assertEqual(utils.LOCALITY, queried_attrs)

    def test_foreign_key(self):
        with self.assertRaisesRegex(sqlalchemy.exc.IntegrityError,
                                    "foreign key"):
            # Set district code to one that doesn't exist
            new_area = utils.ADMIN_AREA.copy()
            new_area['region_ref'] = "L"
            objects = [
                models.Region(**utils.REGION),
                models.AdminArea(**new_area)
            ]
            db.session.add_all(objects)
            db.session.commit()


class RelationshipTests(utils.BaseAppTests):
    """ Testing relations between different models """

    @classmethod
    def setUpClass(cls):
        super(RelationshipTests, cls).setUpClass()
        cls.create_tables()
        with cls.app.app_context():
            objects = [
                models.Region(**utils.REGION),
                models.AdminArea(**utils.ADMIN_AREA),
                models.District(**utils.DISTRICT),
                models.Locality(**utils.LOCALITY)
            ]
            db.session.add_all(objects)
            db.session.commit()

    @classmethod
    def tearDownClass(cls):
        cls.drop_tables()
        super(RelationshipTests, cls).tearDownClass()

    def test_region_areas(self):
        region = models.Region.query.filter_by(code="Y").one()
        admin_area = models.AdminArea.query.filter_by(code="099").one()
        region_areas = region.areas
        self.assertEqual(admin_area, region_areas[0])

    def test_area_region(self):
        region = models.Region.query.filter_by(code="Y").one()
        admin_area = models.AdminArea.query.filter_by(code="099").one()
        self.assertEqual(region, admin_area.region)
