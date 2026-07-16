"""Expansion: per-entity buffering clipped to a matching bounding geometry.

Unlike :mod:`celldega.nbhd.gradient` (concentric rings from ONE dissolved ROI),
this grows **every** entity in a collection independently, clipping each to a
matching row of a per-entity bounding GeoDataFrame so it never grows past its
own outer limit — e.g. a segmented nucleus growing outward until it reaches its
corresponding cell boundary.
"""

from __future__ import annotations

from collections.abc import Sequence

import geopandas as gpd
import numpy as np
from shapely.validation import make_valid

from .gradient import _get_micron_per_pixel, _ring_colors


_DEFAULT_RADII_UM: tuple[float, ...] = (0, 0.5, 1, 1.5, 2, 2.5, 3)


def _calc_expansion(
    gdf_source: gpd.GeoDataFrame,
    gdf_bounds: gpd.GeoDataFrame,
    radii_um: Sequence[float] = _DEFAULT_RADII_UM,
    *,
    id_col: str = "id",
    technology: str | None = None,
    scale_um_per_pixel: float | None = None,
    pixels_per_micron: float | None = None,
    is_pixel_space: bool = False,
    join_style: int = 2,
    mitre_limit: float = 5.0,
    add_colors: bool = True,
) -> dict[float, gpd.GeoDataFrame]:
    """Engine behind :meth:`NeighborhoodCollection.calc_expansion`.

    For each radius in ``radii_um``, buffers every entity in ``gdf_source``
    outward and intersects the result with the matching row (by ``id_col``) in
    ``gdf_bounds``, so growth stops at that entity's own bound. Invalid input
    geometries are repaired with ``shapely.make_valid`` first.

    Args:
        gdf_source: One row per entity to expand, with an ``id_col`` column and
            a ``geometry`` column.
        gdf_bounds: One row per entity's clipping boundary, with a matching
            ``id_col`` column and a ``geometry`` column.
        radii_um: Buffer distances in microns. ``0`` returns the original
            (validity-repaired) source geometry, clipped to its bound.
        id_col: Column identifying each entity, shared by both frames.
        technology: Imaging platform (e.g. ``"Xenium"``) used to look up
            ``scale_um_per_pixel`` for pixel-space geometry.
        scale_um_per_pixel: Microns per pixel (divide a micron distance by this
            to get pixels). Required, directly or via ``technology``/
            ``pixels_per_micron``, when ``is_pixel_space=True``; takes
            precedence over ``pixels_per_micron`` if both are given.
        pixels_per_micron: Pixels per micron — the reciprocal convention
            (multiply a micron distance by this to get pixels, e.g. a
            notebook's own ``high_res_scale``); equivalent to
            ``scale_um_per_pixel=1 / pixels_per_micron``.
        is_pixel_space: ``True`` if the geometry is in pixel units; ``False``
            (default) if already in microns.
        join_style: Shapely buffer join style (``1``=round, ``2``=mitre
            (default), ``3``=bevel).
        mitre_limit: Shapely mitre limit, used when ``join_style=2``.
        add_colors: If ``True`` (default), add a ``color`` column — one shade
            per radius — for visualization.

    Returns:
        A dict mapping each radius to a ``GeoDataFrame`` of that radius's
        buffered, clipped entities (``id_col``, ``geometry``, ``radius_um``,
        ``center_x``/``center_y``, ``area``/``area_um2``/``area_px2``, and
        ``color`` if requested). Entities that vanish at a given radius are
        dropped from that radius's frame.

    Raises:
        KeyError: If ``id_col`` is missing from either frame.
        ValueError: If ids are duplicated or fail to match between frames, or
            if ``is_pixel_space=True`` without a resolvable scale.

    Examples:
        >>> series = nbhd_nuclei.calc_expansion(
        ...     gdf_cells, radii_um=[0, 1, 2, 3],
        ...     is_pixel_space=True, pixels_per_micron=high_res_scale,
        ... )
    """
    if id_col not in gdf_source.columns:
        raise KeyError(f"gdf_source missing '{id_col}'")
    if id_col not in gdf_bounds.columns:
        raise KeyError(f"gdf_bounds missing '{id_col}'")

    if scale_um_per_pixel is None and technology is not None:
        scale_um_per_pixel = _get_micron_per_pixel(technology)
    if scale_um_per_pixel is None and pixels_per_micron is not None:
        scale_um_per_pixel = 1.0 / pixels_per_micron
    if is_pixel_space and scale_um_per_pixel is None:
        raise ValueError(
            "scale_um_per_pixel, pixels_per_micron, or technology is required "
            "when is_pixel_space=True"
        )
    effective_scale = scale_um_per_pixel if is_pixel_space else 1.0

    source = gdf_source[[id_col, "geometry"]].copy()
    source[id_col] = source[id_col].astype(str)
    if source[id_col].duplicated().any():
        dupes = source.loc[source[id_col].duplicated(), id_col].unique()[:5]
        raise ValueError(f"gdf_source has duplicate '{id_col}' values, e.g. {list(dupes)}")
    source["geometry"] = source["geometry"].apply(make_valid)

    bounds = gdf_bounds[[id_col, "geometry"]].copy()
    bounds[id_col] = bounds[id_col].astype(str)
    if bounds[id_col].duplicated().any():
        dupes = bounds.loc[bounds[id_col].duplicated(), id_col].unique()[:5]
        raise ValueError(f"gdf_bounds has duplicate '{id_col}' values, e.g. {list(dupes)}")
    bounds_lookup = bounds.set_index(id_col)["geometry"].apply(make_valid)

    missing = set(source[id_col]) - set(bounds_lookup.index)
    if missing:
        example = sorted(missing)[:5]
        raise ValueError(
            f"{len(missing)} entities have no matching row in gdf_bounds (by '{id_col}'), "
            f"e.g. {example}"
        )

    radii_sorted = sorted({float(r) for r in radii_um})
    colors = (
        _ring_colors("viridis", len(radii_sorted)) if add_colors else [None] * len(radii_sorted)
    )
    color_by_radius = dict(zip(radii_sorted, colors, strict=True))

    results: dict[float, gpd.GeoDataFrame] = {}
    for radius_um in radii_sorted:
        radius_native = radius_um / effective_scale

        buffered = source["geometry"].buffer(
            radius_native, join_style=join_style, mitre_limit=mitre_limit
        )
        clipped = [
            geom.intersection(bounds_lookup.loc[eid])
            for eid, geom in zip(source[id_col], buffered, strict=True)
        ]

        gdf_radius = gpd.GeoDataFrame(
            {id_col: source[id_col].to_numpy()},
            geometry=clipped,
            crs=gdf_source.crs,
        )
        gdf_radius = gdf_radius[~gdf_radius.geometry.is_empty].reset_index(drop=True)
        gdf_radius["radius_um"] = radius_um
        gdf_radius["center_x"] = gdf_radius.centroid.x
        gdf_radius["center_y"] = gdf_radius.centroid.y

        area_native = gdf_radius.geometry.area
        if is_pixel_space:
            gdf_radius["area_px2"] = area_native
            gdf_radius["area_um2"] = area_native * (scale_um_per_pixel**2)
        else:
            gdf_radius["area_um2"] = area_native
            gdf_radius["area_px2"] = (
                area_native / (scale_um_per_pixel**2) if scale_um_per_pixel else np.nan
            )
        gdf_radius["area"] = gdf_radius["area_um2"]

        if add_colors:
            gdf_radius["color"] = color_by_radius[radius_um]

        results[radius_um] = gdf_radius

    return results
