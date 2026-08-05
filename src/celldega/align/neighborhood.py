"""Neighborhood-overlap refinement of a serial-slice alignment.

A second-stage, region-based refinement that sits *after* the landmark
(cluster-centroid Procrustes) alignment in :mod:`celldega.align.serial_slices`,
consuming its result. Cluster centroids reduce a whole neighborhood to one
point, which is noisy in practice — a centroid jumps slice-to-slice with
sampling and segmentation, and in bilaterally symmetric tissue (e.g. mouse
brain) a region's two lobes average to a point near the midline, so several
regions' centroids collapse onto a nearly collinear midline arrangement that
constrains rotation poorly. This module instead refines each slice's rigid
transform by maximizing the *overlap area* of corresponding neighborhood
polygons across a window of neighboring slices, which retains each region's full
footprint (area, orientation, elongation, disconnected components) rather than
just its center of mass.

The refinement is purely rigid (residual rotation + translation per slice, no
scale, no warp), initialized from the Procrustes transform passed in, and
returns another :class:`~celldega.align.serial_slices.SerialAlignmentTransform`
— so it drops straight into the existing
:func:`~celldega.align.serial_slices.align_serial_slices` application step.

The input is a per-(slice, region) polygon ``GeoDataFrame``. This is
*neighborhood*-based, not alpha-shape-specific: the typical source is the
cluster alpha shapes the neighborhood cloud already computes
(:func:`~celldega.nbhd.alpha_shapes.alpha_shape_cell_clusters_by_slice`), so no
new geometry has to be calculated — but any per-(slice, region) polygons with
labels shared across slices work identically, whether manually drawn or produced
by another domain-identification algorithm (converted to polygons, e.g. via
alpha shapes, if that algorithm outputs cell memberships rather than regions).

Because the overlap objective is only well-behaved once corresponding shapes
already sit close together, the Procrustes initialization is not optional here:
it is what lands each slice near enough that maximizing intersection area is a
local optimization rather than a search over disjoint (zero-overlap, zero-
gradient) configurations. The intended workflow is therefore two-stage:

.. code-block:: python

    initial = dega.align.calc_alignment_transform(landmarks, reference=30)
    refined = dega.align.neighborhood_alignment(shapes, initial)
    aligned = dega.align.align_serial_slices(adatas, refined, z_space=10)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd
from scipy.optimize import minimize
import shapely

from celldega.align._transform import (
    SimilarityTransform,
    Transform,
    compose_transforms,
    rigid_delta_transform,
)
from celldega.align.serial_slices import SerialAlignmentTransform


if TYPE_CHECKING:
    import geopandas as gpd
    from shapely.geometry.base import BaseGeometry


__all__ = ["neighborhood_alignment", "transform_shapes"]

_DISTANCE_WEIGHTS = ("inverse", "uniform", "exponential", "gaussian")


def _load_slice_geometries(
    shapes: gpd.GeoDataFrame,
    slice_attr: str,
    cluster_attr: str,
    simplify_tolerance: float | None,
) -> dict[Any, dict[str, BaseGeometry]]:
    """Per-slice ``{cluster -> 2D validated geometry}`` from an alpha-shape table.

    Flattens each polygon to 2D (the neighborhood-cloud shapes carry a Z
    stamp used only for 3D display), repairs invalid rings, optionally
    simplifies, and unions any duplicate (slice, cluster) rows into one
    geometry. Empty geometries are dropped so a cluster that produced no
    representable shape simply doesn't participate.
    """
    result: dict[Any, dict[str, BaseGeometry]] = {}
    for slice_id, sdf in shapes.groupby(slice_attr, sort=False):
        per_cluster: dict[str, BaseGeometry] = {}
        for cluster, cdf in sdf.groupby(cluster_attr, sort=False):
            geoms = [g for g in cdf.geometry.to_numpy() if g is not None and not g.is_empty]
            if not geoms:
                continue
            geom = geoms[0] if len(geoms) == 1 else shapely.union_all(geoms)
            geom = shapely.make_valid(shapely.force_2d(geom))
            if simplify_tolerance is not None:
                geom = geom.simplify(simplify_tolerance)
            if geom.is_empty:
                continue
            per_cluster[str(cluster)] = geom
        result[slice_id] = per_cluster
    return result


def _apply_to_geom(geom: BaseGeometry, transform: Transform) -> BaseGeometry:
    """Apply a fitted transform to every vertex of a geometry (2D; drops any Z)."""
    return shapely.transform(geom, transform.apply)


def _apply_to_geom_keep_z(geom: BaseGeometry, transform: Transform) -> BaseGeometry:
    """Apply a fitted 2D transform to a geometry's x/y, passing any Z through unchanged.

    Used by :func:`transform_shapes` so the Z stamp the neighborhood cloud uses
    for 3D display (see
    :func:`~celldega.nbhd.alpha_shapes.alpha_shape_cell_clusters_by_slice`)
    survives the transform, unlike :func:`_apply_to_geom` which flattens to 2D.
    """
    has_z = geom.has_z

    def _fn(coords: np.ndarray) -> np.ndarray:
        coords = np.asarray(coords, dtype=float)
        xy = transform.apply(coords[..., :2])
        if coords.shape[-1] == 3:
            return np.concatenate([xy, coords[..., 2:3]], axis=-1)
        return xy

    return shapely.transform(geom, _fn, include_z=has_z)


def transform_shapes(
    shapes: gpd.GeoDataFrame,
    transform: SerialAlignmentTransform,
    slice_attr: str = "slice_id",
) -> gpd.GeoDataFrame:
    """Apply a serial-slice transform to an alpha-shape ``GeoDataFrame``.

    Moves each shape's geometry by its slice's fitted transform, in place of
    recomputing alpha shapes from transformed cell coordinates. Handy for
    getting the *refined* neighborhood shapes without recomputing them (feed the
    result to :func:`~celldega.align.write_nbhd_cloud` via its ``shapes=``
    argument, or plot it to inspect the refinement), and the companion to
    :meth:`~celldega.align.serial_slices.SerialAlignmentTransform.apply_to_points`
    for polygon rather than point data. Any Z coordinate (the neighborhood
    cloud's per-cluster display stamp) is passed through unchanged; the ``area``
    column, if present, is recomputed from the transformed (rigid, so
    area-preserving) geometry.

    Args:
        shapes: Alpha shapes with a ``geometry`` column and a ``slice_attr``
            column whose values are ``transform``'s slice ids — e.g. the output
            of :func:`~celldega.nbhd.alpha_shapes.alpha_shape_cell_clusters_by_slice`.
        transform: A fitted
            :class:`~celldega.align.serial_slices.SerialAlignmentTransform`
            (e.g. from :func:`neighborhood_alignment`).
        slice_attr: Column in ``shapes`` naming each row's slice (default
            ``"slice_id"``, the neighborhood-cloud convention).

    Returns:
        A copy of ``shapes`` with transformed geometry (and updated ``area``).
        Rows whose slice id is not in ``transform`` are left unchanged.
    """
    import geopandas as gpd

    out = shapes.copy()
    slices = out[slice_attr].to_numpy()
    new_geoms = []
    for geom, slice_id in zip(out.geometry.to_numpy(), slices, strict=True):
        fitted = transform.transforms.get(slice_id)
        if fitted is None or geom is None or geom.is_empty:
            new_geoms.append(geom)
        else:
            new_geoms.append(_apply_to_geom_keep_z(geom, fitted))
    out = out.set_geometry(gpd.GeoSeries(new_geoms, index=out.index, crs=out.crs))
    if "area" in out.columns:
        out["area"] = out.geometry.area
    return out


def _bounds_overlap(a: tuple, b: tuple) -> bool:
    """Whether two ``(minx, miny, maxx, maxy)`` bounding boxes overlap."""
    return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])


def _intersection_area(a: BaseGeometry, b: BaseGeometry) -> float:
    """Intersection area of two geometries, with a bounding-box fast-reject.

    Returns ``0.0`` for disjoint bounding boxes without computing the
    intersection, and also on the rare GEOS failure for a pathological
    configuration (same fragility handled throughout
    :mod:`celldega.nbhd.alpha_shapes`) rather than aborting a whole
    optimization over one polygon pair.
    """
    try:
        if not _bounds_overlap(a.bounds, b.bounds):
            return 0.0
        return float(a.intersection(b).area)
    except Exception:
        return 0.0


def _pair_metrics(a: BaseGeometry, b: BaseGeometry) -> dict[str, float]:
    """Intersection area, IoU, and recoverable-area coverage for one shape pair."""
    intersection = _intersection_area(a, b)
    area_a = float(a.area)
    area_b = float(b.area)
    union = area_a + area_b - intersection
    smaller = min(area_a, area_b)
    return {
        "intersection": intersection,
        "iou": intersection / union if union > 0 else 0.0,
        "coverage": intersection / smaller if smaller > 0 else 0.0,
    }


def _union_centroid(geoms: list[BaseGeometry]) -> np.ndarray:
    """Centroid of the union of a slice's shapes — the rotation anchor."""
    if not geoms:
        return np.zeros(2)
    union = geoms[0] if len(geoms) == 1 else shapely.union_all(geoms)
    if union.is_empty:
        return np.zeros(2)
    centroid = union.centroid
    return np.array([centroid.x, centroid.y], dtype=float)


