"""
URL converters for coordinates.
"""
import re

from werkzeug.routing import BaseConverter, ValidationError


class LatLong(BaseConverter):
    """ URL converter for lat/long coordinates. """
    FIND_COORD = (r"^([-+]?\d*\.?\d+|[-+]?\d+\.?\d*),\s*"
                  r"([-+]?\d*\.?\d+|[-+]?\d+\.?\d*)$")

    def to_python(self, value):
        result = re.match(self.FIND_COORD, value)
        print(value, result)
        if not result:
            raise ValidationError
        latitude, longitude = float(result.group(1)), float(result.group(2))

        return latitude, longitude

    def to_url(self, value):
        return "%f,%f" % value if value else ""


class LatLongZoom(BaseConverter):
    """ URL converter for lat/long coordinates and zoom value for maps. """
    FIND_COORD_ZOOM = (r"^([-+]?\d*\.?\d+|[-+]?\d+\.?\d*),\s*"
                       r"([-+]?\d*\.?\d+|[-+]?\d+\.?\d*),\s*"
                       r"(\d+)$")

    def to_python(self, value):
        result = re.match(self.FIND_COORD_ZOOM, value)
        if not result:
            raise ValidationError
        latitude, longitude = float(result.group(1)), float(result.group(2))
        zoom = int(result.group(3))

        return latitude, longitude, zoom

    def to_url(self, value):
        return "%f,%f,%d" % value if value else ""


def add_converters(app):
    """ Adds URL converters to the Flask application. """
    app.url_map.converters.update({
        "lat_long": LatLong,
        "lat_long_zoom": LatLongZoom
    })
