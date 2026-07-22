# Changelog

All notable changes to Celldega are documented here. This project follows
[Keep a Changelog](https://keepachangelog.com/) conventions and
[semantic versioning](https://semver.org/).

## [0.19.0a2] - 2026-07-17

### Fixed

- **Unsigned `landscape_parameters.json` fetch with private-bucket creds** —
  `set_landscape_parameters` accepted an `aws` client (for SigV4-signed S3
  requests) but never actually used it, always issuing a plain unsigned
  `fetch`. Against a private bucket this 403s, and the XML error body then
  fails `response.json()` with a confusing `SyntaxError: Unexpected token
  '<'`. A redundant signed "warm-up" fetch to the same URL earlier in init
  likely masked this via browser HTTP caching in some environments. Now
  `set_landscape_parameters` uses `aws.fetch(...)` when creds are provided
  (matching the pattern already used for parquet/arrow requests) and throws
  a clear error on a non-2xx response instead of trying to parse it as JSON.
  Also fixes `landscape_h_e.js`, which never passed `viz_state.aws` through
  to this call at all.

## [0.19.0a1] - 2026-07-17

Alpha pre-release: a new serial-slice alignment module, plus small front-end
fixes needed to render stacked 2D alpha shapes in the 3D point-cloud
`Landscape` view.

### Added

- **`celldega.align`** — registration of serial 3D tissue slices into a
  shared coordinate frame. `calc_landmarks` derives per-slice landmarks from
  shared cluster labels (or accepts manually-placed ones);
  `calc_alignment_transform` chain-walk fits a rigid Procrustes or non-rigid
  thin-plate-spline transform outward from a reference slice, returning a
  reusable, persistable `SerialAlignmentTransform`
  (`.save()`/`.load()`, `.apply_to_points()`); `align_serial_slices` applies
  a fitted transform to a set of `AnnData`, aligning `obsm["spatial"]` and
  assigning each slice a `Z` coordinate (`z_space` or explicit `z_coord`).

### Fixed

- **Widget crash on gene-less datasets** — `set_meta_gene`/
  `set_color_dict_gene` called `.getChild(...)` directly on the result of a
  failed `meta_gene.parquet` fetch (e.g. point-cloud datasets with no
  expression data), throwing `TypeError: n.getChild is not a function` and
  aborting the entire `Landscape` render. Both now go through the same
  null-safe `table_accessors` helpers already used for cluster metadata, so
  a missing `meta_gene.parquet` degrades to an empty gene list instead of
  crashing.

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
