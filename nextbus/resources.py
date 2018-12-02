"""
API resources for the nextbus website.
"""
from flask import Blueprint, current_app, jsonify, request, session
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
    if atco_code:
        matching_stop = (db.session.query(models.StopPoint.atco_code)
                         .filter_by(atco_code=atco_code).one_or_none())
        if not matching_stop:
            current_app.logger.warning("API accessed with invalid ATCO code %s"
                                       % atco_code)
            return bad_request(404, "ATCO code does not exist")
    else:
        current_app.logger.warning("API accessed without ATCO code %s" %
                                   atco_code)
        return bad_request(400, "ATCO code is required.")

    try:
        times = tapi.get_nextbus_times(atco_code)
    except (HTTPError, ValueError):
        # Error came up when accessing the external API or it can't be accessed
        current_app.logger.error("Error occurred when retrieving live times "
                                 "with data %r" % atco_code, exc_info=True)
        return bad_request(503, "There was a problem with the external API")

    response = jsonify(times)
    # Set headers to ensure data is up to date
    response.cache_control.private = True
    response.cache_control.max_age = 60

    return response


@api.route("/tile")
def get_stops_tile():
    """ Gets list of stops within a tile. """
    args = [request.args.get(i) for i in ["x", "y"]]
    try:
        x, y = map(int, args)
    except TypeError:
        return bad_request(400, "API accessed with invalid params: %r" % args)

    box = location.tile_to_box(x, y, location.TILE_ZOOM)
    stops = models.StopPoint.within_box(box)

    return jsonify(_list_geojson(stops))


@api.route("/route/<service_id>")
def get_service_route(service_id):
    """ Gets service data including a MultiLineString GeoJSON object. """
    line = (
        models.Service.query
        .options(db.joinedload(models.Service.local_operator, innerjoin=True),
                 db.joinedload(models.Service.patterns))
        .get(service_id)
    )

    if line is None:
        return bad_request(404, "Service '%s' does not exist." % service_id)

    # Check line patterns - is there more than 1 direction?
    directions = {p.direction for p in line.patterns}
    if directions == {True, False}:
        reverse = request.args.get("reverse") == "true"
    else:
        reverse = directions.pop()

    return jsonify(graph.service_json(line, reverse))


class StarredStop(MethodView):
    """ API to manipulate list of starred stops on cookie, with all responses
        sent in JSON.

        GET: Send list of starred stops by NaPTAN code
        POST: Add starred NaPTAN code to cookie list
        DELETE: Delete starred NaPTAN code from cookie list
    """
    def get(self, naptan_code):
        if naptan_code is None:
            return jsonify({"stops": session.get("stops")})

        sms = naptan_code.lower()
        stop = models.StopPoint.query.filter_by(naptan_code=sms).one_or_none()
        if stop is not None:
            return jsonify({"stop": sms})
        else:
            return bad_request(404, "SMS code %r does not exist" % sms)

    def post(self, naptan_code):
        if naptan_code is None:
            return bad_request(400, "API accessed without valid SMS code")

        sms = naptan_code.lower()
        if "stops" in session and sms in session["stops"]:
            return bad_request(400, "Cookie already exists")
        elif "stops" in session:
            stop = models.StopPoint.query.filter_by(
                naptan_code=sms).one_or_none()
            if stop is not None:
                session["stops"].append(sms)
                session.modified = True
            else:
                return bad_request(404, "SMS code %r does not exist" % sms)
        else:
            session["stops"] = [sms]
            session.permanent = True
            session.modified = True

        return "", 204

    def delete(self, naptan_code):
        if "stops" not in session:
            return bad_request(400, "No cookie has been set")

        sms = naptan_code.lower() if naptan_code is not None else None
        if naptan_code is None:
            session["stops"] = []
            session.permanent = False
            session.modified = True
        elif sms in session["stops"]:
            session["stops"].remove(sms)
            session.modified = True
        else:
            return bad_request(404, "SMS code %r not found within cookie data"
                               % sms)

        return "", 204


api.add_url_rule("/starred/", view_func=StarredStop.as_view("starred"),
                 methods=["GET", "DELETE"],  defaults={"naptan_code": None})
api.add_url_rule("/starred/<naptan_code>",
                 view_func=StarredStop.as_view("starred_stop"),
                 methods=["GET", "POST", "DELETE"])