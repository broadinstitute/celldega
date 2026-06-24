import geopandas as gpd
import numpy as np
from shapely.geometry import Point

from . import NeighborhoodCollection
from .gradient import _calc_gradient


def _circle_roi(radius=30):
    """A simple circular ROI in micron space."""
    return gpd.GeoDataFrame(geometry=[Point(0, 0).buffer(radius)])


def test_gradient_both_directions_ordered_inner_to_outer():
    """Both directions produce ordered inward-then-outward bands with signed distances."""
    gdf = _calc_gradient(_circle_roi(radius=100), direction="both", bin_width=10, max_dist=50)

    assert list(gdf["direction"]) == ["inward"] * 5 + ["outward"] * 5
    # Distances increase monotonically from inner-most to outer-most band.
    assert list(gdf["dist_start_um"]) == sorted(gdf["dist_start_um"])
    assert gdf["dist_start_um"].iloc[0] == -50
    assert gdf["dist_end_um"].iloc[-1] == 50
    assert {"name", "ring_range_um", "area", "area_um2", "color"}.issubset(gdf.columns)


def test_gradient_direction_filters():
    """direction selects only outward or only inward bands."""
    roi = Point(0, 0).buffer(100)  # bare geometry input
    out = _calc_gradient(roi, direction="outward", bin_width=10, max_dist=50)
    inn = _calc_gradient(roi, direction="inward", bin_width=10, max_dist=50)

    assert set(out["direction"]) == {"outward"}
    assert set(inn["direction"]) == {"inward"}
    assert (out["dist_start_um"] >= 0).all()
    assert (inn["dist_end_um"] <= 0).all()


def test_gradient_inward_stops_when_eroded():
    """Inward erosion stops once the geometry erodes away (radius < max_dist)."""
    gdf = _calc_gradient(_circle_roi(radius=25), direction="inward", bin_width=10, max_dist=50)
    # A radius-25 circle cannot yield bands beyond ~25 um of erosion.
    assert len(gdf) < 5
    assert not gdf.empty


def test_gradient_clip_reference_shrinks_outward_rings():
    """An on-the-fly alpha-shape clip reduces outward ring area."""
    roi = _circle_roi(radius=30)
    pts = np.random.RandomState(0).uniform(-60, 60, size=(500, 2))
    ref = gpd.GeoDataFrame(geometry=[Point(p) for p in pts])

    clipped = _calc_gradient(roi, direction="outward", clip_reference=ref, clip_alpha=100)
    unclipped = _calc_gradient(roi, direction="outward")

    assert clipped.area.sum() < unclipped.area.sum()


def test_gradient_pixel_space_reports_both_unit_areas():
    """Pixel-space input converts widths via technology and reports both areas."""
    roi = Point(0, 0).buffer(300)
    gdf = _calc_gradient(
        roi, direction="outward", technology="Xenium", is_pixel_space=True, max_dist=20
    )
    assert not gdf.empty
    # area_um2 should be smaller than area_px2 since 1 px < 1 um for Xenium.
    assert (gdf["area_um2"] < gdf["area_px2"]).all()


def test_calc_gradient_from_named_observation():
    """calc_gradient anchors on a named neighborhood and yields one obs per ring."""
    source = NeighborhoodCollection(
        gdf=gpd.GeoDataFrame({"name": ["islet"]}, geometry=[Point(0, 0).buffer(100)]),
        nbhd_type="alpha_shape",
    )
    grad_nbhd = source.calc_gradient(
        obs_name="islet", direction="both", bin_width=10, max_dist=50
    )
    assert grad_nbhd.nbhd_type == "gradient"
    assert grad_nbhd.obs.shape[0] == 10
    assert "direction" in grad_nbhd.obs.columns


def test_calc_gradient_unknown_obs_name_raises():
    """An unknown obs_name raises KeyError."""
    source = NeighborhoodCollection(
        gdf=gpd.GeoDataFrame({"name": ["islet"]}, geometry=[Point(0, 0).buffer(100)]),
        nbhd_type="alpha_shape",
    )
    try:
        source.calc_gradient(obs_name="missing")
    except KeyError:
        pass
    else:
        raise AssertionError("expected KeyError for unknown obs_name")
