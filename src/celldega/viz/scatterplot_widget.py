"""AnnData-backed, linked two-dimensional scatterplots."""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import suppress
import io
import re
from typing import Any

from anndata import AnnData
from matplotlib import colormaps
from matplotlib.colors import to_hex
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import traitlets

from ._widget_lifecycle import CelldegaWidget
from .widget import _WIDGET_ESM, _hsv_to_hex


__all__ = ["Scatter"]

_CONFIG_TRAITS = ("view", "x", "y", "layer", "color_by")
_DEFAULT_COLOR = "#4f80ff"
_EMBEDDINGS = {"umap": "X_umap", "spatial": "spatial"}


class Scatter(CelldegaWidget):
    """Plot cells from an AnnData in UMAP, spatial, or gene-expression space.

    ``view`` defaults to UMAP, then spatial, then genes, according to available
    data. ``x`` and ``y`` name genes; ``layer=None`` uses ``adata.X``. Only the
    active expression columns are read, including for sparse and backed data.
    ``color_by`` optionally names an observation column. Real numeric columns
    use a continuous Viridis scale; categorical, text, and boolean columns use
    category colors. Missing/nonfinite numeric values are gray.

    Gene/view changes require a live Python kernel. Linear/log1p transitions
    happen in the browser; log1p requires nonnegative coordinates. Changing to
    a negative-valued axis resets that axis to linear. Selection always uses
    observation names and survives changing axes. Selecting cells does not
    change AnnData: :meth:`annotate_selection` and the browser's explicit label
    action write to ``adata.obs`` in memory. Labeling also requires a live
    kernel, and callers explicitly save their data if persistence is wanted.

    As with other Celldega widgets, ``name=`` replaces and closes an earlier
    widget with the same name. Call ``close()`` when a widget is no longer used
    to release its browser/WebGL resources.
    """

    _esm = _WIDGET_ESM
    component = traitlets.Unicode("Scatter").tag(sync=True)
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
    selected_categories = traitlets.List(traitlets.Unicode(), default_value=[]).tag(sync=True)
    click_info = traitlets.Dict(default_value={}).tag(sync=True)
    update_trigger = traitlets.Dict(default_value={}).tag(sync=True)
    annotation_request = traitlets.Dict(default_value={}).tag(sync=True)
    annotation_result = traitlets.Dict(default_value={}).tag(sync=True)
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
        self._annotation_results = {}
        self._syncing_categories = False
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
        if self.selected_categories:
            self._on_selected_categories({"new": self.selected_categories})

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

    @staticmethod
    def _category_labels(series: pd.Series) -> list[str]:
        if isinstance(series.dtype, pd.CategoricalDtype):
            return list(map(str, series.cat.categories))
        return sorted(series.dropna().map(str).unique())

    def _category_palette(self, series: pd.Series, saved_colors) -> dict[str, str]:
        categories = self._category_labels(series)
        palette = {
            label: _hsv_to_hex(i / max(len(categories), 1)) for i, label in enumerate(categories)
        }
        for label, color in zip(categories, saved_colors, strict=False):
            with suppress(TypeError, ValueError):
                palette[label] = to_hex(color)
        return palette

    @staticmethod
    def _is_numeric_color(series: pd.Series) -> bool:
        return (
            pd.api.types.is_numeric_dtype(series.dtype)
            and not pd.api.types.is_bool_dtype(series.dtype)
            and not pd.api.types.is_complex_dtype(series.dtype)
        )

    def _observation_labels(self, series: pd.Series) -> tuple[pd.Series, str]:
        missing_label = "N.A."
        categories = set(self._category_labels(series))
        while missing_label in categories:
            missing_label += " (missing)"
        return series.astype(object).where(series.notna(), missing_label).map(str), missing_label

    def _colors(
        self, color_by: str, *, series: pd.Series | None = None, saved_colors=None
    ) -> tuple[list[str], list[str], dict]:
        meta = {
            "color_by": color_by,
            "color_type": "uniform",
            "color_min": None,
            "color_max": None,
            "color_categories": [],
            "color_scale": [],
        }
        if not color_by:
            return [_DEFAULT_COLOR] * self.adata.n_obs, self.adata.obs_names.tolist(), meta
        if series is None:
            series = self.adata.obs[color_by]
        if self._is_numeric_color(series):
            labels = series.astype(object).where(series.notna(), "N.A.").map(str)
            values = series.to_numpy(dtype=float, na_value=np.nan)
            finite = np.isfinite(values)
            colors = np.full(len(values), "#9ca3af", dtype="<U7")
            meta["color_type"] = "numeric"
            cmap = colormaps["viridis"]
            meta["color_scale"] = [to_hex(cmap(value)) for value in (0.0, 0.25, 0.5, 0.75, 1.0)]
            if finite.any():
                low, high = float(values[finite].min()), float(values[finite].max())
                meta.update(color_min=low, color_max=high)
                if low == high:
                    normalized = np.full(finite.sum(), 0.5)
                else:
                    # Divide first to avoid overflow for extreme finite values.
                    scale = max(abs(low), abs(high), 1)
                    normalized = (values[finite] / scale - low / scale) / (
                        high / scale - low / scale
                    )
                palette = np.array([to_hex(cmap(i / 255)) for i in range(256)])
                colors[finite] = palette[np.rint(normalized * 255).astype(int).clip(0, 255)]
            return colors.tolist(), labels.tolist(), meta
        labels, missing_label = self._observation_labels(series)
        if saved_colors is None:
            saved_colors = self.adata.uns.get(f"{color_by}_colors", [])
        palette = self._category_palette(series, saved_colors)
        if series.isna().any():
            palette[missing_label] = "#9ca3af"
        meta.update(
            color_type="categorical",
            color_categories=[{"name": name, "color": color} for name, color in palette.items()],
        )
        return labels.map(palette).fillna("#9ca3af").tolist(), labels.tolist(), meta

    def _prepare_payload(
        self, config: dict[str, str], *, color_series: pd.Series | None = None, color_palette=None
    ) -> tuple[bytes, dict]:
        xy, x_label, y_label = self._coordinates(config)
        colors, labels, color_meta = self._colors(
            config["color_by"], series=color_series, saved_colors=color_palette
        )
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
            **color_meta,
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
            if self.plot_meta and self.plot_meta.get("color_by") != meta["color_by"]:
                self._clear_category_selection()
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

    @traitlets.validate("selected_categories")
    def _validate_categories(self, proposal):
        categories = list(dict.fromkeys(proposal["value"]))
        if not categories:
            return categories
        if not self.color_by or self._is_numeric_color(self.adata.obs[self.color_by]):
            raise ValueError("category selection requires a categorical color_by column")
        series = self.adata.obs[self.color_by]
        _, missing_label = self._observation_labels(series)
        valid = set(self._category_labels(series))
        if series.isna().any():
            valid.add(missing_label)
        unknown = set(categories) - valid
        if unknown:
            raise ValueError(f"unknown categories: {sorted(unknown)[:5]}")
        return categories

    def _category_cell_ids(self, categories: list[str]) -> list[str]:
        if not categories or not self.color_by:
            return []
        labels, _ = self._observation_labels(self.adata.obs[self.color_by])
        return self.adata.obs_names[labels.isin(categories)].tolist()

    def _clear_category_selection(self) -> None:
        self._syncing_categories = True
        try:
            self.selected_categories = []
        finally:
            self._syncing_categories = False

    @traitlets.observe("selected_categories")
    def _on_selected_categories(self, change):
        if not self._ready or self._closed or self._syncing_categories:
            return
        self._syncing_categories = True
        try:
            self.selected_cells = self._category_cell_ids(change["new"])
        finally:
            self._syncing_categories = False

    @traitlets.observe("selected_cells")
    def _on_selected_cells(self, _change):
        if (
            not self._ready
            or self._closed
            or self._syncing_categories
            or not self.selected_categories
        ):
            return
        if set(self.selected_cells) != set(self._category_cell_ids(self.selected_categories)):
            self._clear_category_selection()

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

    def _set_configuration(self, **changes) -> Scatter:
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

    def set_view(self, view: str) -> Scatter:
        """Choose ``'genes'``, ``'umap'``, or ``'spatial'`` and keep selected IDs."""
        return self._set_configuration(view=view)

    def set_axes(
        self, x: str | None = None, y: str | None = None, *, layer: str | None = None
    ) -> Scatter:
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
    ) -> Scatter:
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

    def select_cells(self, cell_ids: Sequence[str]) -> Scatter:
        """Replace the selection with observation IDs (an empty list clears it)."""
        if isinstance(cell_ids, str):
            raise TypeError("cell_ids must be a sequence of observation IDs, not a string")
        self.selected_cells = list(cell_ids)
        return self

    def highlight_cells(self, cell_ids: Sequence[str]) -> Scatter:
        """Alias for :meth:`select_cells`, shared with Landscape."""
        return self.select_cells(cell_ids)

    def select_categories(self, categories: Sequence[str], *, additive: bool = False) -> Scatter:
        """Select the union of categories in ``color_by`` using their display names.

        ``additive=True`` adds to the current categories. Passing an empty list
        clears category/cell selection. Explicit cell selections and changing
        the color column clear category selection while retaining selected IDs.
        """
        if isinstance(categories, str):
            raise TypeError("categories must be a sequence of names, not a string")
        self.selected_categories = (self.selected_categories if additive else []) + list(categories)
        if not self.selected_categories:
            self.selected_cells = []
        return self

    def get_selection(self, *, as_adata: bool = False):
        """Return selected IDs, or an independent AnnData copy with ``as_adata=True``."""
        if as_adata:
            return self.adata[self.selected_cells].to_memory(copy=True)
        return list(self.selected_cells)

    @traitlets.observe("annotation_request")
    def _on_annotation_request(self, change):
        if not self._ready or self._closed:
            return
        request = change["new"]
        if not request:
            return
        request_id = request.get("request_id")
        response_id = request_id if isinstance(request_id, str) else ""
        if response_id and response_id in self._annotation_results:
            self.annotation_result = dict(self._annotation_results[response_id])
            return
        try:
            if not isinstance(request_id, str) or not request_id.strip():
                raise ValueError("request_id must be a nonempty string")
            value = request.get("value")
            if not isinstance(value, str) or not value.strip():
                raise ValueError("annotation value must be a nonempty string")
            cell_ids = request.get("cell_ids")
            if not isinstance(cell_ids, list) or not cell_ids:
                raise ValueError("cell_ids must be a nonempty list of observation IDs")
            count = self._annotate_cells(
                cell_ids,
                request.get("column"),
                value,
                color=request.get("color"),
                activate=True,
            )
            result = {
                "request_id": request_id,
                "ok": True,
                "count": count,
                "column": request["column"],
                "value": value,
            }
        except Exception as exc:  # Invalid browser requests must not escape the comm callback.
            result = {"request_id": response_id, "ok": False, "error": str(exc)}
        if response_id:
            self._annotation_results[response_id] = dict(result)
        self.annotation_result = result

    def annotate_selection(self, column: str, value: Any, *, color: str | None = None) -> int:
        """Write a scalar annotation to selected rows of ``adata.obs`` in memory.

        Creates missing columns with unselected rows left missing, and adds new
        categorical values without changing existing annotations. Returns the
        number of selected cells. An empty selection performs no write.

        With ``color='#rrggbb'``, the column becomes categorical and the label's
        color is stored in ``adata.uns[f'{column}_colors']`` in category order.
        Browser annotation requests use a captured list of IDs, so subsequent
        selection changes cannot redirect an annotation awaiting confirmation.
        """
        return self._annotate_cells(self.get_selection(), column, value, color=color)

    def _annotate_cells(
        self,
        cell_ids: list[str],
        column: str,
        value: Any,
        *,
        color: str | None = None,
        activate: bool = False,
    ) -> int:
        if not isinstance(column, str) or not column.strip():
            raise ValueError("column must be a nonempty string")
        if not pd.api.types.is_scalar(value):
            raise TypeError("annotation value must be a scalar")
        if not all(isinstance(cell_id, str) for cell_id in cell_ids):
            raise ValueError("cell_ids must contain only string observation IDs")
        if len(set(cell_ids)) != len(cell_ids):
            raise ValueError("cell_ids must be unique")
        unknown = set(cell_ids) - self._cell_ids
        if unknown:
            raise ValueError(f"unknown cell IDs: {sorted(unknown)[:5]}")
        if color is not None:
            if not isinstance(color, str) or not re.fullmatch(
                r"#(?:[\da-fA-F]{3}|[\da-fA-F]{6})", color
            ):
                raise ValueError("color must be a hex color such as '#4f80ff'")
            if pd.isna(value):
                raise ValueError("a color requires a nonmissing annotation value")
            color = to_hex(color)
        if not cell_ids:
            return 0
        old_series = self.adata.obs.get(column)
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
            series.loc[cell_ids] = value
        except (TypeError, ValueError):
            series = series.astype(object)
            series.loc[cell_ids] = value

        palette_key = f"{column}_colors"
        palette = None
        if color is not None or palette_key in self.adata.uns:
            # An explicit categorical order keeps the AnnData palette aligned
            # after new labels are introduced or a fresh widget is constructed.
            series = series.astype("category")
            previous_palette = (
                self._category_palette(old_series, self.adata.uns.get(palette_key, []))
                if old_series is not None
                else {}
            )
            updated_palette = self._category_palette(series, [])
            updated_palette.update(previous_palette)
            if color is not None:
                updated_palette[str(value)] = color
            palette = [updated_palette[label] for label in self._category_labels(series)]

        config = self._configuration()
        if activate:
            config["color_by"] = column
        # Build the entire outgoing plot before mutating AnnData, including
        # coordinate validation, so a rejected request leaves annotations intact.
        payload = (
            self._prepare_payload(config, color_series=series, color_palette=palette)
            if config["color_by"] == column
            else None
        )
        self.adata.obs[column] = series
        if palette is not None:
            self.adata.uns[palette_key] = palette
        self._updating = True
        try:
            with self.hold_sync():
                self._clear_category_selection()
                self.obs_columns = [
                    name for name in self.adata.obs.columns if isinstance(name, str)
                ]
                if activate:
                    self.color_by = column
                if payload is not None:
                    self._publish_payload(payload)
        finally:
            self._updating = False
        return len(cell_ids)

    def get_view_state(self) -> dict:
        """Return a compact JSON-ready plot/selection snapshot.

        ``get_state()`` remains ipywidgets' full state serialization API.
        """
        return {
            **self._configuration(),
            "x_scale": self.x_scale,
            "y_scale": self.y_scale,
            "selected_cells": self.get_selection(),
            "selected_categories": list(self.selected_categories),
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
                "select_categories",
                "highlight_cells",
                "get_selection",
                "annotate_selection",
                "get_view_state",
                "request_raster",
                "close",
            ],
            "live_kernel_required": "Switching gene axes and coordinate views; writing cell labels",
            "annotation_behavior": "annotate_selection and explicit browser label requests write adata.obs in memory",
            "annotation_request_fields": ["request_id", "column", "value", "cell_ids", "color"],
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
