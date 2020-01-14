"""
Testing NSPL database population..
"""
import os

from nextbus import db, models
from nextbus.populate.nspl import populate_nspl_data


TEST_DIR = os.path.dirname(os.path.realpath(__file__))
NSPL = os.path.join(TEST_DIR, "NSPL.json")


def test_commit_nspl_data(load_db):
    with db.engine.begin() as connection:
        populate_nspl_data(connection, NSPL)

    count = models.Postcode.query.count()
    assert count == 100

    pc = models.Postcode.query.get("IG117RX")
    expected = ("IG117RX", "IG11 7RX", "082", "276")
    assert (pc.index, pc.text, pc.admin_area_ref, pc.district_ref) == expected
