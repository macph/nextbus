"""
Views for the nextbus website.
"""
import collections
import datetime
import re
import string

import dateutil.tz
from flask import (abort, Blueprint, current_app, g, jsonify, Markup,
                   render_template, redirect, request, session, url_for)
from sqlalchemy.dialects import postgresql as pg
from werkzeug.urls import url_encode

from nextbus import db, forms, graph, location, models, search, timetable


MIN_GROUPED = 72
REMOVE_BRACKETS = re.compile(r"\s*\([^)]*\)\s*")
GB_TZ = dateutil.tz.gettz("Europe/London")


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


@page.before_app_request
def add_search_form():
    """ Search form enabled in every view within blueprint by adding the form
        object to Flask's ``g``.
    """
    g.form = forms.SearchPlaces(formdata=None)
    g.action = url_for("page.search_query")


@page.after_request
def set_cache_control(response):
    if response.cache_control.max_age is None and response.status_code != 302:
        response.cache_control.max_age = 604800

    return response


@page.app_template_global()
def datetime_now():
    """ Get the current datetime. """
    return datetime.datetime.now(GB_TZ)


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


@page.route("/<exists:filename>")
def send_from_root(filename):
    return current_app.send_static_file(filename)


@page.route("/")
def index():
    """ The home page. """
    starred = models.StopPoint.from_list(session.get("stops", []))
    return render_template("index.html", starred=starred)


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

    # Set up form and retrieve request arguments
    filters = forms.FilterResults(request.args)
    groups = filters.group.data if filters.group.data else None
    areas = filters.area.data if filters.area.data else None
    try:
        # Do the search; raise errors if necessary
        result = search.search_all(query, groups=groups, admin_areas=areas,
                                   page=filters.page.data)
    except ValueError:
        current_app.logger.error(
            f"Query {query!r} resulted in an parsing error", exc_info=True
        )
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
@page.errorhandler(search.SearchNotDefined)
def search_bad_query(error):
    """ Query was too short or non-existent postcode was passed. Not an error
        so no 4xx code required.
    """
    current_app.logger.debug(str(error))
    return render_template("search.html", query=error.query, error=error)


@page.route("/list/")
def list_regions():
    """ Shows list of all regions and their areas. """
    regions_areas = (
        db.session.query(
            models.Region.code.label("region_code"),
            models.Region.name.label("region_name"),
            db.case([(models.District.code.is_(None),
                      db.literal_column("'admin_area'"))],
                    else_=db.literal_column("'district'")).label("area_type"),
            db.case([(models.District.code.is_(None), models.AdminArea.code)],
                    else_=models.District.code).label("area_code"),
            db.case([(models.District.code.is_(None), models.AdminArea.name)],
                    else_=models.District.name).label("area_name")
        ).select_from(models.Region)
        .join(models.Region.areas)
        .outerjoin(models.AdminArea.districts)
        .filter(models.Region.code != "GB")
        .order_by("region_name", "area_name")
        .all()
    )
    regions = {}
    areas = {}
    for row in regions_areas:
        regions[row.region_code] = row.region_name
        areas.setdefault(row.region_code, []).append(row)

    return render_template("regions.html", regions=regions, areas=areas)


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
        raise NotFound(
            Markup("Area with code <strong>{}</strong> does not exist.")
            .format(area_code)
        )

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
        raise NotFound(
            Markup("District with code <strong>{}</strong> does not exist.")
            .format(district_code)
        )

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
        .options(db.undefer_group("coordinates"),
                 db.joinedload(models.Locality.district),
                 db.joinedload(models.Locality.admin_area, innerjoin=True)
                 .joinedload(models.AdminArea.region, innerjoin=True))
        .get(locality_code.upper())
    )

    if locality is None:
        raise NotFound(
            Markup("Place with code <strong>{}</strong> does not exist.")
            .format(locality_code)
        )
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


def _group_lines_stops(list_stops):
    """ Groups lines and stops such that each distinct line and direction has
        a group of stops associated with it.
    """
    stops = [s.atco_code for s in list_stops]

    separator = db.literal_column("' / '")
    destinations = db.func.string_agg(
        db.distinct(models.JourneyPattern.destination),
        pg.aggregate_order_by(separator, models.JourneyPattern.destination)
    )
    array_stops = pg.array_agg(db.distinct(models.JourneyLink.stop_point_ref))
    groups = (
        db.session.query(
            models.Service.code.label("code"),
            models.JourneyPattern.direction.label("direction"),
            models.Service.line.label("line"),
            destinations.label("destination"),
            array_stops.label("stops")
        )
        .select_from(models.Service)
        .join(models.Service.patterns)
        .join(models.JourneyPattern.links)
        .filter(models.JourneyLink.stop_point_ref.in_(stops))
        .group_by(models.Service.code, models.Service.line,
                  models.JourneyPattern.direction)
        .order_by(models.Service.line_index, models.JourneyPattern.direction)
        .all()
    )

    return [g._asdict() for g in groups]


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
    groups = _group_lines_stops(stops)

    return render_template("location.html", latitude=latitude,
                           longitude=longitude, list_stops=stops, groups=groups)


