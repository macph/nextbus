"""
Views for the nextbus website.
"""
import collections
import re
import string

from requests import HTTPError
from flask import (abort, Blueprint, current_app, g, jsonify, render_template,
                   redirect, request, url_for)

from nextbus import db, forms, location, models, search, tapi


MIN_GROUPED = 72
FIND_COORD = re.compile(r"^([-+]?\d*\.?\d+|[-+]?\d+\.?\d*),\s*"
                        r"([-+]?\d*\.?\d+|[-+]?\d+\.?\d*)$")


api = Blueprint("api", __name__, template_folder="templates")
page = Blueprint("page", __name__, template_folder="templates")
# Separate blueprint for pages with no search function
page_ns = Blueprint("page_ns", __name__, template_folder="templates")


class EntityNotFound(Exception):
    """ Used to initiate a 404 with custom message. """
    pass


def _group_objects(list_, attr=None, key=None, default=None, minimum=None):
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


@page.before_request
def add_search():
    """ Search form enabled in every view within blueprint by adding the form
        object to Flask's ``g``.
    """
    g.form = forms.SearchPlaces()
    if g.form.submit_query.data and g.form.search_query.data:
        query = g.form.search_query.data
        try:
            result = search.search_code(query)
        except search.PostcodeException:
            # Pass along to search results page to process
            query_url = query.replace(" ", "+")
            return redirect(url_for(".search_results", query=query_url))

        if result.is_stop():
            stop_code = result.stop.atco_code
            return redirect(url_for(".stop_atco", atco_code=stop_code))
        elif result.is_postcode():
            postcode_url = result.postcode.text.replace(" ", "+")
            return redirect(url_for(".list_near_postcode", code=postcode_url))
        else:
            return redirect(url_for(".search_results",
                                    query=query.replace(" ", "+")))
    else:
        return


@page.route("/", methods=["GET", "POST"])
def index():
    """ The home page. """
    return render_template("index.html")


@page_ns.route("/about")
def about():
    """ The about page. """
    return render_template("about.html")


@page.route("/search/<query>", methods=["GET", "POST"])
def search_results(query):
    """ Shows a list of search results.

        Query string attributes:
        type: Specify areas (admin areas and districts), places (localities) or
        stops (stop points and areas). Can have multiple entries.
        area: Admin area code, can have multiple entries.
    """
    s_query = query.replace("+", " ")
    # Check if query has enough alphanumeric characters
    if not forms.check_alphanum(s_query):
        return render_template(
            "search.html", query=s_query, error="Too few characters; try a "
            "longer phrase."
        )

    categories = {}

    types = {"area", "place", "stop"}
    types_valid = types & set(request.args.getlist("type"))
    categories["types"] = types_valid if types_valid else None

    # Filter by admin areas
    if "area" in request.args:
        categories["admin_areas"] = request.args.getlist("area")

    try:
        page_number = int(request.args.get("page", 1))
        categories["page"] = 1 if page_number < 1 else page_number
    except TypeError:
        categories["page"] = 1

    try:
        result = search.search_all(s_query, **categories)
    except ValueError as err:
        current_app.logger.error("Query %r resulted in an parsing error: %s"
                                 % (query, err), exc_info=True)
        return render_template("search.html", query=s_query, error="error")
    except search.PostcodeException as err:
        current_app.logger.debug(str(err))
        return render_template("search.html", query=s_query, error="postcode",
                               postcode=err.postcode)

    # Redirect to postcode or stop if one was found
    if result.is_stop():
        return redirect(url_for(".stop_atco", atco_code=result.stop.atco_code))
    elif result.is_postcode():
        postcode_url = result.postcode.text.replace(" ", "+")
        return redirect(url_for(".list_near_postcode", code=postcode_url))
    elif result.is_list():
        # Recalculate to get the result types and areas to filter with
        types, areas = search.filter_args(query)
        return render_template("search.html", query=s_query,
                               results=result.list, types=types, areas=areas)
    else:
        return render_template("search.html", query=s_query, error="not_found")


@page.route("/list/", methods=["GET", "POST"])
def list_regions():
    """ Shows list of all regions. """
    regions = (
        models.Region.query
        .filter(models.Region.code != "GB")
        .order_by("name")
        .all()
    )

    return render_template("all_regions.html", regions=regions)


