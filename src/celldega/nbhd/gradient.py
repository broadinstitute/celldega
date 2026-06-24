"""Gradient neighborhoods: concentric rings expanding outward from and eroding
inward into a region of interest (ROI).

A "gradient" is a set of fixed-width bands measured from the boundary of an input
geometry (e.g. a tumor alpha shape). Outward bands grow away from the ROI, inward
bands erode into it, and each band carries a signed micron distance so downstream
analyses can correlate cell composition or gene expression with distance from the
ROI edge. The bands are returned as a tidy ``GeoDataFrame`` that plugs directly
into :class:`~celldega.nbhd.collection.NeighborhoodCollection`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import geopandas as gpd
import numpy as np
from shapely.geometry.base import BaseGeometry

from .alpha_shapes import alpha_shape


if TYPE_CHECKING:
    from celldega.nbhd.collection import NeighborhoodCollection


# Native micron-per-pixel scale of common imaging-based spatial platforms. Used to
# convert micron ring widths into a geometry's pixel units (and vice versa).
_MICRON_PER_PIXEL: dict[str, float] = {
    "xenium": 0.2125,
    "merscope": 0.108,
}

_VALID_DIRECTIONS = ("outward", "inward", "both")


def _get_micron_per_pixel(technology: str) -> float:
    """Return the micron-per-pixel conversion factor for an imaging platform.

    Pixel-space geometries (the native space of most landscape visualizations)
    need this factor to convert a ring width expressed in microns into pixels.

    Args:
        technology: Spatial platform name, case-insensitive (e.g. ``"Xenium"``,
            ``"Merscope"``).

    Returns:
        Microns per pixel for the platform.

    Raises:
        ValueError: If the platform is not recognized.

    Examples:
        >>> from celldega.nbhd.gradient import _get_micron_per_pixel
        >>> _get_micron_per_pixel("Xenium")
        0.2125
    """
    try:
        return _MICRON_PER_PIXEL[technology.lower()]
    except KeyError:
        supported = ", ".join(sorted(_MICRON_PER_PIXEL))
        raise ValueError(
            f"'{technology}' is not supported. Please select from: {supported}"
        ) from None


def _resolve_roi_geometry(source: Any, nbhd_col: str = "name") -> tuple[BaseGeometry, Any]:
    """Coerce a flexible ``source`` into a single merged ROI geometry.

    Accepts a :class:`~celldega.nbhd.collection.NeighborhoodCollection` (its
    ``gdf`` is used), a ``GeoDataFrame``/``GeoSeries`` (all rows are dissolved
    into one shape), or a bare shapely ``(Multi)Polygon``.

    Returns:
        A ``(geometry, crs)`` tuple where ``geometry`` is the unioned ROI and
        ``crs`` is the source coordinate reference system (``None`` for a bare
        geometry).
    """
    # NeighborhoodCollection (and anything else exposing a live ``gdf``).
    gdf = getattr(source, "gdf", None)
    if gdf is not None and isinstance(gdf, gpd.GeoDataFrame):
        return gdf.geometry.unary_union, gdf.crs

    if isinstance(source, gpd.GeoDataFrame):
        return source.geometry.unary_union, source.crs

    if isinstance(source, gpd.GeoSeries):
        return source.unary_union, source.crs

    if isinstance(source, BaseGeometry):
        return source, None

    raise TypeError(
        "source must be a GeoDataFrame, GeoSeries, NeighborhoodCollection, or "
        f"shapely geometry, got {type(source).__name__}"
    )


def _points_from_reference(clip_reference: Any) -> np.ndarray:
    """Extract an ``(N, 2)`` point cloud from a flexible ``clip_reference``.

    Accepts an ``AnnData`` (uses ``obsm["spatial"]`` or x/y centroid ``obs``
    columns), a ``GeoDataFrame``/``GeoSeries`` (geometry centroids), or an array.
    """
    # AnnData: pull spatial coordinates so callers can just pass their adata.
    obsm = getattr(clip_reference, "obsm", None)
    if obsm is not None:
        if "spatial" in obsm:
            return np.asarray(obsm["spatial"], dtype=float)[:, :2]
        obs = getattr(clip_reference, "obs", None)
        if obs is not None:
            for x_col, y_col in (("x_centroid", "y_centroid"), ("x_location", "y_location"), ("x", "y")):
                if x_col in obs and y_col in obs:
                    return obs[[x_col, y_col]].to_numpy(dtype=float)
        raise ValueError(
            "clip_reference AnnData needs obsm['spatial'] or x/y centroid columns in obs"
        )

    if isinstance(clip_reference, (gpd.GeoDataFrame, gpd.GeoSeries)):
        geom = clip_reference.geometry if isinstance(clip_reference, gpd.GeoDataFrame) else clip_reference
        return np.column_stack([geom.centroid.x.to_numpy(), geom.centroid.y.to_numpy()])

    return np.asarray(clip_reference, dtype=float)


def _resolve_clip_boundary(
    clip_boundary: Any,
    clip_reference: Any,
    clip_alpha: float,
) -> BaseGeometry | None:
    """Resolve the optional outward-ring clipping boundary.

    A user-supplied ``clip_boundary`` takes precedence; otherwise, if
    ``clip_reference`` points are given, a tissue alpha shape is computed on the
    fly. Returns ``None`` when no clipping is requested.
    """
    if clip_boundary is not None:
        if isinstance(clip_boundary, (gpd.GeoDataFrame, gpd.GeoSeries)):
            return clip_boundary.geometry.unary_union if isinstance(
                clip_boundary, gpd.GeoDataFrame
            ) else clip_boundary.unary_union
        if isinstance(clip_boundary, BaseGeometry):
            return clip_boundary
        raise TypeError(
            "clip_boundary must be a GeoDataFrame, GeoSeries, or shapely geometry, "
            f"got {type(clip_boundary).__name__}"
        )

    if clip_reference is not None:
        points = _points_from_reference(clip_reference)
        if points.shape[0] < 4:
            raise ValueError("clip_reference needs at least 4 points to build an alpha shape")
        return alpha_shape(points, clip_alpha)

    return None


def _ring_colors(cmap_name: str, n: int) -> list[str]:
    """Sample ``n`` hex colors from a matplotlib colormap (dark -> light)."""
    import matplotlib.colors as mcolors
    import matplotlib.pyplot as plt

    if n == 0:
        return []
    cmap = plt.get_cmap(cmap_name)
    return [mcolors.to_hex(cmap(v)) for v in np.linspace(0.8, 0.3, n)]


def calculate_gradient(
    source: gpd.GeoDataFrame | gpd.GeoSeries | BaseGeometry | NeighborhoodCollection,
    direction: str = "both",
    bin_width: float = 10,
    max_dist: float = 50,
    *,
    technology: str | None = None,
    scale_um_per_pixel: float | None = None,
    is_pixel_space: bool = False,
    clip_boundary: Any | None = None,
    clip_reference: Any | None = None,
    clip_alpha: float = 100,
    add_colors: bool = True,
    nbhd_col: str = "name",
) -> gpd.GeoDataFrame:
    """Generate concentric gradient rings outward from and/or inward into an ROI.

    Starting from the boundary of the merged ``source`` geometry, this builds
    fixed-width bands every ``bin_width`` microns out to ``max_dist``:

    - **Outward** bands grow away from the ROI (positive distance). Use
      ``clip_boundary``/``clip_reference`` to stop them from running off the
      tissue.
    - **Inward** bands erode into the ROI (negative distance) and stop
      automatically once the geometry erodes to nothing.

    Each band is one row of the returned ``GeoDataFrame``, ordered inner-most to
    outer-most, with a signed distance so you can spatially join cells to bands
    (``gpd.sjoin``) and correlate composition or expression against distance from
    the ROI edge.

    Args:
        source: The ROI. May be a ``GeoDataFrame``/``GeoSeries`` (all rows are
            dissolved into one shape), a
            :class:`~celldega.nbhd.collection.NeighborhoodCollection` (its
            ``gdf`` is used), or a bare shapely ``(Multi)Polygon``.
        direction: ``"outward"``, ``"inward"``, or ``"both"`` (default).
        bin_width: Width of each ring in microns (default ``10``).
        max_dist: Maximum distance from the ROI boundary in microns (default
            ``50``). Applied symmetrically to outward and inward bands.
        technology: Imaging platform (e.g. ``"Xenium"``) used to look up
            ``scale_um_per_pixel`` when the geometry is in pixel space. Ignored
            if ``scale_um_per_pixel`` is given.
        scale_um_per_pixel: Microns per pixel. Required (directly or via
            ``technology``) when ``is_pixel_space=True``.
        is_pixel_space: ``True`` if ``source`` geometry is in pixel units;
            ``False`` (default) if it is already in microns — the natural space
            of a ``NeighborhoodCollection``. Controls how micron ring widths are
            converted to the geometry's units and how areas are reported.
        clip_boundary: Optional precomputed tissue boundary
            (``GeoDataFrame``/``GeoSeries``/geometry) to clip **outward** rings
            to. Takes precedence over ``clip_reference``. Use this to pass your
            own whole-tissue alpha shape at an alpha of your choosing.
        clip_reference: Optional source of cell positions from which a tissue
            alpha shape is computed on the fly to clip outward rings. Accepts an
            ``AnnData`` (uses ``obsm["spatial"]`` or x/y centroid ``obs``
            columns), a ``GeoDataFrame``/``GeoSeries`` of cells, or an
            ``(N, 2)`` array. Must be in the same coordinate space as ``source``.
        clip_alpha: Inverse-alpha value for the on-the-fly alpha shape (default
            ``100``). Larger values trace tissue boundaries more loosely.
        add_colors: If ``True`` (default), add a ``color`` column (Blues for
            outward bands, Reds for inward) for visualization.
        nbhd_col: Name of the band-identifier column in the output (default
            ``"name"``), matching what ``NeighborhoodCollection`` expects.

    Returns:
        A ``GeoDataFrame`` with one row per ring, ordered inner-most to
        outer-most, and columns:

        - ``name`` / ``ring_range_um`` — band label, e.g. ``"out (+0~+10) µm"``.
        - ``direction`` — ``"outward"`` or ``"inward"``.
        - ``dist_start_um`` / ``dist_end_um`` — signed band edges in microns.
        - ``area`` / ``area_um2`` / ``area_px2`` — band areas.
        - ``color`` — hex color (when ``add_colors``).
        - ``geometry`` — the band polygon, in the ``source`` coordinate space.

    Raises:
        ValueError: If ``direction`` is invalid, or ``is_pixel_space=True``
            without a resolvable ``scale_um_per_pixel``.

    Examples:
        Inward and outward micron-space rings straight into a collection-ready
        ``GeoDataFrame``::

            >>> import celldega as dega
            >>> gdf_rings = dega.nbhd.calculate_gradient(
            ...     gdf_tumor, direction="both", bin_width=10, max_dist=50
            ... )
            >>> gdf_rings[["name", "direction", "dist_start_um"]].head(3)

        Outward-only rings from pixel-space geometry, clipped to a tissue alpha
        shape computed on the fly from cell centroids so the rings cannot run off
        the tissue::

            >>> gdf_rings = dega.nbhd.calculate_gradient(
            ...     gdf_tumor,
            ...     direction="outward",
            ...     technology="Xenium",
            ...     is_pixel_space=True,
            ...     clip_reference=gdf_cells,
            ...     clip_alpha=100,
            ... )

        Tag cells with the band they fall in for downstream gradient analysis::

            >>> joined = gpd.sjoin(
            ...     gdf_cells, gdf_rings[["ring_range_um", "geometry"]],
            ...     how="left", predicate="within",
            ... )
    """
    if direction not in _VALID_DIRECTIONS:
        raise ValueError(f"direction must be one of {_VALID_DIRECTIONS}, got {direction!r}")

    geometry, crs = _resolve_roi_geometry(source, nbhd_col=nbhd_col)

    # Resolve the micron <-> native-unit scale.
    if scale_um_per_pixel is None and technology is not None:
        scale_um_per_pixel = _get_micron_per_pixel(technology)
    if is_pixel_space and scale_um_per_pixel is None:
        raise ValueError(
            "scale_um_per_pixel (or technology) is required when is_pixel_space=True"
        )
    effective_scale = scale_um_per_pixel if is_pixel_space else 1.0

    # Band edges in microns, e.g. [0, 10, 20, 30, 40, 50] -> five bands.
    n_bins = round(max_dist / bin_width)
    edges_um = [bin_width * i for i in range(n_bins + 1)]
    edges_native = [e / effective_scale for e in edges_um]

    clip_geom = _resolve_clip_boundary(clip_boundary, clip_reference, clip_alpha)

    def outward_label(i: int) -> str:
        return f"out (+{edges_um[i]}~+{edges_um[i + 1]}) µm"

    def inward_label(i: int) -> str:
        start = 0 if edges_um[i] == 0 else -edges_um[i]
        return f"in ({start}~-{edges_um[i + 1]}) µm"

    rows: list[dict[str, Any]] = []

    # Inner-most band first so the observation axis runs inner -> outer.
    if direction in ("inward", "both"):
        for i in reversed(range(n_bins)):
            d_inner, d_outer = edges_native[i + 1], edges_native[i]
            ring = geometry.buffer(-d_outer).difference(geometry.buffer(-d_inner))
            if ring.is_empty:
                continue
            rows.append(
                {
                    nbhd_col: inward_label(i),
                    "ring_range_um": inward_label(i),
                    "direction": "inward",
                    "dist_start_um": -edges_um[i + 1],
                    "dist_end_um": -edges_um[i],
                    "geometry": ring,
                }
            )

    if direction in ("outward", "both"):
        for i in range(n_bins):
            d_inner, d_outer = edges_native[i], edges_native[i + 1]
            ring = geometry.buffer(d_outer).difference(geometry.buffer(d_inner))
            if clip_geom is not None:
                ring = ring.intersection(clip_geom)
            if ring.is_empty:
                continue
            rows.append(
                {
                    nbhd_col: outward_label(i),
                    "ring_range_um": outward_label(i),
                    "direction": "outward",
                    "dist_start_um": edges_um[i],
                    "dist_end_um": edges_um[i + 1],
                    "geometry": ring,
                }
            )

    gdf_rings = gpd.GeoDataFrame(rows, geometry="geometry", crs=crs)

    # Areas in both unit systems regardless of input space.
    area_native = gdf_rings.geometry.area
    if is_pixel_space:
        gdf_rings["area_px2"] = area_native
        gdf_rings["area_um2"] = area_native * (scale_um_per_pixel**2)
    else:
        gdf_rings["area_um2"] = area_native
        gdf_rings["area_px2"] = (
            area_native / (scale_um_per_pixel**2) if scale_um_per_pixel else np.nan
        )
    gdf_rings["area"] = gdf_rings["area_um2"]

    if add_colors and not gdf_rings.empty:
        out_labels = gdf_rings.loc[gdf_rings["direction"] == "outward", "ring_range_um"].tolist()
        in_labels = gdf_rings.loc[gdf_rings["direction"] == "inward", "ring_range_um"].tolist()
        color_map = {
            **dict(zip(out_labels, _ring_colors("Blues", len(out_labels)), strict=True)),
            **dict(zip(in_labels, _ring_colors("Reds", len(in_labels)), strict=True)),
        }
        gdf_rings["color"] = gdf_rings["ring_range_um"].map(color_map).fillna("#cccccc")

    return gdf_rings
