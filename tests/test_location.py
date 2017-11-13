"""
Testing the populate module.
"""
import os
import tempfile
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


class BaseLocationTests(unittest.TestCase):
    """ Base class for testing locations. """

    def assertTupleAlmostEqual(self, tuple_1, tuple_2, delta=None, places=None,
                               msg=None):
        """ Compares tuples, checking if each pair of values are equal to some
            degree of accuracy.
        """
        if delta is None and places is None:
            places = 7
        elif delta is not None and places is not None:
            raise TypeError("Use either delta or places, not both.")

        message = None
        if not isinstance(tuple_1, tuple):
            message = "Tuple 1 %r is not of type tuple." % tuple_1
        elif not isinstance(tuple_2, tuple):
            message = "Tuple 2 %r is not of type tuple." % tuple_2

        if message is None:
            try:
                if len(tuple_1) != len(tuple_2):
                    message = ("Tuple 1 %r has length %d, while tuple 2 %r "
                               "has length %d.") % (tuple_1, len(tuple_1),
                                                    tuple_2, len(tuple_2))
            except TypeError:
                message = "One of the tuples is not a sequence."

        if message is None:
            try:
                list_diff = []
                seq_length = len(tuple_1)
                for i in seq_length:
                    diff = abs(tuple_1[i] - tuple_2[i])
                    if delta is not None:
                        if diff > delta:
                            list_diff.append((i, tuple_1, tuple_2))
                    else:
                        if round(diff, places) > 0:
                            list_diff.append((i, tuple_1, tuple_2))
                message = "Tuples differ in the following indices:\n"
                message += '\n'.join("%d\t%f\t%f" % d for d in list_diff)
            except TypeError:
                message = ("At least one of the tuple values is not a valid "
                           "number.")

        if message is not None:
            msg = self._formatMessage(msg, message)
            raise self.failureException(msg)


class LondonDistanceTests(BaseLocationTests):
    """ Test location functions. Distances taken from Google Maps.
        Min delta 10m.
    """

    def test_distance_museum(self):
        dist = location.get_dist(PLACES['Tottenham Court Road'],
                                 PLACES['British Museum'])
        self.assertAlmostEqual(dist, 438, delta=10)

    def test_distance_square(self):
        dist = location.get_dist(PLACES['Tottenham Court Road'],
                                 PLACES['Trafalgar Square'])
        self.assertAlmostEqual(dist, 950, delta=10)

    def test_distance_market(self):
        dist = location.get_dist(PLACES['Tottenham Court Road'],
                                 PLACES['Smithfield'])
        self.assertAlmostEqual(dist, 2030, delta=10)

    def test_distance_hill(self):
        dist = location.get_dist(PLACES['Tottenham Court Road'],
                                 PLACES['Primrose Hill'])
        self.assertAlmostEqual(dist, 3320, delta=10)

    def test_distance_shard(self):
        dist = location.get_dist(PLACES['Tottenham Court Road'],
                                 PLACES['The Shard'])
        self.assertAlmostEqual(dist, 3330, delta=10)

    def test_distance_wharf(self):
        dist = location.get_dist(PLACES['Tottenham Court Road'],
                                 PLACES['Canary Wharf'])
        self.assertAlmostEqual(dist, 7890, delta=10)

    def test_distance_kew(self):
        dist = location.get_dist(PLACES['Tottenham Court Road'],
                                 PLACES['Kew'])
        self.assertAlmostEqual(dist, 12200, delta=100)

    def test_distance_watford(self):
        dist = location.get_dist(PLACES['Tottenham Court Road'],
                                 PLACES['Watford Junction'])
        self.assertAlmostEqual(dist, 24600, delta=100)

    def test_distance_bedford(self):
        dist = location.get_dist(PLACES['Tottenham Court Road'],
                                 PLACES['Bedford'])
        self.assertAlmostEqual(dist, 72700, delta=100)


class LondonBoxTests(BaseLocationTests):

    def test_south_outwith_square(self):
        boundaries = location.bounding_box(PLACES['Tottenham Court Road'], 920)
        self.assertLess(PLACES['Trafalgar Square'][0], boundaries[0])

    def test_south_with_square(self):
        boundaries = location.bounding_box(PLACES['Tottenham Court Road'], 940)
        self.assertGreater(PLACES['Trafalgar Square'][0], boundaries[0])

    def test_west_outwith_station(self):
        boundaries = location.bounding_box(PLACES['Smithfield'], 1990)
        self.assertLess(PLACES['Tottenham Court Road'][1], boundaries[1])

    def test_west_with_station(self):
        boundaries = location.bounding_box(PLACES['Smithfield'], 2010)
        self.assertGreater(PLACES['Tottenham Court Road'][1], boundaries[1])

    def test_north_outwith_station(self):
        boundaries = location.bounding_box(PLACES['Trafalgar Square'], 920)
        self.assertGreater(PLACES['Tottenham Court Road'][0], boundaries[2])

    def test_north_with_station(self):
        boundaries = location.bounding_box(PLACES['Trafalgar Square'], 940)
        self.assertLess(PLACES['Tottenham Court Road'][0], boundaries[2])

    def test_east_outwith_market(self):
        boundaries = location.bounding_box(PLACES['Tottenham Court Road'], 1990)
        self.assertGreater(PLACES['Smithfield'][1], boundaries[3])

    def test_east_with_market(self):
        boundaries = location.bounding_box(PLACES['Tottenham Court Road'], 2010)
        self.assertLess(PLACES['Smithfield'][1], boundaries[3])
