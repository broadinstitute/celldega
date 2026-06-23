import geopandas as gpd
import numpy as np
from shapely.geometry import Point

from . import NeighborhoodCollection, calculate_gradient


def _circle_roi(radius=30):
    """A simple circular ROI in micron space."""
    return gpd.GeoDataFrame(geometry=[Point(0, 0).buffer(radius)])


def test_gradient_both_directions_ordered_inner_to_outer():
    """Both directions produce ordered inward-then-outward bands with signed distances."""
    gdf = calculate_gradient(_circle_roi(radius=100), direction="both", bin_width=10, max_dist=50)

    assert list(gdf["direction"]) == ["inward"] * 5 + ["outward"] * 5
    # Distances increase monotonically from inner-most to outer-most band.
    assert list(gdf["dist_start_um"]) == sorted(gdf["dist_start_um"])
    assert gdf["dist_start_um"].iloc[0] == -50
    assert gdf["dist_end_um"].iloc[-1] == 50
    assert {"name", "ring_range_um", "area", "area_um2", "color"}.issubset(gdf.columns)


def test_gradient_direction_filters():
    """direction selects only outward or only inward bands."""
    roi = Point(0, 0).buffer(100)  # bare geometry input
    out = calculate_gradient(roi, direction="outward", bin_width=10, max_dist=50)
    inn = calculate_gradient(roi, direction="inward", bin_width=10, max_dist=50)

    assert set(out["direction"]) == {"outward"}
    assert set(inn["direction"]) == {"inward"}
    assert (out["dist_start_um"] >= 0).all()
    assert (inn["dist_end_um"] <= 0).all()


def test_gradient_inward_stops_when_eroded():
    """Inward erosion stops once the geometry erodes away (radius < max_dist)."""
    gdf = calculate_gradient(_circle_roi(radius=25), direction="inward", bin_width=10, max_dist=50)
    # A radius-25 circle cannot yield bands beyond ~25 um of erosion.
    assert len(gdf) < 5
    assert not gdf.empty


def test_gradient_clip_reference_shrinks_outward_rings():
    """An on-the-fly alpha-shape clip reduces outward ring area."""
    roi = _circle_roi(radius=30)
    pts = np.random.RandomState(0).uniform(-60, 60, size=(500, 2))
    ref = gpd.GeoDataFrame(geometry=[Point(p) for p in pts])

    clipped = calculate_gradient(roi, direction="outward", clip_reference=ref, clip_alpha=100)
    unclipped = calculate_gradient(roi, direction="outward")

    assert clipped.area.sum() < unclipped.area.sum()


def test_gradient_pixel_space_reports_both_unit_areas():
    """Pixel-space input converts widths via technology and reports both areas."""
    roi = Point(0, 0).buffer(300)
    gdf = calculate_gradient(
        roi, direction="outward", technology="Xenium", is_pixel_space=True, max_dist=20
    )
    assert not gdf.empty
    # area_um2 should be smaller than area_px2 since 1 px < 1 um for Xenium.
    assert (gdf["area_um2"] < gdf["area_px2"]).all()


def test_from_gradient_builds_collection():
    """The classmethod constructor yields one observation per ring."""
    nbhd = NeighborhoodCollection.from_gradient(
        _circle_roi(radius=100), direction="both", bin_width=10, max_dist=50
    )
    assert nbhd.nbhd_type == "gradient"
    assert nbhd.obs.shape[0] == 10
    assert "direction" in nbhd.obs.columns
