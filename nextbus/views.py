"""
Views for the nextbus website.
"""
import collections
import string

from flask import (abort, Blueprint, current_app, g, jsonify, render_template,
                   redirect, request, session, url_for)
from flask.views import MethodView
from requests import HTTPError
from werkzeug.urls import url_encode

from nextbus import db, forms, location, models, parser, search, tapi


MIN_GROUPED = 72


api = Blueprint("api", __name__, template_folder="templates", url_prefix="/api")
page = Blueprint("page", __name__, template_folder="templates")


class EntityNotFound(Exception):
    """ Used to initiate a 404 with custom message. """
    pass


def _group_objects(list_, attr=None, key=None, default=None,
                   minimum=MIN_GROUPED):
    """ Groups places or stops by the first letter of their names, or under a
        single key "A-Z" if the total is less than MIN_GROUPED.

        :param list_: list of objects.
        :param attr: First letter of attribute to group by.
        :param key: First letter of dict key to group by.
        :param default: Group name to give for all objects in case limit is not
        reached; if None the generic 'A-Z' is used.
        :param minimum: Minimum number of items in list before they are grouped
        :returns: Dictionary of objects.
        :raises AttributeError: Either an attribute or a key must be specified.
    """
    if not bool(attr) ^ bool(key):
        raise AttributeError("Either an attribute or a key must be specified.")

    name = "A-Z" if default is None else default

    if list_ and (minimum is None or len(list_) > minimum):
        groups = collections.defaultdict(list)
        for item in list_:
            value = getattr(item, attr) if attr is not None else item[key]
            letter = value[0].upper()
            if letter not in string.ascii_uppercase:
                groups["0-9"].append(item)
            else:
                groups[letter].append(item)
    elif list_:
        groups = {name: list_}
    else:
        groups = {}

    return groups


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


def _get_starred_stops():
    """ Get list of starred stops from session, querying and ordering them. """
    if "stops" not in session:
        return

    starred = (
        models.StopPoint.query
        .options(db.joinedload(models.StopPoint.admin_area, innerjoin=True))
        .filter(models.StopPoint.naptan_code.in_(session["stops"]))
        .all()
    )
    starred.sort(key=lambda s: session["stops"].index(s.naptan_code))

    return starred


@page.before_app_request
def add_search_form():
    """ Search form enabled in every view within blueprint by adding the form
        object to Flask's ``g``.
    """
    g.form = forms.SearchPlaces(formdata=None)
    g.action = url_for("page.search_query")


@page.app_template_global()
def modify_query(**values):
    """ Jinja function to modify a query URL by replacing query string
        parameters with keyword arguments.

        https://stackoverflow.com/a/31121430
    """
    args = request.args.copy()

    for attr, new_value in values.items():
        if new_value is not None:
            args[attr] = new_value
        elif attr in args:
            del args[attr]

    return request.path + "?" + url_encode(args)


@page.route("/")
def index():
    """ The home page. """
    return render_template("index.html", starred=_get_starred_stops())


@page.route("/about")
def about():
    """ The about page. """
    return render_template("about.html")


@page.route("/search", methods=["POST"])
def search_query():
    """ Receives search query in POST request and redirects to another page.
    """
    g.form.process(request.form)

    if g.form.submit_query.data and g.form.search_query.data:
        query = g.form.search_query.data
        query_url = query.replace(" ", "+")
        try:
            result = search.search_code(query)
        except search.NoPostcode:
            # Pass along to search results page to process
            return redirect(url_for(".search_results", query=query_url))

        if result.is_stop():
            stop_code = result.stop.atco_code
            return redirect(url_for(".stop_atco", atco_code=stop_code))
        elif result.is_postcode():
            postcode_url = result.postcode.text.replace(" ", "+")
            return redirect(url_for(".list_near_postcode", code=postcode_url))
        else:
            return redirect(url_for(".search_results", query=query_url))


