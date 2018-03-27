"""
Views for the nextbus website.
"""
import collections
import re

from requests import HTTPError
from flask import (abort, Blueprint, current_app, g, jsonify, render_template,
                   redirect, request, url_for)

from nextbus import db, forms, location, models, search, tapi


MIN_GROUPED = 72
MAX_DISTANCE = 500
FIND_COORD = re.compile(r"^([-+]?\d*\.?\d+|[-+]?\d+\.?\d*),\s*"
                        r"([-+]?\d*\.?\d+|[-+]?\d+\.?\d*)$")


api = Blueprint("api", __name__, template_folder="templates")
page_search = Blueprint("page", __name__, template_folder="templates")
page_no_search = Blueprint("page_ns", __name__, template_folder="templates")


class EntityNotFound(Exception):
    """ Used to initiate a 404 with custom message. """
    pass


def _group_places(list_places, attr=None, key=None):
    """ Groups places or stops by the first letter of their names, or under a
        single key "A-Z" if the total is less than MIN_GROUPED.

        :param list_places: list of models.Locality objects.
        :param attr: First letter of attribute to group by.
        :param key: First letter of dict key to group by.
        :returns: Dictionary of models.Locality objects.
        :raises AttributeError: Either an attribute or a key must be specified.
    """
    if not bool(attr) ^ bool(key):
        raise AttributeError("Either an attribute or a key must be specified.")
    groups = {}
    if list_places and len(list_places) > MIN_GROUPED:
        groups = collections.defaultdict(list)
        for item in list_places:
            value = getattr(item, attr) if attr is not None else item[key]
            groups[value[0].upper()].append(item)
    elif list_places:
        groups = {"A-Z": list_places}

    return groups


@page_search.before_request
def add_search():
    """ Search form enabled in every view within blueprint by adding the form
        object to Flask's ``g``.
    """
    g.form = forms.SearchPlaces()
    if g.form.submit_query.data and g.form.search_query.data:
        query = g.form.search_query.data
        result = search.search_code(query)
        if isinstance(result, models.StopPoint):
            return redirect(url_for(".stop_atco", atco_code=result.atco_code))
        elif isinstance(result, models.Postcode):
            return redirect(url_for(".list_nr_postcode",
                                    postcode=result.text.replace(" ", "+")))
        else:
            return redirect(url_for(".search_results",
                                    query=query.replace(" ", "+")))
    else:
        return


@page_search.route("/", methods=["GET", "POST"])
def index():
    """ The home page. """
    return render_template("index.html")


@page_no_search.route("/about")
def about():
    """ The about page. """
    return render_template("about.html")


@page_search.route("/search/<query>", methods=["GET", "POST"])
def search_results(query):
    """ Shows a list of search results. """
    s_query = query.replace("+", " ")
    # Check if query has enough alphanumeric characters
    if not forms.check_alphanum(s_query):
        return render_template(
            "search.html", query=s_query, error="Too few characters; try a "
            "longer phrase."
        )
    try:
        results = search.search_full(s_query)
    except ValueError as err:
        current_app.logger.error("Query %r resulted in an parsing error: %s"
                                 % (query, err), exc_info=True)
        return render_template(
            "search.html", query=s_query, error="There was a problem reading "
            "your search query."
        )
    except search.PostcodeException as err:
        current_app.logger.debug(str(err))
        return render_template(
            "search.html", query=s_query, error="Postcode '%s' was not found; "
            "it may not exist or lies outside the area this website covers."
            % err.postcode
        )

    # Redirect to postcode or stop if one was found
    if isinstance(results, models.StopPoint):
        return redirect(url_for(".stop_atco", atco_code=results.atco_code))
    elif isinstance(results, models.Postcode):
        return redirect(url_for(".list_nr_postcode",
                                postcode=results.text.replace(" ", "+")))
    elif not results:
        return render_template(
            "search.html", query=s_query, error="No results were found."
        )
    else:
        # A dict of matching results. Truncate results list if they get
        # too long
        stops_limit = len(results.get("stop", [])) > search.STOPS_LIMIT
        local_limit = len(results.get("locality", [])) > search.LOCAL_LIMIT
        if stops_limit:
            results["stop"] = results["stop"][:search.STOPS_LIMIT]
        if local_limit:
            results["locality"] = results["locality"][:search.LOCAL_LIMIT]

        return render_template(
            "search.html", query=s_query, results=results,
            stops_limit=stops_limit, local_limit=local_limit
        )


