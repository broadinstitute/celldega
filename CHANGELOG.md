# Changelog

All notable changes to Celldega are documented here. This project follows
[Keep a Changelog](https://keepachangelog.com/) conventions and
[semantic versioning](https://semver.org/).

## [0.20.0] - 2026-07-29

Adds a new `Clustergram` body encoding — `dotplot` — and a new dedicated
`Composition` widget for comparing category proportions/counts across groups
as stacked bars, plus a control-panel restyle shared by both widgets and a
round of dendrogram/hover-interaction polish that touches both.

### Added

- **`Clustergram.viz_mode`** — `"heatmap"` (opacity ∝ value, default) or
  `"dotplot"` (opacity from the main matrix, size from a secondary matrix — the
  classic "percent expressing" dot plot). Animates live.
- **`Matrix.set_dot_matrix`** / **`SetCollection.calc_signature(aggregate="fraction")`**
  — attach and compute the dot-plot secondary size channel. `Matrix(collection=...,
  color_by=..., size_by=...)` builds both directly from a collection, no manual
  DataFrame wrangling needed (`dot_plot=` is accepted as an alias for `size_by=`,
  since `size_by` isn't limited to "fraction expressing" — any per-cell magnitude
  works, e.g. a significance score).
- **`dega.viz.Composition`** — a `Clustergram` subclass for count/proportion
  comparison across groups: each group renders as a bottom-anchored stacked bar,
  each category a colored segment, with a global (cross-bar-consistent) stacking
  order, double-click-to-reorder, cross-bar hover highlight, and a `PROP`/`COUNTS`
  toggle. `composition_col_weights` carries `DatasetCollection.calc_population`'s
  true per-group cell counts so `COUNTS` mode reflects real dataset-size
  differences even though the displayed matrix is proportions. Vertical-only zoom
  keeps every group column visible while zooming into small populations.
- **`SetCollection.calc_population`** now carries the source `AnnData`'s category
  color palette (e.g. `uns["cell_type_colors"]`) onto the modality — `Composition`
  picks this up automatically from a `DatasetCollection`/`SetCollection` alone, no
  separate `adata=` needed in the common case.
- **Row dendrogram in `Composition`** — dynamically positioned from the rightmost
  bar's actual (non-uniform) segment geometry, so clusters of co-regulated
  populations across datasets are visible the same way a regular `Clustergram`
  row dendrogram would show them. Recomputes on reorder/normalize/weight changes.
  Both dendrograms' trapezoids animate their shape on resize.
- **Dendrogram hover/click highlight** — hovering (after a short dwell delay,
  matching every other hover-highlight in the widget) or clicking a dendrogram
  trapezoid dims every row/column *not* covered by it, in both `Clustergram` and
  `Composition`.
- **Composition row/column label hover** — hovering a row or column label
  cross-highlights it the same way hovering its bar segment does (`Composition`
  only).
- Two new example notebooks: `Clustergram_Visual_Encodings.ipynb` and
  `Composition_Population_Proportions.ipynb`.

### Changed

- Clustergram control-panel buttons restyled across the board: capitalized text,
  no border/background — active/inactive state shown by text color alone
  (blue/gray); axis-name labels are fixed-width, colon-suffixed, and non-clickable.
- `viz_mode="composition"` is now only settable on a `Composition` instance
  (`TraitError` on a plain `Clustergram`) — the composition body was always
  designed to be reached through the dedicated widget, which handles the matrix
  shape and reorder semantics it needs.
- **`SetCollection.calc_signature`** now requires an explicit `modality_name`
  (previously defaulted to `"expression"`/`"fraction"`/the feature type), so it's
  always clear which modality a given call produces.
- Composition-mode row labels are hidden when their segment is too short to fit
  one line of text, and reveal themselves as you zoom in on rows (previously
  always shown, however small, which cut off badly for small populations or in
  `COUNTS` mode).
- Column dendrogram trapezoids in `Composition` account for the gap between
  bars (previously overshot each bar slightly).

### Fixed

- `Matrix.set_dot_matrix` wasn't transposing `AnnData` input, silently
  misaligning the dot-plot size channel to zero for that input type.
- A hover-highlight (composition bars, dendrogram, or categorical attribute
  tiles) could get stuck showing its last state after the mouse left the
  widget, if a pending delayed-highlight timer fired after the fact. Also
  traced to, and fixed: the widget container's CSS width didn't account for
  the deck.gl canvas's own rendering buffer, so content at the far right edge
  (the row dendrogram) could fall outside the box the browser tracked mouse
  events against.

### Removed

- `Clustergram.viz_mode="size"` (square size ∝ value, full opacity) — never
  released; `"dotplot"` covers the same "size encodes a value" idea via a
  proper secondary matrix. `StackedBar` (deprecated alias for `Composition`) —
  also never released.

[0.20.0]: https://github.com/broadinstitute/celldega/compare/0.19.0...0.20.0

## [0.19.0] - 2026-07-29

Introduces `celldega.align`, a new module for registering serial 3D tissue
slices into a shared coordinate frame, and `celldega.viz.Landmark`, an
interactive widget for manually marking and reviewing corresponding landmark
points across slices. Also fixes an `AnnData`-mutation bug and a cell-metadata
keying bug in `Landscape`/`Yearbook` that could silently break cluster
coloring for any `cluster_attr` (not just `leiden`).

### Added

- **`celldega.align`** — registration of serial 3D tissue slices into a
  shared coordinate frame. `calc_landmarks` derives per-slice landmarks from
  shared cluster labels (or accepts manually-placed ones);
  `calc_alignment_transform` chain-walk fits a rigid Procrustes or non-rigid
  thin-plate-spline transform outward from a reference slice, returning a
  reusable, persistable `SerialAlignmentTransform` (`.save()`/`.load()`,
  `.apply_to_points()`); `align_serial_slices` applies a fitted transform to a
  set of `AnnData`, aligning `obsm["spatial"]` and assigning each slice a `Z`
  coordinate (`z_space` or explicit `z_coord`).
- **Anti-overfit TPS controls** — `area_regularization` and
  `shape_regularization` (both `[0, 1]`) on `fit_transform_tps` /
  `calc_alignment_transform`, applied as a post-fit SVD correction that pulls
  the warp's global area and proportions toward rigid while leaving local
  deformation intact (`1`/`1` makes the global part rotation-only). Both are
  persisted through `save`/`load` and `uns["align_serial_slices"]`.
- **`celldega.align.plot_alignment`** (also `transform.plot()`) — a before/after
  2D scatter to sanity-check a fit at a glance.
- **`celldega.align.write_alignment_point_cloud`** — writes aligned 3D cell
  centroids into a point-cloud DegaFiles as named alignment variants
  (`cell_metadata_<name>.parquet`), registered under a new `"alignments"` key
  in `landscape_parameters.json`. Appends to an existing DegaFiles (positions
  only, reusing clusters/genes) or creates a fresh one (clusters from
  `obs[cluster_key]`, plus gene expression when `adata` carries it).
- **`Landscape(alignment="<name>")`** — a new argument for point-cloud
  technology that loads a named alignment's positions
  (`cell_metadata_<name>.parquet`) while clusters/genes keep loading from
  their normal paths, so alignments can be swapped without a dropdown.
- **`celldega.viz.Landmark`** — an interactive widget for manually marking
  corresponding landmark points across slices. Two side-by-side panels (any
  slice swappable into either via dropdowns) with MARK / MODIFY / SAVE / DEL,
  per-landmark rename + color, and per-slice rotation. Centroids are colored by
  an optional `cluster_key` and streamed over the widget comm channel (no
  bucket reads). Emits `.landmarks` in the exact shape `calc_landmarks`
  produces, so manual and automatic landmarks concatenate; `landmarks=`
  reloads a prior table for review/extension. Includes keyboard shortcuts for
  MARK/SAVE/CANCEL/DELETE (scoped to the widget so Jupyter's command-mode
  shortcuts like `m`/`a`/`b`/`d d` don't fire over it, with focus following the
  mouse/click), and Z-pagination (prev/next slice buttons with a slice-id
  indicator) that preserves the current zoom/pan across a slice swap.

### Fixed

- **`AnnData` mutation in `Landscape`/`Yearbook`** — both widgets called
  `adata.obs.set_index(..., inplace=True)` and, when a cluster's colors were
  missing, ran `sc.pl.umap(adata, ...)` just to harvest the `<attr>_colors` it
  writes back — silently mutating the caller's `AnnData` in both its index and
  `uns`. Cell metadata is now derived from a non-mutated view of `obs`, and
  missing colors fall back to a deterministic HSV palette instead of a scanpy
  plotting call.
- **Cluster attribute lockin / mismatch on cell metadata keying** — cell
  metadata was keyed by an `adata.obs["cell_id"]` column (when present) rather
  than `adata.obs_names`. When that column's values didn't exactly match
  `obs_names` (e.g. a reordered `"cell__slice"` form), every cell silently
  mismatched the DegaFiles `cell_metadata` `name` column, so cluster coloring
  (`leiden` or any other `cluster_attr`) resolved to "N.A." and point-cloud
  cells were culled. Cell metadata is now always keyed by `obs_names`, the
  canonical AnnData cell identifier.
- **Gene panel shown for gene-less datasets** — the `Landscape` gene bar-graph
  and gene search are now hidden when a dataset has no gene expression (e.g. a
  point-cloud DegaFiles written without `cbg/`), instead of rendering an empty
  panel.
- **Unsigned `landscape_parameters.json` fetch with private-bucket creds** —
  `set_landscape_parameters` accepted an `aws` client (for SigV4-signed S3
  requests) but never actually used it, always issuing a plain unsigned
  `fetch`. Against a private bucket this 403s, and the XML error body then
  fails `response.json()` with a confusing `SyntaxError: Unexpected token
  '<'`. Now `set_landscape_parameters` uses `aws.fetch(...)` when creds are
  provided (matching the pattern already used for parquet/arrow requests) and
  throws a clear error on a non-2xx response instead of trying to parse it as
  JSON. Also fixes `landscape_h_e.js`, which never passed `viz_state.aws`
  through to this call at all.
- **Widget crash on gene-less datasets** — `set_meta_gene`/
  `set_color_dict_gene` called `.getChild(...)` directly on the result of a
  failed `meta_gene.parquet` fetch (e.g. point-cloud datasets with no
  expression data), throwing `TypeError: n.getChild is not a function` and
  aborting the entire `Landscape` render. Both now go through the same
  null-safe `table_accessors` helpers already used for cluster metadata, so
  a missing `meta_gene.parquet` degrades to an empty gene list instead of
  crashing.
- **`Landmark` modify-mode drag on the left panel** — disabling camera-pan on
  both panels while modifying a landmark stopped deck.gl from dispatching drag
  events to the left view at all, so a marker on that side couldn't be
  refined. Pan is now correctly disabled on both views without blocking drags.
- **TPS regularization validation** — `fit_transform_tps` accepted any
  `area_regularization`/`shape_regularization` `>= 0`, even though only
  `[0, 1]` is meaningful; validation now enforces that range. `degree` was
  also missing from the persisted `uns["align_serial_slices"]` metadata, so a
  reloaded transform lost its fitted TPS degree.

[0.19.0]: https://github.com/broadinstitute/celldega/compare/0.18.1...0.19.0

## [0.18.1] - 2026-07-15

### Fixed

- **Pinned `numpy<2`** — the previously unconstrained `numpy` dependency let
  pip resolve numpy 2.x in environments that already had numpy1-ABI binary
  wheels (e.g. `h5py`) installed, causing `ValueError: numpy.dtype size
  changed, may indicate binary incompatibility` on `import celldega`.

## [0.18.0] - 2026-06-26

Adds a set-level Collection entity, harmonizes the collection feature-calculation
API, adds programmatic dendrogram cutting, lets linked views color cells by any
attribute, and makes widget-bearing docs notebooks dramatically smaller by loading
the front-end bundle from a CDN. ([#307](https://github.com/broadinstitute/celldega/pull/307))

### Added

- **`dega.set.SetCollection`** — a MuData-backed set-level entity (sets as `obs`,
  elements/cells as a sparse `membership` `var` modality) for clustering results,
  spatial-domain algorithm outputs, and manual annotations. Methods: `calc_signature`
  (gene by default; `feature_type` selects a `MuData` modality, e.g. protein),
  `calc_population`, `calc_overlap` (square set-by-set relation on self, rectangular
  modality across collections), and `concat_sets`; plus a stubbed `to_nbhd`. A
  preferred per-set color is stored in `obs["color"]` and reused by the Clustergram
  and Landscape.
- **`Matrix.to_cluster` / `Clustergram.to_cluster`** — cut a dendrogram into flat
  cluster labels (`fcluster`); the Clustergram reads the front-end slider via a new
  `dendro_cut` trait.
- `SetCollection` docs page, a `SetCollection_Cluster_Space` example notebook, and a
  CONTRIBUTING section on rendering docs notebooks with embedded widget state.

### Changed

- **Harmonized collection API (breaking)** — the entity prefix is dropped now that
  the instance carries it: `calc_dataset_signature`/`calc_nbhd_by_gene` →
  `calc_signature`; `*_by_pop` → `calc_population`; `calc_nbhd_overlap` →
  `calc_overlap`; `calc_nbhd_bordering` → `calc_bordering`;
  `calc_nbhd_transcript_assignment` → `calc_transcript_assignment`.
- **Widget front-end loading** — anywidgets load `celldega.js` from jsdelivr via a
  small `_esm` shim instead of inlining the ~10 MB bundle once per widget, so saved
  widget state stays small (`CELLDEGA_LOCAL_ESM=1`/`ANYWIDGET_HMR` keep the local
  bundle for development).
- Linked Clustergram↔Landscape/Yearbook views color cells by the Clustergram's
  `col_entity` attribute instead of a hard-coded `"leiden"`; `Landscape`/`Yearbook`
  gained a `cluster_attr` kwarg, and `calc_signature` stamps `uns["axis_entities"]`
  so a `Matrix` over a signature auto-infers its linking attribute.

### Fixed

- `Matrix.viz` is now deep-copied from the default, fixing `linkage` state leaking
  across `Matrix` instances.
- Linked-view helpers wrote to the removed `Yearbook.query` trait (now
  `front_end_query`), so cluster/gene selections were silently dropped.
- `Landscape`/`Yearbook` `cell_attr` selection no longer raises when a default
  column is absent; passing `meta_cluster` as a `DataFrame` no longer raises a
  double-`pop` `KeyError`.

## [0.16.0] - 2026-06-18

This release introduces two major capabilities — a MuData-backed **Collection
API** for higher-order biological entities and a composable **select/sampling
layer** over AnnData — along with row-group Parquet storage, a uv-based
developer environment, and assorted fixes.

### Added

- **`dega.select` module** — a composable query and sampling layer over AnnData
  (`Selector`, `Attribute`, `Query`, `Selection`, and `Random`/`QuantileBin`/
  `Gaussian`/`Rank`/`Stratified` samplers), with a safe deterministic preview
  guard for large unsampled queries. ([#300](https://github.com/broadinstitute/celldega/pull/300))
- **`dega.collection.CelldegaCollection`** — a typed, MuData-backed base class
  for modeling biological entities above the single cell. ([#303](https://github.com/broadinstitute/celldega/pull/303))
- **`dega.dataset.DatasetCollection`** — dataset/sample/patient-level entities
  built by binning cells over a column, with `calc_dataset_by_pop` and
  `calc_dataset_signature` feature modalities. ([#303](https://github.com/broadinstitute/celldega/pull/303))
- **`NeighborhoodCollection`** — spatially constructed neighborhoods carrying
  feature modalities, relations (`calc_nbhd_overlap`, `calc_nbhd_bordering`),
  geometry, and a micron-to-pixel transformation matrix. ([#303](https://github.com/broadinstitute/celldega/pull/303))
- **`Yearbook(selection=...)`** — drive the portrait grid from a
  `select.Selection`, a selection dict, or a plain list of cell ids; the
  JSON-ready selection is stored for provenance. ([#300](https://github.com/broadinstitute/celldega/pull/300))
- Row-group Parquet storage mode for tiled data. ([#289](https://github.com/broadinstitute/celldega/pull/289))
- Atera visualization notebook and support. ([#298](https://github.com/broadinstitute/celldega/pull/298))
- uv-based developer setup (`scripts/setup.sh`) on a standalone CPython, which
  resolves the Anaconda/GLib runtime crash with the geo wheels and registers a
  "Python (dega)" Jupyter kernel.
- New API documentation pages (`collection`, `dataset`, `select`) and example
  notebooks (DatasetCollection and NeighborhoodCollection population space,
  Custom Segmentation).

### Changed

- `Landscape(nbhd=...)` now accepts a `NeighborhoodCollection` directly, and
  `Matrix` auto-infers row/column entities from collection metadata. ([#303](https://github.com/broadinstitute/celldega/pull/303))
- **Breaking:** the Yearbook browser-query trait was renamed `query` →
  `front_end_query` to disambiguate it from the `dega.select` query module. The
  old `query=` argument still works but emits a `DeprecationWarning`. ([#300](https://github.com/broadinstitute/celldega/pull/300))
- **Breaking:** `LandscapeFiles` renamed to `DegaFiles`, including
  `path_landscape_files` → `path_dega_files`. ([#303](https://github.com/broadinstitute/celldega/pull/303))

### Removed

- **Breaking:** the legacy `NBHD` class. Its feature/relation logic moved onto
  `NeighborhoodCollection`, and construction is now done with module functions
  (`alpha_shape`, `generate_hextile`, ...). ([#303](https://github.com/broadinstitute/celldega/pull/303))

### Fixed

- Enrich → Clustergram syncing in the `landscape_clustergram` view. ([#290](https://github.com/broadinstitute/celldega/pull/290))
- Yearbook width bug and documentation updates. ([#288](https://github.com/broadinstitute/celldega/pull/288))

### Known issues

- `import celldega` can fail with `ModuleNotFoundError: No module named
  'pkg_resources'` on fresh installs that resolve setuptools >= 82, because the
  pinned `spatialdata_io~=0.1.0` pulls an older `spatialdata`/`xarray_schema`
  that still imports the removed `pkg_resources`. Workaround: install
  `setuptools<82`. ([#292](https://github.com/broadinstitute/celldega/issues/292))

[0.16.0]: https://github.com/broadinstitute/celldega/compare/0.15.0...0.16.0