@page.route("/near/<string:code>")
def list_near_postcode(code):
    """ Show stops within range of postcode. """
    index_postcode = "".join(code.split()).upper()
    postcode = models.Postcode.query.get(index_postcode)

    if postcode is None:
        raise NotFound(
            Markup("Postcode <strong>{}</strong> does not exist.").format(code)
        )
    if postcode.text != code:
        # Redirect to correct URL, eg 'W1A+1AA' instead of 'w1a1aa'
        return redirect(url_for(".list_near_postcode", code=postcode.text),
                        code=302)

    stops = postcode.stops_in_range(db.undefer(models.StopPoint.lines))
    groups = _group_lines_stops(stops)

    return render_template("postcode.html", postcode=postcode, list_stops=stops,
                           groups=groups)


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
        raise NotFound(
            Markup("Stop area <strong>{}</strong> does not exist.")
            .format(stop_area_code)
        )
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
    groups = _group_lines_stops(stops)

    return render_template("stop_area.html", stop_area=area,
                           stops=stops, groups=groups)


def _query_stop(*, atco_code=None, naptan_code=None):
    stop = (
        models.StopPoint.query
        .options(
            db.joinedload(models.StopPoint.admin_area, innerjoin=True),
            db.joinedload(models.StopPoint.locality, innerjoin=True)
            .joinedload(models.Locality.district),
            db.joinedload(models.StopPoint.stop_area),
            db.joinedload(models.StopPoint.other_stops)
        )
    )

    if atco_code is not None and naptan_code is None:
        stop = stop.filter(models.StopPoint.atco_code == atco_code.upper())
    elif atco_code is None and naptan_code is not None:
        stop = stop.filter(models.StopPoint.naptan_code == naptan_code.lower())
    else:
        raise TypeError("Either keyword argument 'atco_code' or 'naptan_code' "
                        "must be used.")

    return stop.one_or_none()


@page.route("/stop/sms/<naptan_code>")
def stop_naptan(naptan_code):
    """ Shows stop with NaPTAN (SMS) code. """
    stop = _query_stop(naptan_code=naptan_code)

    if stop is None:
        raise NotFound(
            Markup("Stop with SMS code <strong>{}</strong> does not exist.")
            .format(naptan_code)
        )
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
    stop = _query_stop(atco_code=atco_code)

    if stop is None:
        raise NotFound(
            Markup("Stop with ATCO code <strong>{}</strong> does not exist.")
            .format(atco_code)
        )
    if stop.atco_code != atco_code:
        return redirect(url_for(".stop_atco", atco_code=stop.atco_code),
                        code=302)

    services, operators = stop.get_services()
    list_operators = [{"code": c, "name": n} for c, n in operators.items()]

    return render_template("stop.html", stop=stop, services=services,
                           operators=list_operators)


def _query_service(service_code, reverse=None):
    """ Finds service as well as all journey patterns and local operators
        associated with the service.
    """
    sv = (
        models.Service.query
        .join(models.Service.patterns)
        .outerjoin(models.JourneyPattern.operator)
        .options(db.undefer(models.Service.mode_name),
                 db.contains_eager(models.Service.patterns),
                 db.contains_eager(models.Service.operators),
                 db.defaultload(models.Service.operators)
                 .undefer_group("contacts"))
        .filter(models.Service.code == service_code.lower())
        .one_or_none()
    )

    if sv is None:
        raise NotFound(
            Markup("Service <strong>{}</strong> does not exist.")
            .format(service_code)
        )

    # Check line patterns - is there more than 1 direction?
    is_reverse, mirrored = sv.has_mirror(reverse)

    return sv, is_reverse, mirrored


def _display_operators(operators):
    """ Returns sorted list of operators with any information. """
    def sort_name(o): return o.name
    def filter_op(o): return any([o.email, o.address, o.website, o.twitter])

    return sorted(filter(filter_op, operators), key=sort_name)


@page.route("/service/<service_code>")
@page.route("/service/<service_code>/<direction:reverse>")
def service(service_code, reverse=None):
    """ Shows service with code and optional direction, which is outbound by
        default.
    """
    sv, is_reverse, mirrored = _query_service(service_code, reverse)

    if sv.code != service_code or reverse is None or reverse != is_reverse:
        return redirect(url_for(".service", service_code=sv.code,
                                reverse=is_reverse))

    destinations = {
        "origin": {
            p.origin for p in sv.patterns
            if p.direction == is_reverse and p.origin is not None
        },
        "destination": {
            p.destination for p in sv.patterns
            if p.direction == is_reverse and p.destination is not None
        }
    }
    similar = sv.similar(is_reverse, 0.5)

    s_graph, d_stops = graph.service_graph_stops(sv.id, is_reverse)
    sequence = s_graph.sequence()
    try:
        layout = s_graph.draw(max_columns=graph.MAX_COLUMNS).serialize()
    except graph.MaxColumnError:
        layout = None

    return render_template("service.html", service=sv, dest=destinations,
                           reverse=is_reverse, mirrored=mirrored,
                           similar=similar,
                           operators=_display_operators(sv.operators),
                           sequence=sequence, stops=d_stops, layout=layout)


