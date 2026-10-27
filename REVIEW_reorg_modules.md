# Review: Celldega `reorg_modules`: methods on plain scverse objects, separated from the data structures

**Branch:** `reorg_modules` (on top of `2c982e87`)
**Commits:** `4446da47` (code + tests), `41294eae` (docs + CHANGELOG), `bfdeb531` (notebook code cells), `f97bb59d` (pre-review audit fixes), then the module restore (§2.5)
**Target release:** 0.28.0 (breaking; the version bump is left to the release)

## 1. Summary

Celldega now works directly on standard scverse data structures (`AnnData`,
`MuData`) and `GeoDataFrame` neighborhoods, the way Scanpy works on `AnnData`.
The higher-level data structures (`CelldegaCollection`, `DatasetCollection`,
`NeighborhoodCollection`, `SetCollection`), the `select` query layer, and the
serial-slice `align` module stay in Celldega, in their own modules, separated
from the methods the way AnnData is separate from Scanpy.

The methods don't depend on the collections. Functions and widgets accept
collection objects by duck typing (`to_geodataframe()`, `.mod`/`.obs`,
`to_json()`). `NeighborhoodCollection` now stores data only: its `calc_*`
methods are gone, and you pass the collection to the `nbhd` functions and
store what they return.

The reorganization is staged. This branch separates the modules; removing the
collection, `select`, and `align` modules from Celldega may follow in a later
PR.

Also in this branch: the per-gene alpha shapes are removed (too slow to
compute; per-gene coloring in a NeighborhoodCloud now comes only from the
per-gene cell scatter), and the `Landmark` widget is marked as an alpha
feature.

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
- `Landmark` is unchanged apart from an alpha-feature note in its Python and
  JS docstrings. Its JS modules and the `landmark` / `render_landmark` bundle
  exports are kept, and the docs bundle `docs/assets/js/celldega.js` is rebuilt.

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

### 2.5 Data-structure modules: kept, separated from the methods

`celldega.collection`, `celldega.dataset`, `celldega.set`,
`celldega.nbhd.NeighborhoodCollection`, `celldega.select`, and `celldega.align`
keep their 0.27 exports, including the top-level `CelldegaCollection`,
`DatasetCollection`, `NeighborhoodCollection`, `SetCollection`, `concat_sets`,
and `align_serial_slices`. Changes from 0.27:

