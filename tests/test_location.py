"""
Testing the populate module.
"""
import unittest

from nextbus import location

PLACES = {
    'Tottenham Court Road': (51.51623, -0.13067),
    'British Museum': (51.51939, -0.12692),
    'Trafalgar Square': (51.50786, -0.12803),
    'Smithfield': (51.51911, -0.10172),
    'Primrose Hill': (51.53954, -0.16066),
    'The Shard': (51.5045, -0.08649),
    'Canary Wharf': (51.5035, -0.01861),
    'Kew': (51.47867, -0.29555),
    'Watford Junction': (51.66354, -0.39651),
    'Bedford': (52.13584, -0.46632)
}


class LondonDistanceTests(unittest.TestCase):
    """ Test location functions. Distances taken from Google Maps.
        Min delta 10m.
    """

    def test_distance_museum(self):
        dist = location.get_distance(PLACES['Tottenham Court Road'],
                                     PLACES['British Museum'])
        self.assertAlmostEqual(dist, 438, delta=10)

    def test_distance_square(self):
        dist = location.get_distance(PLACES['Tottenham Court Road'],
                                     PLACES['Trafalgar Square'])
        self.assertAlmostEqual(dist, 950, delta=10)

    def test_distance_market(self):
        dist = location.get_distance(PLACES['Tottenham Court Road'],
                                     PLACES['Smithfield'])
        self.assertAlmostEqual(dist, 2030, delta=10)

    def test_distance_hill(self):
        dist = location.get_distance(PLACES['Tottenham Court Road'],
                                     PLACES['Primrose Hill'])
        self.assertAlmostEqual(dist, 3320, delta=10)

    def test_distance_shard(self):
        dist = location.get_distance(PLACES['Tottenham Court Road'],
                                     PLACES['The Shard'])
        self.assertAlmostEqual(dist, 3330, delta=10)

    def test_distance_wharf(self):
        dist = location.get_distance(PLACES['Tottenham Court Road'],
                                     PLACES['Canary Wharf'])
        self.assertAlmostEqual(dist, 7890, delta=10)

    def test_distance_kew(self):
        dist = location.get_distance(PLACES['Tottenham Court Road'],
                                     PLACES['Kew'])
        self.assertAlmostEqual(dist, 12200, delta=100)

    def test_distance_watford(self):
        dist = location.get_distance(PLACES['Tottenham Court Road'],
                                     PLACES['Watford Junction'])
        self.assertAlmostEqual(dist, 24600, delta=100)

    def test_distance_bedford(self):
        dist = location.get_distance(PLACES['Tottenham Court Road'],
                                     PLACES['Bedford'])
        self.assertAlmostEqual(dist, 72700, delta=100)


class LondonBoxTests(unittest.TestCase):
    """ Test whether coordinates exist within or outwith boxes centred around
        coordinates
    """

    def test_south_outwith_square(self):
        box = location.bounding_box(*PLACES['Tottenham Court Road'], 920)
        self.assertLess(PLACES['Trafalgar Square'][0], box.south)

    def test_south_with_square(self):
        box = location.bounding_box(*PLACES['Tottenham Court Road'], 940)
        self.assertGreater(PLACES['Trafalgar Square'][0], box.south)

    def test_west_outwith_station(self):
        box = location.bounding_box(*PLACES['Smithfield'], 1990)
        self.assertLess(PLACES['Tottenham Court Road'][1], box.west)

    def test_west_with_station(self):
        box = location.bounding_box(*PLACES['Smithfield'], 2010)
        self.assertGreater(PLACES['Tottenham Court Road'][1], box.west)

    def test_north_outwith_station(self):
        box = location.bounding_box(*PLACES['Trafalgar Square'], 920)
        self.assertGreater(PLACES['Tottenham Court Road'][0], box.north)

    def test_north_with_station(self):
        box = location.bounding_box(*PLACES['Trafalgar Square'], 940)
        self.assertLess(PLACES['Tottenham Court Road'][0], box.north)

    def test_east_outwith_market(self):
        box = location.bounding_box(*PLACES['Tottenham Court Road'], 1990)
        self.assertGreater(PLACES['Smithfield'][1], box.east)

    def test_east_with_market(self):
        box = location.bounding_box(*PLACES['Tottenham Court Road'], 2010)
        self.assertLess(PLACES['Smithfield'][1], box.east)
