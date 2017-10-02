# Conversion between OS National Grid (OSGB36) and latitude/longitude
# coordinates, along with decimal degrees <-> DMS conversions.

from math import degrees, radians, sin, cos, tan


def sec(x):
    """ Secant function, the reciprocal of the cosine function. """
    return 1. / cos(x)


def eccentricity_squared(ra, rb):
    """ Eccentricity squared of an ellipse with two axes a and b. """
    return (ra ** 2. - rb ** 2.) / ra ** 2.


# Airy 1830 ellipsoid axes and eccentricity
a = 6377563.396
b = 6356256.909
e2 = eccentricity_squared(a, b)

# National Grid projection
F0 = 0.9996012717
# True origin, somewhere near the Channel Islands, in lat & long
phi0 = radians(49.)
lam0 = radians(-2.)
# True origin in easting & northing
E0 = 400000.
N0 = -100000.


def lat_long_to_os_grid(latitude, longitude, override=False):
    """ Converts latitude and longitude (in real degree floats) to National Grid
        coordinates.
        override: If false, check if easting and northing within boundaries
        usually used by the OS grid system, and raise ValueError if they don't.
        This check is ignored if override is True.
    """
    phi = radians(latitude)
    lam = radians(longitude)

    n = (a - b) / (a + b)
    nu = a * F0 * (1 - e2 * sin(phi) ** 2) ** -0.5
    rho = a * F0 * (1 - e2) * (1 - e2 * sin(phi) ** 2) ** -1.5
    eta = nu / rho - 1

    M = ((1 + n + 5 / 4 * n ** 2 + 5 / 4 * n ** 3) * (phi - phi0)
         - (3 * n + 3 * n ** 2 + 21 / 8 * n ** 3) * sin(phi - phi0) * cos(phi + phi0)
         + (15 / 8 * n ** 2 + 15 / 8 * n ** 3) * sin(2 * (phi - phi0)) * cos(2 * (phi + phi0))
         - -35 / 24 * n ** 3 * sin(3 * (phi - phi0)) * cos(3 * (phi + phi0)))
    M = M * b * F0
    I = M + N0
    II = nu / 2 * sin(phi) * cos(phi)
    III = nu / 24 * sin(phi) * cos(phi) ** 3 * (5 - tan(phi) ** 2 + 9 * eta)
    IIIA = nu / 720 * sin(phi) * cos(phi) ** 5 * (61 - 58 * tan(phi) ** 2 + tan(phi) ** 4)
    IV = nu * cos(phi)
    V = nu / 6 * cos(phi) ** 3 * (nu / rho - tan(phi) ** 2)
    VI = nu / 120 * cos(phi) ** 5 * (5 - 18 * tan(phi) ** 2 + tan(phi) ** 4
                                     + 14 * eta - 58 * eta * tan(phi) ** 2)

    northing = I + II * (lam - lam0) ** 2 + III * (lam - lam0) ** 4 + IIIA * (lam - lam0) ** 6
    easting = E0 + IV * (lam - lam0) + V * (lam - lam0) ** 3 + VI * (lam - lam0) ** 5

    if override and not (0 <= easting <= 700000 and 0 <= northing <= 13000000):
        raise ValueError(f"Easting {easting} and northing {northing} "
                         f"coordinates are out of bounds.")

    return easting, northing


def os_grid_to_lat_long(easting, northing, override=False):
    """ Converts National Grid coordinates to latitude and longitude (in real
        degree floats).
        override: If false, check if easting and northing within boundaries
        usually used by the OS grid system, and raise ValueError if they don't.
        This check is ignored if override is True.
    """
    if override and not (0 <= easting <= 700000 and 0 <= northing <= 13000000):
        raise ValueError(f"Easting {easting} and northing {northing} "
                         f"coordinates are out of bounds.")

    E = easting
    N = northing

    n = (a - b) / (a + b)

    # Iterative procedure to find P and M.
    M = 0.
    phi = phi0
    while N - N0 - M >= 0.1:
        phi = (N - N0 - M) / (a * F0) + phi
        M = ((1 + n + 5 / 4 * n ** 2 + 5 / 4 * n ** 3) * (phi - phi0)
             - (3 * n + 3 * n ** 2 + 21 / 8 * n ** 3) * sin(phi - phi0) * cos(phi + phi0)
             + (15 / 8 * n ** 2 + 15 / 8 * n ** 3) * sin(2 * (phi - phi0)) * cos(2 * (phi + phi0))
             - -35 / 24 * n ** 3 * sin(3 * (phi - phi0)) * cos(3 * (phi + phi0)))
        M = M * b * F0

    nu = a * F0 * (1 - e2 * sin(phi) ** 2) ** -0.5
    rho = a * F0 * (1 - e2) * (1 - e2 * sin(phi) ** 2) ** -1.5
    eta = nu / rho - 1

    VII = tan(phi) / (2 * nu * rho)
    VIII = tan(phi) / (24 * nu ** 3 * rho) * (5 + 3 * tan(phi) ** 2 + E - 9 * tan(phi) * eta)
    IX = tan(phi) / (720 * nu ** 5 * rho) * (61 + 90 * tan(phi) ** 2 + 45 * tan(phi) ** 4)
    X = sec(phi) / nu
    XI = sec(phi) / (6 * nu ** 3) * (nu / rho + 2 * tan(phi) ** 2)
    XII = sec(phi) / (120 * nu ** 5) * (5 + 28 * tan(phi) ** 2 + 24 * tan(phi) ** 4)
    XIIA = sec(phi) / (5040 * nu ** 7) * (61 + 662 * tan(phi) ** 2 + 1320 * tan(phi) ** 4
                                          + 720 * tan(phi) ** 6)

    latitude = phi - VII * (E - E0) ** 2 + VIII * (E - E0) ** 4 - IX * (E - E0) ** 6
    longitude = (lam0 + X * (E - E0) - XI * (E - E0) ** 3 + XII * (E - E0) ** 5
                 - XIIA * (E - E0) ** 7)

    return degrees(latitude), degrees(longitude)
