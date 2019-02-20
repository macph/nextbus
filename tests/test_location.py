"""
Testing the populate module.
"""
import pytest

from nextbus import location

PLACES = {
    "Tottenham Court Road": (51.51623, -0.13067),
    "British Museum": (51.51939, -0.12692),
    "Trafalgar Square": (51.50786, -0.12803),
    "Smithfield": (51.51911, -0.10172),
    "Primrose Hill": (51.53954, -0.16066),
    "The Shard": (51.5045, -0.08649),
    "Canary Wharf": (51.5035, -0.01861),
    "Kew": (51.47867, -0.29555),
    "Watford Junction": (51.66354, -0.39651),
    "Bedford": (52.13584, -0.46632)
}


@pytest.mark.parametrize("place_1, place_2, expected", [
    ("Tottenham Court Road", "British Museum", 438),
    ("Tottenham Court Road", "Trafalgar Square", 950),
    ("Tottenham Court Road", "Smithfield", 2030),
    ("Tottenham Court Road", "Primrose Hill", 3320),
    ("Tottenham Court Road", "The Shard", 3330),
    ("Tottenham Court Road", "Canary Wharf", 7890),
    ("Tottenham Court Road", "Kew", 12200),
    ("Tottenham Court Road", "Watford Junction", 24600),
    ("Tottenham Court Road", "Bedford", 72700),
])
def test_distance(place_1, place_2, expected):
    """ Test location functions. Distances taken from Google Maps.
        Min delta 10m.
    """
    distance = location.get_distance(PLACES[place_1], PLACES[place_2])

    assert distance == pytest.approx(expected, 0.01)


TCR = PLACES["Tottenham Court Road"]
DISTANCE = 1000


@pytest.fixture
def box():
    return location.bounding_box(*TCR, DISTANCE)


def test_bounding_box_sides(box):
    north = location.get_distance((box.north, box.west), (box.north, box.east))
    east = location.get_distance((box.south, box.east), (box.north, box.east))
    south = location.get_distance((box.south, box.west), (box.south, box.east))
    west = location.get_distance((box.south, box.west), (box.north, box.west))

    assert north == pytest.approx(2 * DISTANCE, 0.001)
    assert east == pytest.approx(2 * DISTANCE, 0.001)
    assert south == pytest.approx(2 * DISTANCE, 0.001)
    assert west == pytest.approx(2 * DISTANCE, 0.001)


def test_bounding_box_to_centre(box):
    north = location.get_distance((box.north, TCR[1]), TCR)
    east = location.get_distance((TCR[0], box.east), TCR)
    south = location.get_distance((box.south, TCR[1]), TCR)
    west = location.get_distance((TCR[0], box.west), TCR)

    assert north == pytest.approx(DISTANCE, 0.001)
    assert east == pytest.approx(DISTANCE, 0.001)
    assert south == pytest.approx(DISTANCE, 0.001)
    assert west == pytest.approx(DISTANCE, 0.001)
