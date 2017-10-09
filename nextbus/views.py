"""
Views for the nextbus website.
"""
import re
from flask import render_template, redirect
from nextbus import app, forms, location, models, tapi

MAX_DISTANCE = 500
FIND_POSTCODE = re.compile(r"^([A-Za-z]{1,2}\d{1,2}[A-Za-z]?)[+\s]*"
                           r"(\d[A-Za-z]{2})$")
FIND_COORD = re.compile(r"^([-+]?\d*\.?\d+|[-+]?\d+\.?\d*),\s*"
                        r"([-+]?\d*\.?\d+|[-+]?\d+\.?\d*)$")


class EntityNotFound(Exception):
    """ Used to initiate a 404 with custom message. """
    pass


def _find_stops_in_range(coord):
    """ Helper function for finding stop points in range of lat/long
        coordinates (as tuple of two decimal degrees). Returns an ordered
        list of stop points and their distances from said coordinate.
    """
    lat_0, long_0, lat_1, long_1 = location.bounding_box(coord, MAX_DISTANCE)
    query_nearby_stops = models.StopPoint.query.filter(
        models.StopPoint.latitude > lat_0,
        models.StopPoint.latitude < lat_1,
        models.StopPoint.longitude > long_0,
        models.StopPoint.longitude < long_1,
        models.StopPoint.naptan_code.isnot(None)
    )
    filter_stops = []
    for stop in query_nearby_stops.all():
        distance = location.distance(coord, (stop.latitude, stop.longitude))
        if distance < MAX_DISTANCE:
            filter_stops.append((stop, distance))

    return sorted(filter_stops, key=lambda x: x[1])


@app.route('/', methods=['GET', 'POST'])
def index():
    """ The home page. """
    f_naptan = forms.FindStop()
    f_postcode = forms.FindPostcode()
    if f_naptan.validate_on_submit():
        return redirect('/naptan/%s' % f_naptan.code.data)
    if f_postcode.validate_on_submit():
        str_ps = ''.join(f_postcode.postcode.data.split()).upper()
        psc = models.Postcode.query.filter_by(postcode_2=str_ps).scalar()
        return redirect('/postcode/%s' % psc.postcode.replace(' ', '+'))

    return render_template('index.html', form_naptan=f_naptan,
                           form_postcode=f_postcode)


@app.route('/about')
def about():
    """ The about page. """
    return "About me: Uhm. Check later?"


@app.route('/naptan/<naptan_code>')
def bus_stop_naptan(naptan_code):
    """ Shows stop with NaPTAN code. """
    s_pt = models.StopPoint.query.filter_by(naptan_code=naptan_code).scalar()
    if s_pt is not None:
        nxb = tapi.get_nextbus_times(s_pt.atco_code)
        return render_template('stop_naptan.html', naptan_code=naptan_code,
                               stop=s_pt, times=nxb)
    else:
        raise EntityNotFound("Bus stop with NaPTAN code %r does not exist"
                             % naptan_code)


@app.route('/postcode/<postcode>')
def list_stops_nr_postcode(postcode):
    """ Show stops within range of postcode. """
    str_psc = ''.join(postcode.split()).upper().replace('+', ' ')
    psc = models.Postcode.query.filter_by(postcode=str_psc).scalar()
    if psc is None:
        new_psc = models.Postcode.query.filter_by(postcode_2=str_psc).scalar()
        if new_psc is not None:
            # Redirect to correct URL, eg 'W1A+1AA' instead of 'w1a1aa'
            return redirect('/postcode/%s' % new_psc.postcode.replace(' ', '+'),
                            code=301)
        else:
            raise EntityNotFound("Postcode '%s' does not exist." % postcode)

    coord = (psc.latitude, psc.longitude)
    stops = _find_stops_in_range(coord)

    return render_template('postcode.html', postcode=psc, list_stops=stops)


@app.route('/location/<lat_long>')
def list_stops_nr_location(lat_long):
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


@app.route('/locality/<locality_code>')
def list_stops_in_locality(locality_code):
    """ Shows stops in locality. """
    lty = (models.Locality.query
           .filter_by(nptg_locality_code=locality_code).scalar())
    if lty is None:
        str_lty = locality_code.upper()
        new_lty = (models.Locality.query
                   .filter_by(nptg_locality_code=str_lty).scalar())
        if new_lty is not None:
            return redirect('/locality/%s' % new_lty.nptg_locality_code,
                            code=301)
        else:
            raise EntityNotFound("Locality with code '%s' does not exist."
                                 % locality_code)

    return render_template('locality.html', locality=lty)


@app.route('/district/<district_code>')
def list_localities_in_district(district_code):
    """ Shows list of localities in district. """
    district = (models.District.query
                .filter_by(nptg_district_code=district_code).scalar())
    if district is not None:
        return render_template('district.html', district=district)
    else:
        raise EntityNotFound("District with code '%s' does not exist."
                             % district_code)


@app.route('/area/<area_code>')
def list_in_area(area_code):
    """ Shows list of districts or localities in administrative area - not all
        administrative areas have districts.
    """
    area = models.AdminArea.query.filter_by(admin_area_code=area_code).scalar()
    if area is not None:
        return render_template('area.html', area=area)
    else:
        raise EntityNotFound("Area with code '%s' does not exist." % area_code)

@app.route('/regions')
def list_regions():
    """ Shows list of all regions being used. """
    regions = models.Region.query.all()

    return render_template('regions.html', regions=regions)


@app.errorhandler(404)
@app.errorhandler(EntityNotFound)
def not_found_msg(error):
    """ Returned in case of an invalid URL, with message. Can be called with
        EntityNotFound, eg if the correct URL is used but the wrong value is
        given.
    """
    return render_template('not_found.html', message=error), 404