@page.route("/search/")
@page.route("/search/<path:query>")
def search_results(query=None):
    """ Shows a list of search results.

        Query string attributes:
        - group: Specify areas (admin areas and districts), places (localities)
        or stops (stop points and areas). Can have multiple entries.
        - area: Admin area code. Can have multiple entries.
        - page: Page number for results.
    """
    if query is None:
        # Blank search page
        return render_template("search.html", query=query)

    s_query = query.replace("+", " ")
    # Check if query has enough alphanumeric characters, else raise
    search.validate_characters(s_query)
    # Set up form and retrieve request arguments
    filters = forms.FilterResults(request.args)
    try:
        # Do the search; raise errors if necessary
        result = search.search_all(
            s_query,
            types=filters.group.data if filters.group.data else None,
            admin_areas=filters.area.data if filters.area.data else None,
            page=filters.page.data
        )
        if not result:
            raise ValueError
    except ValueError:
        current_app.logger.error("Query %r resulted in an parsing error" %
                                 query, exc_info=True)
        abort(500)
        return

    # Redirect to postcode or stop if one was found
    if result.is_stop():
        return redirect(url_for(".stop_atco", atco_code=result.stop.atco_code))
    elif result.is_postcode():
        postcode_url = result.postcode.text.replace(" ", "+")
        return redirect(url_for(".list_near_postcode", code=postcode_url))
    else:
        # List of results
        groups, areas = search.filter_args(s_query, filters.area.data)
        filters.add_choices(groups, areas)
        # Check the form data - if valid the area parameters are probably wrong
        if not filters.validate():
            raise search.InvalidParameters(s_query, "area",
                                           filters.area.data)

        return render_template("search.html", query=s_query,
                               results=result.list, filters=filters)


@page.errorhandler(search.InvalidParameters)
def search_invalid_parameters(error):
    """ Invalid parameters were passed with the search query, raise 400 """
    current_app.logger.info(str(error))
    return render_template("search.html", query=error.query, error=error), 400


@page.errorhandler(search.QueryTooShort)
@page.errorhandler(search.NoPostcode)
@page.errorhandler(parser.SearchNotDefined)
def search_bad_query(error):
    """ Query was too short or non-existent postcode was passed. Not an error
        so no 4xx code required.
    """
    current_app.logger.debug(str(error))
    return render_template("search.html", query=error.query, error=error)


@page.route("/list/")
def list_regions():
    """ Shows list of all regions. """
    regions = (
        models.Region.query
        .filter(models.Region.code != "GB")
        .order_by("name")
        .all()
    )

    return render_template("all_regions.html", regions=regions)


@page.route("/list/region/<region_code>")
def list_in_region(region_code):
    """ Shows list of administrative areas and districts in a region.
        Administrative areas with districts are excluded in favour of listing
        districts.
    """
    region = models.Region.query.get(region_code.upper())

    if region is None:
        raise EntityNotFound("Region with code '%s' does not exist."
                             % region_code)
    if region.code != region_code:
        return redirect(url_for(".list_in_region", region_code=region.code),
                        code=301)

    return render_template("region.html", region=region,
                           areas=region.list_areas())


@page.route("/list/area/<area_code>")
def list_in_area(area_code):
    """ Shows list of districts or localities in administrative area - not all
        administrative areas have districts.
    """
    area = (
        models.AdminArea.query
        .options(db.joinedload(models.AdminArea.region, innerjoin=True))
        .get(area_code)
    )

    if area is None:
        raise EntityNotFound("Area with code '%s' does not exist." % area_code)

    # Show list of localities with stops if districts do not exist
    if not area.districts:
        group_local = _group_objects(area.list_localities(), attr="name",
                                     default="Places")
    else:
        group_local = {}

    return render_template("area.html", area=area, localities=group_local)


