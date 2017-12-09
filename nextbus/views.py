"""
Views for the nextbus website.
"""
import collections
import re
from requests import HTTPError
from sqlalchemy import or_
from sqlalchemy.orm import load_only
from flask import abort, Blueprint, current_app, jsonify, render_template, redirect, request
from nextbus import db, forms, location, models, tapi


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


def _group_places(list_places, attribute):
    """ Groups localities by their names, or under a single key 'A-Z' if the
        total is less than MIN_GROUPED.

        :param list_places: list of models.Locality objects.
        :param attribute: First letter of attribute to group by.
        :returns: Dictionary of models.Locality objects.
    """
    groups = {}
    if list_places:
        if len(list_places) > MIN_GROUPED:
            groups = collections.defaultdict(list)
            for p in list_places:
                groups[getattr(p, attribute)[0]].append(p)
        else:
            groups = {'A-Z': list_places}

    return groups


@page.route('/', methods=['GET', 'POST'])
def index():
    """ The home page. """
    f_naptan = forms.FindStop()
    f_postcode = forms.FindPostcode()
    if f_naptan.submit_code.data and f_naptan.validate():
        return redirect('/stop/naptan/%s' % f_naptan.new)
    if f_postcode.submit_postcode.data and f_postcode.validate():
        return redirect('/near/postcode/%s' % f_postcode.new.replace(' ', '+'))

    return render_template('index.html', form_naptan=f_naptan, form_postcode=f_postcode)


@page.route('/about')
def about():
    """ The about page. """
    return render_template('about.html')


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
    region = models.Region.query.get(region_code)
    if region is None:
        raise EntityNotFound("Region with code '%s' does not exist." % region_code)

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
    group_local = _group_places(ls_local, 'name')

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
            .join(models.Region.areas)
            .filter(models.AdminArea.code == district.admin_area_code)).one()
    ls_local = (models.Locality.query
                .outerjoin(models.Locality.stop_points)
                .filter(models.StopPoint.atco_code.isnot(None),
                        models.Locality.district_code == district.code)
                .order_by(models.Locality.name)).all()
    group_local = _group_places(ls_local, 'name')


    return render_template('district.html', info=info._asdict(), district=district,
                           localities=group_local)


@page.route('/list/locality/<locality_code>')
def list_in_locality(locality_code):
    """ Shows stops in locality. """
    lty = models.Locality.query.get(locality_code)
    if lty is None:
        str_lty = locality_code.upper()
        new_lty = models.Locality.query.filter_by(code=str_lty).one_or_none()
        if new_lty is not None:
            return redirect('/list/locality/%s' % new_lty.code,
                            code=301)
        else:
            raise EntityNotFound("Locality with code '%s' does not exist." % locality_code)

    # SELECT admin_area.code AS area_code,
    #        admin_area.name AS area_name,
    #        region.code AS region_code,
    #        region.name AS region_name,
    #        district.code AS district_code,
    #        district.name AS district_name
    #   FROM region, admin_area
    #        LEFT OUTER JOIN district
    #                     ON admin_area.code = district.admin_area_cod
    #        INNER JOIN admin_area
    #                ON admin_area.region_code = region.code
    #  WHERE admin_area.code = ? AND (district.code = ? OR district.code IS NULL)
    info = (db.session.query(models.AdminArea.code.label('area_code'),
                             models.AdminArea.name.label('area_name'),
                             models.Region.code.label('region_code'),
                             models.Region.name.label('region_name'),
                             models.District.code.label('district_code'),
                             models.District.name.label('district_name'))
            .outerjoin(models.AdminArea.districts)
            .join(models.Region, models.AdminArea.region_code == models.Region.code)
            .filter(models.AdminArea.code == lty.admin_area_code,
                    or_(models.District.code == lty.district_code,
                        models.District.code.is_(None)))
           ).one()

    list_stops = (models.StopPoint.query
                  .filter(models.StopPoint.locality_code == lty.code)
                  .order_by('common_name', 'short_ind')).all()
    stops = _group_places(list_stops, 'common_name')

    return render_template('locality.html', info=info._asdict(), locality=lty, stops=stops)


@page.route('/near/postcode/<postcode>')
def list_nr_postcode(postcode):
    """ Show stops within range of postcode. """
    str_psc = postcode.replace('+', ' ')
    psc = models.Postcode.query.filter_by(text=str_psc).one_or_none()
    if psc is None:
        new_str = ''.join(str_psc.split()).upper()
        new_psc = models.Postcode.query.filter_by(index=new_str).one_or_none()
        if new_psc is not None:
            # Redirect to correct URL, eg 'W1A+1AA' instead of 'w1a1aa'
            return redirect('/near/postcode/%s' % new_psc.text.replace(' ', '+'), code=301)
        else:
            raise EntityNotFound("Postcode '%s' does not exist." % postcode)

    coord = (psc.latitude, psc.longitude)
    stops = _find_stops_in_range(coord)

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
    s_area = models.StopArea.query.get(stop_area_code)
    if s_area is None:
        s_area2 = models.StopArea.query.filter(models.StopArea.code
                                               .ilike(stop_area_code)).one_or_none()
        if s_area2 is not None:
            return redirect('/stop/naptan/%s' % s_area2.stop_area_code, code=301)
        else:
            raise EntityNotFound("Bus stop with NaPTAN code %r does not exist"
                                 % stop_area_code)

    area_info = {c: getattr(s_area, c) for c in ['name', 'latitude', 'longitude']}

    query_stops = db.session.query(
        models.StopPoint.atco_code,
        models.StopPoint.common_name,
        models.StopPoint.indicator,
        models.StopPoint.short_ind,
        models.StopPoint.street,
        models.StopPoint.latitude,
        models.StopPoint.longitude
    ).filter_by(stop_area_code=s_area.code).all()
    list_stops = list(map(lambda i: i._asdict(), query_stops))

    return render_template('stop_area.html', stop_area=s_area, area_info=area_info,
                           list_stops=list_stops)


@page.route('/stop/naptan/<naptan_code>')
def stop_naptan(naptan_code):
    """ Shows stop with NaPTAN code. """
    s_pt = models.StopPoint.query.filter_by(naptan_code=naptan_code).one_or_none()
    if s_pt is None:
        s_pt2 = models.StopPoint.query.filter(models.StopPoint.naptan_code
                                              .ilike(naptan_code)).one_or_none()
        if s_pt2 is not None:
            return redirect('/stop/naptan/%s' % s_pt2.naptan_code, code=301)
        else:
            raise EntityNotFound("Bus stop with NaPTAN code %r does not exist"
                                 % naptan_code)

    return render_template('stop.html', stop=s_pt)


@page.route('/stop/atco/<atco_code>')
def stop_atco(atco_code):
    """ Shows stop with NaPTAN code. """
    s_pt = models.StopPoint.query.filter_by(atco_code=atco_code).one_or_none()
    if s_pt is None:
        s_pt2 = models.StopPoint.query.filter(models.StopPoint.atco_code
                                              .ilike(atco_code)).one_or_none()
        if s_pt2 is not None:
            return redirect('/stop/atco/%s' % s_pt2.atco_code, code=301)
        else:
            raise EntityNotFound("Bus stop with ATCO code %r does not exist"
                                 % atco_code)

    return render_template('stop.html', stop=s_pt)


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
