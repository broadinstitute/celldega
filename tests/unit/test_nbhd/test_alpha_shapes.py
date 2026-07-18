from unittest.mock import patch

import numpy as np
from shapely.geometry import Polygon

from celldega.nbhd.alpha_shapes import _verify_polygons_with_alpha_bulk


def _square_points(n_per_side=4):
    xs = np.linspace(0, 10, n_per_side)
    ys = np.linspace(0, 10, n_per_side)
    return np.array([(x, y) for x in xs for y in ys])


def test_verify_polygons_skips_a_candidate_whose_recompute_raises():
    """A libpysal/GEOS failure recomputing one candidate's alpha shape (e.g. a
    self-intersecting triangulation raising GEOSException) must not abort
    verification of the other candidates in the same batch."""
    points = _square_points()
    good_poly = Polygon([(0, 0), (0, 10), (10, 10), (10, 0)])
    bad_poly = Polygon([(0, 0), (0, 10), (10, 10), (10, 0)])

    class _FakeShape:
        def __init__(self, area):
            self.shape = (1,)
            self.area = type("Area", (), {"values": [area]})()

    call_count = {"n": 0}

    def fake_alpha_shape(coords, _alpha):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise Exception("GEOSException: TopologyException: side location conflict")
        return _FakeShape(area=good_poly.area)

    with patch("celldega.nbhd.alpha_shapes.libpysal_alpha_shape", side_effect=fake_alpha_shape):
        result = _verify_polygons_with_alpha_bulk([bad_poly, good_poly], points, alpha=0.1)

    # The first candidate's recompute raised and was skipped; the second
    # candidate still gets verified and kept.
    assert call_count["n"] == 2
    assert len(result) == 1
    assert result.iloc[0].equals(good_poly)


def test_verify_polygons_returns_empty_when_all_recomputes_raise():
    points = _square_points()
    poly = Polygon([(0, 0), (0, 10), (10, 10), (10, 0)])

    def always_raises(_coords, _alpha):
        raise Exception("GEOSException: TopologyException")

    with patch("celldega.nbhd.alpha_shapes.libpysal_alpha_shape", side_effect=always_raises):
        result = _verify_polygons_with_alpha_bulk([poly], points, alpha=0.1)

    assert len(result) == 0
