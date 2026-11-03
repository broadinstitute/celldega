# Python API Overview

Use Celldega to prepare visualization data, summarize analysis results, and
explore them in linked widgets. It fits downstream of single-cell and spatial
workflows such as Scanpy and Squidpy: most analysis functions accept standard
`AnnData`, `MuData`, and `GeoDataFrame` objects.

You can start with these objects directly. Celldega's collection classes are
useful when you want to keep several feature spaces, metadata, and relationships
organized around the same datasets, neighborhoods, or cell sets.

## Choose a module

| Module | What you use it for | Main inputs and results |
| --- | --- | --- |
| [pre](pre/api.md) | Prepare instrument output for browser visualization | Instrument files → DegaFiles; optional aligned H&E; point-cloud and neighborhood-cloud writers |
| [viz](viz/api.md) | Display and link interactive views | Prepared spatial data, analysis objects, or saved matrices → notebook widgets |
| [clust](clust/api.md) | Find patterns through hierarchical bi-clustering | Expression or other feature matrices → clustered `Matrix`, heatmaps, and dot plots |
| [nbhd](nbhd/api.md) | Define spatial neighborhoods and summarize their contents | Cell coordinates and polygons → neighborhood geometry, expression, composition, and relationships |
| [collection](collection/api.md) | Store multiple feature spaces on one observation axis | MuData-backed `CelldegaCollection`, the shared base for collection classes |
| [dataset](dataset/api.md) | Compare samples or datasets | Cell-level data → `DatasetCollection` with sample metadata, population composition, and signatures |
| [set](set/api.md) | Represent and compare groups defined by cell membership | Cell labels → `SetCollection`, signatures, composition, and overlap |
| [select](select/api.md) | Choose, rank, and sample observations | Metadata/expression queries → an ordered `Selection` for inspection or visualization |
| [align](align/api.md) | Register tissue slices in physical space | Landmarks and cell coordinates → reusable transforms and aligned coordinates |
| [qc](qc/api.md) | Inspect segmentation and transcript-assignment quality | Instrument output and segmentation assignments → summary and gene-level QC metrics |

## Start with an example

- **Single-cell expression:** [Chromium PBMC](../examples/tutorial_notebooks/Scanpy_Chromium.ipynb)
  combines Scanpy analysis with UMAP/XY Landscapes, marker dot plots, and Enrich
  using `clust` and `viz`.
- **Spatial analysis:** [Scanpy–Squidpy Xenium Pancreas](../examples/tutorial_notebooks/Scanpy-Squidpy_Xenium_Pancreas.ipynb)
  connects cell clustering and spatial neighborhood enrichment to interactive views.
- **Neighborhoods:** [Atera breast cancer neighborhoods](../examples/tutorial_notebooks/Atera_Breast_Cancer_Neighborhood_Exploration.ipynb)
  uses `nbhd`, `clust`, and `viz` for hextile niches and cell-type composition.
- **Preparing your own data:** [Atera preprocessing](../examples/brief_notebooks/Atera_Pre-process.ipynb)
  turns an instrument output bundle into DegaFiles with `pre`, then opens a Landscape.

