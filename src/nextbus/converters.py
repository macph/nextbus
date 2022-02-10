"""
URL converters for strings and coordinates.
"""
import os

from flask import current_app
from werkzeug import routing, urls


class String(routing.UnicodeConverter):
    """ Converter for strings with `+` representing spaces, eg 'W1A+1AA'. """
    def to_python(self, value):
        return value.replace("+", " ")

    def to_url(self, value):
        return value.replace(" ", "+")


class PathString(routing.PathConverter):
    """ Converter for strings with `/` and `+` representing spaces. """
    def to_python(self, value):
        return value.replace("+", " ")

    def to_url(self, value):
        escaped = urls.url_quote(value, charset=self.map.charset)
        return escaped.replace("%20", "+")


class PathExists(routing.PathConverter):
    """ Path URL converter checking beforehand if static URL exists. """
    def to_python(self, value):
        if current_app.has_static_folder:
            path = os.path.join(current_app.static_folder, value)
            if os.path.isfile(path):
                return value

        raise routing.ValidationError


class LatLong(routing.BaseConverter):
    """ URL converter for lat/long coordinates. """
    def to_python(self, value):
        try:
            latitude, longitude = map(float, value.split(","))
        except ValueError:
            raise routing.ValidationError

        return latitude, longitude

    def to_url(self, value):
        return f"{value[0]},{value[1]}" if value else ""


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
        return f"{value[0]},{value[1]},{value[2]}" if value else ""


class Direction(routing.BaseConverter):
    """ Direction for service which must be either 'inbound' or 'outbound'. """
    def to_python(self, value):
        if value == "outbound":
            return False
        elif value == "inbound":
            return True
        else:
            raise routing.ValidationError

    def to_url(self, value):
        return "inbound" if value else "outbound"


def add_converters(app):
    """ Adds URL converters to the Flask application. """
    app.url_map.converters.update({
        "string": String,
        "path_string": PathString,
        "exists": PathExists,
        "lat_long": LatLong,
        "lat_long_zoom": LatLongZoom,
        "direction": Direction
    })