@page.route("/list/region/<region_code>", methods=["GET", "POST"])
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


@page.route("/list/area/<area_code>", methods=["GET", "POST"])
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
                                     default="Places", minimum=MIN_GROUPED)
    else:
        group_local = {}

    return render_template("area.html", area=area, localities=group_local)


@page.route("/list/district/<district_code>", methods=["GET", "POST"])
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
                                 default="Places", minimum=MIN_GROUPED)

    return render_template("district.html", district=district,
                           localities=group_local)


@page.route("/list/place/<locality_code>", methods=["GET", "POST"])
def list_in_locality(locality_code):
    """ Shows stops in locality.

        Query string attributes:
        'group': If 'true', stops belonging to stop areas are grouped,
        otherwise all stops in locality are shown.
    """
    locality = (
        models.Locality.query
        .options(db.joinedload(models.Locality.district),
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

    group = request.args.get("group") == "true"
    stops = locality.list_stops(group_areas=group)

    stops = _group_objects(stops, attr="name", default="Stops",
                           minimum=MIN_GROUPED)

    return render_template("place.html", locality=locality, stops=stops)


@page.route("/near/postcode/<code>", methods=["GET", "POST"])
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
    geojson = _list_geojson([s[0] for s in stops])

    return render_template("postcode.html", postcode=postcode, data=geojson,
                           list_stops=stops)


@page.route("/near/location/<lat_long>", methods=["GET", "POST"])
def list_near_location(lat_long):
    """ Show stops within range of a GPS coordinate. """
    sr_m = FIND_COORD.match(lat_long)
    if sr_m is None:
        raise EntityNotFound("Invalid latitude/longitude values.")

    coord = (float(sr_m.group(1)), float(sr_m.group(2)))
    # Quick check to ensure coordinates are within range of Great Britain
    if not (49 < coord[0] < 61 and -8 < coord[1] < 2):
        raise EntityNotFound("The latitude and longitude coordinates are "
                             "nowhere near Great Britain!")

    stops = models.StopPoint.in_range(coord)
    str_coord = location.format_dms(*coord)
    geojson = _list_geojson([s[0] for s in stops])

    return render_template("location.html", coord=coord, str_coord=str_coord,
                           data=geojson, list_stops=stops)


@page.route("/stop/area/<stop_area_code>", methods=["GET", "POST"])
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

    return render_template("stop_area.html", stop_area=area,
                           data=_list_geojson(area.stop_points))


@page.route("/stop/sms/<naptan_code>", methods=["GET", "POST"])
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

    static = request.args.get("static") == "true"
    data = tapi.get_live_data(stop.atco_code) if static else None

    return render_template("stop.html", stop=stop, live_data=data)


@page.route("/stop/atco/<atco_code>", methods=["GET", "POST"])
def stop_atco(atco_code):
    """ Shows stop with ATCO code. """
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

    static = request.args.get("static") == "true"
    data = tapi.get_live_data(stop.atco_code) if static else None

    return render_template("stop.html", stop=stop, live_data=data)


@api.route("/stop/get", methods=["POST"])
def stop_get_times():
    """ Requests and retrieve bus times. """
    if request.method == "POST":
        data = request.get_json()
    else:
        # Trying to access with something other than POST
        current_app.logger.error("/stop/get was accessed with something other "
                                 "than POST")
        abort(405)

    try:
        times = tapi.get_nextbus_times(data["code"])
    except (KeyError, ValueError):
        # Malformed request; no ATCO code
        current_app.logger.error("Error occurred when retrieving live times "
                                 "with data %r" % data, exc_info=True)
        abort(400)
    except HTTPError:
        # Problems with the API service
        current_app.logger.warning("Can't access API service.")
        abort(503)

    return jsonify(times)



@page_ns.app_errorhandler(404)
@page_ns.app_errorhandler(EntityNotFound)
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


@page_ns.app_errorhandler(500)
def error_msg(error):
    """ Returned in case an internal server error (500) occurs, with message.
        Note that this page does not appear in debug mode.
    """
    return render_template("error.html", message=error), 500