See [Installation](../getting-started/installation.md) for Python dependencies and
optional extras, and [Usage](../getting-started/usage/index.md#prepare-degafiles-from-instrument-output)
for the preparation and hosting workflow.

## pre: prepare data for visualization

`pre` writes the files that let the browser load large spatial datasets a piece
at a time: image pyramids, cell metadata, tiled transcripts and boundaries,
per-gene expression, and a visualization manifest. `pre.main` handles Xenium
(including Atera) and MERSCOPE output bundles. Other technologies and custom data
use the appropriate readers and lower-level writers described in the reference.

Use `pre.add_aligned_he` to add an already aligned histology background, or
`pre.write_point_cloud_dataset` and `pre.write_nbhd_cloud_dataset` for the 3D views.
Preparing DegaFiles is separate from clustering an AnnData for analysis.

**Examples:** [Atera preprocessing](../examples/brief_notebooks/Atera_Pre-process.ipynb),
[custom segmentation](../examples/brief_notebooks/Custom_Segmentation.ipynb), and
[adding aligned H&E](aligned_he.md).
**Reference:** [pre API](pre/api.md) and [DegaFiles layout](../getting-started/file_formats.md#degafiles).

## viz: explore and connect results

`viz` creates the interactive notebook widgets. Landscape shows tissue data or
low dimensional embedding landscapes (UMAP/XY); Yearbook compares cell portraits;
CellCloud and NeighborhoodCloud show 3D spatial data. Clustergram compares
expression and other measurements, Composition compares category proportions or
counts, and Enrich interprets a gene set.

Link them with `viz.spatial_clustergram` or `viz.clustergram_enrich` so that a
selection in one view updates the others.

**Examples:** [Atera kidney](../examples/tutorial_notebooks/Atera_Kidney_Landscape-Clustergram.ipynb)
combines Landscape, Clustergram, Yearbook, and Composition;
[Visium HD colorectal cancer](../examples/tutorial_notebooks/Visium_HD_Human_CRC_Landscape-Clustergram-Enrich.ipynb)
connects Landscape, Clustergram, and Enrich.
**Reference:** [widget guides](../visualizations/index.md) and [viz API](viz/api.md).

## clust: hierarchically cluster high-dimensional data

`clust.Matrix` prepares a feature matrix for hierarchical bi-clustering: filter
features, normalize values, cluster both axes, and precompute different views.
For single-cell expression, `Matrix(adata, groupby="leiden")` summarizes clusters
identified in an earlier analysis, using mean expression for color and the
fraction of expressing cells for dot size.

Display the result with `viz.Clustergram`. Save a complete clustered object with
`Matrix.write_zarr` and restore it with `Matrix.read_zarr`, including its
metadata, dendrograms, colors, marker rankings, and precomputed views.

**Examples:** [Chromium PBMC](../examples/tutorial_notebooks/Scanpy_Chromium.ipynb)
and [Atera breast cancer](../examples/tutorial_notebooks/Atera_Breast_Cancer_Landscape-Clustergram.ipynb).
**Reference:** [clust API](clust/api.md) and
[advanced Clustergram usage](../visualizations/clustergram.md#advanced-usage).

## nbhd: define and analyze neighborhoods

`nbhd` builds alpha shapes around cell groups, regular hextile grids, and
inward/outward gradients around a region. Its functions summarize neighborhood
expression and cell-type composition and calculate overlap or bordering
relationships. Geometry is represented by a `GeoDataFrame`; summaries are
`AnnData` or `MuData` objects that can be clustered and visualized.

Use `NeighborhoodCollection` when you want to store geometry, feature modalities,
and neighborhood relationships together. Compute summaries with the `nbhd`
functions and attach their results to the collection.

**Examples:** [Atera breast cancer neighborhoods](../examples/tutorial_notebooks/Atera_Breast_Cancer_Neighborhood_Exploration.ipynb)
and [pancreas islet gradients](../examples/brief_notebooks/Gradient_Neighborhood_Pancreas_Islets.ipynb).
**Reference:** [nbhd API](nbhd/api.md).

## collection: keep related feature spaces together

`CelldegaCollection` is the common MuData-backed storage model used by the
collection classes. One observation axis can have several feature modalities,
shared annotations, pairwise relationships, and provenance. For example, the
same neighborhoods can have both gene-expression and cell-population summaries.
The collection stores these results; analysis and visualization functions use them.

**Example:** [Pancreas islet gradients](../examples/brief_notebooks/Gradient_Neighborhood_Pancreas_Islets.ipynb)
stores gradient geometry, population and expression summaries, and a bordering
relationship in a `NeighborhoodCollection`.
**Reference:** [collection model and API](collection/api.md).

## dataset: summarize samples and cohorts

`DatasetCollection` makes samples or datasets the observations. Build it from
cell-level metadata, retain sample annotations such as patient and condition,
and calculate population composition or expression signatures for comparison
across samples. Store the feature spaces as modalities and persist the collection
as MuData.

**Examples and reference:** [DatasetCollection construction, population summaries,
signatures, and persistence](dataset/api.md). For interactive comparisons of
group composition, see the [Composition guide](../visualizations/composition.md).

## set: compare groups defined by membership

`SetCollection` represents groups of cells without requiring spatial geometry.
Its membership matrix records exactly which cells belong to each set. Use it to
summarize cluster labels or algorithm-defined groups, compare their expression
and composition, and quantify overlap between different groupings. `concat_sets`
combines collections for cross-grouping comparisons.

**Examples and reference:** [SetCollection membership, signatures, overlap, and
persistence](set/api.md). Display its feature modalities with
[Matrix and Clustergram](clust/api.md).

## select: query and sample observations

`select.Selector` combines metadata and gene-expression filters with reproducible
sampling or ranking. It returns a `Selection`: ordered observation IDs plus
information about the query and sampling method. Use it to choose representative
cells, inspect high-expression cells, or drive a Yearbook without manually
assembling ID lists.

**Examples and reference:** [Selector queries and samplers](select/api.md) and
[choosing cells for Yearbook](../visualizations/yearbook.md#choosing-which-cells-to-show).

## align: register tissue coordinates

`align` provides a landmark-based serial-slice workflow: calculate landmarks,
fit rigid or thin-plate-spline transforms, inspect the fit, and apply the
transforms to cell positions or other points in the same coordinate system.
Save a fitted transform for reuse, then write the aligned coordinates as
point-cloud DegaFiles for CellCloud. These are transformations of physical
coordinates; expression-space integration remains part of the upstream analysis.

**Reference:** [alignment API](align/api.md).
**Visualization example:** [aligned developing mouse brain in 3D](../gallery/gallery_broad_allen_mouse_brain_3d.md).
For importing an already aligned image, use the separate
[aligned H&E workflow](aligned_he.md).

## qc: assess segmentation and transcript assignment

`qc` computes metrics such as the fraction of assigned transcripts, cell counts,
cell areas, and gene-level assignment statistics. Use these to inspect instrument
segmentations or compare a custom segmentation before interpreting the resulting
expression measurements. `qc_segmentation` writes summary and gene-level CSV files.

**Reference:** [segmentation QC API](qc/api.md).
For the related preparation workflow, see the
[custom segmentation example](../examples/brief_notebooks/Custom_Segmentation.ipynb);
that notebook demonstrates importing a segmentation, rather than running QC.