def _overall_width(slice_geoms: dict[Any, dict[str, BaseGeometry]]) -> float:
    """Largest extent (max of x-span, y-span) across every shape — the scale
    translation bounds are expressed as a fraction of."""
    mins = np.array([np.inf, np.inf])
    maxs = np.array([-np.inf, -np.inf])
    for per_cluster in slice_geoms.values():
        for geom in per_cluster.values():
            minx, miny, maxx, maxy = geom.bounds
            mins = np.minimum(mins, [minx, miny])
            maxs = np.maximum(maxs, [maxx, maxy])
    if not np.all(np.isfinite(mins)):
        return 1.0
    span = maxs - mins
    return float(max(span)) if max(span) > 0 else 1.0


def _window_neighbors(index: int, n_slices: int, window: int) -> list[tuple[int, int]]:
    """``(neighbor_index, slice_distance)`` for every slice within ``window`` on
    either side (excluding the slice itself)."""
    return [
        (j, abs(index - j))
        for j in range(max(0, index - window), min(n_slices, index + window + 1))
        if j != index
    ]


def _distance_weight(distance: int, mode: str, decay: float) -> float:
    """Weight a neighbor's contribution by slice separation ``distance`` (>= 1).

    All modes give the nearest (adjacent, ``distance == 1``) neighbor weight
    ``1.0`` and fall off from there, so ``decay`` and the mode change only how
    fast farther neighbors are discounted, not the adjacent baseline:

    - ``"inverse"``: ``1 / distance`` (``decay`` unused).
    - ``"uniform"``: ``1.0`` for every neighbor in the window (``decay`` unused).
    - ``"exponential"``: ``exp(-(distance - 1) / decay)`` — geometric falloff.
    - ``"gaussian"``: ``exp(-(distance - 1)**2 / (2 * decay**2))`` — slow near,
      then sharp; concentrates the window on the closest slices.
    """
    if mode == "uniform":
        return 1.0
    if mode == "exponential":
        return float(np.exp(-(distance - 1) / decay))
    if mode == "gaussian":
        return float(np.exp(-((distance - 1) ** 2) / (2.0 * decay**2)))
    return 1.0 / distance  # "inverse"


