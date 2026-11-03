# Viz Module API Reference

For a conceptual overview of what each widget shows and how to use it, see
the [Visualizations](../../visualizations/index.md) section.
Try the [Chromium PBMC notebook](../../examples/tutorial_notebooks/Scanpy_Chromium.ipynb)
for low dimensional embedding landscapes, or the
[Visium HD CRC notebook](../../examples/tutorial_notebooks/Visium_HD_Human_CRC_Landscape-Clustergram-Enrich.ipynb)
for linked spatial, expression, and enrichment views.

## Landscape data sources and controls

`Landscape` supports spatial DegaFiles and single-cell AnnData Zarr for
**low dimensional embedding landscapes** (UMAP/XY). Choose one expression
source:

```python
import celldega as dega

# Spatial image, centroid, boundary, transcript, and expression files.
spatial = dega.viz.Landscape(
    base_url="https://your-data-host/DegaFiles",
    adata=adata,
    cluster_attr="cell_type",
)

# Cell-level AnnData Zarr with a CSC expression layer.
single_cell = dega.viz.Landscape(
    zarr_url="cells.zarr",
    zarr_layer="counts_csc",
    cluster_attr="cell_type",
    nbhd_edit=True,
)
```

Local Zarr paths must be beneath the working directory; the widget starts a
local HTTP server. HTTP(S) URLs are passed directly to the browser.
Optional `adata` supplies cell metadata, cluster colors, and UMAP positions
in preference to the source's metadata. It does not supply expression to the
browser. Match its `obs_names` to the source cell IDs.

| Argument / trait | Purpose |
| --- | --- |
| `base_url` / `base_urls` | DegaFiles URL or multiple DegaFiles datasets |
| `zarr_url` / `zarr_layer` | Single-cell AnnData Zarr and its CSC expression layer; defaults to Chromium technology |
| `adata` | Optional AnnData metadata, palette, and `obsm["X_umap"]` |
| `cluster_attr` / `cell_attr` | Category used for cluster colors (default `"leiden"`) and cell attributes |
| `landscape_state` | `"spatial"`, `"umap"`, or `"xy"`; the available views depend on the dataset |
| `xy_genes` / `xy_scale` | X/Y genes and `"linear"` or `"log1p"` scaling |
| `adata_sig` / `gene_signature_url` | In-memory cell-type means or a separate signature AnnData Zarr for viewport estimates |
| `nbhd` / `nbhd_edit` | Supplied neighborhoods and whether editing is enabled |
| `gates` / `selected_cells` | Named polygons with coordinate-space metadata / current selected cell IDs |
| `min_zoom` / `max_zoom` | Optional zoom limits |
| `max_tiles_to_view` / `intermediate_zoom_limit` | Automatic and on-demand spatial transcript/boundary loading thresholds |

### XY and neighborhood selections

```python
single_cell.set_xy("CD3D", "MS4A1", scale="log1p")
single_cell.landscape_state = "umap"  # requires obsm["X_umap"]

# After selecting clusters or drawing a neighborhood in the browser:
cell_ids = single_cell.get_selected_cells()
selected = single_cell.get_selected_cells(adata)  # copied AnnData subset
polygons = single_cell.nbhd_polygons
single_cell.save_nbhds("neighborhoods.geojson")
single_cell.load_nbhds("neighborhoods.geojson")
```

`select_nbhd(name)` restores a saved neighborhood's view/axes and selects its
cells. `save_gates`, `load_gates`, and `select_gate` are equivalent names.
Spatial polygons use native tissue coordinates; embedding polygons retain
their coordinate-space metadata. Filter `polygons["space"]` before computing
physical tissue areas or distances.

UMAP/XY viewport cell-type counts are exact. Gene bars estimate expression
from matching cell-type signatures; no per-cell expression is fetched on
pan/zoom. TRX indicates the summary mode in these views. Selected-gene
coloring and XY coordinates read actual expression. See the
[Landscape guide](../../visualizations/landscape.md) for signature preparation,
selection behavior, and adding aligned H&E to DegaFiles, and
[File Formats](../../getting-started/file_formats.md) for storage schemas.

