"""AnnData-backed, linked two-dimensional scatterplots."""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import suppress
import io
from typing import Any

from anndata import AnnData
from matplotlib.colors import to_hex
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import traitlets

from ._widget_lifecycle import CelldegaWidget
from .widget import _WIDGET_ESM, _hsv_to_hex


__all__ = ["Scatterplot"]

_CONFIG_TRAITS = ("view", "x", "y", "layer", "color_by")
_DEFAULT_COLOR = "#4f80ff"
_EMBEDDINGS = {"umap": "X_umap", "spatial": "spatial"}


class Scatterplot(CelldegaWidget):
    """Plot cells from an AnnData in UMAP, spatial, or gene-expression space.

    ``view`` defaults to UMAP, then spatial, then genes, according to available
    data. ``x`` and ``y`` name genes; ``layer=None`` uses ``adata.X``. Only the
    active expression columns are read, including for sparse and backed data.
    ``color_by`` optionally names an observation column for categorical colors.

    Gene/view changes require a live Python kernel. Linear/log1p transitions
    happen in the browser; log1p requires nonnegative coordinates. Changing to
    a negative-valued axis resets that axis to linear. Selection always uses
    observation names and survives changing axes. Selecting cells does not
    change AnnData: only :meth:`annotate_selection` writes to ``adata.obs``,
    in memory, and callers explicitly save their data if persistence is wanted.

    As with other Celldega widgets, ``name=`` replaces and closes an earlier
    widget with the same name. Call ``close()`` when a widget is no longer used
    to release its browser/WebGL resources.
    """

    _esm = _WIDGET_ESM
    component = traitlets.Unicode("Scatterplot").tag(sync=True)
    width = traitlets.Int(0, min=0).tag(sync=True)
    height = traitlets.Int(600, min=1).tag(sync=True)
    point_size = traitlets.Float(3.0, min=0.1).tag(sync=True)
    animation_duration = traitlets.Int(450, min=0).tag(sync=True)

    view = traitlets.Enum(["genes", "umap", "spatial"], default_value="genes").tag(sync=True)
    x = traitlets.Unicode("").tag(sync=True)
    y = traitlets.Unicode("").tag(sync=True)
    layer = traitlets.Unicode("").tag(sync=True)
    color_by = traitlets.Unicode("").tag(sync=True)
    x_scale = traitlets.Enum(["linear", "log1p"], default_value="linear").tag(sync=True)
    y_scale = traitlets.Enum(["linear", "log1p"], default_value="linear").tag(sync=True)
    available_views = traitlets.List(traitlets.Unicode(), default_value=[]).tag(sync=True)
    gene_names = traitlets.List(traitlets.Unicode(), default_value=[]).tag(sync=True)
    obs_columns = traitlets.List(traitlets.Unicode(), default_value=[]).tag(sync=True)
    layers = traitlets.List(traitlets.Unicode(), default_value=[]).tag(sync=True)

    points_parquet = traitlets.Bytes(b"").tag(sync=True)
    plot_meta = traitlets.Dict(default_value={}).tag(sync=True)
    selected_cells = traitlets.List(traitlets.Unicode(), default_value=[]).tag(sync=True)
    click_info = traitlets.Dict(default_value={}).tag(sync=True)
    update_trigger = traitlets.Dict(default_value={}).tag(sync=True)
    raster_request = traitlets.Int(0).tag(sync=True)
    raster_png = traitlets.Unicode("").tag(sync=True)
    raster_view_state = traitlets.Dict(default_value={}).tag(sync=True)

    def __init__(
        self,
        adata: AnnData,
        *,
        view: str | None = None,
        x: str | None = None,
        y: str | None = None,
        layer: str | None = None,
        color_by: str | None = None,
        **kwargs,
    ):
        self._ready = False
        self._closed = False
        self._updating = False
        self._pending_payload = None
        self._revision = 0
        if not isinstance(adata, AnnData):
            raise TypeError("adata must be an AnnData object")
        if not adata.obs_names.is_unique or not adata.var_names.is_unique:
            raise ValueError("adata.obs_names and adata.var_names must be unique")
        if not adata.obs.columns.is_unique:
            raise ValueError("adata.obs columns must be unique")
        if not all(isinstance(name, str) for name in (*adata.obs_names, *adata.var_names)):
            raise ValueError("adata.obs_names and adata.var_names must be strings")
        self.adata = adata
        self._cell_ids = set(adata.obs_names)
        self._gene_ids = set(adata.var_names)
        genes = adata.var_names.tolist()
        views = [name for name, key in _EMBEDDINGS.items() if key in adata.obsm]
        if genes:
            views.append("genes")
        if not views:
            raise ValueError("adata needs genes, obsm['X_umap'], or obsm['spatial']")
        config = {
            "view": view if view is not None else views[0],
            "x": x if x is not None else (genes[0] if genes else ""),
            "y": y if y is not None else (genes[min(1, len(genes) - 1)] if genes else ""),
            "layer": "" if layer is None else layer,
            "color_by": "" if color_by is None else color_by,
        }
        self._views = views
        self._validate_configuration(config)
        payload = self._prepare_payload(config)
        for axis in ("x", "y"):
            if kwargs.get(f"{axis}_scale") == "log1p" and not payload[1][f"{axis}_nonnegative"]:
                raise ValueError(f"{axis}_scale='log1p' requires nonnegative coordinates")
        super().__init__(
            **config,
            available_views=views,
            gene_names=genes,
            obs_columns=[name for name in adata.obs.columns if isinstance(name, str)],
            layers=list(adata.layers),
            **kwargs,
        )
        self._ready = True
        self._publish_payload(payload)

    def _configuration(self) -> dict[str, str]:
        return {name: getattr(self, name) for name in _CONFIG_TRAITS}

    def _validate_configuration(self, config: dict[str, str]) -> None:
        if config["view"] not in self._views:
            raise ValueError(f"view {config['view']!r} is unavailable; choose from {self._views}")
        for axis in ("x", "y"):
            gene = config[axis]
            if gene not in self._gene_ids and not (gene == "" and not self._gene_ids):
                raise ValueError(f"unknown {axis} gene: {gene!r}")
        if config["layer"] and config["layer"] not in self.adata.layers:
            raise ValueError(f"unknown layer: {config['layer']!r}")
        if config["color_by"] and config["color_by"] not in self.adata.obs.columns:
            raise ValueError(f"unknown obs column: {config['color_by']!r}")

    def _coordinates(self, config: dict[str, str]) -> tuple[np.ndarray, str, str]:
        if config["view"] == "genes":
            matrix = self.adata.layers[config["layer"]] if config["layer"] else self.adata.X
            if matrix is None:
                raise ValueError("gene plots require adata.X or a selected expression layer")
            indices = self.adata.var_names.get_indexer([config["x"], config["y"]])
            # Sorted, unique indices also work with h5py/backed fancy indexing.
            unique, inverse = np.unique(indices, return_inverse=True)
            subset = matrix[:, unique.tolist()]
            if hasattr(subset, "toarray"):
                subset = subset.toarray()
            xy = np.asarray(subset)[:, inverse]
            labels = (config["x"], config["y"])
        else:
            key = _EMBEDDINGS[config["view"]]
            embedding = self.adata.obsm[key]
            if len(embedding.shape) != 2 or embedding.shape[1] < 2:
                raise ValueError(f"obsm[{key!r}] must have at least two coordinate columns")
            subset = (
                embedding.iloc[:, :2] if isinstance(embedding, pd.DataFrame) else embedding[:, :2]
            )
            if hasattr(subset, "toarray"):
                subset = subset.toarray()
            xy = np.asarray(subset)
            prefix = "UMAP" if config["view"] == "umap" else "Spatial"
            labels = (f"{prefix} 1", f"{prefix} 2")
        if not np.isrealobj(xy):
            raise ValueError("scatterplot coordinates must be real numbers")
        try:
            xy = np.asarray(xy, dtype=float)
        except (TypeError, ValueError) as exc:
            raise ValueError("scatterplot coordinates must be numeric") from exc
        if xy.shape != (self.adata.n_obs, 2) or not np.isfinite(xy).all():
            raise ValueError("scatterplot coordinates must be finite and match adata observations")
        return xy, *labels

    def _colors(self, color_by: str) -> tuple[list[str], list[str]]:
        if not color_by:
            return [_DEFAULT_COLOR] * self.adata.n_obs, self.adata.obs_names.tolist()
        series = self.adata.obs[color_by]
        labels = series.astype(object).where(series.notna(), "N.A.").map(str)
        categories = (
            list(map(str, series.cat.categories))
            if isinstance(series.dtype, pd.CategoricalDtype)
            else sorted(labels.unique())
        )
        palette = {
            label: _hsv_to_hex(i / max(len(categories), 1)) for i, label in enumerate(categories)
        }
        saved_colors = self.adata.uns.get(f"{color_by}_colors", [])
        for label, color in zip(categories, saved_colors, strict=False):
            with suppress(TypeError, ValueError):
                palette[label] = to_hex(color)
        return labels.map(palette).fillna("#9ca3af").tolist(), labels.tolist()

    def _prepare_payload(self, config: dict[str, str]) -> tuple[bytes, dict]:
        xy, x_label, y_label = self._coordinates(config)
        colors, labels = self._colors(config["color_by"])
        table = pa.table(
            {
                "cell_id": pa.array(self.adata.obs_names, type=pa.string()),
                "x": pa.array(xy[:, 0], type=pa.float64()),
                "y": pa.array(xy[:, 1], type=pa.float64()),
                "color": pa.array(colors, type=pa.string()),
                "label": pa.array(labels, type=pa.string()),
            }
        )
        buffer = io.BytesIO()
        pq.write_table(table, buffer, compression="zstd")
        return buffer.getvalue(), {
            "view": config["view"],
            "x_label": x_label,
            "y_label": y_label,
            "x_nonnegative": bool((xy[:, 0] >= 0).all()),
            "y_nonnegative": bool((xy[:, 1] >= 0).all()),
            "n_cells": self.adata.n_obs,
        }

    def _publish_payload(self, payload: tuple[bytes, dict]) -> None:
        data, meta = payload
        self._revision += 1
        with self.hold_sync():
            self.plot_meta = {**meta, "revision": self._revision}
            for axis in ("x", "y"):
                if not meta[f"{axis}_nonnegative"]:
                    setattr(self, f"{axis}_scale", "linear")
            self.points_parquet = data

    @traitlets.validate(*_CONFIG_TRAITS)
    def _validate_config_trait(self, proposal):
        if not self._ready or self._updating:
            return proposal["value"]
        config = {**self._configuration(), proposal["trait"].name: proposal["value"]}
        self._validate_configuration(config)
        # Reading/validating before accepting the trait keeps invalid coordinates
        # from leaving Python and the browser on different plot configurations.
        self._pending_payload = (config, self._prepare_payload(config))
        return proposal["value"]

    @traitlets.observe(*_CONFIG_TRAITS)
    def _on_configuration(self, _change):
        if not self._ready or self._updating or self._closed:
            return
        config = self._configuration()
        pending = self._pending_payload
        self._pending_payload = None
        payload = (
            pending[1]
            if pending is not None and pending[0] == config
            else self._prepare_payload(config)
        )
        self._publish_payload(payload)

    @traitlets.validate("x_scale", "y_scale")
    def _validate_scale(self, proposal):
        axis = proposal["trait"].name[0]
        if (
            self._ready
            and proposal["value"] == "log1p"
            and not self.plot_meta[f"{axis}_nonnegative"]
        ):
            raise ValueError(f"{axis}_scale='log1p' requires nonnegative coordinates")
        return proposal["value"]

    @traitlets.validate("selected_cells")
    def _validate_selection(self, proposal):
        ids = proposal["value"]
        unknown = set(ids) - self._cell_ids
        if unknown:
            raise ValueError(f"unknown cell IDs: {sorted(unknown)[:5]}")
        return list(dict.fromkeys(ids))

    @traitlets.observe("update_trigger")
    def _on_update_trigger(self, change):
        if not self._ready or self._closed:
            return
        event = change["new"]
        event_type = event.get("type", event.get("click_type", ""))
        value = event.get("value", event.get("click_value"))
        if isinstance(value, dict):
            if value.get("entity", "gene") != "gene":
                return
            value = value.get("name")
        if (
            event_type in ("row_label", "row-label")
            and isinstance(value, str)
            and value in self._gene_ids
        ):
            self.set_axes(y=value)

    def _set_configuration(self, **changes) -> Scatterplot:
        config = {**self._configuration(), **changes}
        self._validate_configuration(config)
        payload = self._prepare_payload(config)
        self._updating = True
        try:
            with self.hold_sync():
                for name, value in changes.items():
                    setattr(self, name, value)
                self._publish_payload(payload)
        finally:
            self._updating = False
        return self

    def set_view(self, view: str) -> Scatterplot:
        """Choose ``'genes'``, ``'umap'``, or ``'spatial'`` and keep selected IDs."""
        return self._set_configuration(view=view)

    def set_axes(
        self, x: str | None = None, y: str | None = None, *, layer: str | None = None
    ) -> Scatterplot:
        """Atomically choose gene axes and enter gene view.

        Omitted axes/layer retain their current value; pass ``layer=''`` to
        return from a layer to ``adata.X``.
        """
        changes = {"view": "genes"}
        changes.update(
            {
                key: value
                for key, value in {"x": x, "y": y, "layer": layer}.items()
                if value is not None
            }
        )
        return self._set_configuration(**changes)

    def set_scale(
        self, scale: str | None = None, *, x: str | None = None, y: str | None = None
    ) -> Scatterplot:
        """Set both scales with ``scale`` or individual axes with ``x``/``y``."""
        scales = {"x": x if x is not None else scale, "y": y if y is not None else scale}
        for axis, value in scales.items():
            if value is not None:
                if value not in ("linear", "log1p"):
                    raise ValueError("scale must be 'linear' or 'log1p'")
                if value == "log1p" and not self.plot_meta[f"{axis}_nonnegative"]:
                    raise ValueError(f"{axis}_scale='log1p' requires nonnegative coordinates")
        with self.hold_sync():
            for axis, value in scales.items():
                if value is not None:
                    setattr(self, f"{axis}_scale", value)
        return self

    def select_cells(self, cell_ids: Sequence[str]) -> Scatterplot:
        """Replace the selection with observation IDs (an empty list clears it)."""
        if isinstance(cell_ids, str):
            raise TypeError("cell_ids must be a sequence of observation IDs, not a string")
        self.selected_cells = list(cell_ids)
        return self

    def highlight_cells(self, cell_ids: Sequence[str]) -> Scatterplot:
        """Alias for :meth:`select_cells`, shared with Landscape."""
        return self.select_cells(cell_ids)

    def get_selection(self, *, as_adata: bool = False):
        """Return selected IDs, or an independent AnnData copy with ``as_adata=True``."""
        if as_adata:
            return self.adata[self.selected_cells].to_memory(copy=True)
        return list(self.selected_cells)

    def annotate_selection(self, column: str, value: Any) -> int:
        """Write a scalar annotation to selected rows of ``adata.obs`` in memory.

        Creates missing columns with unselected rows left missing, and adds new
        categorical values without changing existing annotations. Returns the
        number of selected cells. An empty selection performs no write.
        """
        if not isinstance(column, str) or not column:
            raise ValueError("column must be a nonempty string")
        if not pd.api.types.is_scalar(value):
            raise TypeError("annotation value must be a scalar")
        if not self.selected_cells:
            return 0
        if column in self.adata.obs:
            series = self.adata.obs[column].copy()
            if isinstance(series.dtype, pd.CategoricalDtype):
                if not pd.isna(value) and value not in series.cat.categories:
                    series = series.cat.add_categories([value])
            elif pd.api.types.is_numeric_dtype(series.dtype) and isinstance(value, str):
                series = series.astype(object)
        else:
            series = pd.Series(pd.NA, index=self.adata.obs_names, dtype=object)
        try:
            series.loc[self.selected_cells] = value
        except (TypeError, ValueError):
            series = series.astype(object)
            series.loc[self.selected_cells] = value
        self.adata.obs[column] = series
        self.obs_columns = [name for name in self.adata.obs.columns if isinstance(name, str)]
        if self.color_by == column:
            self._publish_payload(self._prepare_payload(self._configuration()))
        return len(self.selected_cells)

    def get_view_state(self) -> dict:
        """Return a compact JSON-ready plot/selection snapshot.

        ``get_state()`` remains ipywidgets' full state serialization API.
        """
        return {
            **self._configuration(),
            "x_scale": self.x_scale,
            "y_scale": self.y_scale,
            "selected_cells": self.get_selection(),
            "n_cells": self.adata.n_obs,
            "revision": self.plot_meta["revision"],
        }

    def describe(self) -> dict:
        """Describe available data, controls, and the explicit annotation API."""
        return {
            "component": self.component,
            "views": list(self.available_views),
            "genes": list(self.gene_names),
            "layers": list(self.layers),
            "obs_columns": list(self.obs_columns),
            "state": self.get_view_state(),
            "methods": [
                "set_view",
                "set_axes",
                "set_scale",
                "select_cells",
                "highlight_cells",
                "get_selection",
                "annotate_selection",
                "get_view_state",
                "request_raster",
                "close",
            ],
            "live_kernel_required": "Switching gene axes and coordinate views",
            "annotation_behavior": "annotate_selection explicitly writes adata.obs in memory",
        }

    def request_raster(self) -> int:
        """Request an asynchronous browser PNG; observe ``raster_png`` for the result."""
        self.raster_request += 1
        return self.raster_request

    def close(self):
        """Finalize the browser renderer and stop reacting to linked updates."""
        self._closed = True
        self._pending_payload = None
        super().close()