def _refine_one_slice(
    base: dict[str, BaseGeometry],
    anchor: np.ndarray,
    neighbor_geoms: list[dict[str, BaseGeometry]],
    weights: list[float],
    shared_sets: list[set[str]],
    clusters_needed: set[str],
    bounds: list[tuple[float, float]],
    max_rotation: float,
    n_rotation_grid: int,
    x0: np.ndarray,
) -> np.ndarray:
    """Best residual ``(theta, dx, dy)`` maximizing this slice's window overlap.

    Coarse-searches rotation (the parameter the objective is least smooth in)
    on a grid, then refines all three parameters with a derivative-free
    bounded Powell search from the best grid point — the recommended strategy
    for a nonsmooth polygon-intersection objective with no reliable gradient.
    ``base`` shapes are the slice's initially-aligned geometry; the returned
    delta is applied relative to it (rotation about ``anchor``).
    """

    def objective(params: np.ndarray) -> float:
        theta, dx, dy = params
        delta = rigid_delta_transform(theta, dx, dy, center=anchor)
        moved = {k: _apply_to_geom(base[k], delta) for k in clusters_needed}
        total = 0.0
        for neighbor, weight, shared in zip(neighbor_geoms, weights, shared_sets, strict=True):
            for cluster in shared:
                total += weight * _intersection_area(moved[cluster], neighbor[cluster])
        return -total

    best_params = np.asarray(x0, dtype=float)
    best_value = objective(best_params)
    if n_rotation_grid > 0 and max_rotation > 0:
        for theta in np.linspace(-max_rotation, max_rotation, n_rotation_grid):
            candidate = np.array([theta, x0[1], x0[2]])
            value = objective(candidate)
            if value < best_value:
                best_value = value
                best_params = candidate

    result = minimize(
        objective,
        best_params,
        method="Powell",
        bounds=bounds,
        options={"maxiter": 100, "xtol": 1e-4, "ftol": 1e-4},
    )
    if result.fun < best_value:
        return np.clip(result.x, [b[0] for b in bounds], [b[1] for b in bounds])
    return best_params