- `NeighborhoodCollection` stores data only. `calc_population`,
  `calc_signature`, `calc_overlap`, `calc_bordering`,
  `calc_transcript_assignment`, and `calc_gradient` are removed; the
  `nbhd.calc_nbhd_*` functions and `nbhd.calc_gradient` take the collection in
  place of a GeoDataFrame. Two storage operations are new:
  - `subset(obs_names)` keeps modalities, geometry, relations, and memberships
    aligned (it replaces the methods' `drop_missing=True`);
  - `add_relation(key, square)` aligns a square AnnData (from
    `calc_nbhd_overlap` / `calc_nbhd_bordering`) to the obs axis by id.
- Fixed: subsetting a collection with both modalities and relations failed,
  because MuData slices `obsp` along one axis only.
- The collection glue (`_subset_neighborhood_collection_to_obs`,
  `_relation_from_square_adata`) lives in `nbhd/_glue.py`; the computation
  modules don't import it.
- `align.write_alignment_point_cloud` and `align.write_nbhd_cloud` are removed:
  `align` returns an aligned AnnData, and `pre` writes the DegaFiles (§2.4).
- `DatasetCollection` and `SetCollection` still have their `calc_*` methods.
  Their computation lives in the collection modules, so making them
  storage-only means first moving that logic into functions.

### 2.6 Docs, notebooks, CI

- The `align`, `collection`, `dataset`, `select`, and `set` API pages are in
  the nav. The nbhd API page shows the function-then-store pattern for
  `NeighborhoodCollection`.
- Rewrote the nbhd, clust, and viz API pages and the Composition, CellCloud,
  NeighborhoodCloud, and Yearbook pages around plain AnnData/MuData/GeoDataFrame
  inputs.
- Added point-cloud and neighborhood-cloud DegaFiles sections to File Formats.
- Removed the collection/align/select notebooks from the nav.
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
| `nc.calc_population(adata, category="leiden")` | `pop = dega.nbhd.calc_nbhd_by_pop(adata, nc, category="leiden")`; `nc.subset(pop.obs_names)`; `nc.add_mod("population", pop)` |
| `nc.calc_signature(adata)` | `nc.add_mod("gene", dega.nbhd.calc_nbhd_by_gene(nc, adata=adata))` |
| `nc.calc_overlap()` / `calc_bordering()` | `nc.add_relation("overlap", dega.nbhd.calc_nbhd_overlap(nc))` (same for bordering) |
| `nc.calc_transcript_assignment(data_dir)` | `nc.obs = nc.obs.join(dega.nbhd.calc_nbhd_transcript_assignment(nc, dega.nbhd.read_transcripts(data_dir)))` |
| `nc.calc_gradient(obs_name="9", ...)` | `NeighborhoodCollection(gdf=dega.nbhd.calc_gradient(nc.gdf.loc[["9"]], ...), nbhd_type="gradient")` |
| Plain-data workflows | Any of the above with a GeoDataFrame in place of `nc`, keeping the returned objects |
| `setc = dega.SetCollection(adata, set_col="leiden"); setc.calc_signature(..., rank_genes_groups=True); Matrix(collection=setc, color_by=..., size_by_layer=...)` | `Matrix(adata, groupby="leiden", rank_genes_groups=True)` |
| `dset.calc_population(adata, category=...); Composition(dset, ...)` | `Composition(adata, groupby="sample_id", category=...)` |
| `dega.align.write_alignment_point_cloud(adata, path, "name")` | `dega.pre.write_point_cloud_dataset(adata, path, name="name")` |
| `dega.align.write_nbhd_cloud(adata, path, ...)` | `gdf = dega.nbhd.alpha_shape_cell_clusters_by_slice(adata, ...)`; `dega.pre.write_nbhd_cloud_dataset(adata, gdf, path, ...)` |
| `Matrix(collection=x, ...)` | `Matrix(mdata=x, ...)` |

## 4. Verification

- **Python tests:** `pytest`: 495 passed, 1 failed, no skips (run with `-rs`).
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
  - A regression test for each audit fix (§6).
  - The restored module tests (`test_align`, `test_select`, `test_schema`),
    `test_nbhd/test_nbhd_collection.py` rewritten for the storage-only
    `NeighborhoodCollection` (`subset`, `add_relation`, and a no-`calc_*`
    check), and `test_viz/test_collection_interop.py` (collections passed to
    Landscape, Composition, Yearbook, Matrix, and the `nbhd` functions).
- **JS:** `jest`: 62 suites, 505 tests passed. `eslint` and `prettier` are clean.
- **Python lint/format:** `ruff check` and `ruff format` are clean.
- **Docs:** `mkdocs build` succeeds with no new warnings. The only anchor
  notice (`export_viz_parquet`) predates this branch.
- **Bundle:** `npm run build` rebuilds the static and docs bundles (Landmark
  included).
- **Pre-review audit:** a read-only multi-agent review of the diff, with each
  finding adversarially verified. See §6 for results.

## 5. Known limitations and follow-ups

- **Notebook outputs.** The edited docs notebooks keep their old outputs until
  re-executed. Re-executing needs the data and embedding widget state
  (CONTRIBUTING.md), which is planned as a separate PR.
- **Untracked notebooks.** The Broad-Allen E15.5 Viz notebook is untracked; its
  code cells were updated locally. The E15.5 Align notebook and two older local
  alignment drafts (`1.0_Preprocess_and_Align`, `2.0_Viz_CellCloud`) are
  excluded from the docs build in `mkdocs.yaml` until they are updated to the
  current APIs.
- **DatasetCollection / SetCollection.** Still carry `calc_*` methods (§2.5).
- **NeighborhoodCloud gene shapes.** The JS still has the gene-shape rendering
  path (`nbhd_cloud_shapes_layer.js`), which now has no producer. Remove it in
  a follow-up.
- **Variant names.** Point-cloud variant names share the
  `cell_metadata_<name>.parquet` namespace with segmentation versions.
  `default` is reserved; other collisions are not checked.

## 6. Pre-review audit findings

**Method.** Five read-only reviewers covered `nbhd`, `Matrix`/`Composition`, the
`pre` writers, viz/removal completeness/docs, and the collection wiring.
An adversarial verifier then tried to refute each finding by tracing it through
the code. Of the 28 findings, 23 were confirmed (two of them reported twice) and
5 were rejected as intended behavior or as predating this branch. Every
confirmed Celldega finding is fixed in `f97bb59d` with a regression test, except
the notebook re-run.

| # | Finding (Celldega) | Severity | Status |
| --- | --- | --- | --- |
| 1 | `calc_nbhd_by_pop` dropped the Categorical dtype: categories missing or lexicographically reordered (e.g. `'10'` before `'2'`) | medium | fixed (`labels.array`) |
| 2 | Duplicate `obs_names` crashed `calc_nbhd_by_gene` / `calc_nbhd_by_pop` / alpha shapes (old code was positional) | medium | fixed (positional alignment when indices match; clear error otherwise) |
| 3 | `Composition(groupby=..., group_attrs=...)` silently dropped categorical attribute tracks | medium | fixed (here and in Matrix node info) |
| 4 | By-slice alpha shapes all black without stored cluster colors (the removed `write_nbhd_cloud` used to add a fallback palette) | medium | fixed (fallback palette) |
| 5 | The removed Align tutorial and two old drafts in `docs/` were still built and published | medium | fixed (`exclude_docs`) |
| 6 | Cell-free `calc_nbhd_by_gene(min_cells=0)` dropped empty neighborhoods | low | fixed |
| 7 | `Matrix(groupby=)` counted negative (scaled) values as expressing | low | fixed (`> 0` indicator) |
| 8 | `rank_genes_groups={}` computed no ranks | low | fixed |
| 9 | `Matrix(groupby=)` discarded `adata.var`, so `row_attr` was ignored | low | fixed |
| 10 | `Composition(groupby=)` ignored the `adata=` color fallback | low | fixed |
| 11 | `write_cell_clusters_meta` failed for neighborhood objects with a custom id column | low | fixed |
| 12 | `write_point_cloud_dataset` wrote the manifest before clusters/genes, so a corrected retry skipped them | low | fixed (validate first, manifest last) |
| 13 | CHANGELOG overstated where `to_geodataframe()` objects are accepted | low | fixed (narrowed) |
| 14 | CHANGELOG misdescribed `calc_nbhd_transcript_assignment` | low | fixed |
| 15 | nbhd API page used an undefined `gdf_alpha` | low | fixed |
| 16 | Edited notebooks still show outputs from the removed classes | low | open: re-execute in a follow-up PR |

Rejected:
- NaN propagation in `calc_nbhd_by_gene` means (affects only neighborhoods containing a NaN cell).
- `name` taking precedence over an object's `nbhd_col` (documented behavior).
- Same precedence in the nbhd-cloud writers.
- `overwrite=True` without `name` resetting the variant list (documented).
- `Yearbook(selection=pd.Index)` (predates this branch).

## 7. Suggested review focus

1. `celldega/nbhd/neighborhoods.py` and `nbhd/utils.py`: membership
   aggregation, MuData resolution, and `_as_nbhd_gdf` validation.
2. `clust/matrix.py` `_group_signature` and the `Matrix.__init__`
   argument-validation matrix (`groupby` / `mdata` / `size_by*`).
3. `pre/point_cloud.py` create vs append semantics (now the only point-cloud
   writer).
4. `nbhd/collection.py` and `nbhd/_glue.py`: the storage-only
   `NeighborhoodCollection` (`subset`, `add_relation`).
5. Whether the duck-typing hooks (`to_geodataframe()`, `.mod`/`.obs`,
   `to_json()`) are the right contract to document for third-party data
   structures.
