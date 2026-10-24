# Review: Celldega `reorg_modules` — methods on plain scverse objects; data structures move to dega-collection

**Branch:** `reorg_modules` (on top of `2c982e87`)
**Commits:** `4446da47` (code + tests), `41294eae` (docs + CHANGELOG), `bfdeb531` (notebook code cells)
**Companion package:** `dega-collection` (separate review document)
**Target release:** 0.28.0 (breaking; the version bump is left to the release)

## 1. Summary

Celldega now works directly on standard scverse data structures (`AnnData`,
`MuData`) and `GeoDataFrame` neighborhoods, the way Scanpy works on `AnnData`.
The higher-level data structures (`CelldegaCollection`, `DatasetCollection`,
`NeighborhoodCollection`, `SetCollection`), the `select` query layer, and the
serial-slice `align` module move to a new package, `dega-collection`, the way
AnnData lives apart from Scanpy. Celldega keeps the methods; `dega-collection`
keeps the data structures and the tools that query and align them.

Celldega never imports `dega-collection`. Its functions and widgets accept
`dega-collection` objects by duck typing (`to_geodataframe()`, `.mod`/`.obs`,
`to_json()`), so existing collection-based workflows keep working once
`dega-collection` is installed.

Also in this branch: the `Landmark` widget is removed, and the per-gene alpha
shapes are removed (too slow to compute; per-gene coloring in a
NeighborhoodCloud now comes only from the per-gene cell scatter).

## 2. What changed

### 2.1 `celldega.nbhd`: public functions on GeoDataFrame + AnnData/MuData

The neighborhood calculations are public functions again under their original
names and argument order (they were made private `_calc_nbhd_*` kernels behind
`NeighborhoodCollection` methods in 0.16):

| Function | Inputs → output |
| --- | --- |
| `calc_nbhd_by_gene(gdf_nbhd, by="cell", adata, ...)` | GeoDataFrame + AnnData/MuData → AnnData nbhd × gene (MuData in → one modality per input modality; `modality=` picks one) |
| `calc_nbhd_by_pop(adata, gdf_nbhd, category, ...)` | → AnnData nbhd × category |
| `calc_nbhd_overlap(gdf_nbhd, metric)` / `calc_nbhd_bordering(gdf_nbhd, metric)` | → square AnnData nbhd × nbhd |
| `calc_nbhd_transcript_assignment(gdf_nbhd, gdf_trx)` + `read_transcripts(data_dir)` | → DataFrame per neighborhood |

- Neighborhood inputs: a `GeoDataFrame` with a `name` column (falling back to
  `neighborhood_id` / `nbhd_id`), or any object exposing `to_geodataframe()`
  (or a `geometry`/`gdf` GeoDataFrame). Ids must be unique.
- New parameters are keyword-only (`modality`, `layer`, `feature_type`,
  `spatial_key`, `gdf_trx`, `include_variance`).
- Outputs set `var["entity_type"]` and `uns["axis_entities"]`, so `Matrix`
  infers the row/column entities and links to Landscape neighborhoods (this
  was previously done by the collection's `add_mod`).
- `calc_nbhd_by_gene` aggregates through one sparse neighborhood × cell
  membership matrix from a single spatial join, reused per modality, instead
  of densifying `X`. Means and population variances match the previous pandas
  groupby (tested).
- Alpha shapes and hextiles accept `MuData` (`modality=`, `spatial_key=`).
- `stamp_z` and `read_transcripts` are public; `calc_img_zonal_stats` is
  exported.
- Removed: `iter_gene_alpha_shapes`, `iter_gene_alpha_shapes_by_slice`,
  `alpha_shape_gene_expression_by_slice`, the dead `alpha_shape_geojson`.
- Fixed:
  - `alpha_shape_cell_clusters_by_slice` drew every shape black when the
    cluster colors lived in `uns`.
  - `hextile_niche(dissolve=False)` failed when the index was named like a
    column.
  - `filter_alpha_shapes` didn't strip float alpha suffixes (`_150.0`).

### 2.2 `celldega.clust.Matrix`: scanpy-backed dot plots from cell-level AnnData

- `Matrix(adata, groupby="leiden", *, layer=None, rank_genes_groups=None)`:
  - Aggregates with `scanpy.get.aggregate`: mean expression drives color, and
    count_nonzero ÷ group size drives dot size.
  - Reuses `adata.uns["rank_genes_groups"]` when it was computed for the same
    `groupby`. `rank_genes_groups=True` or a dict of kwargs runs
    `sc.tl.rank_genes_groups` instead.
  - Takes group colors from `uns[f"{groupby}_colors"]` and sets the column
    entity to `{"entity": "cell", "attr": groupby}`.
  - Drops cells with NaN group labels.
  - `cluster(view="rank_genes_groups")` then gives the RANK-slider marker
    filtering.
- `Matrix(collection=...)` is renamed `Matrix(mdata=...)`: any `MuData`, or
  any object with `.mod`.
- `size_by_layer` now also works with a plain AnnData `data`.
- `compute_marker_ranks`, `marker_ranks_to_uns`, and `marker_ranks_from_uns`
  are exported from `celldega.clust`.

### 2.3 `celldega.viz`

- `Composition(adata, groupby="sample_id", category="cell_type", group_attrs=[...])`
  cross-tabulates a cell-level AnnData internally. It takes colors from
  `uns[f"{category}_colors"]` and uses group sizes as `composition_col_weights`.
- Landscape's `nbhd=` resolves geometry through a shared helper (GeoDataFrame,
  `to_geodataframe()`, or a `geometry`/`gdf` attribute). The legacy
  `.collection` unwrap is gone.
