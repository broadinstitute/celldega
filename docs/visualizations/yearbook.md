# Yearbook

`Yearbook` renders a grid of cell "portraits" — small, zoomed-in spatial
crops centered on individual cells, all sharing synchronized zoom/pan state
while each shows a different region of the tissue. It's useful for
inspecting many individual cells side by side (e.g. the top cells for a gene,
or a random sample from a cluster).

## What it shows

- A **grid** of portraits (configurable `rows`/`cols`), each centered on one
  cell, with the same CELL/TRX controls and gene search as
  [Landscape](landscape.md).
- **Pagination** controls to page through a larger cell selection than fits
  on one page.
- A small **review checkbox** at the bottom right of each portrait. Checked
  portraits have a blue border, and their cell IDs remain selected across pages.
- A **query box** for selecting cells by cluster and/or gene directly in the
  browser (see `front_end_query` below), independent of pagination.

## Choosing which cells to show

There are three ways to choose which cells `Yearbook` displays, in increasing
order of power:

1. **An explicit id list** — `cells=["cell_1", "cell_2", ...]`.
2. **A back-end selection** — `selection=...`, accepting a
   [`celldega.select.Selection`](../python/select/api.md), a JSON-ready
   selection dict, or a plain id list. This is the recommended way to drive
   the grid from a Python `AnnData` object.
3. **A stateless front-end query** — `front_end_query=...`, evaluated in the
   browser against the dataset's DegaFiles, needing only a `base_url`
   and no Python `AnnData`.

## Usage

```python
import celldega as dega

yb = dega.viz.Yearbook(
    base_url="https://your-landscape-files-url",
    front_end_query={"gene": "BRCA1", "max_cells": 50},
    rows=2,
    cols=2,
)
yb
```

`Yearbook` can also be linked to a `Clustergram` via
[`dega.viz.spatial_clustergram`](../python/viz/api.md), exactly like
`Landscape`. For the full query/selection algebra and constructor arguments,
see the [Viz Module API reference](../python/viz/api.md).

## Mark cells for review

Click a portrait's checkbox to select or deselect its cell. The control has a
transparent background and becomes clearer on hover or keyboard focus. Checked
portraits have a blue border. Selections persist when changing pages or replacing
the displayed cells with another query.

With a live notebook kernel, read the selected IDs from `selected_cells` or
`get_selected_cells()`:

```python
reviewed_ids = yb.get_selected_cells()  # same IDs as yb.selected_cells
adata.obs["yearbook_review"] = adata.obs_names.isin(reviewed_ids)

# Or get a copy of the marked cells for downstream work.
reviewed = yb.get_selected_cells(adata)

# Clear every review checkbox, including those on other pages.
yb.selected_cells = []
```

Use `cells=` or `selection=` to choose the portraits to display, and
`selected_cells=` to initialize the review checkboxes. The selected list stores
original cell IDs independently of the current page and query.

## Example

The [Atera kidney tutorial](../examples/tutorial_notebooks/Atera_Kidney_Landscape-Clustergram.ipynb)
includes a Yearbook for inspecting individual cells alongside a Landscape.

The [Atera kidney Yearbook review](../examples/brief_notebooks/Atera_Kidney_Yearbook_Review.ipynb)
brief example uses `dega.select` to build a candidate queue, inspect portraits
across pages, and retrieve checked cell IDs for follow-up.
