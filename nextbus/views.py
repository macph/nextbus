"""
Views for the nextbus website.
"""
import collections
import re
from requests import HTTPError
from sqlalchemy import literal_column, or_
from sqlalchemy.orm import load_only
from flask import abort, Blueprint, current_app, jsonify, render_template, redirect, request
from nextbus import db, forms, location, models, search, tapi


MIN_GROUPED = 72
MAX_DISTANCE = 500
FIND_COORD = re.compile(r"^([-+]?\d*\.?\d+|[-+]?\d+\.?\d*),\s*"
                        r"([-+]?\d*\.?\d+|[-+]?\d+\.?\d*)$")

page = Blueprint('page', __name__, template_folder='templates')


class EntityNotFound(Exception):
    """ Used to initiate a 404 with custom message. """
    pass


def _find_stops_in_range(coord):
    """ Helper function for finding stop points in range of lat/long
        coordinates. Returns an ordered list of stop points and their distances
        from said coordinates.
        :param coord: Latitude and longitude as tuple of two floats.
        :returns: List of tuples (stop, distance from coord), sorted by the
        latter value.
    """
    lat_0, long_0, lat_1, long_1 = location.bounding_box(coord, MAX_DISTANCE)
    query_nearby_stops = models.StopPoint.query.filter(
        models.StopPoint.latitude > lat_0,
        models.StopPoint.latitude < lat_1,
        models.StopPoint.longitude > long_0,
        models.StopPoint.longitude < long_1
    )
    stops = [(stop, location.get_dist(coord, (stop.latitude, stop.longitude)))
             for stop in query_nearby_stops.all()]
    return sorted(filter(lambda x: x[1] < MAX_DISTANCE, stops), key=lambda x: x[1])


def _group_places(list_places, attr=None, key=None):
    """ Groups localities by their names, or under a single key 'A-Z' if the
        total is less than MIN_GROUPED.

        :param list_places: list of models.Locality objects.
        :param attr: First letter of attribute to group by.
        :param key: First letter of dict key to group by.
        :returns: Dictionary of models.Locality objects.
        :raises AttributeError: Either an attribute or a key must be specified.
    """
    groups = {}
    if list_places:
        if len(list_places) > MIN_GROUPED:
            groups = collections.defaultdict(list)
            for item in list_places:
                if attr is None and key is not None:
                    groups[item[key][0]].append(item)
                elif attr is not None and key is None:
                    groups[getattr(item, attr)[0]].append(item)
                else:
                    raise AttributeError("Either an attribute or a key must "
                                         "be specified.")
        else:
            groups = {'A-Z': list_places}

    return groups


@page.route('/', methods=['GET', 'POST'])
def index():
    """ The home page. """
    f_search = forms.SearchPlaces()
    if f_search.submit_query.data and f_search.validate():
        if isinstance(f_search.result, models.StopPoint):
            return redirect('/stop/atco/%s' % f_search.result.atco_code)
        elif isinstance(f_search.result, models.Postcode):
            return redirect('/near/postcode/%s' % f_search.result.text.replace(' ', '+'))
        else:
            return redirect('/search/%s' % f_search.query.replace(' ', '+'))

    return render_template('index.html', form_search=f_search)


@page.route('/about')
def about():
    """ The about page. """
    return render_template('about.html')


@page.route('/search/<query>')
def search_results(query):
    """ Shows a list of search results. """
    s_query = query.replace('+', ' ')
    result = search.search_full(s_query, forms.parser.parse_query)
    # Redirect to postcode or stop if one was found
    if isinstance(result, models.StopPoint):
        return redirect('/stop/atco/%s' % result.atco_code)
    elif isinstance(result, models.Postcode):
        return redirect('/near/postcode/%s' % result.text.replace(' ', '+'))

    dict_result = collections.defaultdict(list)
    for row in result:
        if row.table_name in ['admin_area', 'district']:
            dict_result['area'].append(row)
        elif row.table_name in ['stop_area', 'stop_point']:
            dict_result['stop'].append(row)
        else:
            dict_result[row.table_name].append(row)
    for group, rows in dict_result.items():
        dict_result[group] = sorted(rows, key=lambda r: r.name)

    return render_template('search.html', query=s_query, results=dict_result)


@page.route('/list/')
def list_regions():
    """ Shows list of all regions. """
    regions = (models.Region.query.options(load_only('code', 'name'))
               .filter(models.Region.code != 'GB').order_by('name')).all()

    return render_template('all_regions.html', regions=regions)


