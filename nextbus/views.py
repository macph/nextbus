"""
Views for the nextbus website.
"""
from flask import render_template, redirect
from nextbus import app, forms, location, models

MAX_DISTANCE = 500


class EntityNotFound(Exception):
    """ Used to initiate a 404 with custom message. """
    pass


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
    sp = models.StopPoint.query.filter_by(naptan_code=naptan_code).scalar()
    if sp is not None:
        ly = sp.locality
        ds = ly.district if ly is not None else None
        return render_template('stop_naptan.html', naptan_code=naptan_code,
                               stop=sp, locality=ly, district=ds)
    else:
        raise EntityNotFound("Bus stop with NaPTAN code '%s' does not exist"
                             % naptan_code)


@app.route('/postcode/<postcode>')
def list_stops_postcode(postcode):
    """ Show stops within range of postcode. """
    regex = r"([A-Za-z]{1,2}\d{1,2}[A-Za-z]?)[+\s]*(\d[A-Za-z]{2})"

    str_psc = ''.join(postcode.split()).upper().replace('+', ' ')
    psc = models.Postcode.query.filter_by(postcode=str_psc).scalar()
    if psc is None:
        new_psc = models.Postcode.query.filter_by(postcode_2=str_psc).scalar()
        if new_psc is not None:
            return redirect('/postcode/%s' % new_psc.postcode.replace(' ', '+'),
                            code=301)
        else:
            raise EntityNotFound("Postcode '%s' does not exist." % postcode)
    
    coord = (psc.latitude, psc.longitude)
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
    ordered_stops = sorted(filter_stops, key=lambda x: x[1])

    return render_template('postcode.html', postcode=psc,
                           list_stops=ordered_stops)

@app.route('/location/<lat_long>')
def list_stops_location(lat_long):
    """ Show stops within range of a GPS coordinate. """
    regex = r"([-+]?\d*\.?\d+|[-+]?\d+\.?\d*)"
    oob = ("Latitude and longitude values out of bounds; this application is "
           "meant to be used within Great Britain only.")
    invalid = "Invalid latitude/longitude values."

    try:
        split = lat_long.split(',')
        if len(split) != 2:
            raise EntityNotFound(invalid)
        coord = (float(split[0]), float(split[1]))
        if not (49 < coord[0] < 61 and -8 < coord[1] < 2):
            raise EntityNotFound(oob)
    except (TypeError, ValueError):
        raise EntityNotFound(invalid)
    
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
    ordered_stops = sorted(filter_stops, key=lambda x: x[1])

    return render_template('location.html', coord=coord,
                           list_stops=ordered_stops)


@app.route('/locality/<locality>')
def list_stops_locality(locality):
    """ Shows stops in locality. """
    return "This is the page for the locality '%s'." % locality


@app.errorhandler(404)
@app.errorhandler(EntityNotFound)
def not_found_msg(error):
    """ Returned in case of an invalid URL, with message. Can be called with
        EntityNotFound, eg if the correct URL is used but the wrong value is
        given.
    """
    return render_template('not_found.html', message=error), 404
