"""
Location tools for the nextbus package.
"""
import math

# WSG84 ellipsoid axes and the mean radius, defined by IUGG
WGS84_A = 6378137.0
WGS84_B = 6356752.314245
R_MEAN = (2 * WGS84_A + WGS84_B) / 3


def bounding_box(coord, distance):
    """ Calculates latitudes and longitudes for a bounding box around a pair
        of coordinates with distance from centre to one of the sides. Uses the
        mean radius for the WGS84 ellipsoid.

        :param coord: tuple of lat/long coordinates, in decimal degrees
        :param distance: Distance from centre to sides of box, in metres
        :returns: tuple of 4 results: min_lat, min_long, max_lat, max_long
    """
    latitude, longitude = coord
    r_parallel = R_MEAN * math.cos(math.radians(latitude))

    min_lat = latitude - 180 * distance / (R_MEAN * math.pi)
    max_lat = latitude + 180 * distance / (R_MEAN * math.pi)
    min_long = longitude - 180 * distance / (r_parallel * math.pi)
    max_long = longitude + 180 * distance / (r_parallel * math.pi)

    return min_lat, min_long, max_lat, max_long


def distance(coord_1, coord_2):
    """ Calculates distance in metres between two lat/long coordinates. Uses
        the Haversine formula and the mean radius for the WGS84 ellipsoid.
        https://en.wikipedia.org/wiki/Great-circle_distance

        :param coord_1: first tuple of lat/long coordinates, in degrees
        :param coord_2: second tuple of lat/long coordinates, in degrees
        :returns: distance, in metres
    """
    phi_1, lambda_1 = math.radians(coord_1[0]), math.radians(coord_1[1])
    phi_2, lambda_2 = math.radians(coord_2[0]), math.radians(coord_2[1])
    delta_phi, delta_lambda = abs(phi_1 - phi_2), abs(lambda_1 - lambda_2)

    hav = math.sqrt(math.sin(delta_phi / 2) ** 2
                    + math.cos(phi_1) * math.cos(phi_2)
                    * math.sin(delta_lambda / 2) ** 2)
    distance = R_MEAN * 2 * math.asin(hav)

    return distance
