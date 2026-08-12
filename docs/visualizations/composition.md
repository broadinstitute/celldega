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

dset = dega.dataset.DatasetCollection(
    adata, dataset_col="sample_id", obs_columns=["condition"]
)
dset.calc_population(adata, category="cell_type")

dega.viz.Composition(
    dset, category="cell_type", group_attrs=["condition"]
)
```

`Composition` accepts a Celldega collection (`DatasetCollection` /
`SetCollection`), a `MuData`, an `AnnData`, or a plain `DataFrame` of
group-by-population values — typically the output of `calc_population`. See
[Clustergram](clustergram.md) for the shared heatmap controls, and the
[Viz Module API reference](../python/viz/api.md) for the full set of
constructor arguments.

!!! note
    Screenshots and an example video are coming soon.
