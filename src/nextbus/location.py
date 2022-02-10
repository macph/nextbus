"""
Location tools for the nextbus package.
"""
import collections
import math

# WSG84 ellipsoid axes and the mean radius, defined by IUGG
WGS84_A = 6378137.0
WGS84_B = 6356752.314245
R_MEAN = (2 * WGS84_A + WGS84_B) / 3

# Limits and centre for Great Britain coordinates
GB_NORTH = 61
GB_EAST = -8
GB_SOUTH = 49
GB_WEST = 2
GB_CENTRE = 54.00366, -2.547855
TILE_ZOOM = 15

Box = collections.namedtuple("BoundingBox", ["north", "east", "south", "west"])


def bounding_box(latitude, longitude, distance):
    """ Calculates a bounding box around a pair of coordinates with distance
        from centre to one of the sides.

        Uses the mean radius for the WGS84 ellipsoid to find the minimum and
        maximum latitude and longitude.

        :param latitude: Box centre latitude.
        :param longitude: Box centre longitude.
        :param distance: Distance from centre to sides of box, in metres
        :returns: tuple for 4 sides of the box: north, east, south and west
    """
    r_parallel = R_MEAN * math.cos(math.radians(latitude))

    north = latitude + math.degrees(distance / R_MEAN)
    east = longitude + math.degrees(distance / r_parallel)
    south = latitude - math.degrees(distance / R_MEAN)
    west = longitude - math.degrees(distance / r_parallel)

    return Box(north, east, south, west)


def get_distance(coord_1, coord_2):
    """ Calculates distance in metres between two lat/long coordinates.

        Uses the Haversine formula and the mean radius for the WGS84 ellipsoid.
        https://en.wikipedia.org/wiki/Great-circle_distance

        :param coord_1: first lat/long coordinates, in decimal degrees
        :param coord_2: second lat/long coordinates, in decmial degrees
        :returns: distance, in metres
    """
    phi_1, lambda_1 = map(math.radians, coord_1)
    phi_2, lambda_2 = map(math.radians, coord_2)
    delta_phi, delta_lambda = abs(phi_1 - phi_2), abs(lambda_1 - lambda_2)

    hav = math.sqrt(
        math.sin(delta_phi / 2) ** 2 +
        math.cos(phi_1) * math.cos(phi_2) * math.sin(delta_lambda / 2) ** 2
    )
    distance = R_MEAN * 2 * math.asin(hav)

    return distance


def check_bounds(latitude, longitude):
    """ Checks if a pair of coordinates is within the GB boundaries. """
    return GB_SOUTH < latitude < GB_NORTH and GB_EAST < longitude < GB_WEST


def tile_to_box(tile_x, tile_y, zoom):
    """ Gets bounding box from a tile with x and y coordinates and zoom level.
    """
    factor = 2 ** zoom

    def latitude(y):
        lat_rad = math.atan(math.sinh(math.pi - 2 * math.pi * y / factor))
        return math.degrees(lat_rad)

    def longitude(x):
        return x * 360 / factor - 180

    box = Box(
        north=latitude(tile_y),
        east=longitude(tile_x + 1),
        south=latitude(tile_y + 1),
        west=longitude(tile_x)
    )

    return box