def _window_overlap(
    moving: dict[str, BaseGeometry],
    neighbor_geoms: list[dict[str, BaseGeometry]],
    weights: list[float],
    shared_sets: list[set[str]],
) -> float:
    """Summed, distance-weighted intersection area of ``moving`` against a window."""
    total = 0.0
    for neighbor, weight, shared in zip(neighbor_geoms, weights, shared_sets, strict=True):
        for cluster in shared:
            total += weight * _intersection_area(moving[cluster], neighbor[cluster])
    return total


def _reapply_landmarks(
    landmarks: pd.DataFrame, transforms: dict[Any, Transform], slice_attr: str
) -> pd.DataFrame:
    """Recompute a landmark table's aligned positions under new per-slice transforms."""
    if not len(landmarks) or slice_attr not in landmarks.columns:
        return landmarks.copy()
    out = landmarks.copy()
    xy = out[["x", "y"]].to_numpy(dtype=float)
    result = xy.copy()
    slices = out[slice_attr].to_numpy()
    for slice_id, transform in transforms.items():
        mask = slices == slice_id
        if mask.any():
            result[mask] = transform.apply(xy[mask])
    out["x"] = result[:, 0]
    out["y"] = result[:, 1]
    return out


def neighborhood_alignment(
    shapes: gpd.GeoDataFrame,
    initial_transform: SerialAlignmentTransform,
    slice_attr: str = "slice_id",
    cluster_attr: str = "cluster_id",
    alignment_window: int | None = None,
    n_sweeps: int = 2,
    rotation_range: float = 10.0,
    translation_range: float = 0.1,
    n_rotation_grid: int = 7,
    distance_weight: str = "inverse",
    distance_decay: float = 1.0,
    simplify_tolerance: float | None = None,
    min_shared_clusters: int = 1,
    compute_diagnostics: bool = True,
) -> SerialAlignmentTransform:
    """Refine a serial-slice alignment by maximizing neighborhood polygon overlap.

    Starts from ``initial_transform`` (a cluster-centroid Procrustes fit from
    :func:`~celldega.align.serial_slices.calc_alignment_transform`) and adds,
    per slice, a small residual rigid transform (rotation + translation, never
    scale) chosen to maximize the summed intersection area of corresponding
    neighborhood regions across a window of neighboring slices. This recovers
    alignment that region centroids miss — footprint orientation and bilateral
    structure a centroid averages away — while staying rigid and reusing the
    Procrustes fit as a starting point close enough for the (nonsmooth) overlap
    objective to optimize locally. The regions are typically cluster alpha
    shapes, but any per-(slice, region) polygons with labels shared across
    slices work (manually drawn regions, other domain-ID algorithms).

    Optimization is block coordinate descent: the reference slice is held
    fixed, and every other slice is optimized in turn against its neighbors'
    *current* estimates, in alternating forward and backward passes over
    ``n_sweeps`` sweeps. Each per-slice step coarse-searches residual rotation
    on a grid, then refines all three parameters with a bounded Powell search
    (see :func:`_refine_one_slice`).

    Args:
        shapes: A per-(slice, region) polygon ``GeoDataFrame`` in each slice's
            *native* coordinate frame, with ``slice_attr``/``cluster_attr``
            columns and a ``geometry`` column — typically the cluster alpha
            shapes :func:`~celldega.nbhd.alpha_shapes.alpha_shape_cell_clusters_by_slice`
            returns, but any polygons with labels shared across slices (manual
            regions, other domain-ID algorithms) work. ``initial_transform`` is
            applied to these, so they must be pre-alignment (do not pass shapes
            computed from already-aligned coordinates). Geometry may be 2D or 3D
            (a Z stamp is flattened away).
        initial_transform: The Procrustes
            :class:`~celldega.align.serial_slices.SerialAlignmentTransform` to
            refine. Its slice order, reference slice, and (unless overridden)
            alignment window are reused, and its landmarks are carried through
            as provenance. Every slice present in ``shapes`` must be one of its
            slices.
        slice_attr: Column in ``shapes`` identifying each row's slice (default
            ``"slice_id"``, matching the neighborhood-cloud output). Its values
            must match ``initial_transform``'s slice ids. Note this is the
            *input* column name; the returned transform keeps
            ``initial_transform``'s own ``slice_attr``.
        cluster_attr: Column in ``shapes`` identifying each row's region/label
            (default ``"cluster_id"``). A region is matched to its counterpart
            in another slice by this value, so it need not be a cluster — any
            label consistent across slices (a manual region name, a domain id)
            works.
        alignment_window: Number of neighboring slices on each side to score a
            slice's overlap against. ``None`` (default) reuses
            ``initial_transform``'s ``alignment_window``.
        n_sweeps: Number of forward+backward coordinate-descent sweeps over the
            non-reference slices.
        rotation_range: Bound (in degrees) on each slice's residual rotation,
            ``±`` this value. Kept modest since the Procrustes fit already
            resolves gross rotation.
        translation_range: Bound on each slice's residual translation, as a
            fraction of the overall tissue width (largest x/y extent across all
            shapes), applied ``±`` in each axis.
        n_rotation_grid: Number of grid points in the coarse residual-rotation
            search over ``[-rotation_range, +rotation_range]`` before the Powell
            refinement. ``0`` skips the grid (Powell only).
        distance_weight: How a neighbor's overlap contribution falls off with
            slice separation ``d`` (all modes give an adjacent neighbor weight
            ``1.0``): ``"inverse"`` (default, ``1/d``), ``"uniform"`` (all
            neighbors in the window weighted equally), ``"exponential"``
            (``exp(-(d-1)/distance_decay)``), or ``"gaussian"``
            (``exp(-(d-1)**2 / (2*distance_decay**2))``, a slow-then-sharp
            tail-off that concentrates the window on the closest slices).
        distance_decay: Falloff scale for the ``"exponential"``/``"gaussian"``
            weights (larger = slower falloff, so farther slices keep more
            influence); ignored by ``"inverse"``/``"uniform"``. Default ``1.0``.
        simplify_tolerance: If given, Douglas-Peucker tolerance applied to each
            alpha shape before optimization, to speed up intersection at the
            cost of boundary detail. ``None`` (default) leaves shapes as-is.
        min_shared_clusters: A slice is only refined if it shares at least this
            many cluster labels with its neighbor window; otherwise its residual
            stays identity (it keeps its Procrustes transform) and it is marked
            skipped in the transform log.
        compute_diagnostics: If ``True`` (default), record per-slice overlap
            before/after refinement and per-cluster IoU/coverage against the
            nearest neighbor in the transform log.

    Returns:
        A refined :class:`~celldega.align.serial_slices.SerialAlignmentTransform`
        with ``method="neighborhood"``, each slice's transform being its
        residual delta composed with its initial Procrustes transform, ready to
        pass to :func:`~celldega.align.serial_slices.align_serial_slices`.

    Raises:
        ValueError: If ``distance_weight`` is not recognized, ``shapes`` is
            missing a required column, ``shapes`` references a slice not in
            ``initial_transform``, ``alignment_window`` is less than 1, or the
            initial transforms are not rigid (a residual rigid refinement is
            only well-defined on top of a rigid, e.g. ``method="procrustes"``,
            initial fit — not a thin-plate-spline warp).
    """
    if distance_weight not in _DISTANCE_WEIGHTS:
        raise ValueError(
            f"distance_weight must be one of {_DISTANCE_WEIGHTS}, got {distance_weight!r}"
        )
    if distance_decay <= 0:
        raise ValueError(f"distance_decay must be > 0, got {distance_decay}")
    for column in (slice_attr, cluster_attr, "geometry"):
        if column not in shapes.columns:
            raise ValueError(f"shapes is missing required column {column!r}")

    slice_ids = list(initial_transform.slice_ids)
    n_slices = len(slice_ids)
    slice_id_set = set(slice_ids)
    unknown = set(shapes[slice_attr].unique()) - slice_id_set
    if unknown:
        raise ValueError(
            f"shapes references slice(s) {sorted(map(str, unknown))} not in initial_transform's "
            f"slices {[str(s) for s in slice_ids]}; slice ids in shapes[{slice_attr!r}] must "
            "match the transform being refined"
        )

    non_rigid = [
        str(slice_id)
        for slice_id, transform in initial_transform.transforms.items()
        if not isinstance(transform, SimilarityTransform)
    ]
    if non_rigid:
        raise ValueError(
            "neighborhood_alignment refines a rigid initial transform; slice(s) "
            f"{non_rigid} have a non-rigid (e.g. thin-plate-spline) transform. Refit the "
            "initial alignment with method='procrustes'."
        )

    window = initial_transform.alignment_window if alignment_window is None else alignment_window
    if window < 1:
        raise ValueError(f"alignment_window must be >= 1, got {window}")

    reference_id = initial_transform.reference
    reference_index = slice_ids.index(reference_id)

    native = _load_slice_geometries(shapes, slice_attr, cluster_attr, simplify_tolerance)

    # Initially-aligned geometry per slice (native shapes under the Procrustes fit).
    initial_aligned: dict[Any, dict[str, BaseGeometry]] = {}
    anchors: dict[Any, np.ndarray] = {}
    for slice_id in slice_ids:
        transform = initial_transform.transforms[slice_id]
        geoms = {k: _apply_to_geom(g, transform) for k, g in native.get(slice_id, {}).items()}
        initial_aligned[slice_id] = geoms
        anchors[slice_id] = _union_centroid(list(geoms.values()))

    tissue_width = _overall_width(initial_aligned)
    max_translation = translation_range * tissue_width
    max_rotation = np.deg2rad(rotation_range)
    bounds = [
        (-max_rotation, max_rotation),
        (-max_translation, max_translation),
        (-max_translation, max_translation),
    ]

    # Residual delta per slice, parameterized as (theta, dx, dy) about the
    # slice's anchor; reference stays at identity. `aligned` caches each
    # slice's geometry under its current residual (initially == initial_aligned).
    residual: dict[Any, np.ndarray] = {slice_id: np.zeros(3) for slice_id in slice_ids}
    aligned: dict[Any, dict[str, BaseGeometry]] = {
        slice_id: dict(geoms) for slice_id, geoms in initial_aligned.items()
    }

    def _optimize_slice(index: int, neighbor_pairs: list[tuple[int, int]]) -> None:
        """Refine one slice's residual against a given set of ``(neighbor, distance)``.

        Reads each neighbor's *current* aligned geometry (Gauss-Seidel), so a
        neighbor refined earlier in the same pass is seen at its updated pose.
        """
        slice_id = slice_ids[index]
        base = initial_aligned[slice_id]
        neighbor_geoms: list[dict[str, BaseGeometry]] = []
        weights: list[float] = []
        shared_sets: list[set[str]] = []
        for j, distance in neighbor_pairs:
            neighbor = aligned[slice_ids[j]]
            shared = set(base) & set(neighbor)
            if not shared:
                continue
            neighbor_geoms.append(neighbor)
            weights.append(_distance_weight(distance, distance_weight, distance_decay))
            shared_sets.append(shared)
        clusters_needed = set().union(*shared_sets) if shared_sets else set()
        if len(clusters_needed) < min_shared_clusters:
            return
        params = _refine_one_slice(
            base,
            anchors[slice_id],
            neighbor_geoms,
            weights,
            shared_sets,
            clusters_needed,
            bounds,
            max_rotation,
            n_rotation_grid,
            residual[slice_id],
        )
        residual[slice_id] = params
        delta = rigid_delta_transform(*params, center=anchors[slice_id])
        aligned[slice_id] = {k: _apply_to_geom(g, delta) for k, g in base.items()}

    # Pass 1: propagate the reference frame outward. Walking away from the
    # reference in both directions, each slice is aligned only to its already-
    # aligned neighbors on the reference side (like calc_alignment_transform's
    # chain-walk). This anchors the whole stack to the reference before the
    # symmetric refinement below, which otherwise could collapse a run of
    # slices onto an outer neighbor's frame instead of the reference's.
    for chain in (range(reference_index - 1, -1, -1), range(reference_index + 1, n_slices)):
        processed = [reference_index]
        for index in chain:
            window_idxs = processed[-window:]
            _optimize_slice(index, [(j, abs(index - j)) for j in window_idxs])
            processed.append(index)

    # Pass 2: symmetric full-window coordinate descent. Each non-reference slice
    # is refined against neighbors on both sides, in alternating forward and
    # backward passes, now that every slice already sits near the reference frame.
    for _sweep in range(n_sweeps):
        for pass_indices in (range(n_slices), range(n_slices - 1, -1, -1)):
            for index in pass_indices:
                if index == reference_index:
                    continue
                _optimize_slice(index, _window_neighbors(index, n_slices, window))

    transforms: dict[Any, Transform] = {}
    for slice_id in slice_ids:
        delta = rigid_delta_transform(*residual[slice_id], center=anchors[slice_id])
        transforms[slice_id] = compose_transforms(delta, initial_transform.transforms[slice_id])

    transform_log = _build_transform_log(
        slice_ids,
        reference_index,
        window,
        residual,
        initial_aligned,
        aligned,
        distance_weight,
        distance_decay,
        min_shared_clusters,
        compute_diagnostics,
    )

    landmarks_initial = initial_transform.landmarks_initial.copy()
    landmarks_aligned = _reapply_landmarks(
        landmarks_initial, transforms, initial_transform.slice_attr
    )

    return SerialAlignmentTransform(
        slice_attr=initial_transform.slice_attr,
        slice_ids=slice_ids,
        reference=reference_id,
        transforms=transforms,
        transform_log=transform_log,
        landmarks_initial=landmarks_initial,
        landmarks_aligned=landmarks_aligned,
        method="neighborhood",
        allow_reflection=initial_transform.allow_reflection,
        smoothing=initial_transform.smoothing,
        degree=initial_transform.degree,
        area_regularization=initial_transform.area_regularization,
        shape_regularization=initial_transform.shape_regularization,
        weight_by_adjacent_counts=initial_transform.weight_by_adjacent_counts,
        manual_landmark_weight=initial_transform.manual_landmark_weight,
        alignment_window=window,
    )