@page.route('/list/region/<region_code>')
def list_in_region(region_code):
    """ Shows list of administrative areas and districts in a region.
        Administrative areas with districts are excluded in favour of listing
        districts.
    """
    region = models.Region.query.get(region_code.upper())
    if region is None:
        raise EntityNotFound("Region with code '%s' does not exist." % region_code)
    if region.code != region_code:
        return redirect('/list/region/%s' % region.code, code=301)

    q_area = (models.AdminArea.query
              .outerjoin(models.AdminArea.districts) # LEFT OUTER JOIN
              .filter(models.District.code.is_(None),
                      models.AdminArea.region_code == region.code))
    q_district = (models.District.query
                  .join(models.AdminArea.districts)
                  .filter(models.AdminArea.region_code == region.code))
    list_areas = sorted(q_area.all() + q_district.all(), key=lambda a: a.name)

    return render_template('region.html', region=region, areas=list_areas)


@page.route('/list/area/<area_code>')
def list_in_area(area_code):
    """ Shows list of districts or localities in administrative area - not all
        administrative areas have districts.
    """
    area = models.AdminArea.query.get(area_code)
    if area is None:
        raise EntityNotFound("Area with code '%s' does not exist." % area_code)

    region = (models.Region.query
              .filter(models.Region.code == area.region_code)).one()
    ls_district = (models.District.query
                   .filter(models.District.admin_area_code == area.code)
                   .order_by(models.District.name)).all()
    if not ls_district:
        ls_local = (models.Locality.query
                    .outerjoin(models.Locality.stop_points)
                    .filter(models.StopPoint.atco_code.isnot(None),
                            models.Locality.admin_area_code == area.code)
                    .order_by(models.Locality.name)).all()
    else:
        ls_local = []
    group_local = _group_places(ls_local, attr='name')

    return render_template('area.html', region=region, area=area, districts=ls_district,
                           localities=group_local)


@page.route('/list/district/<district_code>')
def list_in_district(district_code):
    """ Shows list of localities in district. """
    district = models.District.query.get(district_code)
    if district is None:
        raise EntityNotFound("District with code '%s' does not exist." % district_code)

    info = (db.session.query(models.Region.code.label('region_code'),
                             models.Region.name.label('region_name'),
                             models.AdminArea.code.label('area_code'),
                             models.AdminArea.name.label('area_name'))
            .select_from(models.District)
            .join(models.AdminArea,
                  models.AdminArea.code == models.District.admin_area_code)
            .join(models.Region,
                  models.Region.code == models.AdminArea.region_code)
            .filter(models.District.code == district.code)).one()
    ls_local = (models.Locality.query
                .outerjoin(models.Locality.stop_points)
                .filter(models.StopPoint.atco_code.isnot(None),
                        models.Locality.district_code == district.code)
                .order_by(models.Locality.name)).all()
    group_local = _group_places(ls_local, attr='name')


    return render_template('district.html', info=info, district=district,
                           localities=group_local)


@page.route('/list/locality/<locality_code>')
def list_in_locality(locality_code):
    """ Shows stops in locality. """
    lty = models.Locality.query.get(locality_code.upper())
    if lty is None:
        raise EntityNotFound("Locality with code '%s' does not exist." % locality_code)
    else:
        if lty.code != locality_code:
            return redirect('/list/locality/%s' % lty.code, code=301)

    info = (db.session.query(models.AdminArea.code.label('area_code'),
                             models.AdminArea.name.label('area_name'),
                             models.Region.code.label('region_code'),
                             models.Region.name.label('region_name'),
                             models.District.code.label('district_code'),
                             models.District.name.label('district_name'))
            .select_from(models.Locality)
            .outerjoin(models.District,
                       models.District.code == models.Locality.district_code)
            .join(models.AdminArea,
                  models.AdminArea.code == models.Locality.admin_area_code)
            .join(models.Region,
                  models.Region.code == models.AdminArea.region_code)
            .filter(models.Locality.code == lty.code)
           ).one()

    # Find all stop areas and all stop points _not_ associated with a stop area
    table_name = lambda m: literal_column("'%s'" % m.__tablename__)
    stops = (db.session.query(table_name(models.StopPoint).label('table'),
                              models.StopPoint.atco_code.label('code'),
                              models.StopPoint.common_name.label('name'),
                              models.StopPoint.short_ind.label('ind'))
             .outerjoin(models.StopPoint.stop_area)
             .filter(models.StopPoint.locality_code == lty.code,
                     models.StopPoint.stop_area_code.is_(None))
            )
    areas = (db.session.query(table_name(models.StopArea).label('table'),
                              models.StopArea.code,
                              models.StopArea.name,
                              db.cast(db.func.count(models.StopArea.code), db.Text).label('ind'))
             .join(models.StopArea.stop_points)
             .group_by(models.StopArea.code)
             .filter(models.StopArea.locality_code == lty.code)
            )
    list_stops = stops.union(areas).order_by('name', 'ind').all()
    stops = _group_places(list_stops, attr='name')

    return render_template('locality.html', info=info, locality=lty, stops=stops)


