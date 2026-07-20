"""Interactive landmark-marking widget for alignment.

:class:`Landmark` pairs with :class:`~celldega.viz.widget.Landscape`: it
renders two side-by-side 2D point-cloud viewports (cell centroids from each
slice's own ``obsm["spatial"]``, always in micron/data space — pixel-space
image registration is Landscape's job, not this widget's) and lets a user
mark corresponding points between them. Either viewport can swap to any
slice in the dataset (not just the initial pair) — useful since a real
alignment session usually needs landmarks across more than one adjacent
pair. MARK mode drops a draft point in each viewport; dragging either one
refines its position; SAVE commits the current pair as one landmark row
(DEL removes an already-committed pair). Revisiting a slice on either side
restores whatever landmarks were already saved for it.

The output, :attr:`Landmark.landmarks`, matches
:func:`~celldega.align.landmarks.calc_landmarks`'s output shape exactly (a
plain ``DataFrame`` with columns ``label``, ``x``, ``y``, and a slice-tagging
column) so manually- and automatically-derived landmarks concatenate
directly and both feed :func:`~celldega.align.serial_slices.calc_alignment_transform`.
"""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import suppress
import io
from typing import Any

from anndata import AnnData
import anywidget
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import traitlets

from celldega.align._slices import _ordered_slices
from celldega.viz.widget import _WIDGET_ESM, _hsv_to_hex


__all__ = ["Landmark"]

_DEFAULT_MARKER_COLOR = "#4f80ff"
_EMPTY_FEATURE_COLLECTION = {"type": "FeatureCollection", "features": []}


def _df_to_parquet_bytes(df: pd.DataFrame) -> bytes:
    df = df.copy()
    df.columns = df.columns.map(str)
    buf = io.BytesIO()
    pq.write_table(pa.Table.from_pandas(df), buf, compression="zstd")
    return buf.getvalue()


def _slice_categories(adata: AnnData, cluster_key: str) -> list[str]:
    series = adata.obs[cluster_key]
    if isinstance(series.dtype, pd.CategoricalDtype):
        return [str(c) for c in series.dtype.categories]
    return sorted(series.astype(str).unique())


def _global_cluster_colors(all_slices: list[AnnData], cluster_key: str) -> dict[str, str]:
    """One color per cluster label, consistent across every slice.

    Splitting a single combined ``AnnData`` by ``slice_attr`` already shares
    one categorical dtype/colors across every split, so this only matters
    for a list of genuinely separate ``AnnData`` — reuses the first slice's
    own ``uns[f"{cluster_key}_colors"]`` if present, falling back to an
    evenly-spaced HSV palette over the pooled category list otherwise, so a
    given cluster label never gets a different color depending on which
    slice happens to be showing.
    """
    categories: list[str] = []
    seen: set[str] = set()
    colors_source: tuple[list[str], list[str]] | None = None

    for adata in all_slices:
        cats = _slice_categories(adata, cluster_key)
        for cat in cats:
            if cat not in seen:
                seen.add(cat)
                categories.append(cat)
        if colors_source is None:
            colors = adata.uns.get(f"{cluster_key}_colors")
            if colors is not None:
                colors_source = (cats, list(colors))

    if colors_source is not None:
        cats, colors = colors_source
        color_by_category = dict(zip(cats, colors, strict=False))
    else:
        color_by_category = {}

    n = max(len(categories), 1)
    for i, cat in enumerate(categories):
        color_by_category.setdefault(cat, _hsv_to_hex(i / n))
    return color_by_category


def _global_cluster_counts(all_slices: list[AnnData], cluster_key: str) -> dict[str, int]:
    """Cluster label -> cell count, summed across every slice in the dataset
    (not just the two currently shown), for the shared CELL bar graph."""
    counts: dict[str, int] = {}
    for adata in all_slices:
        for cat, count in adata.obs[cluster_key].astype(str).value_counts().items():
            counts[cat] = counts.get(cat, 0) + int(count)
    return counts