def _build_transform_log(
    slice_ids: list[Any],
    reference_index: int,
    window: int,
    residual: dict[Any, np.ndarray],
    initial_aligned: dict[Any, dict[str, BaseGeometry]],
    aligned: dict[Any, dict[str, BaseGeometry]],
    distance_weight: str,
    distance_decay: float,
    min_shared_clusters: int,
    compute_diagnostics: bool,
) -> dict[str, dict]:
    """Per-slice refinement provenance and (optionally) overlap diagnostics.

    Records, for each non-reference slice, the residual rotation/translation
    applied and — when ``compute_diagnostics`` — the window overlap before and
    after refinement (both against the *converged* neighbor geometry, so it's a
    fair per-slice before/after) plus per-cluster IoU/coverage against the
    nearest neighbor that shares clusters.
    """
    n_slices = len(slice_ids)
    log: dict[str, dict] = {}
    for index, slice_id in enumerate(slice_ids):
        if index == reference_index:
            continue
        neighbors = _window_neighbors(index, n_slices, window)
        base = initial_aligned[slice_id]
        neighbor_geoms: list[dict[str, BaseGeometry]] = []
        weights: list[float] = []
        shared_sets: list[set[str]] = []
        for j, distance in neighbors:
            neighbor = aligned[slice_ids[j]]
            shared = set(base) & set(neighbor)
            if not shared:
                continue
            neighbor_geoms.append(neighbor)
            weights.append(_distance_weight(distance, distance_weight, distance_decay))
            shared_sets.append(shared)
        clusters_needed = set().union(*shared_sets) if shared_sets else set()

        theta, dx, dy = residual[slice_id]
        entry: dict[str, Any] = {
            "aligned_to": [
                str(slice_ids[j]) for j, _ in neighbors if set(base) & set(aligned[slice_ids[j]])
            ],
            "n_shared_clusters": len(clusters_needed),
            "residual_rotation_deg": float(np.rad2deg(theta)),
            "residual_translation": [float(dx), float(dy)],
            "skipped": len(clusters_needed) < min_shared_clusters,
        }

        if compute_diagnostics and clusters_needed:
            entry["overlap_initial"] = _window_overlap(base, neighbor_geoms, weights, shared_sets)
            entry["overlap_final"] = _window_overlap(
                aligned[slice_id], neighbor_geoms, weights, shared_sets
            )
            entry["per_cluster"] = _nearest_neighbor_metrics(index, slice_ids, neighbors, aligned)
        log[str(slice_id)] = entry
    return log


def _nearest_neighbor_metrics(
    index: int,
    slice_ids: list[Any],
    neighbors: list[tuple[int, int]],
    aligned: dict[Any, dict[str, BaseGeometry]],
) -> dict[str, dict[str, float]]:
    """Per-cluster IoU/coverage against the nearest neighbor that shares clusters."""
    this = aligned[slice_ids[index]]
    for j, _distance in sorted(neighbors, key=lambda pair: pair[1]):
        neighbor = aligned[slice_ids[j]]
        shared = sorted(set(this) & set(neighbor))
        if shared:
            return {cluster: _pair_metrics(this[cluster], neighbor[cluster]) for cluster in shared}
    return {}