- Docstrings and error messages no longer refer to `celldega.select` or
  `celldega.align`.
- `Landmark` removed: the Python widget, six JS modules, the `landmark` and
  `render_landmark` exports of the npm bundle, and the Landmark-only
  `per_view_controllers` option of `ini_deck` (restored to its pre-Landmark
  form). The docs bundle `docs/assets/js/celldega.js` is rebuilt.

### 2.4 `celldega.pre`

- New `write_point_cloud_dataset(adata, path, *, name=None, z_key="Z",
  cluster_key=None, write_genes=None, write_base_metadata=None, overwrite=False)`
  writes the point-cloud DegaFiles for `CellCloud`. It is the generic part of
  the former `align.write_alignment_point_cloud`. `name=` writes a named
  position variant (e.g. one alignment) that `CellCloud(alignment=...)` reads.
- `write_nbhd_cloud_dataset` and its parts take a neighborhood `GeoDataFrame`
  (or neighborhood-like object). They validate unique ids and the required
  `slice_id`, `cluster_id`, `color`, and `cell_count` columns.
- Removed `write_gene_shapes` and `write_gene_shapes_streaming`.
- `make_meta_gene` is added to `pre.__all__`.

### 2.5 Removed from Celldega (now in dega-collection)

`celldega.collection`, `celldega.dataset`, `celldega.set`,
`celldega.nbhd.NeighborhoodCollection`, `celldega.select`, `celldega.align`
(and the top-level exports `CelldegaCollection`, `DatasetCollection`,
`NeighborhoodCollection`, `SetCollection`, `concat_sets`, `align_serial_slices`,
`Landmark`). No import shims: `from celldega import DatasetCollection` now
fails with a standard ImportError.

### 2.6 Docs, notebooks, CI

- Removed the `align`, `collection`, `dataset`, `select`, and `set` API pages
  and their nav entries.
- Rewrote the nbhd, clust, and viz API pages and the Composition, CellCloud,
  NeighborhoodCloud, and Yearbook pages around plain AnnData/MuData/GeoDataFrame
  inputs.
- Added point-cloud and neighborhood-cloud DegaFiles sections to File Formats.
  These layouts are now the hand-off between the two packages.
- Moved the collection/align/select notebooks to dega-collection and removed
  them from the nav.
- Rewrote code cells (outputs not yet re-executed) in:
  - `Atera_Breast_Cancer_Neighborhood_Exploration`
  - `Gradient_Neighborhood_Pancreas_Islets`
  - `notebooks/Composition_Population_Proportions`
  - `notebooks/Clustergram_Visual_Encodings`
- The hidden CCLE helpers use plain `MuData` instead of `DatasetCollection`.
- CI installs `.[dev,scanpy]`, so the marker dot-plot tests run instead of
  skipping.
- CHANGELOG 0.28.0 has Breaking / Added / Fixed entries.

## 3. Migration for users