@page.route("/service/<service_code>/timetable")
@page.route("/service/<service_code>/<direction:reverse>/timetable")
def service_timetable(service_code, reverse=None):
    """ Shows timetable for service with ID and optional direction. """
    sv, is_reverse, mirrored = _query_service(service_code, reverse)

    if (sv.code != service_code or reverse is None or reverse != is_reverse or
            "date" not in request.args):
        if "date" in request.args:
            today = request.args["date"]
        else:
            today = datetime.datetime.now(GB_TZ).strftime("%Y-%m-%d")

        return redirect(url_for(".service_timetable", service_code=sv.code,
                                reverse=is_reverse, date=today))

    similar = sv.similar(is_reverse, 0.5)

    select_date = forms.SelectDate(request.args)
    select_date.set_dates(sv)

    if select_date.validate():
        tt_data = timetable.Timetable(sv.id, is_reverse, select_date.date.data)
    else:
        tt_data = None

    return render_template("timetable.html", service=sv, reverse=is_reverse,
                           mirrored=mirrored, similar=similar,
                           operators=_display_operators(sv.operators),
                           timetable=tt_data,
                           select_date=select_date)


def _show_map(service_code=None, reverse=None, atco_code=None, coords=None):
    """ Shows map.

        The map, service line, stop being shown and coordinates/zoom are
        expected to be the same as if the user has navigated there through the
        map interface.

        :param service_code: Service code to show the paths on map. If ATCO code
        is None the service diagram will be shown in panel.
        :param reverse: Direction of service. Ignored if service ID is None.
        :param atco_code: Stop point code to show live data in panel.
        :param coords: Starting map coordinates. If None, the coordinates will
        default to stop point if specified, service paths if specified or the
        centre of GB if neither are specified.
    """
    if atco_code is not None:
        stop = models.StopPoint.query.get(atco_code.upper())
        if stop is None:
            raise NotFound(
                Markup("Stop with code <strong>{}</strong> does not exist.")
                .format(atco_code)
            )
    else:
        stop = None

    if service_code is not None:
        sv = (
            models.Service.query
            .options(db.joinedload(models.Service.patterns))
            .filter(models.Service.code == service_code)
            .one_or_none()
        )
        if sv is None:
            raise NotFound(
                Markup("Service <strong>{}</strong> does not exist.")
                .format(service_code)
            )
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


@page.route("/map/service/<service_code>")
@page.route("/map/service/<service_code>/<lat_long_zoom:coords>")
def show_map_service_no_direction(service_code, coords=None):
    """ Shows map with service and unspecified direction. """
    return _show_map(service_code, coords=coords)


@page.route("/map/service/<service_code>/<direction:reverse>")
@page.route("/map/service/<service_code>/<direction:reverse>/"
            "<lat_long_zoom:coords>")
def show_map_service_direction(service_code, reverse, coords=None):
    """ Shows map with service and direction. """
    return _show_map(service_code, reverse, coords=coords)


@page.route("/map/stop/<atco_code>")
@page.route("/map/stop/<atco_code>/<lat_long_zoom:coords>")
def show_map_stop(atco_code, coords=None):
    """ Shows map with stop. """
    return _show_map(atco_code=atco_code, coords=coords)


@page.route("/map/service/<service_code>/stop/<atco_code>")
@page.route("/map/service/<service_code>/stop/<atco_code>/"
            "<lat_long_zoom:coords>")
def show_map_service_no_direction_stop(service_code, atco_code, coords=None):
    """ Shows map with service, unspecified direction and stop. """
    return _show_map(service_code, atco_code=atco_code, coords=coords)


@page.route("/map/service/<service_code>/<direction:reverse>/stop/<atco_code>")
@page.route("/map/service/<service_code>/<direction:reverse>/stop/<atco_code>/"
            "<lat_long_zoom:coords>")
def show_map_service_direction_stop(service_code, reverse, atco_code,
                                    coords=None):
    """ Shows map with service, direction and stop. """
    return _show_map(service_code, reverse, atco_code, coords)


@page.route("/map/place/<locality_code>")
def show_map_locality(locality_code):
    """ Shows map centred around locality with code. """
    locality = (
        models.Locality.query
        .options(db.undefer_group("coordinates"))
        .get(locality_code.upper())
    )

    if locality is not None:
        return _show_map(coords=(locality.latitude, locality.longitude, 16))
    else:
        raise NotFound(
            Markup("Place with code <strong>{}</strong> does not exist.")
            .format(locality_code)
        )


@page.route("/map/stop_area/<stop_area_code>")
def show_map_stop_area(stop_area_code):
    """ Shows map centred around locality with code. """
    area = models.StopArea.query.get(stop_area_code.upper())

    if area is not None:
        return _show_map(coords=(area.latitude, area.longitude, 17))
    else:
        raise NotFound(
            Markup("Stop area <strong>{}</strong> does not exist.")
            .format(stop_area_code)
        )


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
            message = f"API endpoint {request.path!r} does not exist."
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
        return jsonify({"message": str(error)}), 500
    else:
        return render_template("error.html", message=error), 500
