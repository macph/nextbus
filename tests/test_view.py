"""
Tests for views.
"""
import copy

from nextbus import models
from nextbus.resources import _list_geojson
import utils


class GeoJsonTests(utils.BaseAppTests):
    """ Testing conversion to GeoJSON format. """
    EXPECTED = {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [-1.49382723113, 53.36567543456]
        },
        "properties": {
            "atcoCode": "370020602",
            "naptanCode": "37020602",
            "name": "Cherry Tree Road",
            "indicator": "adj",
            "title": "Cherry Tree Road (adj)",
            "adminAreaRef": "099",
            "bearing": "SW",
            "stopType": "BCT",
            "street": "Psalter Lane"
        }
    }

    def test_single_stop(self):
        stop = models.StopPoint(**utils.STOP_POINT)
        self.assertEqual(stop.to_geojson(), self.EXPECTED)

    def test_two_stops(self):
        second = utils.STOP_POINT.copy()
        second["indicator"] = ""
        second["short_ind"] = ""

        first_stop = models.StopPoint(**utils.STOP_POINT)
        second_stop = models.StopPoint(**second)

        second_exp = copy.deepcopy(self.EXPECTED)
        second_exp["properties"]["indicator"] = ""
        second_exp["properties"]["title"] = "Cherry Tree Road"
        expected = {
            "type": "FeatureCollection",
            "features": [self.EXPECTED, second_exp]
        }

        self.assertEqual(_list_geojson([first_stop, second_stop]), expected)
