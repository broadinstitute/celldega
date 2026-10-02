# Changelog

All notable changes to Celldega are documented here. This project follows
[Keep a Changelog](https://keepachangelog.com/) conventions and
[semantic versioning](https://semver.org/).

## [0.26.0]

### Breaking

- `Matrix` construction now always preserves supplied values. The bundled
  `process()` pipeline and the `filter_genes`, `norm_col`, `norm_row`, and
  `disable_processing` constructor arguments are removed (passing them raises
  `TypeError`); transform explicitly with `filter()` and `norm()` before
  clustering.
- Marker rankings are calculated and persisted only by `SetCollection`; `Matrix`
  consumes rankings attached to its input. `Matrix.marker_ranks`,
  `Matrix.set_marker_ranks()`, and the `rank_genes_groups` /
  `rank_genes_groups_kwargs` arguments of `Matrix.downsample_to()` are removed.
- `Matrix.cluster()` now returns the `Matrix` itself (for chaining) instead of
  the documented visualization dict; read `mat.viz` if you need that structure.
- `SetCollection.calc_signature(rank_genes_groups=True)` no longer lets Scanpy
  silently rank `adata.raw` when it exists: it ranks the aggregated `layer`, or
  `adata.X`, with `use_raw=False`. Marker results change for AnnData objects
  carrying `.raw`; pass `rank_genes_groups_kwargs={"use_raw": True}` to keep the
  old behavior. By default (`rank_genes_groups_layer=None`) a raw-count source
  is log-normalized on the fly (`log1p(normalize_total(counts))`, as Scanpy
  recommends) before ranking; an already-normalized source is ranked as-is.
- Clustergram/Enrich linking is now entirely browser-side (`jslink`), so live
  and static (documentation) notebooks behave identically. The Python observers
  that mirrored selections into `Enrich.gene_list` are gone; a kernel-side
  change to `Clustergram.selected_genes` no longer updates Enrich.
- The unimplemented `SetCollection.to_nbhd()` stub (it only raised
  `NotImplementedError`) is removed; geometry graduation remains planned.

### Added

- `SetCollection.calc_signature` can store fraction expressing as a layer on the
  expression signature via `fraction_expressing_layer`, and can rank a different
  expression source via `rank_genes_groups_layer` (including normalized `X`).
- `calc_signature` prints the expression source used for aggregation, fraction
  expressing, and marker ranking (`verbose=False` silences it), and warns when
  the aggregated source has non-integer values, i.e. does not look like raw
  counts. It also warns when `rank_genes_groups_layer` is passed without
  `rank_genes_groups=True`.
- `Matrix(..., size_by_layer=...)` can use a layer on the color modality as its
  dot-size channel.
- `calc_signature(rank_genes_groups=True)` also stores each feature's
  best-scoring set in `var[f"{set_col}_marker"]` (e.g. `leiden_marker`), a
  gene-level grouping derived from the cell clustering. Select it with
  `Matrix(..., row_attr=["leiden_marker"])`, alongside `col_attr=["leiden"]`, to
  color rows and columns with the shared per-set palette.
- Clustergram column-label clicks send Enrich only genes above
  `Clustergram.top_gene_min_value` (default `0`, i.e. enriched in that column
  after row z-scoring; `None` disables).
- Clustergram category bars (ROW/COL) have a source dropdown listing every
  categorical attribute passed via `col_attr`/`row_attr`, plus the manual
  category once it exists; blue marks a clickable picker.
- Hovering a Clustergram category (tile or control-panel bar) now also outlines
  the matching tiles and bar in dark gray, so light colors still read.
- Docs: new Atera breast cancer Landscape + Clustergram + Enrich tutorial; the
  notebook sidebar toggle has a sidebar icon that reflects its direction, and
  is also available on gallery example pages.

### Changed

- `Matrix.cluster(view=...)` is now the canonical clustering entry point;
  `clust()` and `views=` remain deprecated compatibility aliases.
- The secondary quantitative channel is now named `size_matrix` and configured
  with `set_size_matrix()` / `size_by_layer`. `dot_mat`, `set_dot_matrix()`, and
  `dot_plot` remain deprecated compatibility aliases.
- `Matrix.cut_tree()` replaces `Matrix.to_cluster()` (kept as a deprecated
  alias) and requires exactly one of `n_clusters` or `threshold`.
- `spatial_clustergram(width=...)` now sizes only the spatial widget. The
  Clustergram panel fits the Clustergram's canvas (`width` + ~100px for
  labels), widened to at least 550px so its control bar (including gene search)
  is never clipped.
- Clustergram control panel redesign: a compact ROW / COL grid with an order
  dropdown (CLUST, SUM, VAR, INI; shows CUSTOM after a label reorder) and the
  dendrogram slider on each axis row, then DIM (precomputed views only),
  CROP | UNDO and PROP | UNIT. Axes are labeled ROW/COL rather than by entity
  name. Optional rows drop out without shifting the layout.
- The Celldega logo now sits inside the gene search bar (Clustergram,
  Landscape, CellCloud, NeighborhoodCloud), freeing control-panel width; gene
  info boxes are narrower.
- Clustergram tooltips appear after a 0.1 s dwell, and control-panel category
  bar hovers apply after 150 ms (with a short clear delay) to stop flicker.

### Fixed

- `Matrix.write_dega_files()` raised `AttributeError` when called without
  `name=`; it now falls back to the matrix's name (or data hash).
- `SetCollection.read()` from `.h5mu` now restores `set_col`, `name`,
  `element_type`, and `source`.
- A Clustergram with both static and manual categories failed to render
  ("error in render function"): the manual-category bar breakdown called
  methods the manual-category store does not have.
- Manual categories now appear in the category bars immediately (with their
  chosen colors) and survive switching the bar's source.
- The manual-category editor keeps one color for a new category while you type
  its name, instead of allocating a new color on every keystroke.
- Mouse-wheel gestures over the Clustergram (including the empty corner left of
  the column labels) no longer scroll the page.

## [0.25.1]

### Performance

- Improved linked **Clustergram → Landscape/CellCloud gene-selection performance**.
  - Avoids clearing `selected_cells` when no individual cells are selected, preventing an unnecessary full cell-layer rebuild.
  - Removes redundant explicit cell and transcript layer refreshes after linked gene selection.
  - Uses the existing `selected_cats` subscription as the canonical cell-layer update path, reducing duplicate deck.gl updates during gene selection.
- Retains selection-keyed cell-layer IDs to ensure updated binary color buffers are reliably uploaded to deck.gl.

### Fixes

- Preserves correct cell coloring when switching genes through linked Clustergram interactions.
- Avoids redundant deck.gl `setProps` calls while retaining the buffer invalidation behavior required for binary cell attributes.

### Validation

- Validated with 2D `Landscape` datasets using gene and cluster selections from both the Clustergram and Landscape controls.
- Includes additional JavaScript tests covering linked gene-selection update behavior.
- This release will also be used to evaluate the performance improvements on very large 3D `CellCloud` datasets.

## [0.25.0] - 2026-09-29

Major Clustergram-focused release adding interactive matrix filtering, reduced-dimensionality views, full dendrogram tree visualization, tighter Enrich integration, and a broad round of visualization and lifecycle improvements.

### Added

- **Interactive Clustergram crop filtering** — a new `CROP` / `UNDO` workflow lets users drag-select a region of the matrix and filter to the selected rows and columns. Double-clicking a dendrogram branch can also crop directly to that hierarchical cluster. Cropping updates the matrix, labels, annotations, dendrograms, and category summaries together, and gene-row crops propagate to linked Enrich and spatial views. Crop filtering can be used within an active reduced-dimensionality view. ([#251](https://github.com/broadinstitute/celldega/pull/251))

- **Reduced-dimensionality Clustergram views** — `Matrix.clust(views=..., levels=...)` can now precompute filtered views using `"rank_genes_groups"`, `"var"`, `"sum"`, or `"mean"`. Each level is independently re-biclustered on both axes rather than simply hiding rows, and is exposed through a new `RANK` / `VAR` / `SUM` / `MEAN` slider in the Clustergram. The complete matrix remains available as the `all` view. `Clustergram.rank_dim` can also select a view programmatically. ([#334](https://github.com/broadinstitute/celldega/pull/334))

- **Marker ranking support for dimensionality filtering** — `Matrix.downsample_to(..., rank_genes_groups=True)`, `Matrix.set_marker_ranks(...)`, and `SetCollection.calc_signature(..., rank_genes_groups=True)` can compute or preserve differential-expression rankings for marker-driven Clustergram views. Existing `AnnData.uns["rank_genes_groups"]` results are recognized automatically. ([#334](https://github.com/broadinstitute/celldega/pull/334))

- **Full dendrogram tree and rising-water cut visualization** — adjusting a dendrogram cutoff slider now temporarily displays the complete row or column tree over the matrix, together with a watershed-style blue region showing the portion of the hierarchy merged below the current linkage threshold. The preview follows matrix zoom and pan, supports reduced `RANK` views and cropped layouts, and can be dismissed immediately with Escape. ([#342](https://github.com/broadinstitute/celldega/pull/342))

- **Clustergram row search and shared gene information** — gene rows can be searched and focused directly in the Clustergram. UniProt-backed gene names and descriptions are now shared across Clustergram row tooltips, Enrich, and Landscape transcript tooltips. ([#251](https://github.com/broadinstitute/celldega/pull/251))

- **Programmatic Clustergram matrix slices** — new `request_matrix_slice`, `request_matrix_slice_async`, and `matrix_slice_result` interfaces expose row, column, and cell slices from the live browser-side matrix. `matrix_dataframe()` provides access to the backing Python matrix when available. ([#251](https://github.com/broadinstitute/celldega/pull/251))

### Changed

- **Enrich visualization and interaction improvements** — Enrich now reports the source and size of its input gene set, provides a `CLEAR` action, respects its configured widget height, contains scrolling within the widget, and provides richer term and gene hover information including combined score, p-values, odds ratio, gene overlap, and UniProt gene information. Async enrichment updates now guard against stale results replacing a newer request. ([#251](https://github.com/broadinstitute/celldega/pull/251))

- **Improved Clustergram ↔ Enrich linking** — column, crop, and dendrogram selections can populate Enrich while preserving the source of the selection; selecting an enriched term highlights its member genes in the Clustergram; and selecting a gene in Enrich focuses the corresponding Clustergram row and linked spatial view. Single row-label selections no longer overwrite an existing enrichment gene set. ([#251](https://github.com/broadinstitute/celldega/pull/251), [#334](https://github.com/broadinstitute/celldega/pull/334))

- **Enrichment gene selection adapts to filtered views** — genes sent from a Clustergram column to Enrich are now selected from the currently visible rows and scale with the visible dimensionality using `top_gene_percent`, capped by `top_n_genes`. This avoids selecting nearly an entire reduced `RANK` view as the enrichment gene set. ([#334](https://github.com/broadinstitute/celldega/pull/334))

- **Widget lifecycle and cleanup were consolidated** — Celldega widgets now share explicit replacement and teardown behavior, with more complete cleanup of model listeners, timers, WebGL resources, observable stores, and asynchronous Parquet/WASM reader handles when widgets are closed or replaced. ([#340](https://github.com/broadinstitute/celldega/pull/340))

- **Tutorial documentation updated** — the documentation now links the Xenium `Preprocess DegaFiles and Viz Pancreas` workflow in place of the older Visium-HD preprocessing tutorial. ([#331](https://github.com/broadinstitute/celldega/pull/331))

### Fixed

- **Cosine clustering with zero or duplicate rows** — zero vectors now have well-defined cosine distances, numerical roundoff is constrained to valid distances, and the same behavior is used for both full matrices and reduced views. This also fixes dendrogram behavior around zero-distance/duplicate merges. ([#340](https://github.com/broadinstitute/celldega/pull/340), [#342](https://github.com/broadinstitute/celldega/pull/342))

- **Clustergram metadata could become stale after adding categories** — `Matrix.make_viz()` now rebuilds node metadata so newly-added row or column attributes are included correctly in the visualization. ([#251](https://github.com/broadinstitute/celldega/pull/251))

- **Clustergram visualization and interaction fixes** — numerous fixes improve filtered matrix layout, dendrogram visibility and interaction, label highlighting, row focus, tooltips, reorder animations, zoom/pan behavior, and cleanup when widgets are re-rendered or replaced. Dedicated regression coverage was added for crop filtering, dimensionality views, dendrogram cutting, zero-distance trees, row search, tooltips, and widget lifecycle. ([#251](https://github.com/broadinstitute/celldega/pull/251), [#334](https://github.com/broadinstitute/celldega/pull/334), [#340](https://github.com/broadinstitute/celldega/pull/340), [#342](https://github.com/broadinstitute/celldega/pull/342))

## [0.24.2] - 2026-08-12

Patch release fixing missing/generic documentation links on the visualization
widgets.

### Fixed

- **Visualization widgets were missing a link to their specific
  documentation.** The Celldega logo shown in the Landscape and Yearbook
  control panels linked only to the docs homepage; it now links to each
  widget's own documentation page and shows a "Documentation" tooltip on
  hover. Clustergram and Enrich, which had no logo/documentation link at all,
  now have one too.

## [0.24.1] - 2026-08-06

Patch release fixing a NumPy binary-incompatibility crash on import in
environments that already had NumPy 1.x installed.

### Fixed

- **`import celldega` failed with `ValueError: numpy.dtype size changed`** in
  environments with a preinstalled NumPy 1.x (e.g. a conda base). The `numpy>=1.23`
  floor introduced in 0.24.0 was satisfied by the existing 1.x, so it was left in
  place while NumPy-2-built wheels (`h5py`, `anndata`, ...) were installed,
  producing a dtype-ABI mismatch. The floor is now a hard `numpy>=2`, forcing the
  runtime NumPy to match the wheels.

## [0.24.0] - 2026-08-06

Removes Scanpy from the default install path and modernizes the spatial-data
stack. Cluster/gene coloring is now generated without Scanpy, several viral
(GPL) and unused dependencies are dropped, and a fresh-environment install no
longer fails on `pkg_resources`.

### Added

- **`scanpy` optional extra** — Scanpy is now installed only via
  `pip install celldega[scanpy]`, needed solely for
  `celldega.clust.Matrix.downsample_to()` (already behind a lazy import with a
  clear error message).

### Changed

- **Cluster and gene coloring no longer depend on Scanpy.** The color palettes
  in `Landscape`/`Clustergram` widgets and in `pre` (`_create_cluster_colors`,
  `make_meta_gene`) and neighborhood gradients (`_ring_colors`) are now built
  from a deterministic `colorsys` HSV generator instead of triggering a
  `sc.pl.umap` call to populate `adata.uns[...]_colors`. Widgets no longer mutate
  the caller's `AnnData`.
- **`qc.orthogonal_expression_calc` returns data instead of plotting.** It now
  returns `(results, orthogonal_summary)` DataFrames rather than rendering
  Seaborn/Matplotlib figures, so callers can plot with any library.
- **Modernized the spatial-data stack** — `spatialdata>=0.7.2,<0.8`,
  `spatialdata-io>=0.7.1`, `ome-zarr>=0.12.2`, and `zarr>=3` (with `open_zarr`
  migrated to the Zarr v3 storage API). `numpy>=2` is now required by the updated
  stack.

### Removed

- **Dropped viral/copyleft dependencies** `igraph` (GPL-2.0-or-later) and
  `leidenalg` (GPL-3.0-or-later), plus the `pytest-html` dev dependency
  (MPL-2.0) — none were imported by celldega.
- **Dropped unused runtime dependencies** `squidpy`, `dask`, and `datashader`
  (not imported by celldega; `dask`/`datashader` remain available transitively
  through `spatialdata`). Scanpy moved to an optional extra (see Added).

### Fixed

- **Fresh-environment install failed with `ModuleNotFoundError: pkg_resources`**
  ([#292]). The old `spatialdata` pin held back `xarray_schema`, which imports
  `pkg_resources` (removed in setuptools 82+). Bumping to `spatialdata>=0.7.2`
  drops `xarray_schema` entirely, fixing the import at its root.

[#292]: https://github.com/broadinstitute/celldega/issues/292

## [0.23.1] - 2026-08-05

Fixes a batch of `Yearbook` selection, coloring, and layout bugs so that
querying or clicking a gene behaves like `Landscape`, and the portrait grid
fills its container instead of leaving dead space.

### Fixed

- **Yearbook portraits all showed the same cell** — portrait centering read
  `spatial.cell_scatter_data_objects`, an array-of-objects buffer that stopped
  being populated when cell centroids moved to flat typed arrays. Every lookup
  missed, so every portrait fell back to the landscape center and a multi-cell
  selection rendered the same location repeatedly. Centering now reads the flat
  `cell_scatter_data` position buffer via `cell_name_to_index_map` (handles both
  2- and 3-coordinate data).
- **Cell polygons vanished when a gene was selected** — `get_path_color` treated
  `selected_cats` as a cluster filter, but selecting a gene stores the gene name
  there; no cluster category matched, so every polygon's alpha dropped to 0. The
  cluster filter is now applied only to `selected_cats` entries that are real
  cluster categories, so a gene selection leaves all cell boundaries visible and
  cluster-colored (matching `Landscape`).
- **Selecting a gene didn't recolor the cell centroids** — the 2D (scatterplot)
  Yearbook refreshed only the point-cloud code path, cloning the layer id without
  rebuilding its color buffer, so centroids kept their stale cluster colors. Gene
  selections now rebuild the scatterplot data, turning centroids red with opacity
  scaled by expression, as in `Landscape`.
- **Querying a gene didn't focus its transcripts** — the query flow assigned
  `genes.selected_genes` directly, leaving `genes.selected_gene_ids` (the set the
  transcript layer reads) stale, so the queried gene's transcripts were never
  emphasized over the rest. Query handling now force-sets the selection through a
  path that keeps that set in sync, dimming non-selected transcripts.
- **Clicking a gene/cluster bar didn't update the bar highlight** — the bar fill
  baked selection opacity into its color on data re-render, while a click updated
  group opacity; the two mechanisms fought and left the coloring stale. Both
  paths now share one group-opacity highlight — the selected bar is full opacity
  and bold, the rest dimmed.
- **Dead space below the Yearbook portrait grid** — the deck canvas and root
  container used a fixed height, so a width-limited grid (many columns) left a
  large gap under the last row. They are now sized to the actual grid height.

### Added

- **Gene-bar focus on Yearbook query** — running a gene query in the control
  panel now scrolls the gene bar graph to that gene and highlights it, so the
  gene of interest is visible without manual scrolling.

## [0.22.0] - 2026-08-04

Lets a manually-placed landmark carry as much (or as little) influence as
an automated cluster centroid when fitting a serial-slice alignment.

### Added

- **`calc_alignment_transform(..., manual_landmark_weight=...)`** — controls
  how a landmark with no cell count (e.g. one placed with
  `celldega.viz.Landmark`) is weighted when `weight_by_adjacent_counts=True`
  (the default). Its count is filled in from the automated counts sharing
  that fit step: their mean (`"equal"`, default — as much influence as a
  typical automated landmark), min (`"less"`), or max (`"greater"`).
  Previously a manual landmark was always pinned to a flat, neutral weight
  of `1.0` regardless of the automated centroids around it — often far
  below a real cluster's weight, so manually-added landmarks barely
  influenced the fit.
- **`source` column on landmark tables** — `calc_landmarks` now tags every
  row `"automated"`; `celldega.viz.Landmark` tags every row it creates
  `"manual"`. Threaded through `calc_alignment_transform`/
  `align_serial_slices` into `landmarks_aligned` for provenance.
- **`calc_landmarks(..., label_prefix="C-")`** — cluster centroid labels are
  now prefixed (cluster `"0"` becomes landmark label `"C-0"`) so they can't
  collide with `Landmark`'s own auto-numbered manual labels (plain
  integers) once the two tables are concatenated. Pass `""` to disable.

## [0.21.3] - 2026-08-03

Fixes a `NeighborhoodCloud` + linked `Clustergram` bug and generalizes the
linking helper beyond `Landscape`.

### Fixed

- **`NeighborhoodCloud` Clustergram links didn't recolor the cloud** —
  clicking a gene row or cluster column in a Clustergram linked via
  `landscape_clustergram`/`spatial_clustergram` updated the gene bar graph
  and selection state, but never `NeighborhoodCloud`'s own coloring.
  `NeighborhoodCloud`'s gene/cluster coloring lives in dedicated layers
  (`nbhd_cloud_shapes_layer` / `nbhd_cloud_cell_layer`), not the generic
  per-cell path `Landscape`/`CellCloud` share, and the shared
  Clustergram-click handler only ever refreshed that generic (inert, for
  this technology) path. It now routes to `NeighborhoodCloud`'s own
  selection functions instead.

- **`NeighborhoodCloud` couldn't show "meta-clusters"** — a Clustergram
  column-dendrogram cut selecting more than one cluster column silently did
  nothing for a linked `NeighborhoodCloud` (single-cluster selection only).
  `nbhd_cloud.selected_cluster_ids` now holds every selected cluster at
  once; `NeighborhoodCloud`'s shapes/cell layers highlight and load real
  cell centroids for the whole group, keeping each cluster's own color.

- **Dendrogram trapezoids animated on every redraw, not just the
  composition PROP/COUNTS toggle** — cutting the dendrogram at a different
  linkage threshold (the "slice" that produces contiguous clusters),
  reordering rows/columns, or switching viz mode all reused the same
  transition config as the PROP/COUNTS toggle, so trapezoids visibly
  morphed/slid around for redraws where the leaf groupings themselves had
  changed (not just repositioned) — reading as random appearing/sliding
  shapes rather than a meaningful animation. `update_dendro_layer_data` /
  `refresh_composition_dendro` now take an explicit `animate` flag
  (default `false`, instant snap); only the composition PROP/COUNTS toggle
  handler passes `true`.

### Added

- **`dega.viz.spatial_clustergram`** — generalizes `landscape_clustergram`
  to any of celldega's spatial widgets (`Landscape`, `CellCloud`,
  `NeighborhoodCloud`, or `Yearbook`), not just `Landscape`.
  `landscape_clustergram` still works exactly as before, now a thin alias.

## [0.21.2] - 2026-07-31

Standardizes `neighborhood-cloud`'s per-gene DegaFile writers on `AnnData`
as the single source of gene expression, and adds a cheap `AnnData`-native
cell-scatter writer for genes without a precomputed alpha shape.

### Added

- **`write_gene_cell_scatter`** — writes a capped, top-expressing cell
  scatter per gene (no alpha shape) directly from an already-loaded
  `adata.X` column, mirroring `write_gene_shapes_streaming`'s `AnnData`
  sourcing. Lets "browse any gene" scale to a much larger gene list than
  curated gene-nbhds, without requiring a per-gene `cbg/<gene>.parquet`
  file on disk first.

### Removed

- **`write_gene_shapes_from_cbg`, `write_gene_cell_scatter_from_cbg`** — the
  per-gene-`cbg/`-file writers are gone; `write_gene_shapes_streaming` and
  `write_gene_cell_scatter` now cover both use cases directly from an
  `AnnData`, since `neighborhood-cloud` DegaFiles are always built from one.

## [0.21.1] - 2026-07-31

Bug-fix release for `NeighborhoodCloud`'s beneath-view transparency artifact
(viewing the alpha-shape stack from one side showed lower slices as almost
fully transparent, since disabling WebGL depth testing to fix a worse
tearing artifact left draw order fixed regardless of camera angle).

### Fixed

- **Beneath-view transparency** — the neighborhood-cloud shapes layer now
  reorders its polygons whenever the camera crosses from viewing the
  Z-stack from above to below (or back), so the slice nearest the camera
  always draws last and correctly reads as "in front," regardless of which
  side you're viewing from. Detected cheaply from the OrbitView's live
  `rotationX` sign (a small deadband prevents flicker near the horizon) —
  no full per-frame depth sort or order-independent transparency needed,
  since the geometry is a small number of near-planar, Z-stacked slices.
- **Intra-slice neighborhood stacking** — within one slice, larger-area
  neighborhoods now consistently draw first and smaller ones last (on top),
  regardless of camera side, so a small neighborhood isn't visually
  swallowed by a larger one jittered onto a nearby Z in the same slice.
  Applied from the very first frame (not just after the first camera-side
  flip) and to newly-selected gene shapes immediately, not only to shapes
  already on screen when a flip happens.
- **Reorder latency** — the camera-side check now runs on deck.gl's raw,
  undebounced view-state callback instead of behind the existing 200ms
  debounce (which exists to protect heavier 2D-tile/viewport-bar work that
  neighborhood-cloud doesn't do) — the check itself is a cheap sign compare
  on nearly every call, and only resorts the (small) shapes array at the
  rare moment the camera actually crosses sides.

## [0.21.0] - 2026-07-30

Adds dedicated 3D-orbit widgets — `CellCloud` and `NeighborhoodCloud` — and a
new `neighborhood-cloud` DegaFiles writer, so 3D point-cloud and
neighborhood-cloud visualizations move off the `Landscape` widget onto their
own entry points. Direct new usage to `CellCloud` for point-cloud
visualizations of 3D data, and to `NeighborhoodCloud` for visualizations of
very large 3D datasets (precomputed, per-slice alpha-shape neighborhoods that
stay cheap to load regardless of cell count).

### Added

- **`celldega.viz.CellCloud`** — a dedicated widget for 3D point-cloud
  visualization, replacing `Landscape(technology="point-cloud")`. Reads a
  `cell_cloud.json` manifest (falling back to `landscape_parameters.json` for
  DegaFiles written before the rename, so existing datasets keep rendering).
- **`celldega.viz.NeighborhoodCloud`** — a dedicated widget for the
  `neighborhood-cloud` technology, replacing
  `Landscape(technology="neighborhood-cloud")`. Shows a bounded, precomputed
  alpha-shape neighborhood per cluster/slice at low zoom — cheap to load in
  full regardless of dataset size — and streams in real cells only when
  zoomed into a slice. Reads a `neighborhood_cloud.json` manifest with the
  same fallback behavior as `CellCloud`.
- **`_SpatialWidget`** — an internal base class shared by `Landscape`,
  `CellCloud`, and `NeighborhoodCloud`, holding the trait surface and
  AnnData→parquet plumbing common to every celldega spatial widget.
- **`celldega.align.write_nbhd_cloud`** — a one-call writer that turns an
  aligned 3D `AnnData` into a `neighborhood-cloud` DegaFiles directory,
  mirroring `write_alignment_point_cloud`'s ergonomics: computes per-slice
  alpha-shape neighborhoods, writes cluster shapes, and optionally computes
  and writes gene-nbhd expression (`compute_gene_nbhds=True`) for coloring
  neighborhoods by gene. Reports progress by default (`progress_every`).
- **`celldega.nbhd.alpha_shape_cell_clusters_by_slice`** gained a
  `progress_every` parameter (off by default) for reporting progress on
  large, many-slice datasets.

### Changed

- **JS `is_point_cloud_technology` renamed to `is_orbit_technology`** — the
  predicate now covers both the `point-cloud` and `neighborhood-cloud`
  technology families, which share the same 3D-orbit camera behavior.

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
