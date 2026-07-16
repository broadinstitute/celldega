"""Expansion: per-entity buffering clipped to a matching bounding geometry.

Unlike :mod:`celldega.nbhd.gradient` — which grows concentric rings outward from and
inward into ONE dissolved region of interest (e.g. a tumor alpha shape) — this grows
**every** neighborhood in a collection independently, using each one as its own tiny
ROI. Each buffered entity is clipped to a matching row of a per-entity bounding
GeoDataFrame, so the expansion never grows past that entity's own outer limit. The
canonical use case is growing a segmented nucleus outward until it reaches its
corresponding cell boundary (to profile how nuclear vs. cytoplasmic transcript
capture changes with the working boundary), but the same mechanics apply to any
pair of nested per-entity geometries — e.g. a core region expanding into a parent
tissue domain, or a seed point buffer expanding into a Voronoi/tile boundary.
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

    For each radius in ``radii_um``, buffers every entity in ``gdf_source`` outward
    by that distance and intersects the result with the matching row (by
    ``id_col``) in ``gdf_bounds``, so growth stops at that entity's own bounding
    geometry (e.g. a nucleus growing into its cell, or any other per-entity
    container). Invalid input geometries are repaired with ``shapely.make_valid``
    first.

    Args:
        gdf_source: One row per entity to expand (e.g. a nucleus), with an
            ``id_col`` column and a ``geometry`` column.
        gdf_bounds: One row per entity's clipping boundary (e.g. its cell), with
            an ``id_col`` column matching ``gdf_source`` and a ``geometry``
            column. Must have exactly one row per id.
        radii_um: Buffer distances in microns. ``0`` returns the original
            (validity-repaired) source geometry, clipped to its bound.
        id_col: Column identifying each entity, shared by both frames (default
            ``"id"``).
        technology: Imaging platform (e.g. ``"Xenium"``) used to look up
            ``scale_um_per_pixel`` when the geometry is in pixel space. Ignored if
            ``scale_um_per_pixel`` is given.
        scale_um_per_pixel: Microns per pixel — the factor a micron distance is
            *divided* by to get pixels (e.g. an OME-XML ``PhysicalSizeX``).
            Required (directly, via ``technology``, or via ``pixels_per_micron``)
            when ``is_pixel_space=True``. Takes precedence over
            ``pixels_per_micron`` if both are given.
        pixels_per_micron: Pixels per micron — the reciprocal convention, where a
            micron distance is *multiplied* by this factor to get pixels (e.g. a
            notebook's own ``buffer_dist = expand_um * high_res_scale``). Only
            used when ``scale_um_per_pixel`` is not resolved some other way;
            equivalent to passing ``scale_um_per_pixel=1 / pixels_per_micron``.
        is_pixel_space: ``True`` if ``gdf_source``/``gdf_bounds`` geometry is in
            pixel units; ``False`` (default) if already in microns.
        join_style: Shapely buffer join style (``1``=round, ``2``=mitre (default,
            matches sharp polygon corners), ``3``=bevel).
        mitre_limit: Shapely mitre limit, used when ``join_style=2``.
        add_colors: If ``True`` (default), add a ``color`` column — one shade per
            radius (dark to light) — for visualization.

    Returns:
        A dict mapping each radius in ``radii_um`` (in microns, ascending) to a
        ``GeoDataFrame`` of that radius's buffered, clipped entities, with columns
        ``id_col``, ``geometry``, ``radius_um``, ``center_x``, ``center_y``,
        ``area``/``area_um2``/``area_px2``, and (when ``add_colors``) ``color``.
        Entities that vanish entirely at a given radius (empty intersection) are
        dropped from that radius's frame.

    Raises:
        KeyError: If ``id_col`` is missing from either frame.
        ValueError: If ids are duplicated in ``gdf_bounds``, if any source id is
            missing from ``gdf_bounds``, or if ``is_pixel_space=True`` without a
            resolvable scale (``scale_um_per_pixel``, ``pixels_per_micron``, or
            ``technology``).

    Examples:
        Prefer the public method, which anchors on a collection of entities and
        returns one new collection per radius (pass ``pixels_per_micron=`` for
        pixel-space geometry, e.g. a notebook's own ``high_res_scale``)::

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
