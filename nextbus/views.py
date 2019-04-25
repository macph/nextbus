"""
Views for the nextbus website.
"""
import collections
import datetime
import re
import string

from flask import (abort, Blueprint, current_app, g, jsonify, Markup,
                   render_template, redirect, request, session, url_for)
from werkzeug.urls import url_encode

from nextbus import (db, forms, graph, location, models, parser, search,
                     timetable)


MIN_GROUPED = 72
REMOVE_BRACKETS = re.compile(r"\s*\([^)]*\)\s*")


page = Blueprint("page", __name__, template_folder="templates")


class NotFound(Exception):
    """ Used to initiate a 404 with custom message. """
    def __init__(self, message):
        self.message = message

    def __str__(self):
        try:
            return self.message.striptags()
        except AttributeError:
            return self.message


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
    groups = collections.defaultdict(list)

    if list_ and (minimum is None or len(list_) > minimum):
        for item in list_:
            value = getattr(item, attr) if attr is not None else item[key]
            letter = value[0].upper()
            if letter not in string.ascii_uppercase:
                groups["#"].append(item)
            else:
                groups[letter].append(item)
    elif list_:
        groups[name] = list_

    return groups


def _get_starred_stops():
    """ Get list of starred stops from session, querying and ordering them. """
    if "stops" not in session:
        return

    starred = (
        models.StopPoint.query
        .options(db.joinedload(models.StopPoint.locality, innerjoin=True),
                 db.joinedload(models.StopPoint.admin_area, innerjoin=True))
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

    if args:
        return request.base_url + "?" + url_encode(args)
    else:
        return request.base_url


@page.app_template_global()
def truncate_description(description):
    """ Truncate longer descriptions such that only starting and ending
        labels remain.
    """
    truncated = REMOVE_BRACKETS.sub("", description)

    sep = " – "  # en dash
    places = truncated.split(sep)
    if len(places) > 3:
        new_description = sep.join([places[0], places[-1]])
    else:
        new_description = truncated

    return new_description


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

    if g.form.submit.data and g.form.search.data:
        query = g.form.search.data
        try:
            result = search.search_code(query)
        except search.NoPostcode:
            # Pass along to search results page to process
            return redirect(url_for(".search_results", query=query))

        if isinstance(result, models.StopPoint):
            return redirect(url_for(".stop_atco", atco_code=result.atco_code))
        elif isinstance(result, models.Postcode):
            return redirect(url_for(".list_near_postcode", code=result.text))
        else:
            return redirect(url_for(".search_results", query=query))
    else:
        return redirect(url_for(".search_results"))


@page.route("/search/")
@page.route("/search/<path_string:query>")
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

    # Check if query has enough alphanumeric characters, else raise
    parser.validate_characters(query)
    # Set up form and retrieve request arguments
    filters = forms.FilterResults(request.args)
    groups = filters.group.data if filters.group.data else None
    areas = filters.area.data if filters.area.data else None
    try:
        # Do the search; raise errors if necessary
        result = search.search_all(query, groups=groups, admin_areas=areas,
                                   page=filters.page.data)
    except ValueError:
        current_app.logger.error("Query %r resulted in an parsing error" %
                                 query, exc_info=True)
        abort(500)
        return

    # Redirect to postcode or stop if one was found
    if isinstance(result, models.StopPoint):
        return redirect(url_for(".stop_atco", atco_code=result.atco_code))
    elif isinstance(result, models.Postcode):
        return redirect(url_for(".list_near_postcode",
                                code=result.text))
    else:
        # List of results
        filters.add_choices(*search.filter_args(query, areas))
        # Groups will have already been checked so only check areas here
        if not filters.area.validate(filters):
            raise search.InvalidParameters(query, "area", filters.area.data)

        return render_template("search.html", query=query, results=result,
                               filters=filters)


@page.errorhandler(search.InvalidParameters)
def search_invalid_parameters(error):
    """ Invalid parameters were passed with the search query, raise 400 """
    current_app.logger.info(str(error))
    return render_template("search.html", query=error.query, error=error), 400


@page.errorhandler(search.NoPostcode)
@page.errorhandler(parser.QueryTooShort)
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
        raise NotFound(Markup("Region with code <strong>%s</strong> does not "
                              "exist.") % region_code)
    if region.code != region_code:
        return redirect(url_for(".list_in_region", region_code=region.code),
                        code=302)

    areas = region.list_areas()

    return render_template("region.html", region=region, areas=areas)


@page.route("/list/area/<area_code>")
def list_in_area(area_code):
    """ Shows list of districts or localities in administrative area - not all
        administrative areas have districts.
    """
    area = (
        models.AdminArea.query
        .options(db.joinedload(models.AdminArea.region, innerjoin=True),
                 db.joinedload(models.AdminArea.districts))
        .get(area_code)
    )

    if area is None:
        raise NotFound(Markup("Area with code <strong>%s</strong> does not "
                              "exist.") % area_code)

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
        raise NotFound(Markup("District with code <strong>%s</strong> does not "
                              "exist.") % district_code)

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
        raise NotFound(Markup("Place with code <strong>%s</strong> does not "
                              "exist.") % locality_code)
    if locality.code != locality_code:
        code = locality.code
        return redirect(url_for(".list_in_locality", locality_code=code),
                        code=302)

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


@page.route("/near/")
def find_near_location():
    """ Starts looking for nearby stops. """
    return render_template("location.html", latitude=None, longitude=None,
                           list_stops=None)


@page.route("/near/<lat_long:coords>")
def list_near_location(coords):
    """ Show stops within range of a GPS coordinate. """
    latitude, longitude = coords
    # Quick check to ensure coordinates are within range of Great Britain
    if not location.check_bounds(latitude, longitude):
        raise NotFound("Latitude and longitude coordinates are too far from "
                       "Great Britain.")

    stops = models.StopPoint.in_range(latitude, longitude,
                                      db.undefer(models.StopPoint.lines))

    return render_template("location.html", latitude=latitude,
                           longitude=longitude, list_stops=stops)


@page.route("/near/<string:code>")
def list_near_postcode(code):
    """ Show stops within range of postcode. """
    index_postcode = "".join(code.split()).upper()
    postcode = models.Postcode.query.get(index_postcode)

    if postcode is None:
        raise NotFound(Markup("Postcode <strong>%s</strong> does not exist.")
                       % code)
    if postcode.text != code:
        # Redirect to correct URL, eg 'W1A+1AA' instead of 'w1a1aa'
        return redirect(url_for(".list_near_postcode", code=postcode.text),
                        code=302)

    stops = postcode.stops_in_range(db.undefer(models.StopPoint.lines))

    return render_template("postcode.html", postcode=postcode, list_stops=stops)


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
        raise NotFound(Markup("Stop area <strong>%s</strong> does not exist.")
                       % stop_area_code)
    if area.code != stop_area_code:
        return redirect(url_for(".stop_area", stop_area_code=area.code),
                        code=302)

    stops = (
        db.session.query(models.StopPoint)
        .options(db.undefer(models.StopPoint.lines))
        .filter(models.StopPoint.stop_area_ref == area.code,
                models.StopPoint.active)
        .order_by(models.StopPoint.ind_index)
        .all()
    )

    return render_template("stop_area.html", stop_area=area,
                           stops=stops)


@page.route("/stop/sms/<naptan_code>")
def stop_naptan(naptan_code):
    """ Shows stop with NaPTAN (SMS) code. """
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
        raise NotFound(Markup("Stop with SMS code <strong>%s</strong> does not "
                              "exist.") % naptan_code)
    if stop.naptan_code != naptan_code:
        return redirect(url_for(".stop_naptan", naptan_code=stop.naptan_code),
                        code=302)

    services, operators = stop.get_services()
    list_operators = [{"code": c, "name": n} for c, n in operators.items()]

    return render_template("stop.html", stop=stop, services=services,
                           operators=list_operators)


@page.route("/stop/atco/<atco_code>")
def stop_atco(atco_code=""):
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
        raise NotFound(Markup("Stop with ATCO code <strong>%s</strong> does "
                              "not exist.") % atco_code)
    if stop.atco_code != atco_code:
        return redirect(url_for(".stop_atco", atco_code=stop.atco_code),
                        code=302)

    services, operators = stop.get_services()
    list_operators = [{"code": c, "name": n} for c, n in operators.items()]

    return render_template("stop.html", stop=stop, services=services,
                           operators=list_operators)


def _query_service(service_id, reverse=None):
    """ Finds service as well as all journey patterns and local operators
        associated with the service.
    """
    sv = (
        models.Service.query
        .join(models.Service.patterns)
        .join(models.JourneyPattern.operator)
        .join(models.JourneyPattern.region)
        .options(db.undefer(models.Service.mode_name),
                 db.contains_eager(models.Service.patterns),
                 db.contains_eager(models.Service.operators),
                 db.contains_eager(models.Service.regions),
                 db.defaultload(models.Service.operators)
                 .undefer_group("contacts"))
        .filter(models.Service.id == service_id)
        .one_or_none()
    )

    if sv is None:
        raise NotFound(Markup("Service <strong>%s</strong> does not exist.")
                       % service_id)

    # Check line patterns - is there more than 1 direction?
    is_reverse, mirrored = sv.has_mirror(reverse)

    return sv, is_reverse, mirrored


@page.route("/service/<service_id>")
@page.route("/service/<service_id>/<direction:reverse>")
def service(service_id, reverse=None):
    """ Shows service with ID and optional direction, which is outbound by
        default.
    """
    sv, is_reverse, mirrored = _query_service(service_id, reverse)

    if reverse is None or reverse != is_reverse:
        return redirect(url_for(".service", service_id=service_id,
                                reverse=is_reverse))

    destinations = {
        "origin": {p.origin for p in sv.patterns
                   if p.direction == is_reverse},
        "destination": {p.destination for p in sv.patterns
                        if p.direction == is_reverse}
    }

    s_graph, d_stops = graph.service_graph_stops(sv.id, is_reverse)
    sequence = s_graph.sequence()
    try:
        layout = s_graph.draw(max_columns=graph.MAX_COLUMNS).serialize()
    except graph.MaxColumnError:
        layout = None

    return render_template("service.html", service=sv, dest=destinations,
                           reverse=is_reverse, mirrored=mirrored,
                           sequence=sequence, stops=d_stops, layout=layout)


@page.route("/service/<service_id>/timetable")
@page.route("/service/<service_id>/<direction:reverse>/timetable")
def service_timetable(service_id, reverse=None):
    """ Shows timetable for service with ID and optional direction. """
    sv, is_reverse, mirrored = _query_service(service_id, reverse)

    if reverse is None or reverse != is_reverse:
        return redirect(url_for(".service_timetable", service_id=service_id,
                                reverse=is_reverse))

    select_date = forms.SelectDate(request.args)
    if select_date.date.data is None:
        # Set to today by default
        select_date.date.data = datetime.date.today()

    select_date.set_dates(sv)
    select_date.validate()

    tt_data = timetable.Timetable(sv.id, is_reverse, select_date.date.data)

    return render_template("timetable.html", service=sv, reverse=is_reverse,
                           mirrored=mirrored, timetable=tt_data,
                           select_date=select_date)


def _show_map(service_id=None, reverse=None, atco_code=None, coords=None):
    """ Shows map.

        The map, service line, stop being shown and coordinates/zoom are
        expected to be the same as if the user has navigated there through the
        map interface.

        :param service_id: Service ID to show the paths on map. If ATCO code is
        None the service diagram will be shown in panel.
        :param reverse: Direction of service. Ignored if service ID is None.
        :param atco_code: Stop point code to show live data in panel.
        :param coords: Starting map coordinates. If None, the coordinates will
        default to stop point if specified, service paths if specified or the
        centre of GB if neither are specified.
    """
    if atco_code is not None:
        stop = models.StopPoint.query.get(atco_code.upper())
        if stop is None:
            raise NotFound(Markup("Stop with ATCO code <strong>%s</strong> "
                                  "does not exist.") % atco_code)
    else:
        stop = None

    if service_id is not None:
        sv = (
            models.Service.query
            .options(db.joinedload(models.Service.patterns))
            .get(service_id)
        )
        if sv is None:
            raise NotFound(Markup("Service <strong>%s</strong> does not exist.")
                           % service_id)

        is_reverse, _ = sv.has_mirror(reverse)
    else:
        sv = None
        is_reverse = None

    # TODO: Add redirect for incorrect capitalisation, etc

    # Quick check to ensure coordinates are within range of Great Britain
    if coords is not None and location.check_bounds(coords[0], coords[1]):
        latitude, longitude, zoom = coords
    else:
        latitude, longitude, zoom = None, None, None

    return render_template("map.html", latitude=latitude, longitude=longitude,
                           zoom=zoom, stop=stop, service=sv, reverse=is_reverse)


@page.route("/map/")
@page.route("/map/<lat_long_zoom:coords>")
def show_map(coords=None):
    """ Shows map without service or stop. """
    return _show_map(coords=coords)


@page.route("/map/service/<service_id>")
@page.route("/map/service/<service_id>/<lat_long_zoom:coords>")
def show_map_service_no_direction(service_id, coords=None):
    """ Shows map with service and unspecified direction. """
    return _show_map(service_id, coords=coords)


@page.route("/map/service/<service_id>/<direction:reverse>")
@page.route("/map/service/<service_id>/<direction:reverse>/"
            "<lat_long_zoom:coords>")
def show_map_service_direction(service_id, reverse, coords=None):
    """ Shows map with service and direction. """
    return _show_map(service_id, reverse, coords=coords)


@page.route("/map/stop/<atco_code>")
@page.route("/map/stop/<atco_code>/<lat_long_zoom:coords>")
def show_map_stop(atco_code, coords=None):
    """ Shows map with stop. """
    return _show_map(atco_code=atco_code, coords=coords)


@page.route("/map/service/<service_id>/stop/<atco_code>")
@page.route("/map/service/<service_id>/stop/<atco_code>/<lat_long_zoom:coords>")
def show_map_service_no_direction_stop(service_id, atco_code, coords=None):
    """ Shows map with service, unspecified direction and stop. """
    return _show_map(service_id, atco_code=atco_code, coords=coords)


@page.route("/map/service/<service_id>/<direction:reverse>/stop/<atco_code>")
@page.route("/map/service/<service_id>/<direction:reverse>/stop/<atco_code>/"
            "<lat_long_zoom:coords>")
def show_map_service_direction_stop(service_id, reverse, atco_code,
                                    coords=None):
    """ Shows map with service, direction and stop. """
    return _show_map(service_id, reverse, atco_code, coords)


@page.app_errorhandler(NotFound)
@page.app_errorhandler(404)
def not_found_msg(error):
    """ Returned in case of an invalid URL, with message. Can be called with
        NotFound, eg if the correct URL is used but the wrong value is given.
    """
    if request.path.startswith("/api"):
        # Respond with JSON data with message and 404 code
        if isinstance(error, NotFound):
            message = str(error)
        else:
            message = "API endpoint %r does not exist." % request.path
        response = jsonify({"message": message}), 404
    else:
        # Respond with 404 page
        message = error.message if isinstance(error, NotFound) else None
        response = render_template("not_found.html", message=message), 404

    return response


@page.app_errorhandler(500)
def error_msg(error):
    """ Returned in case an internal server error (500) occurs, with message.
        Note that this page does not appear in debug mode.
    """
    if request.path.startswith("/api"):
        return jsonify({"message": error}), 500
    else:
        return render_template("error.html", message=error), 500
