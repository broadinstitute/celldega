"""``_to_coords`` and ``_to_geometry`` are mutual inverses for the geometry types the
landscape writers serialise: Point, Polygon (with or without holes) and MultiPolygon.

Coordinates make a lossless round trip through plain JSON-able lists and dicts -- in
particular polygon *interiors* survive, since a hole silently dropped in serialisation
would change cell areas without raising anything. Anything outside that supported set
raises TypeError rather than being coerced.

Both functions are underscore-prefixed but are imported directly by several notebooks,
so their behaviour is a contract, not an implementation detail.
"""

import pytest
from shapely.geometry import LineString, MultiPolygon, Point, Polygon

from celldega.pre.geometry import _to_coords, _to_geometry


_SQUARE = [(0.0, 0.0), (0.0, 10.0), (10.0, 10.0), (10.0, 0.0)]
_HOLE = [(2.0, 2.0), (2.0, 4.0), (4.0, 4.0), (4.0, 2.0)]
_TRIANGLE = [(20.0, 20.0), (20.0, 25.0), (25.0, 25.0)]


def _holed_square() -> Polygon:
    """A 10x10 square with a 2x2 hole punched out: area 100 - 4 = 96."""
    return Polygon(_SQUARE, [_HOLE])


def _multipolygon() -> MultiPolygon:
    return MultiPolygon([_holed_square(), Polygon(_TRIANGLE)])


# --- Point ------------------------------------------------------------------


def test_point_serialises_to_a_flat_xy_list() -> None:
    assert _to_coords(Point(1.5, -2.25)) == [1.5, -2.25]


def test_point_round_trips() -> None:
    point = Point(1.5, -2.25)

    restored = _to_geometry(_to_coords(point))

    assert isinstance(restored, Point)
    assert restored.equals(point)


def test_two_element_tuple_is_read_as_a_point() -> None:
    # _to_coords only ever emits lists, but callers hand in tuples too.
    assert _to_geometry((3.0, 4.0)).equals(Point(3.0, 4.0))


# --- Polygon ----------------------------------------------------------------


def test_polygon_without_interiors_round_trips() -> None:
    polygon = Polygon(_SQUARE)

    coords = _to_coords(polygon)
    restored = _to_geometry(coords)

    assert coords["interiors"] == []
    assert restored.equals(polygon)
    assert restored.area == pytest.approx(100.0)


def test_polygon_serialisation_closes_the_exterior_ring() -> None:
    coords = _to_coords(Polygon(_SQUARE))

    # shapely appends the closing vertex, so 4 corners serialise as 5 points.
    assert len(coords["exterior"]) == 5
    assert coords["exterior"][0] == coords["exterior"][-1] == [0.0, 0.0]


def test_polygon_hole_survives_the_round_trip() -> None:
    """The case most likely to be lost: a dropped interior leaves a polygon that is
    still valid and still 'looks right', but is 100 units of area instead of 96."""
    polygon = _holed_square()

    coords = _to_coords(polygon)
    restored = _to_geometry(coords)

    assert len(coords["interiors"]) == 1
    assert len(restored.interiors) == 1
    assert restored.equals(polygon)
    assert restored.area == pytest.approx(96.0)
    assert not restored.contains(Point(3.0, 3.0))


def test_polygon_dict_without_interiors_key_is_accepted() -> None:
    restored = _to_geometry({"exterior": _SQUARE})

    assert isinstance(restored, Polygon)
    assert len(restored.interiors) == 0
    assert restored.equals(Polygon(_SQUARE))


# --- MultiPolygon -----------------------------------------------------------


def test_multipolygon_round_trips_with_every_part_and_hole() -> None:
    multi = _multipolygon()

    coords = _to_coords(multi)
    restored = _to_geometry(coords)

    assert isinstance(coords, list)
    assert len(coords) == 2
    assert isinstance(restored, MultiPolygon)
    assert len(restored.geoms) == 2
    assert restored.equals(multi)
    # 96 (holed square) + 12.5 (triangle); the hole must still be missing.
    assert restored.area == pytest.approx(108.5)


def test_multipolygon_coords_round_trip_bytewise() -> None:
    coords = _to_coords(_multipolygon())

    assert _to_coords(_to_geometry(coords)) == coords


# --- pass-through and rejection ---------------------------------------------


@pytest.mark.parametrize(
    "geom",
    [
        Point(1.0, 2.0),
        Polygon(_SQUARE),
        Polygon(_SQUARE, [_HOLE]),
        MultiPolygon([Polygon(_SQUARE)]),
    ],
)
def test_already_shapely_input_is_returned_untouched(geom) -> None:
    assert _to_geometry(geom) is geom


@pytest.mark.parametrize(
    "bad",
    [
        "nope",
        42,
        None,
        [1.0, 2.0, 3.0],  # three numbers: not an (x, y) pair
        {"no_exterior": _SQUARE},
        [{"exterior": _SQUARE}, {"not_a_polygon": 1}],
    ],
)
def test_unrecognised_structures_raise_type_error(bad) -> None:
    with pytest.raises(TypeError, match="Unexpected structure"):
        _to_geometry(bad)


@pytest.mark.parametrize("geom", [LineString([(0.0, 0.0), (1.0, 1.0)]), (1.0, 2.0), "POINT (0 0)"])
def test_to_coords_rejects_unsupported_geometry_types(geom) -> None:
    with pytest.raises(TypeError, match="Unsupported geometry type"):
        _to_coords(geom)


# --- pinned quirks (current behaviour, not necessarily desirable) ------------


def test_empty_list_becomes_an_empty_multipolygon() -> None:
    """BUG (pinned, not fixed): ``all(...)`` over an empty list is vacuously True, so
    ``[]`` slips past the MultiPolygon guard instead of raising TypeError. Callers get
    a MULTIPOLYGON EMPTY back."""
    restored = _to_geometry([])

    assert isinstance(restored, MultiPolygon)
    assert restored.is_empty


def test_three_dimensional_point_does_not_round_trip() -> None:
    """BUG (pinned, not fixed): _to_coords keeps the z value, but _to_geometry only
    accepts two-element sequences, so a 3D Point cannot be deserialised."""
    coords = _to_coords(Point(1.0, 2.0, 3.0))

    assert coords == [1.0, 2.0, 3.0]
    with pytest.raises(TypeError, match="Unexpected structure"):
        _to_geometry(coords)