@page.route('/near/postcode/<postcode>')
def list_nr_postcode(postcode):
    """ Show stops within range of postcode. """
    str_psc = postcode.replace('+', ' ')
    index_psc = ''.join(str_psc.split()).upper()
    psc = models.Postcode.query.get(index_psc)
    if psc is None:
        raise EntityNotFound("Postcode '%s' does not exist." % postcode)
    else:
        if psc.text != str_psc:
            # Redirect to correct URL, eg 'W1A+1AA' instead of 'w1a1aa'
            return redirect('/near/postcode/%s' % psc.text.replace(' ', '+'), code=301)

    stops = _find_stops_in_range((psc.latitude, psc.longitude))

    return render_template('postcode.html', postcode=psc, list_stops=stops)


@page.route('/near/location/<lat_long>')
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
    stops = _find_stops_in_range(coord)

    return render_template('location.html', coord=coord, list_stops=stops)


@page.route('/stop/area/<stop_area_code>')
def stop_area(stop_area_code):
    """ Show stops in stop area, eg pair of tram platforms. """
    s_area = models.StopArea.query.get(stop_area_code.upper())
    if s_area is None:
        raise EntityNotFound("Bus stop with NaPTAN code %r does not exist"
                             % stop_area_code)
    else:
        if s_area.code != stop_area_code:
            return redirect('/stop/naptan/%s' % s_area.code, code=301)

    area_info = {c: getattr(s_area, c) for c in ['name', 'latitude', 'longitude']}
    query_stops = (
        db.session.query(
            models.StopPoint.atco_code,
            models.StopPoint.common_name,
            models.StopPoint.indicator,
            models.StopPoint.short_ind,
            models.StopPoint.street,
            models.StopPoint.latitude,
            models.StopPoint.longitude,
            models.StopPoint.bearing
        ).filter(models.StopPoint.stop_area_code == s_area.code)
    )
    list_stops = [r._asdict() for r in query_stops.all()]

    return render_template('stop_area.html', stop_area=s_area, area_info=area_info,
                           list_stops=list_stops)


@page.route('/stop/naptan/<naptan_code>')
def stop_naptan(naptan_code):
    """ Shows stop with NaPTAN code. """
    stop = models.StopPoint.query.filter_by(naptan_code=naptan_code.lower()).one_or_none()
    if stop is None:
        raise EntityNotFound("Bus stop with NaPTAN code %r does not exist"
                             % naptan_code)
    else:
        if stop.naptan_code != naptan_code:
            return redirect('/stop/naptan/%s' % stop.naptan_code, code=301)

    return render_template('stop.html', stop=stop)


@page.route('/stop/atco/<atco_code>')
def stop_atco(atco_code):
    """ Shows stop with NaPTAN code. """
    stop = models.StopPoint.query.get(atco_code.upper())
    if stop is None:
        raise EntityNotFound("Bus stop with ATCO code %r does not exist"
                             % atco_code)
    else:
        if stop.atco_code != atco_code:
            return redirect('/stop/atco/%s' % stop.atco_code, code=301)

    return render_template('stop.html', stop=stop)


@page.route('/stop/get', methods=['POST'])
def stop_get_times():
    """ Requests and retrieve bus times. """
    if request.method == 'POST':
        data = request.get_json()
    else:
        # Trying to access with something other than POST
        current_app.logger.error("/stop/get was accessed with something other than POST")
        abort(405)
    try:
        nxb = tapi.parse_nextbus_times(data['code'])
    except (KeyError, ValueError) as err:
        # Malformed request; no ATCO code
        current_app.logger.error(err)
        abort(400)
    except HTTPError:
        # Problems with the API service
        current_app.logger.warning("Can't access API service.")
        abort(503)

    return jsonify(nxb)


@page.errorhandler(404)
@page.errorhandler(EntityNotFound)
def not_found_msg(error):
    """ Returned in case of an invalid URL, with message. Can be called with
        EntityNotFound, eg if the correct URL is used but the wrong value is
        given.
    """
    return render_template('not_found.html', message=error), 404


@page.errorhandler(500)
def error_msg(error):
    """ Returned in case an internal server error (500) occurs, with message.
        Note that this page does not appear in debug mode.
    """
    return render_template('error.html', message=error), 500