@page_search.route("/list/", methods=["GET", "POST"])
def list_regions():
    """ Shows list of all regions. """
    regions = (models.Region.query.filter(models.Region.code != "GB")
               .order_by("name")).all()

    return render_template("all_regions.html", regions=regions)


@page_search.route("/list/region/<region_code>", methods=["GET", "POST"])
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


@page_search.route("/list/area/<area_code>", methods=["GET", "POST"])
def list_in_area(area_code):
    """ Shows list of districts or localities in administrative area - not all
        administrative areas have districts.
    """
    area = (models.AdminArea.query
            .options(db.joinedload(models.AdminArea.region, innerjoin=True))
            .get(area_code))

    if area is None:
        raise EntityNotFound("Area with code '%s' does not exist." % area_code)

    # Show list of localities with stops if districts do not exist
    if not area.districts:
        group_local = _group_places(area.list_localities(), attr="name")
    else:
        group_local = {}

    return render_template("area.html", area=area, localities=group_local)


@page_search.route("/list/district/<district_code>", methods=["GET", "POST"])
def list_in_district(district_code):
    """ Shows list of localities in district. """
    district = (models.District.query
                .options(db.joinedload(models.District.admin_area,
                                       innerjoin=True)
                         .joinedload(models.AdminArea.region, innerjoin=True))
                .get(district_code))

    if district is None:
        raise EntityNotFound("District with code '%s' does not exist."
                             % district_code)

    group_local = _group_places(district.list_localities(), attr="name")

    return render_template("district.html", district=district,
                           localities=group_local)


@page_search.route("/list/place/<locality_code>", methods=["GET", "POST"])
def list_in_locality(locality_code):
    """ Shows stops in locality. """
    locality = (models.Locality.query
                .options(db.joinedload(models.Locality.district),
                         db.joinedload(models.Locality.admin_area,
                                       innerjoin=True)
                         .joinedload(models.AdminArea.region, innerjoin=True))
                .get(locality_code.upper()))

    if locality is None:
        raise EntityNotFound("Place with code '%s' does not exist."
                             % locality_code)
    else:
        if locality.code != locality_code:
            return redirect(url_for(
                ".list_in_locality", locality_code=locality.code
            ), code=301)

    stops = _group_places(locality.list_stops(group_areas=True), attr="name")

    return render_template("place.html", locality=locality, stops=stops)


@page_search.route("/near/postcode/<postcode>", methods=["GET", "POST"])
def list_nr_postcode(postcode):
    """ Show stops within range of postcode. """
    str_psc = postcode.replace("+", " ")
    index_psc = "".join(str_psc.split()).upper()
    psc = models.Postcode.query.get(index_psc)

    if psc is None:
        raise EntityNotFound("Postcode '%s' does not exist." % postcode)
    else:
        if psc.text != str_psc:
            # Redirect to correct URL, eg 'W1A+1AA' instead of 'w1a1aa'
            return redirect(url_for(
                ".list_nr_postcode", postcode=psc.text.replace(" ", "+")
            ), code=301)

    stops = models.StopPoint.in_range((psc.latitude, psc.longitude))
    stop_data = [stop._asdict() for stop, _ in stops]

    return render_template("postcode.html", postcode=psc, list_stops=stops,
                           stop_data=stop_data)