def _slice_centroids(
    adata: AnnData, cluster_key: str | None, color_by_category: dict[str, str] | None
) -> pd.DataFrame:
    """One slice's cell centroids (+ optional cluster/color) for a Landmark viewport."""
    spatial = adata.obsm.get("spatial")
    if spatial is None or np.asarray(spatial).shape[1] < 2:
        raise ValueError("each slice must have obsm['spatial'] with at least 2 columns (x, y)")

    xy = np.asarray(spatial)[:, :2]
    df = pd.DataFrame({"x": xy[:, 0], "y": xy[:, 1]}, index=adata.obs_names.astype(str))
    df.index.name = "cell_id"

    if cluster_key is None:
        df["color"] = _DEFAULT_MARKER_COLOR
        return df.reset_index()

    df["cluster"] = adata.obs[cluster_key].astype(str).to_numpy()
    df["color"] = df["cluster"].map(color_by_category or {}).fillna(_DEFAULT_MARKER_COLOR)
    return df.reset_index()


class Landmark(anywidget.AnyWidget):
    """A widget for interactively marking corresponding landmark points across
    dataset slices, for procrustes/thin-plate-spline alignment.

    Args:
        adatas: A single ``AnnData`` with ``slice_attr`` given, or a list of
            per-slice ``AnnData`` (list order is slice order) — the same two
            input shapes :func:`~celldega.align.landmarks.calc_landmarks`
            accepts. Must resolve to at least 2 slices; any number beyond 2
            is fine — both viewports can swap to any slice in the resolved
            set after construction (driven by the front-end dropdowns), not
            just the initial pair.
        slice_attr: For a single combined ``AnnData``, the ``obs`` column
            identifying each cell's slice.
        slices: The initial ``(slice_id_a, slice_id_b)`` pair to show.
            Defaults to the first two resolved slice ids.
        cluster_key: Optional ``obs`` column to color centroids by, for
            visual context while marking. Purely cosmetic — has no effect on
            the resulting landmark table.
        slice_labels: Optional ``{slice_id: display_name}`` overrides for the
            dropdown/panel labels. Slices not present default to
            ``str(slice_id)``.
        landscapes: Not implemented yet — planned future alternative to
            ``adatas`` that would point Landmark directly at two
            :class:`~celldega.viz.widget.Landscape` instances.

    Raises:
        NotImplementedError: If ``landscapes`` is given.
        ValueError: If ``adatas`` is missing, resolves to fewer than 2
            slices, if a ``slices`` id isn't found among them, or if a
            selected slice is missing ``obsm["spatial"]``.
    """

    _esm = _WIDGET_ESM
    component = traitlets.Unicode("Landmark").tag(sync=True)

    width = traitlets.Int(0).tag(sync=True)
    height = traitlets.Int(600).tag(sync=True)

    # Full pool of slice ids (as str) available to swap between, in resolved
    # order, and their display labels — drive the front-end dropdowns.
    slice_ids = traitlets.List(trait=traitlets.Unicode(), default_value=[]).tag(sync=True)
    slice_labels = traitlets.Dict({}).tag(sync=True)

    # Which slice id (as str) is currently shown on each side.
    slice_id_a = traitlets.Unicode("").tag(sync=True)
    slice_id_b = traitlets.Unicode("").tag(sync=True)

    # Committed landmark points for whichever slice is currently shown on
    # each side, as a GeoJSON FeatureCollection of Point features
    # (properties.label pairs a point across the two sides). Draft
    # (not-yet-SAVEd) points live only in JS state and never reach here.
    landmark_geojson_a = traitlets.Dict(dict(_EMPTY_FEATURE_COLLECTION)).tag(sync=True)
    landmark_geojson_b = traitlets.Dict(dict(_EMPTY_FEATURE_COLLECTION)).tag(sync=True)

    # Next label the front end should use for a new SAVEd pair. Python is
    # authoritative: it only ever bumps this up (see `_bump_label_counter`),
    # so labels never collide even across many slice swaps.
    next_landmark_label = traitlets.Int(1).tag(sync=True)

    # Static per-slice cell counts (for a "SLICE" bar graph), and per-label
    # count of distinct slices a landmark has a saved point in (for a
    # "LNDMRK" bar graph) — the latter recomputed whenever `landmarks` changes.
    slice_cell_counts = traitlets.Dict({}).tag(sync=True)
    landmark_coverage = traitlets.Dict({}).tag(sync=True)

    # Cluster label -> cell count summed across every slice (not just the
    # two currently shown) and -> color, for the single shared CELL bar
    # graph. Static; empty if no `cluster_key` was given.
    cluster_counts = traitlets.Dict({}).tag(sync=True)
    cluster_colors = traitlets.Dict({}).tag(sync=True)

    # Python-only materialized table, spanning every slice visited so far.
    landmarks = traitlets.Instance(pd.DataFrame, allow_none=True)

    def __init__(
        self,
        adatas: AnnData | list[AnnData] | None = None,
        slice_attr: str | None = None,
        slices: Sequence[Any] | None = None,
        cluster_key: str | None = None,
        slice_labels: dict[Any, str] | None = None,
        landscapes: Any = None,
        **kwargs,
    ):
        if landscapes is not None:
            raise NotImplementedError(
                "landscapes= isn't implemented yet — pass 'adatas' instead. Pointing "
                "Landmark directly at two Landscape instances is planned future work."
            )
        if adatas is None:
            raise ValueError(
                "Landmark requires 'adatas' (a single AnnData with slice_attr, "
                "or a list of per-slice AnnData)"
            )

        all_slice_ids, all_slices, resolved_slice_attr = _ordered_slices(
            adatas, slice_attr, copy=False
        )
        if len(all_slice_ids) < 2:
            raise ValueError(f"Landmark needs at least 2 slices, got {len(all_slice_ids)}")

        self._slice_attr = resolved_slice_attr
        self._cluster_key = cluster_key
        self._slice_id_by_str = {str(s): s for s in all_slice_ids}
        self._slices_by_str = {str(s): a for s, a in zip(all_slice_ids, all_slices, strict=True)}
        self._centroid_cache: dict[str, bytes] = {}

        if cluster_key is not None:
            missing_cluster_key = [a for a in all_slices if cluster_key not in a.obs.columns]
            if missing_cluster_key:
                raise ValueError(f"'{cluster_key}' is not a column in every slice's adata.obs")
            self._cluster_colors = _global_cluster_colors(all_slices, cluster_key)
            cluster_counts = _global_cluster_counts(all_slices, cluster_key)
        else:
            self._cluster_colors = {}
            cluster_counts = {}

        if slices is not None:
            if len(slices) != 2:
                raise ValueError(f"slices must select exactly 2 slice ids, got {len(slices)}")
            initial_a, initial_b = slices
        else:
            initial_a, initial_b = all_slice_ids[0], all_slice_ids[1]

        missing = [s for s in (initial_a, initial_b) if str(s) not in self._slice_id_by_str]
        if missing:
            raise ValueError(f"slice id(s) {missing!r} not found among {all_slice_ids!r}")

        resolved_labels = dict(slice_labels) if slice_labels else {}
        kwargs.setdefault("slice_ids", [str(s) for s in all_slice_ids])
        kwargs.setdefault(
            "slice_labels", {str(s): str(resolved_labels.get(s, s)) for s in all_slice_ids}
        )
        kwargs.setdefault("slice_id_a", str(initial_a))
        kwargs.setdefault("slice_id_b", str(initial_b))
        kwargs.setdefault(
            "slice_cell_counts",
            {str(s): int(a.n_obs) for s, a in zip(all_slice_ids, all_slices, strict=True)},
        )
        kwargs.setdefault("cluster_counts", cluster_counts)
        kwargs.setdefault("cluster_colors", dict(self._cluster_colors))

        self.add_traits(
            centroids_parquet_a=traitlets.Bytes(b"").tag(sync=True),
            centroids_parquet_b=traitlets.Bytes(b"").tag(sync=True),
        )

        super().__init__(**kwargs)

        if self.landmarks is None:
            self.landmarks = pd.DataFrame(columns=["label", "x", "y", resolved_slice_attr])

    def _get_centroids(self, slice_id_str: str) -> bytes:
        if slice_id_str not in self._centroid_cache:
            adata = self._slices_by_str[slice_id_str]
            self._centroid_cache[slice_id_str] = _df_to_parquet_bytes(
                _slice_centroids(adata, self._cluster_key, self._cluster_colors)
            )
        return self._centroid_cache[slice_id_str]

    def _geojson_for_slice(self, slice_id_str: str) -> dict:
        slice_id = self._slice_id_by_str[slice_id_str]
        landmarks = self.landmarks
        if landmarks is None or landmarks.empty:
            return dict(_EMPTY_FEATURE_COLLECTION)

        subset = landmarks.loc[landmarks[self._slice_attr] == slice_id]
        features = [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [row.x, row.y]},
                "properties": {"label": row.label},
            }
            for row in subset.itertuples()
        ]
        return {"type": "FeatureCollection", "features": features}

    @traitlets.observe("slice_id_a")
    def _on_slice_id_a_change(self, change: dict) -> None:
        self._switch_side("a", change["new"])

    @traitlets.observe("slice_id_b")
    def _on_slice_id_b_change(self, change: dict) -> None:
        self._switch_side("b", change["new"])

    def _switch_side(self, side: str, slice_id_str: str) -> None:
        if not slice_id_str or slice_id_str not in self._slice_id_by_str:
            return
        setattr(self, f"centroids_parquet_{side}", self._get_centroids(slice_id_str))
        setattr(self, f"landmark_geojson_{side}", self._geojson_for_slice(slice_id_str))

    @traitlets.observe("landmark_geojson_a")
    def _on_landmark_geojson_a_change(self, change: dict) -> None:
        self._commit_side_landmarks(self.slice_id_a, change["new"])

    @traitlets.observe("landmark_geojson_b")
    def _on_landmark_geojson_b_change(self, change: dict) -> None:
        self._commit_side_landmarks(self.slice_id_b, change["new"])

    def _commit_side_landmarks(self, slice_id_str: str, geojson: dict) -> None:
        """Replace this slice's rows in :attr:`landmarks` with what the currently
        displayed side reports — that side's committed feature collection is
        the complete, authoritative state for whichever slice it's showing."""
        if not slice_id_str or slice_id_str not in self._slice_id_by_str:
            return
        slice_id = self._slice_id_by_str[slice_id_str]

        rows = []
        for feature in (geojson or {}).get("features", []):
            label = feature.get("properties", {}).get("label")
            coordinates = feature.get("geometry", {}).get("coordinates")
            if label is None or coordinates is None:
                continue
            rows.append(
                {
                    "label": str(label),
                    "x": float(coordinates[0]),
                    "y": float(coordinates[1]),
                    self._slice_attr: slice_id,
                }
            )

        existing = (
            self.landmarks
            if self.landmarks is not None
            else pd.DataFrame(columns=["label", "x", "y", self._slice_attr])
        )
        others = existing.loc[existing[self._slice_attr] != slice_id]
        new_rows = pd.DataFrame(rows, columns=["label", "x", "y", self._slice_attr])
        self.landmarks = pd.concat([others, new_rows], ignore_index=True)
        self._bump_label_counter(row["label"] for row in rows)
        self._recompute_landmark_coverage()

    def _recompute_landmark_coverage(self) -> None:
        """Number of distinct slices each landmark label has a saved point in,
        for the front end's LNDMRK bar graph (bar length = this count)."""
        if self.landmarks is None or self.landmarks.empty:
            self.landmark_coverage = {}
            return
        counts = self.landmarks.groupby("label")[self._slice_attr].nunique()
        self.landmark_coverage = {str(label): int(count) for label, count in counts.items()}

    def _bump_label_counter(self, labels) -> None:
        numeric = []
        for label in labels:
            with suppress(ValueError):
                numeric.append(int(label))
        if numeric:
            self.next_landmark_label = max(self.next_landmark_label, max(numeric) + 1)

    def calc_alignment_transform(self, **kwargs):
        """Fit a transform directly from the currently-marked landmarks.

        Convenience wrapper over
        :func:`~celldega.align.serial_slices.calc_alignment_transform` —
        equivalent to calling it on :attr:`landmarks` directly.
        """
        from celldega.align.serial_slices import calc_alignment_transform

        if self.landmarks is None or self.landmarks.empty:
            raise ValueError("no landmarks marked yet — MARK and SAVE at least one pair first")
        kwargs.setdefault("slice_attr", self._slice_attr)
        return calc_alignment_transform(self.landmarks, **kwargs)

    def close(self):  # pragma: no cover - cleanup depends on JS
        """Close the widget and notify the frontend to release resources."""
        with suppress(Exception):
            self.send({"event": "finalize"})
        super().close()
