"""
URL converters for strings and coordinates.
"""
from werkzeug import routing


class String(routing.UnicodeConverter):
    """ Converter for string to """
    def to_python(self, value):
        return value.replace("+", " ")

    def to_url(self, value):
        return value.replace(" ", "+")


class PathString(routing.PathConverter):
    def to_python(self, value):
        return value.replace("+", " ")

    def to_url(self, value):
        return value.replace(" ", "+")


class LatLong(routing.BaseConverter):
    """ URL converter for lat/long coordinates. """
    def to_python(self, value):
        try:
            latitude, longitude = map(float, value.split(","))
        except ValueError:
            raise routing.ValidationError

        return latitude, longitude

    def to_url(self, value):
        return "%f,%f" % value if value else ""


class LatLongZoom(routing.BaseConverter):
    """ URL converter for lat/long coordinates and zoom value for maps. """

    def to_python(self, value):
        try:
            numbers = value.split(",")
            latitude, longitude, zoom = map(float, numbers)
        except ValueError:
            raise routing.ValidationError

        if zoom == int(zoom):
            zoom = int(zoom)
        else:
            raise routing.ValidationError

        return latitude, longitude, zoom

    def to_url(self, value):
        return "%f,%f,%d" % value if value else ""


def add_converters(app):
    """ Adds URL converters to the Flask application. """
    app.url_map.converters.update({
        "string": String,
        "path_string": PathString,
        "lat_long": LatLong,
        "lat_long_zoom": LatLongZoom
    })