@page.route("/list/district/<district_code>")
def list_in_district(district_code):
    """ Shows list of localities in district. """
    district = (
        models.District.query
        .options(db.joinedload(models.District.admin_area, innerjoin=True)
                 .joinedload(models.AdminArea.region, innerjoin=True))
        .get(district_code)
    )

    if district is None:
        raise EntityNotFound("District with code '%s' does not exist."
                             % district_code)

    group_local = _group_objects(district.list_localities(), attr="name",
                                 default="Places")

    return render_template("district.html", district=district,
                           localities=group_local)


@page.route("/list/place/<locality_code>")
def list_in_locality(locality_code):
    """ Shows stops in locality.

        Query string attributes:
        'group': If 'true', stops belonging to stop areas are grouped,
        otherwise all stops in locality are shown.
    """
    locality = (
        models.Locality.query
        .options(db.undefer(models.Locality.latitude),
                 db.undefer(models.Locality.longitude),
                 db.joinedload(models.Locality.district),
                 db.joinedload(models.Locality.admin_area, innerjoin=True)
                 .joinedload(models.AdminArea.region, innerjoin=True))
        .get(locality_code.upper())
    )

    if locality is None:
        raise EntityNotFound("Place with code '%s' does not exist."
                             % locality_code)
    if locality.code != locality_code:
        code = locality.code
        return redirect(url_for(".list_in_locality", locality_code=code),
                        code=301)

    group_areas = request.args.get("group") == "true"
    stops = locality.list_stops(group_areas=group_areas)
    # Check if listed stops do have associated stop areas - enable option to
    # group by stop areas or not
    if group_areas and not any(s.table_name == "stop_area" for s in stops):
        group_areas = None
    if not group_areas and all(s.stop_area_ref is None for s in stops):
        group_areas = None

    stops = _group_objects(stops, attr="name", default="Stops")

    return render_template("place.html", locality=locality, stops=stops,
                           grouped=group_areas)


@page.route("/near/postcode/<code>")
def list_near_postcode(code):
    """ Show stops within range of postcode. """
    str_postcode = code.replace("+", " ")
    index_postcode = "".join(str_postcode.split()).upper()
    postcode = models.Postcode.query.get(index_postcode)

    if postcode is None:
        raise EntityNotFound("Postcode '%s' does not exist." % postcode)
    if postcode.text != str_postcode:
        # Redirect to correct URL, eg 'W1A+1AA' instead of 'w1a1aa'
        postcode_url = postcode.text.replace(" ", "+")
        return redirect(url_for(".list_near_postcode", code=postcode_url),
                        code=301)

    stops = postcode.stops_in_range()
    geojson = _list_geojson(stops)

    return render_template("postcode.html", postcode=postcode, data=geojson,
                           list_stops=stops)


@page.route("/near/location/<lat_long:coords>")
def list_near_location(coords):
    """ Show stops within range of a GPS coordinate. """
    latitude, longitude = coords
    # Quick check to ensure coordinates are within range of Great Britain
    if not location.check_bounds(latitude, longitude):
        raise EntityNotFound("The latitude and longitude coordinates are "
                             "nowhere near Great Britain!")

    stops = models.StopPoint.in_range(latitude, longitude)
    geojson = _list_geojson(stops)

    return render_template("location.html", latitude=latitude,
                           longitude=longitude, data=geojson, list_stops=stops)


@page.route("/stop/area/<stop_area_code>")
def stop_area(stop_area_code):
    """ Show stops in stop area, eg pair of tram platforms. """
    area = (
        models.StopArea.query
        .options(db.joinedload(models.StopArea.admin_area, innerjoin=True),
                 db.joinedload(models.StopArea.locality, innerjoin=True)
                 .joinedload(models.Locality.district))
        .get(stop_area_code.upper())
    )

    if area is None:
        raise EntityNotFound("Bus stop with NaPTAN code '%s' does not exist."
                             % stop_area_code)
    if area.code != stop_area_code:
        return redirect(url_for(".stop_area", stop_area_code=area.code),
                        code=301)

    return render_template("stop_area.html", stop_area=area)


