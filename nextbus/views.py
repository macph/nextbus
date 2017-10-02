"""
Views for the nextbus website.
"""
from flask import render_template, redirect
from nextbus import app, forms, models, os_grid

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
        ly = (models.Locality.query
              .filter_by(nptg_locality_code=sp.nptg_locality_code).scalar())
        if ly is not None:
            str_ly = ly.locality_name
            ds = (models.District.query
                  .filter_by(nptg_district_code=ly.nptg_district_code).scalar())
            str_ds = ds.district_name if ds is not None else ''
        else:
            str_ly, str_ds = '', ''
        return render_template('stop_naptan.html', naptan_code=naptan_code,
                               stop=sp, locality=str_ly, district=str_ds)
    else:
        raise EntityNotFound("Bus stop with NaPTAN code '%s' does not exist"
                             % naptan_code)


@app.route('/postcode/<postcode>')
def list_stops_postcode(postcode):
    """ Show stops within range of postcode. """
    str_psc = ''.join(postcode.split()).upper().replace('+', ' ')
    psc = models.Postcode.query.filter_by(postcode=str_psc).scalar()
    if psc is None:
        new_psc = models.Postcode.query.filter_by(postcode_2=str_psc).scalar()
        if new_psc is not None:
            return redirect('/postcode/%s' % new_psc.postcode.replace(' ', '+'),
                            code=301)
        else:
            raise EntityNotFound("Postcode '%s' does not exist." % postcode)

    query_nearby_stops = models.StopPoint.query.filter(
        models.StopPoint.easting < psc.easting + MAX_DISTANCE,
        models.StopPoint.easting > psc.easting - MAX_DISTANCE,
        models.StopPoint.northing < psc.northing + MAX_DISTANCE,
        models.StopPoint.northing > psc.northing - MAX_DISTANCE,
        models.StopPoint.naptan_code.isnot(None)
    )
    filter_stops = []
    for stop in query_nearby_stops.all():
        distance = (abs(stop.easting-psc.easting) ** 2
                    + abs(stop.northing-psc.northing) ** 2) ** 0.5
        if distance < MAX_DISTANCE:
            filter_stops.append((stop, distance))
    ordered_stops = sorted(filter_stops, key=lambda x: x[1])

    return render_template('postcode.html', postcode=psc,
                           list_stops=ordered_stops)

@app.route('/location/<lat_long>')
def list_stops_location(lat_long):
    """ Show stops within range of a GPS coordinate. """
    oob = ("Latitude and longitude values out of bounds; this application is "
           "meant to be used within Great Britain only.")
    invalid = "Invalid latitude/longitude values."
    coordinates = lat_long.split(',')
    if len(coordinates) != 2:
        raise EntityNotFound(invalid)
    try:
        latitude, longitude = float(coordinates[0]), float(coordinates[1])
    except (TypeError, ValueError):
        raise EntityNotFound(invalid)
    if not (49 < latitude < 62 and -9 < longitude < 4):
        raise EntityNotFound(oob)
    try:
        easting, northing = os_grid.lat_long_to_os_grid(latitude, longitude)
    except ValueError:
        raise EntityNotFound(oob)

    query_nearby_stops = models.StopPoint.query.filter(
        models.StopPoint.easting < easting + MAX_DISTANCE,
        models.StopPoint.easting > easting - MAX_DISTANCE,
        models.StopPoint.northing < northing + MAX_DISTANCE,
        models.StopPoint.northing > northing - MAX_DISTANCE,
        models.StopPoint.naptan_code.isnot(None)
    )
    filter_stops = []
    for stop in query_nearby_stops.all():
        distance = (abs(stop.easting-easting) ** 2
                    + abs(stop.northing-northing) ** 2) ** 0.5
        if distance < MAX_DISTANCE:
            filter_stops.append((stop, distance))
    ordered_stops = sorted(filter_stops, key=lambda x: x[1])

    return render_template('location.html', lat=latitude, long=longitude,
                           list_stops=ordered_stops)


@app.route('/locality/<locality>')
def list_stops_locality(locality):
    """ Shows stops in locality. """
    return "This is the page for the locality '%s'." % locality


@app.errorhandler(404)
def not_found(error):
    """ Returned in case of an invalid URL. """
    return render_template('not_found.html', message=error), 404


@app.errorhandler(EntityNotFound)
def not_found_msg(error):
    """ Returned in case of an invalid URL, with message. Can be called with
        EntityNotFound, eg if the correct URL is used but the wrong value is
        given.
    """
    return render_template('not_found.html', message=error), 404