| Before (≤ 0.27) | After (0.28) |
| --- | --- |
| `dega.nbhd.NeighborhoodCollection(gdf=gdf).calc_population(adata, category="leiden")` | `dega.nbhd.calc_nbhd_by_pop(adata, gdf, category="leiden")` (or keep the collection via `dega_collection`) |
| `nbhd.calc_signature(adata)` | `dega.nbhd.calc_nbhd_by_gene(gdf, "cell", adata)` |
| `nbhd.calc_overlap()` / `calc_bordering()` | `dega.nbhd.calc_nbhd_overlap(gdf)` / `calc_nbhd_bordering(gdf)` |
| `setc = dega.SetCollection(adata, set_col="leiden"); setc.calc_signature(..., rank_genes_groups=True); Matrix(collection=setc, color_by=..., size_by_layer=...)` | `Matrix(adata, groupby="leiden", rank_genes_groups=True)` |
| `dset.calc_population(adata, category=...); Composition(dset, ...)` | `Composition(adata, groupby="sample_id", category=...)` |
| `dega.align.*`, `dega.select.*`, `dega.DatasetCollection`, ... | `dega_collection.align.*`, `dega_collection.select.*`, `dega_collection.DatasetCollection`, ... |
| `dega.align.write_alignment_point_cloud(adata, path, "name")` | `dega.pre.write_point_cloud_dataset(adata, path, name="name")` |
| `dega.align.write_nbhd_cloud(adata, path, ...)` | `gdf = dega.nbhd.alpha_shape_cell_clusters_by_slice(adata, ...)`; `dega.pre.write_nbhd_cloud_dataset(adata, gdf, path, ...)` |
| `Matrix(collection=x, ...)` | `Matrix(mdata=x, ...)` |
| `dega.viz.Landmark` | removed |

## 4. Verification

- **Python tests:** `pytest`: 263 passed, 1 failed, no skips (run with `-rs`).
  The failure is `test_pre/test_atera.py::test_read_atera_variable_length_strings`,
  a known local-only zarr 2 issue in the dev venv that predates this branch.
- **New tests:**
  - `test_nbhd/test_nbhd_functions.py`:
    - AnnData and real MuData (rna + protein);
    - sparse vs dense X and variance;
    - overlapping neighborhoods and `min_cells`;
    - cell-free mode;
    - overlap and bordering;
    - transcript assignment;
    - duck-typed neighborhoods, id-column fallbacks and validation;
    - MuData alpha shapes and hextiles.
  - `test_clust/test_matrix_groupby.py`:
    - means and fractions vs a pandas reference;
    - reusing scanpy ranks, computing them on request, and ignoring ranks for another grouping;
    - NaN labels, `layer=`, errors.
  - `test_pre/test_point_cloud.py`: the former align point-cloud tests ported to the new writer, plus `name=None` and manifest sync.
  - Composition `groupby` and duck-typed Landscape/Yearbook inputs in `test_viz/test_widget.py`.
- **JS:** `jest`: 56 suites, 420 tests passed. `eslint` and `prettier` are clean.
- **Python lint/format:** `ruff check` and `ruff format` are clean.
- **Docs:** `mkdocs build` succeeds with no new warnings. The only anchor
  notice (`export_viz_parquet`) predates this branch.
- **Bundle:** `npm run build`. Neither the static bundle nor the docs bundle
  contains Landmark code.
- **Pre-review audit:** a read-only multi-agent review of the diff, with each
  finding adversarially verified. See §6 for results.

## 5. Known limitations and follow-ups

- **Notebook outputs.** The edited docs notebooks keep their old outputs until
  re-executed. Re-executing needs the data and embedding widget state
  (CONTRIBUTING.md), which is planned as a separate PR.
- **Untracked notebooks.** The Broad-Allen E15.5 Viz notebook is untracked; its
  code cells were updated locally. The E15.5 Align notebook moved to
  dega-collection and is no longer in the nav.
- **NeighborhoodCloud gene shapes.** The JS still has the gene-shape rendering
  path (`nbhd_cloud_shapes_layer.js`), which now has no producer. Remove it in
  a follow-up.
- **Pickles.** Old pickles of `SerialAlignmentTransform` or `Selection` that
  reference `celldega.*` paths won't load. Use `save()`/`load()` (the
  transform's on-disk format stores no module paths).
- **Variant names.** Point-cloud variant names share the
  `cell_metadata_<name>.parquet` namespace with segmentation versions.
  `default` is reserved; other collisions are not checked.

## 6. Pre-review audit findings

_To be filled from the verification workflow results._

## 7. Suggested review focus

1. `celldega/nbhd/neighborhoods.py` and `nbhd/utils.py`: membership
   aggregation, MuData resolution, and `_as_nbhd_gdf` validation.
2. `clust/matrix.py` `_group_signature` and the `Matrix.__init__`
   argument-validation matrix (`groupby` / `mdata` / `size_by*`).
3. `pre/point_cloud.py` create vs append semantics (now the only point-cloud
   writer).
4. Whether the duck-typing hooks (`to_geodataframe()`, `.mod`/`.obs`,
   `to_json()`) are the right contract to document for third-party data
   structures.
