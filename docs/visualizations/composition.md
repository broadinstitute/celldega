# Composition

`Composition` is a `Clustergram` variant for comparing category
composition across groups — e.g. cell-type proportions across samples or
conditions — rather than a general-purpose heatmap. It shows the count or
relative proportion of categories within each group, and compares those
compositions across groups.

## What it shows

- Each **group** (e.g. dataset or sample) as a **stacked bar**, whose
  segments are the categories (e.g. cell types) that make it up.
- The same column-attribute tracks and reorder buttons (`ini` / `sum` /
  `clust`) as `Clustergram`.
- A **PROP / COUNTS** toggle in the control panel to switch between relative
  proportions and raw counts.

## Usage

```python
import celldega as dega

# Cell types across samples, straight from a cell-level AnnData
dega.viz.Composition(
    adata, groupby="sample_id", category="cell_type", group_attrs=["condition"]
)
```

With `groupby`, the cells are cross-tabulated into groups x categories and
colored from `adata.uns[f"{category}_colors"]`. `Composition` also accepts a
precomputed group-by-population matrix: an `AnnData` (groups as obs), a
`MuData` modality, or a plain `DataFrame` (e.g. from
[`dega.nbhd.calc_nbhd_by_pop`](../python/nbhd/api.md)). See
[Clustergram](clustergram.md) for the shared heatmap controls, and the
[Viz Module API reference](../python/viz/api.md) for the full set of
constructor arguments.

!!! note
    Screenshots and an example video are coming soon.