Source: [Python widget and methods](https://github.com/broadinstitute/celldega/blob/main/src/celldega/viz/widget.py),
[browser entry points](https://github.com/broadinstitute/celldega/blob/main/js/celldega.js),
and [AnnData Zarr reader](https://github.com/broadinstitute/celldega/blob/main/js/read_zarr/anndata_zarr.js).

## Widget Classes

The `Clustergram` widget accepts a `parquet_data` argument for efficient
initialization. Use [`Matrix.export_viz_parquet`](../clust/api.md#celldega.clust.Matrix.export_viz_parquet)
to generate this data from a clustered matrix. Passing a JSON ``network``
object is deprecated; pass ``matrix`` or ``parquet_data`` instead.

## Reusing widgets in notebooks

When rerunning a notebook cell, give a widget a `name` if the new instance
should replace the previous one of that kind:

```python
landscape = dega.viz.Landscape(
    base_url="https://your-data-host/DegaFiles",
    name="tissue_overview",
)
```

Creating another Landscape named `"tissue_overview"` closes the previous
one. Use different names to keep several Landscapes open. `registry_key` is
an alternative to `name`; if both are supplied, use the same value.

Without an explicit key, most widgets coexist. Clustergram uses its Matrix
name by default, and Enrich uses `"default"`, so give those widgets distinct
names when displaying several instances. Call `widget.close()` to release
a widget when it is no longer needed.

Source: [widget lifecycle](https://github.com/broadinstitute/celldega/blob/main/src/celldega/viz/_widget_lifecycle.py).

## Yearbook Selection

A `Yearbook` renders a grid of cell "portraits". There are three ways to choose
which cells it shows, in increasing order of power:

1. **An explicit id list** — `cells=["cell_1", "cell_2", ...]`. The simplest
   path: you already know the cells you want.
2. **A back-end selection** — `selection=...`. Accepts a
   [`celldega.select.Selection`](../select/api.md), a JSON-ready selection dict,
   or a plain id list. This is the recommended way to drive the grid from a
   Python `AnnData` object, because it carries the query, sampler, scores, and
   provenance with the cells. See the
   [select module docs](../select/api.md) for the full query/sampling algebra.
3. **A stateless front-end query** — `front_end_query=...`. Evaluated in the
   browser against the dataset's DegaFiles, so it needs only a `base_url`
   and **no Python `AnnData`**.

Passing both `cells=` and `selection=` is rejected. `front_end_query=` is
independent of those two — when set, the browser computes the cell list itself.

### Front-End Query

`front_end_query` is a small dict evaluated entirely in the browser. It is a
deliberately narrow counterpart to the Python `select` module — it supports a
single cluster filter and/or a single-gene ranking:

| Query | Behavior |
| --- | --- |
| `{"cluster": {"attr": "leiden", "value": "8"}}` | Random cells from cluster `8` (capped at `num_rows * num_cols * 10` by default). |
| `{"gene": "BRCA1"}` | All cells ranked by `BRCA1` expression, highest first. |
| `{"cluster": {"attr": "leiden", "value": "8"}, "gene": "BRCA1"}` | Cells in cluster `8`, ranked by `BRCA1` expression. |
| `{"gene": "BRCA1", "max_cells": 50}` | As above, capped at 50 cells. |

```python
yb = dega.viz.Yearbook(
    base_url="https://path-to-dataset",
    front_end_query={"gene": "BRCA1", "max_cells": 50},
    rows=2,
    cols=2,
)
```

!!! note
    The former `query=` argument was renamed to `front_end_query=` to
    distinguish this stateless browser query from the Python-side
    `celldega.select` query module. Passing `query=` still works but emits a
    `DeprecationWarning`.

::: celldega.viz

