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
   browser against the dataset's LandscapeFiles, needing only a `base_url`
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

`Yearbook` can also be linked to a `Landscape` view — see the
[Landscape-Yearbook gallery example](../gallery/gallery_landscape_yearbook.md).
For the full query/selection algebra and constructor arguments, see the
[Viz Module API reference](../python/viz/api.md).

!!! note
    Screenshots and an example video are coming soon.
