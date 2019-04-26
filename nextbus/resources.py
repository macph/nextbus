"""
API resources for the nextbus website.
"""
from flask import Blueprint, current_app, jsonify, session
from flask.views import MethodView
from requests import HTTPError

from nextbus import db, graph, location, models, tapi


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


@api.route("/live/<atco_code>")
def stop_get_times(atco_code=None):
    """ Requests and retrieve bus times. """
    matching_stop = (db.session.query(models.StopPoint.atco_code)
                     .filter_by(atco_code=atco_code).one_or_none())
    if not matching_stop:
        current_app.logger.warning("API accessed with invalid ATCO code %s."
                                   % atco_code)
        return bad_request(404, "ATCO code does not exist.")

    try:
        times = tapi.get_nextbus_times(atco_code)
    except (HTTPError, ValueError):
        # Error came up when accessing the external API or it can't be accessed
        current_app.logger.error("Error occurred when retrieving live times "
                                 "with data %r." % atco_code, exc_info=True)
        return bad_request(503, "There was a problem with the external API.")

    response = jsonify(times)
    # Set headers to ensure data is up to date
    response.cache_control.private = True
    response.cache_control.max_age = 60

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


@api.route("/route/<service_id>")
@api.route("/route/<service_id>/<direction:reverse>")
def get_service_route(service_id, reverse=False):
    """ Gets service data including a MultiLineString GeoJSON object. """
    data = graph.service_json(service_id, reverse)

    if data is None:
        return bad_request(404, "Service '%s' does not exist." % service_id)
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

        GET: Send list of starred stops by NaPTAN code or single stop if
        specified
        POST: Add starred NaPTAN code to cookie list
        PATCH: Move starred NaPTAN code to new index in list
        DELETE: Delete starred NaPTAN code from cookie list
    """
    def get(self, naptan_code):
        if "stops" not in session:
            return bad_request(422, "No cookie has been set.")

        code = naptan_code.lower() if naptan_code is not None else None
        if code is None:
            return jsonify({"stops": session.get("stops", [])})
        elif code in session["stops"]:
            return jsonify({"stop": code})
        else:
            return bad_request(
                404, "Stop %r not in list of starred stops." % naptan_code
            )

    def post(self, naptan_code):
        if naptan_code is None:
            return bad_request(400, "API accessed without valid SMS code.")

        code = naptan_code.lower()
        if "stops" in session and code in session["stops"]:
            return bad_request(
                422, "SMS code %r already in list of starred stops." % code
            )

        stop = models.StopPoint.query.filter_by(naptan_code=code).one_or_none()
        if stop is None:
            return bad_request(404, "SMS code %r does not exist." % code)
        if "stops" in session:
            session["stops"].append(code)
            session.modified = True
        else:
            session["stops"] = [code]
            session.permanent = True
            session.modified = True

        return "", 204

    def patch(self, naptan_code, index):
        if "stops" not in session:
            return bad_request(422, "No cookie has been set.")

        code = naptan_code.lower()
        if code not in session["stops"]:
            return bad_request(
                404, "Stop %r not in list of starred stops." % code
            )

        length = len(session["stops"])
        if index not in range(length):
            return bad_request(400, "Index %d out of range [0, %d]." %
                               (index, length - 1))

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
            session["stops"] = []
            session.permanent = False
            session.modified = True
        elif code in session["stops"]:
            session["stops"].remove(code)
            session.modified = True
        else:
            return bad_request(
                404, "SMS code %r not in list of starred stops." % code
            )

        return "", 204


def starred_stop_data(naptan_code=None):
    """ GET endpoint for GeoJSON data for starred stops.

        If a NaPTAN code is specified, the Feature GeoJSON data is returned for
        that stop only, otherwise a FeatureCollection is returned with a list of
        starred stops.
    """
    if "stops" not in session:
        return bad_request(422, "No cookie has been set.")

    codes = session["stops"]
    def _by_index(s): return codes.index(s.naptan_code)

    if naptan_code is not None:
        sms = naptan_code.lower()
        if sms not in codes:
            return bad_request(
                404, "SMS code %r not in list of starred stops." % sms
            )
        stop = (
            models.StopPoint.query
            .options(db.joinedload(models.StopPoint.locality))
            .filter(models.StopPoint.naptan_code == sms)
            .one_or_none()
        )
        if stop is not None:
            return jsonify(stop.to_geojson())
        else:
            return bad_request(404, "SMS code %r does not exist." % sms)
    else:
        stops = (
            models.StopPoint.query
            .options(db.joinedload(models.StopPoint.locality))
            .filter(models.StopPoint.naptan_code.in_(codes))
            .all()
        )
        return jsonify(_list_geojson(sorted(stops, key=_by_index)))


api.add_url_rule("/starred/", view_func=StarredStop.as_view("starred"),
                 methods=["GET", "DELETE"],  defaults={"naptan_code": None})
api.add_url_rule("/starred/<naptan_code>",
                 view_func=StarredStop.as_view("starred_stop"),
                 methods=["GET", "POST", "DELETE"])
api.add_url_rule("/starred/<naptan_code>/<int:index>",
                 view_func=StarredStop.as_view("starred_stop_index"),
                 methods=["PATCH"])
api.add_url_rule("/starred/data", view_func=starred_stop_data,
                 defaults={"naptan_code": None})
api.add_url_rule("/starred/<naptan_code>/data", view_func=starred_stop_data)
