# Viz Module API Reference

For a conceptual overview of what each widget shows and how to use it, see
the [Visualizations](../../visualizations/index.md) section.

## Widget Classes

The `Clustergram` widget accepts a `parquet_data` argument for efficient
initialization. Use [`Matrix.export_viz_parquet`](../clust/api.md#celldega.clust.matrix.Matrix.export_viz_parquet)
to generate this data from a clustered matrix. Passing a JSON ``network``
object is deprecated; pass ``matrix`` or ``parquet_data`` instead.

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
   browser against the dataset's LandscapeFiles, so it needs only a `base_url`
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