@page_search.route("/near/location/<lat_long>", methods=["GET", "POST"])
def list_nr_location(lat_long):
    """ Show stops within range of a GPS coordinate. """
    sr_m = FIND_COORD.match(lat_long)
    if sr_m is None:
        raise EntityNotFound("Invalid latitude/longitude values.")

    coord = (float(sr_m.group(1)), float(sr_m.group(2)))
    # Quick check to ensure coordinates are within range of Great Britain
    if not (49 < coord[0] < 61 and -8 < coord[1] < 2):
        raise EntityNotFound("Latitude and longitude values out of bounds; "
                             "this application is meant to be used within "
                             "Great Britain only.")

    stops = models.StopPoint.in_range(coord)
    stop_data = [stop._asdict() for stop, _ in stops]
    str_coord = location.format_dms(*coord)

    return render_template("location.html", coord=coord, str_coord=str_coord,
                           list_stops=stops, stop_data=stop_data)


@page_search.route("/stop/area/<stop_area_code>", methods=["GET", "POST"])
def stop_area(stop_area_code):
    """ Show stops in stop area, eg pair of tram platforms. """
    area = (models.StopArea.query
            .options(db.joinedload(models.StopArea.admin_area, innerjoin=True),
                     db.joinedload(models.StopArea.locality, innerjoin=True)
                     .joinedload(models.Locality.district))
            .get(stop_area_code.upper()))

    if area is None:
        raise EntityNotFound("Bus stop with NaPTAN code '%s' does not exist."
                             % stop_area_code)
    else:
        if area.code != stop_area_code:
            return redirect(url_for(".stop_area", stop_area_code=area.code),
                            code=301)

    return render_template("stop_area.html", stop_area=area,
                           list_stops=[r._asdict() for r in area.stop_points])


@page_search.route("/stop/sms/<naptan_code>", methods=["GET", "POST"])
def stop_naptan(naptan_code):
    """ Shows stop with NaPTAN code. """
    stop = (models.StopPoint.query
            .options(db.joinedload(models.StopPoint.admin_area,
                                   innerjoin=True),
                     db.joinedload(models.StopPoint.locality, innerjoin=True)
                     .joinedload(models.Locality.district),
                     db.joinedload(models.StopPoint.stop_area))
            .filter(models.StopPoint.naptan_code == naptan_code.lower())
           ).one_or_none()

    if stop is None:
        raise EntityNotFound("Bus stop with SMS code '%s' does not exist."
                             % naptan_code)
    else:
        if stop.naptan_code != naptan_code:
            return redirect(url_for(
                ".stop_naptan", naptan_code=stop.naptan_code
            ), code=301)

    return render_template("stop.html", stop=stop)


@page_search.route("/stop/atco/<atco_code>", methods=["GET", "POST"])
def stop_atco(atco_code):
    """ Shows stop with ATCO code. """
    stop = (models.StopPoint.query
            .options(db.joinedload(models.StopPoint.admin_area,
                                   innerjoin=True),
                     db.joinedload(models.StopPoint.locality, innerjoin=True)
                     .joinedload(models.Locality.district),
                     db.joinedload(models.StopPoint.stop_area))
            .get(atco_code.upper()))

    if stop is None:
        raise EntityNotFound("Bus stop with ATCO code '%s' does not exist."
                             % atco_code)
    else:
        if stop.atco_code != atco_code:
            return redirect(url_for(".stop_atco", atco_code=stop.atco_code),
                            code=301)

    return render_template("stop.html", stop=stop)


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
        nxb = tapi.get_nextbus_times(data["code"])
    except (KeyError, ValueError):
        # Malformed request; no ATCO code
        current_app.logger.error("Error occurred when retrieving live times "
                                 "with data %r" % data, exc_info=True)
        abort(400)
    except HTTPError:
        # Problems with the API service
        current_app.logger.warning("Can't access API service.")
        abort(503)

    return jsonify(nxb)


@page_no_search.app_errorhandler(404)
@page_no_search.app_errorhandler(EntityNotFound)
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


@page_no_search.app_errorhandler(500)
def error_msg(error):
    """ Returned in case an internal server error (500) occurs, with message.
        Note that this page does not appear in debug mode.
    """
    return render_template("error.html", message=error), 500
