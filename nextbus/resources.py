"""
API resources for the nextbus website.
"""
from flask import Blueprint, current_app, jsonify, session
from flask.views import MethodView
from requests import HTTPError

from nextbus import db, graph, location, models, live


api = Blueprint("api", __name__, template_folder="templates", url_prefix="/api")


def _list_geojson(list_stops):
    """ Creates a list of stop data in GeoJSON format.

        :param list_stops: List of StopPoint objects.
        :returns: JSON-serializable dict.
    """
    geojson = {
        "type": "FeatureCollection",
        "features": [s.to_geojson() for s in list_stops]
    }

    return geojson


def bad_request(status, message):
    """ Sends a response explaining the bad request. """
    response = jsonify({"message": message})
    response.status_code = status

    return response


@api.after_request
def set_cache_control(response):
    if response.cache_control.max_age is None and response.status_code != 302:
        response.cache_control.max_age = 604800

    return response


@api.route("/live/<atco_code>")
def stop_get_times(atco_code=None):
    """ Requests and retrieve bus times. """
    matching_stop = (db.session.query(models.StopPoint.atco_code)
                     .filter_by(atco_code=atco_code).one_or_none())
    if not matching_stop:
        current_app.logger.warning("API accessed with invalid ATCO code %s."
                                   % atco_code)
        return bad_request(404, "ATCO code %r does not exist." % atco_code)

    try:
        times = live.get_nextbus_times(atco_code)
    except (HTTPError, ValueError):
        # Error came up when accessing the external API or it can't be accessed
        current_app.logger.error("Error occurred when retrieving live times "
                                 "with data %r." % atco_code, exc_info=True)
        return bad_request(503, "There was a problem with the external API.")

    response = jsonify(times)
    # Set headers to ensure data is up to date
    response.cache_control.private = True
    response.cache_control.max_age = 60
    response.headers["X-Robots-Tag"] = "noindex"

    return response


@api.route("/tile/<coord>")
def get_stops_tile(coord):
    """ Gets list of stops within a tile. """
    try:
        x, y = map(int, coord.split(","))
    except ValueError:
        return bad_request(400, "API accessed with invalid args: %r." % coord)

    stops = models.StopPoint.within_box(
        location.tile_to_box(x, y, location.TILE_ZOOM),
        db.joinedload(models.StopPoint.locality)
    )

    return jsonify(_list_geojson(stops))


@api.route("/route/<service_code>")
@api.route("/route/<service_code>/<direction:reverse>")
def get_service_route(service_code, reverse=False):
    """ Gets service data including a MultiLineString GeoJSON object. """
    data = graph.service_json(service_code, reverse)

    if data is None:
        return bad_request(404, "Service '%s' does not exist." % service_code)
    else:
        return jsonify(data)


@api.route("/stop/<atco_code>")
def get_stop(atco_code):
    stop = (
        models.StopPoint.query
        .options(db.joinedload(models.StopPoint.admin_area, innerjoin=True),
                 db.joinedload(models.StopPoint.locality, innerjoin=True)
                 .joinedload(models.Locality.district),
                 db.joinedload(models.StopPoint.stop_area))
        .get(atco_code.upper())
    )

    if not stop:
        return bad_request(404, "Stop point '%s' does not exist." % atco_code)

    return jsonify(stop.to_full_json())


class StarredStop(MethodView):
    """ API to manipulate list of starred stops on cookie, with all responses
        sent in JSON.

        GET: Send list of SMS codes for starred stops, or null if cookie not set
        POST: Add starred NaPTAN code to cookie list
        PATCH: Move starred NaPTAN code to new index in list
        DELETE: Delete starred NaPTAN code from cookie list
    """
    def get(self, naptan_code=None):
        return jsonify({"stops": session.get("stops")})

    def post(self, naptan_code):
        if naptan_code is None:
            return bad_request(400, "API accessed without valid SMS code.")

        code = naptan_code.lower()
        if "stops" in session and code in session["stops"]:
            message = "SMS code %r already in list of starred stops." % code
            return bad_request(422, message)

        stop = models.StopPoint.query.filter_by(naptan_code=code).one_or_none()
        if stop is None:
            return bad_request(404, "SMS code %r does not exist." % code)

        if "stops" in session:
            session["stops"].append(code)
            session.modified = True
            return "", 204
        else:
            session["stops"] = [code]
            session.permanent = True
            session.modified = True
            return "", 201

    def patch(self, naptan_code, index):
        if "stops" not in session:
            return bad_request(422, "No cookie has been set.")

        code = naptan_code.lower()
        if code not in session["stops"]:
            message = "Stop %r not in list of starred stops." % code
            return bad_request(404, message)

        length = len(session["stops"])
        if index not in range(length):
            message = "Index %d is outside range [0, %d]." % (index, length - 1)
            return bad_request(400, message)

        if session["stops"].index(code) != index:
            session["stops"].remove(code)
            session["stops"].insert(index, code)
            session.modified = True

        return "", 204

    def delete(self, naptan_code):
        if "stops" not in session:
            return bad_request(422, "No cookie has been set.")

        code = naptan_code.lower() if naptan_code is not None else None
        if naptan_code is None:
            del session["stops"]
            session.permanent = False
            session.modified = True
        elif code in session["stops"]:
            session["stops"].remove(code)
            session.modified = True
        else:
            message = "SMS code %r not in list of starred stops." % code
            return bad_request(404, message)

        return "", 204


def starred_stop_data():
    """ GET endpoint for GeoJSON data for starred stops. """
    starred = models.StopPoint.from_list(session.get("stops", []))
    return jsonify(_list_geojson(starred))


api.add_url_rule("/starred/", view_func=StarredStop.as_view("starred"),
                 methods=["GET", "DELETE"],  defaults={"naptan_code": None})
api.add_url_rule("/starred/<naptan_code>",
                 view_func=StarredStop.as_view("starred_stop"),
                 methods=["POST", "DELETE"])
api.add_url_rule("/starred/<naptan_code>/<int:index>",
                 view_func=StarredStop.as_view("starred_stop_index"),
                 methods=["PATCH"])
api.add_url_rule("/starred/data", view_func=starred_stop_data, methods=["GET"])
