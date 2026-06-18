# Changelog

All notable changes to Celldega are documented here. This project follows
[Keep a Changelog](https://keepachangelog.com/) conventions and
[semantic versioning](https://semver.org/).

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
