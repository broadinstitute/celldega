# Scatter

`Scatter` plots AnnData observations in two dimensions. Switch between
UMAP (`obsm['X_umap']`), spatial coordinates (`obsm['spatial']`), and a pair of
genes from `X` or a named layer. It needs no LandscapeFiles or preprocessing.
The compact control panel follows the other Celldega widgets.

## Usage

```python
import celldega as dega

scatter = dega.viz.Scatter(
    adata,
    view="genes",
    x="CD3D",
    y="MS4A1",
    color_by="cell_type",  # optional adata.obs column
    name="cell-scatter",  # rerunning replaces the previous widget
)
scatter
```

The X and Y gene inputs offer searchable choices from `adata.var_names`.
The view selector offers the embeddings present in AnnData. Omitting `view`
selects UMAP first, then spatial, then genes. Embeddings use their first two
dimensions and preserve their aspect ratio. Observation and gene names must
be unique, and active coordinates must be finite real numbers.

Choose **linear** or **log1p** for each axis to animate between scales.
`log1p` means the natural logarithm of `1 + value` and is available only for
nonnegative coordinates. Switching to an axis with negative coordinates
automatically restores linear scaling. Scaling is a display transformation;
it never modifies expression values. Use an unlogged layer when appropriate
to avoid applying another logarithm to already transformed expression.

```python
scatter.set_axes("CD8A", "GZMB", layer="counts")
scatter.set_scale("log1p")
scatter.set_scale(x="linear", y="log1p")
scatter.set_view("umap")
```

Only the active pair of gene columns is materialized and sent as compressed
Parquet, including when `X` is sparse or backed by a file. Changing views,
genes, layers, or coloring needs a live Python kernel; saved widget output
cannot load new axes by itself. Scales and selections work on the active
browser payload.

## Cell attributes and local populations

The **CELL** dropdown selects an `adata.obs` attribute. Categorical attributes
use their saved AnnData palette when available; the bars report counts among
cells inside the current viewport and update as you pan or zoom. Click a bar
to select that category, or Shift-click to add or remove categories. The
selection contains every matching cell, including cells outside the viewport.
Drawing a gate replaces the category selection with the gated cell IDs.

Numerical attributes use a continuous Viridis gradient with a global finite
minimum and maximum so colors remain comparable when zooming. Missing or
infinite values are gray; a constant numerical attribute uses the middle
color. Boolean and categorical-typed columns are treated as categories.

```python
scatter.color_by = "leiden"
scatter.select_categories(["0", "3"])
scatter.select_categories(["5"], additive=True)
scatter.color_by = "total_counts"
```

## Selection and annotations

Click a cell to select it; Shift-click adds or removes a cell. **GATE** lets
you drag a rectangular selection. **SKTCH** uses the same polygon drawing
mode as Landscape: click vertices, then click the first vertex to finish.
Press Escape to cancel a sketch. **CLEAR** clears the cell selection.
Selected cell IDs survive view, gene, and scale changes. Pan and zoom in the
normal browse mode.

With cells selected, click **LABEL** to choose an `adata.obs` column, a label,
and a color. **Apply** writes the label to those cells in memory and colors
the Scatter by that column; **Cancel** makes no annotation changes. The
dialog uses the same controls as the Landscape neighborhood editor. The
selection is captured when the dialog opens, so later selection changes do
not redirect a pending annotation to other cells.

```python
scatter.selected_cells              # observation names
scatter.select_cells(["cell-1", "cell-2"])
subset = scatter.get_selection(as_adata=True)

# Explicitly write the selected cells' annotation to adata.obs, in memory.
scatter.annotate_selection("manual_gate", "CD8 candidate")
scatter.color_by = "manual_gate"
```

Selection alone never writes annotations. `annotate_selection` preserves
unselected annotations, extends categorical columns as needed, and returns
the number of annotated cells. Save AnnData yourself to persist annotations.
The polygon is a selection gesture, not a spatial neighborhood stored in
AnnData. Labels belong to cells and remain valid when coordinates change.
Annotation requires a live kernel. Cell-cell communication overlays remain
future work.

## Link widgets and inspect state

Use the same `selected_cells` trait as Landscape and CellCloud. Linked widgets
must use matching observation IDs.

```python
from ipywidgets import jsdlink

selection_link = jsdlink(
    (scatter, "selected_cells"),
    (landscape, "selected_cells"),
)

# Clustergram gene clicks choose the Scatter Y axis.
gene_link = jsdlink((clustergram, "click_info"), (scatter, "update_trigger"))

scatter.describe()        # available views, genes, layers, and methods
scatter.get_view_state()  # compact configuration and selection snapshot
scatter.highlight_cells(["cell-1"])  # shared Landscape-style API
```

`get_state()` retains ipywidgets' standard serialization behavior, including
binary widget data. Use `get_view_state()` for lightweight programmatic
inspection. `request_raster()` follows the raster API in PR #312: it returns
an incrementing request ID, and the browser asynchronously fills `raster_png`
with a base64 PNG and `raster_view_state` with capture metadata.

```python
request_id = scatter.request_raster()
# Observe raster_png, or inspect it in a later notebook cell after capture.
```

Each Scatter has its own observable state and WebGL context. Reusing
`name=` closes the prior Scatter with that name; distinct names (or no
name) allow multiple widgets. Release widgets and links when finished:

```python
selection_link.unlink()
gene_link.unlink()
scatter.close()
```

For the full API, see the [Viz Module reference](../python/viz/api.md).
For a complete three-panel example, see the
[linked pancreas notebook](../examples/brief_notebooks/Scatter_Pancreas_Linked.ipynb).