@page.route("/stop/sms/<naptan_code>")
def stop_naptan(naptan_code):
    """ Shows stop with NaPTAN code. """
    stop = (
        models.StopPoint.query
        .options(db.joinedload(models.StopPoint.admin_area, innerjoin=True),
                 db.joinedload(models.StopPoint.locality, innerjoin=True)
                 .joinedload(models.Locality.district),
                 db.joinedload(models.StopPoint.stop_area))
        .filter(models.StopPoint.naptan_code == naptan_code.lower())
        .one_or_none()
    )

    if stop is None:
        raise EntityNotFound("Bus stop with SMS code '%s' does not exist."
                             % naptan_code)
    if stop.naptan_code != naptan_code:
        return redirect(url_for(".stop_naptan", naptan_code=stop.naptan_code),
                        code=301)

    return render_template("stop.html", stop=stop)


@page.route("/stop/atco/<atco_code>")
def stop_atco(atco_code=''):
    """ Shows stop with ATCO code. """
    if not atco_code:
        abort(404)

    stop = (
        models.StopPoint.query
        .options(db.joinedload(models.StopPoint.admin_area, innerjoin=True),
                 db.joinedload(models.StopPoint.locality, innerjoin=True)
                 .joinedload(models.Locality.district),
                 db.joinedload(models.StopPoint.stop_area))
        .get(atco_code.upper())
    )

    if stop is None:
        raise EntityNotFound("Bus stop with ATCO code '%s' does not exist."
                             % atco_code)
    if stop.atco_code != atco_code:
        return redirect(url_for(".stop_atco", atco_code=stop.atco_code),
                        code=301)

    return render_template("stop.html", stop=stop)


@page.route("/map/")
@page.route("/map/<lat_long_zoom:coords>")
def show_map(coords=None):
    """ Shows map. """
    if coords:
        latitude, longitude, zoom = coords
    # Quick check to ensure coordinates are within range of Great Britain
    if not coords or not location.check_bounds(latitude, longitude):
        # Centre of GB, min zoom
        latitude, longitude = location.GB_CENTRE
        zoom = 9

    return render_template("map.html", latitude=latitude, longitude=longitude,
                           zoom=zoom, stop=None)


@page.route("/map/stop/<atco_code>/")
@page.route("/map/stop/<atco_code>/<lat_long_zoom:coords>")
def show_map_with_stop(atco_code, coords=None):
    """ Shows map with a stop already selected. """
    stop = models.StopPoint.query.get(atco_code.upper())
    if stop.atco_code != atco_code:
        return redirect(url_for(".show_map", atco_code=stop.atco_code,
                                coords=coords), code=301)
    elif stop is None:
        raise EntityNotFound("Bus stop with ATCO code '%s' does not exist."
                             % atco_code)

    if coords:
        latitude, longitude, zoom = coords
    if not coords or not location.check_bounds(latitude, longitude):
        latitude, longitude = None, None
        zoom = None

    return render_template("map.html", latitude=latitude, longitude=longitude,
                           zoom=zoom, stop=stop.to_geojson())


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

    return jsonify(times)


@api.route("/tile", methods=["GET"])
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


@page.app_errorhandler(EntityNotFound)
@page.app_errorhandler(404)
def not_found_msg(error):
    """ Returned in case of an invalid URL, with message. Can be called with
        EntityNotFound, eg if the correct URL is used but the wrong value is
        given.
    """
    if isinstance(error, EntityNotFound):
        message = str(error)
    else:
        message = "There's nothing here!"

    return render_template("not_found.html", message=message), 404


@page.app_errorhandler(500)
def error_msg(error):
    """ Returned in case an internal server error (500) occurs, with message.
        Note that this page does not appear in debug mode.
    """
    return render_template("error.html", message=error), 500
