# Celldega File Formats

Celldega uses two complementary storage approaches: **DegaFiles** prepare
spatial data for interactive rendering, and **AnnData Zarr** stores analysis
inputs and visualization data. CellCloud can read either format; AnnData Zarr
also supports single-cell Landscape data and complete clustered Matrix objects.
Both can be served over HTTP from a local server or cloud storage.

| Format | Contents | Used by |
| --- | --- | --- |
| Landscape DegaFiles | Image pyramids, cell centroids, tiled boundaries/transcripts, per-gene expression, and a manifest | Landscape and Yearbook |
| Point-cloud DegaFiles | XYZ cell positions, categories, per-gene expression, and a manifest | CellCloud |
| Cell-level AnnData Zarr | Cell metadata, optional UMAP or XYZ positions, and a CSC expression matrix | Single-cell Landscape, CellCloud, and Python analysis |
| Analysis AnnData Zarr | Values, observation/variable metadata, and any layers or analysis annotations saved on the AnnData | Python inputs to Matrix |
| Clustered Matrix AnnData Zarr | Values plus clustering, precomputed views, colors, metadata, and optional sizes | Python Matrix/Clustergram and browser Clustergram |
| Cell-type signature AnnData Zarr | A small dense cell-type-by-gene matrix with units and grouping metadata | UMAP/XY viewport expression estimates |

See the [Landscape guide](../visualizations/landscape/index.md) for spatial and
**low dimensional embedding landscapes** (UMAP/XY), and the
[Matrix Python API](../python/clust/api.md) for analysis and persistence.
For an end-to-end preparation and sharing workflow, see
[generating DegaFiles](usage/index.md#prepare-degafiles-from-instrument-output)
and [hosting prepared data](usage/index.md#host-and-share-prepared-data).

<span id="landscapefiles"></span>

## DegaFiles

DegaFiles are a directory of
visualization-specific files written by the [pre module](../python/pre/api.md).
They complement an analysis AnnData or SpatialData object: microscopy images,
spatial geometry, and expression are arranged for the browser to request the
parts needed for its current view.

### Landscape layout

A typical dataset using individual tile files has this layout. Available image
channels and segmentation variants depend on the input technology.

```text
DegaFiles/
├── landscape_parameters.json
├── cell_metadata.parquet
├── cell_clusters/
│   ├── cluster.parquet
│   └── meta_cluster.parquet
├── cbg/
│   └── <gene>.parquet
├── meta_gene.parquet
├── df_sig.parquet
├── cell_segmentation/
│   └── <tile>.parquet
├── transcript_tiles/
│   └── <tile>.parquet
├── pyramid_images/
│   ├── <channel>.dzi
│   └── <channel>_files/<zoom>/<tile>.webp
└── micron_to_image_transform.csv
```

| File or directory | Role in Landscape |
| --- | --- |
| `landscape_parameters.json` | Technology, tile size, image channels/format, segmentation variants, and optional row-group or aligned H&E configuration |
| `cell_metadata.parquet` | Cell identifiers and centroid geometry used to position the cell scatter |
| `cell_clusters/cluster.parquet` | Default cell-to-cluster assignments |
| `cell_clusters/meta_cluster.parquet` | Cluster colors and whole-dataset cell counts |
| `cbg/<gene>.parquet` | Nonzero expression values for one gene, used for cell coloring and XY axes |
| `meta_gene.parquet` | Gene statistics such as mean, standard deviation, maximum, detection proportion, and color |
| `df_sig.parquet` | Genes by default clusters: mean counts per cell, also used for UMAP/XY viewport estimates |
| `cell_segmentation/` | Spatially tiled cell-boundary polygons |
| `transcript_tiles/` | Spatially tiled transcript coordinates and gene identities |
| `pyramid_images/` | Deep Zoom metadata and image tiles at multiple resolutions |
| `micron_to_image_transform.csv` | Affine mapping from physical tissue coordinates to reference-image pixels |

Some datasets use compact integer cell/gene identifiers. Readers resolve them
against the dataset's name ordering; use the preprocessing writers to keep
identifiers consistent across centroids, expression, boundaries, and transcripts.

#### How Landscape reads DegaFiles

1. The Python widget supplies `base_url` and display options. Optional `adata`
   supplies cell attributes, cluster colors, and `obsm["X_umap"]`; its
   `obs_names` must match the DegaFiles cell IDs.
2. The browser reads the manifest, centroid and cluster data, and gene
   metadata to initialize the view.
3. Panning and zooming request image tiles at the appropriate resolution.
   Transcript and cell-boundary tiles load automatically at close zoom, or on
   demand through TRX at intermediate zoom.
4. Selecting a gene reads its expression data to color cells. XY uses the
   same reader to position cells by the expression of its two axis genes.
5. UMAP/XY viewport bars count visible cell types. With matching signatures,
   gene bars estimate local mean expression from those counts; selected-gene
   coloring and XY axes use actual cell expression.

```python
import celldega as dega

port = dega.viz.get_local_server(file_server_root="data")
landscape = dega.viz.Landscape(
    base_url=f"http://localhost:{port}/DegaFiles",
    adata=adata,
    cluster_attr="cell_type",
)
```

The browser reads the hosted files directly. A separate analysis service is
not required to render prepared datasets. Cross-origin hosting must allow
browser requests; efficient row-group reads also require HTTP byte ranges.

Source: [Python preprocessing](https://github.com/broadinstitute/celldega/blob/main/src/celldega/pre/__init__.py),
[widget metadata/URL handling](https://github.com/broadinstitute/celldega/blob/main/src/celldega/viz/widget.py),
[browser initialization](https://github.com/broadinstitute/celldega/blob/main/js/viz/landscape_ist.js),
[viewport loading](https://github.com/broadinstitute/celldega/blob/main/js/deck-gl/core/calc_viewport.js),
and [gene-expression loading](https://github.com/broadinstitute/celldega/blob/main/js/global_variables/cell_exp_array.js).

### Row Group Storage Mode (Optional)

Row-group storage is an optional DegaFiles layout. It packs many logical
tiles or genes into fewer Parquet files while retaining partial reads in the
browser. This reduces the number of files to host and distribute.

Enable it during preprocessing:

```python
dega.pre.main(
    sample="Xenium_Sample",
    data_root_dir="data/xenium_data",
    path_dega_files="data/DegaFiles",
    tile_size=250,
    use_row_groups=True,
    max_row_groups_per_file=400,
)
```

The input dataset is `data/xenium_data/Xenium_Sample`. Large outputs are split
into chunk files; `max_row_groups_per_file` controls the gene/vector chunks,
while image packing has its own chunk size.

```text
DegaFiles/
├── landscape_parameters.json
├── cell_metadata.parquet
├── cell_clusters/
├── meta_gene.parquet
├── df_sig.parquet
├── cbg/chunk_<n>.parquet
├── transcripts/chunk_<n>.parquet
├── cell_segmentation/chunk_<n>.parquet
└── pyramid_images/
    ├── <channel>.dzi
    └── <channel>/chunk_<n>.parquet
```

| Data | Logical row group | Browser lookup |
| --- | --- | --- |
| Transcripts | One spatial tile | Visible tile coordinates |
| Cell boundaries | One spatial tile | The same spatial tile grid |
| Cell-by-gene expression | One gene | Gene-to-row-group metadata |
| Image pyramid | One image tile | Channel, zoom level, and tile coordinates |

The manifest's `use_row_groups` flag selects the readers. `tile_grid` records
the grid dimensions, and `row_group_files` lists each data type's directory,
chunk files, and row-group counts. Image entries also contain zoom information.
Readers also support older layouts with a single Parquet file per data type.

For spatial vector tiles, the logical index is
`tile_x * num_tiles_y + tile_y`. Empty tiles retain their grid positions, and
chunk metadata maps the logical index to a file and local row group. Parquet
footer metadata supplies the byte ranges for that group's data.

The browser uses HTTP Range requests to read the required groups. Hosting must
support byte ranges and, for cross-origin access, CORS. The readers require
range-capable hosting; there is no general whole-file fallback. Celldega's local
file server, `viz.get_local_server`, supports byte ranges from version 0.28.1. Larger chunks
reduce file counts but increase footer and memory costs. Individual-tile
DegaFiles remain supported, with `use_row_groups=False`.

Source: [preprocessing options](https://github.com/broadinstitute/celldega/blob/main/src/celldega/pre/run_pre_processing.py),
[tile reader](https://github.com/broadinstitute/celldega/blob/main/js/read_parquet/row_group_tile_reader.js),
[gene reader](https://github.com/broadinstitute/celldega/blob/main/js/read_parquet/cbg_row_group_reader.js),
and [image reader](https://github.com/broadinstitute/celldega/blob/main/js/read_parquet/image_row_group_reader.js).

### Adding an aligned H&E background

`pre.add_aligned_he()` adds an RGB image pyramid and an `aligned_he` manifest
entry to existing DegaFiles:

```python
dega.pre.add_aligned_he(
    "data/DegaFiles",
    "sample_he.ome.tif",
    alignment="sample_he_imagealignment.csv",
)
```

The supplied 3×3 affine maps H&E pixels into reference-image pixels. If the
image already shares the reference grid, omit `alignment`. Landscape and
Yearbook then expose a Fluorescence/H&E selector using the same cell and
transcript overlays. See [Add aligned H&E to DegaFiles](../python/aligned_he.md)
for requirements and the example workflow.

Source: [H&E importer](https://github.com/broadinstitute/celldega/blob/main/src/celldega/pre/aligned_he.py)
and [background selector](https://github.com/broadinstitute/celldega/blob/main/js/ui/image_source.js).

## AnnData Zarr for a single-cell Landscape

`Landscape(zarr_url=...)` reads a cell-level AnnData Zarr instead of
DegaFiles. This path uses `technology="Chromium"` and supports UMAP and XY.

| AnnData location | Meaning |
| --- | --- |
| `obs_names` / `var_names` | Cell IDs / gene names |
| `obs[cluster_attr]` | Cell categories used for colors and composition bars |
| Other requested `obs` columns | Cell attributes selected through `cell_attr` |
| `uns[f"{cluster_attr}_colors"]` | Optional palette in category order |
| `obsm["X_umap"]` | Optional UMAP coordinates |
| CSC `X` or a CSC layer | Expression fetched one gene at a time |
| `var["mean"]`, `var["max"]`, `var["color"]` | Optional gene statistics and colors |

For a sparse counts layer:

```python
import zarr

adata.layers["counts_csc"] = adata.layers["counts"].tocsc()
adata.write_zarr("cells.zarr")
zarr.consolidate_metadata("cells.zarr")

landscape = dega.viz.Landscape(
    zarr_url="cells.zarr",
    zarr_layer="counts_csc",
    cluster_attr="cell_type",
)
```

The browser uses Zarrita to read Zarr v2 or v3. It loads cell/gene metadata,
UMAP positions, and the CSC column pointers, then slices `data` and `indices`
for requested genes. It does not load the entire cell-by-gene expression
matrix. Without `var["mean"]`, the initial gene ranking uses detection
fraction; without `var["max"]`, the maximum is computed when a gene loads.

Choose the layer with `zarr_layer`. Otherwise, CSC `X` is preferred, then the
only discoverable CSC layer. Consolidated metadata permits layer discovery;
an explicit `zarr_layer` also works without consolidation. Dense and CSR
expression matrices need a CSC copy for this Landscape reader.

Pass an HTTP(S) URL or a local store beneath the working directory; Python
serves local paths over HTTP. Python does not open the expression matrix.
If `adata` is also supplied, its metadata, colors, and UMAP take precedence.
Pass one of `base_url` or `zarr_url`.

Cell-type signature stores are separate from this cell-level store. They
contain dense, finite, nonnegative means and `uns["viewport_signature"]`
grouping/units metadata. See
[viewport estimates](../visualizations/landscape/umap-xy.md#viewport-cell-types-and-estimated-expression)
for `adata_sig` and `gene_signature_url`, including exact counts versus
estimated expression.

Source: [AnnData Zarr reader](https://github.com/broadinstitute/celldega/blob/main/js/read_zarr/anndata_zarr.js),
[Landscape entry point](https://github.com/broadinstitute/celldega/blob/main/js/celldega.js),
[signature reader](https://github.com/broadinstitute/celldega/blob/main/js/read_zarr/gene_signatures.js),
and [viewport summaries](https://github.com/broadinstitute/celldega/blob/main/js/umap/viewport_summary.js).

## AnnData Zarr for CellCloud

`CellCloud(zarr_url=...)` reads a self-contained cell-level AnnData Zarr store
as an alternative to [point-cloud DegaFiles](#point-cloud-degafiles).
Both sources support 3D positions, cluster colors, on-demand gene-expression
coloring, named alignments, and links to a Clustergram.

| AnnData location | Meaning in CellCloud |
| --- | --- |
| `obs_names` / `var_names` | Original cell IDs / gene names |
| `obs[cluster_attr]` | Categories used to color cells |
| `uns[f"{cluster_attr}_colors"]` | Palette in category order |
| `obsm["spatial"]` | Default cell positions, shape `(n_cells, 3)`, in microns |
| `obsm["spatial_<alignment>"]` | Optional named XYZ alignment in the same cell order |
| CSC `X` or a CSC layer | Sparse expression indexed by zero-based observation position |
| `var["mean"]`, `var["max"]`, `var["color"]` | Gene statistics and colors |
| `uns["cell_cloud"]` | Export metadata: alignment names, coordinate units, and optional rounding resolution |

[`pre.write_point_cloud_zarr`](../python/pre/api.md) prepares this layout from
an AnnData. It writes CSC expression, consolidated Zarr v2 metadata, and
compressed position arrays; its default 1 µm rounding uses int32 coordinates.
Original cell IDs remain in `obs_names`, while numeric row positions index
expression. The writer requires a new output path unless `overwrite=True`
is explicitly selected.

```python
dega.pre.write_point_cloud_zarr(
    adata,
    "data/cells.zarr",
    cluster_key="cell_type",
    coordinate_resolution=1.0,
)

cell_cloud = dega.viz.CellCloud(
    zarr_url="data/cells.zarr",
    cluster_attr="cell_type",
)
```

The browser loads cell IDs, category labels and colors, positions, and CSC
column pointers to initialize the view. Selecting a gene fetches only the
chunks covering its sparse values and row indices. It does not load the
entire expression matrix. A named `alignment="neighborhood"` reads
`obsm["spatial_neighborhood"]`; omit `alignment` to use `obsm["spatial"]`.
Use `zarr_layer` when the expression is in a CSC layer rather than `X`.

Pass an HTTP(S) URL, or a local store beneath the working directory; Python
serves local paths over HTTP. Pass one of `base_url` or `zarr_url` per widget.
See the [CellCloud guide](../visualizations/cell-cloud.md) and
[3D mouse brain example](../gallery/gallery_broad_allen_mouse_brain_3d.md)
for equivalent DegaFiles and Zarr usage.

Source: [point-cloud exporters](https://github.com/broadinstitute/celldega/blob/main/src/celldega/pre/point_cloud.py),
[CellCloud Python widget](https://github.com/broadinstitute/celldega/blob/main/src/celldega/viz/cloud.py),
[AnnData Zarr reader](https://github.com/broadinstitute/celldega/blob/main/js/read_zarr/anndata_zarr.js),
and [cell initialization](https://github.com/broadinstitute/celldega/blob/main/js/deck-gl/layers/cell_layer.js).

## AnnData Zarr before and after Matrix clustering

Both stages use AnnData's observations-by-variables orientation. A Matrix
displays the transpose: genes/features are rows, and cells/groups are columns.

### Before clustering: save the analysis input

Save the AnnData used to construct a Matrix, including the layers and
annotations needed for the analysis:

```python
import anndata as ad
import celldega as dega

adata.write_zarr("matrix_input.zarr")
loaded = ad.read_zarr("matrix_input.zarr")
mat = dega.clust.Matrix(loaded)
mat.cluster()
```

For an already prepared, unclustered Matrix,
`mat.to_adata().write_zarr("matrix_values.zarr")` saves its current values and
row/column metadata. Rebuild it with `Matrix(ad.read_zarr(...))`.
`to_adata()` does not preserve the Matrix's size matrix, colors, axis-entity
settings, marker rankings, or clustering/view state. Save the original
AnnData when its layers and analysis annotations are needed.

### After clustering: save the complete Matrix (experimental)

`Matrix.write_zarr()` requires `cluster()` first and preserves:

- Values and the optional dot-size matrix.
- Row and column metadata.
- Dendrogram orders and linkages.
- Precomputed views.
- Colors, visualization settings, axis entities, and marker rankings when present.

```python
mat.cluster(view="var", levels=[100, 500])
mat.write_zarr("clustered_matrix.zarr")

restored = dega.clust.Matrix.read_zarr("clustered_matrix.zarr")
cgm = dega.viz.Clustergram(matrix=restored)
```

Choose view levels appropriate to the number of features. Reloading restores
the saved values and clustering without reclustering or repeating
normalization. Values are written as float32 by default; `dtype=None` retains
their existing precision. `zarr_format=3` is the default, with version 2 also
supported. `to_clustered_adata()` and `from_clustered_adata()` provide the same
conversion in memory.

| AnnData location | Saved Matrix content |
| --- | --- |
| `X` | Matrix values, transposed to observations × variables |
| `obs` / `var` | Column / row metadata |
| `layers["size"]` | Optional size values, with the same orientation as `X` |
| `obsm["celldega_nodes"]` / `varm["celldega_nodes"]` | Column / row node records, including orders and attributes |
| `uns["celldega"]["linkage"]` | Row and column dendrogram linkages |
| `uns["celldega"]["views"]` | Packed arrays for precomputed views |
| `uns["celldega"]["meta_json"]` | Versioned format metadata, view descriptions, colors, visualization settings, and axis entities |
| `uns["marker_ranks"]` | Optional marker rankings |

This is a regular AnnData Zarr store with Celldega-specific annotations.
`anndata.read_zarr()` opens it; `Matrix.read_zarr()` restores the complete
clustered object and requires those annotations. An arbitrary AnnData store
is loaded through `Matrix(anndata.read_zarr(...))` instead.

The browser renders the same clustered store without Python:

```javascript
const cgm = await celldega.clustergram(element, {
    url: "https://your-data-host/clustered_matrix.zarr",
});
```

`matrix_from_zarr()` is another rendering entry point;
`network_from_zarr()` returns the visualization network. The Matrix readers
load the saved matrix into memory. Per-gene fetching applies to the
single-cell Landscape reader, rather than these Matrix readers. See the
[Clust API](../python/clust/api.md#saving-matrix-inputs-and-clustered-objects)
and [JavaScript API](../javascript/api.md) for usage.

Source: [Matrix conversion, writer, and reader](https://github.com/broadinstitute/celldega/blob/main/src/celldega/clust/matrix.py),
[browser Matrix reader](https://github.com/broadinstitute/celldega/blob/main/js/read_zarr/network_from_zarr.js),
and [browser rendering APIs](https://github.com/broadinstitute/celldega/blob/main/js/celldega.js).

## Other DegaFiles layouts

### Point-Cloud DegaFiles

Written by [`celldega.pre.write_point_cloud_dataset`](../python/pre/api.md)
and rendered by [`CellCloud`](../visualizations/cell-cloud.md). There is no
image pyramid or transcript layer; cells are points with 3D positions.

```
point_cloud_files/
├── cell_metadata.parquet               # cell key + geometry ([x, y, z] fixed-size list)
├── cell_metadata_<name>.parquet        # optional named position variants
├── cell_ids.parquet                    # original IDs once, in the optional indexed layout
├── cell_clusters/
│   ├── cluster.parquet
│   └── meta_cluster.parquet
├── cbg/<gene>.parquet                  # expressing cells only, keyed by cell name or row index
├── meta_gene.parquet
├── cell_cloud.json                     # manifest
└── landscape_parameters.json           # same manifest, for older loaders
```

The manifest has `"technology": "point-cloud"` and an `"alignments"` list
naming the position variants. `CellCloud(alignment="<name>")` reads positions from
`cell_metadata_<name>.parquet` while clusters and genes keep loading from the
shared files, so several 3D alignments of the same cells share one dataset.
Variant names may contain only letters, digits, `.`, `_`, and `-`, and
`default` is reserved.

The writer supports two cell-key layouts:

| Layout | Geometry and cluster keys | Expression keys | Original cell identity |
| --- | --- | --- | --- |
| Name-based, the existing default (`use_int_index=False`) | String IDs in `name` | String IDs in `__index_level_0__` | Repeated in the data files |
| Indexed (`use_int_index=True`) | uint32 row positions in `name` | uint32 row positions in `__index_level_0__` | Stored once in `cell_ids.parquet`, whose `name` column follows canonical row order |

For an indexed dataset, the manifest records `"use_int_index": true` and
`"cell_ids": "cell_ids.parquet"`. Geometry rows follow the canonical
`0..n_cells-1` order. Appending an alignment requires exactly the same original
cell IDs; the writer reorders its positions to match before writing.
The browser resolves original IDs for selections and tooltips while reading
expression by numeric row index.

Use `coordinate_resolution=1.0` with micron inputs to round XYZ to the nearest
micron and store int32 coordinates. This changes each axis by at most 0.5 µm.
The manifest records the resolution. With the default `None`, coordinates
remain float32. `compression="zstd", compression_level=6` provides a compact
Parquet alternative to the default Snappy codec. These options reduce data
transfer and decoding costs; the number of rendered cells is unchanged.

See the [CellCloud preparation examples](../visualizations/cell-cloud.md#prepare-either-format).

Source: [point-cloud writer](https://github.com/broadinstitute/celldega/blob/main/src/celldega/pre/point_cloud.py),
[indexed identity reader](https://github.com/broadinstitute/celldega/blob/main/js/global_variables/cell_names_array.js),
and [cell initialization](https://github.com/broadinstitute/celldega/blob/main/js/deck-gl/layers/cell_layer.js).

### Neighborhood-Cloud DegaFiles

Written by [`celldega.pre.write_nbhd_cloud_dataset`](../python/pre/api.md) from
a cell-level `AnnData` plus a `GeoDataFrame` of per-slice neighborhoods (e.g.
[`celldega.nbhd.alpha_shape_cell_clusters_by_slice`](../python/nbhd/api.md)),
and rendered by [`NeighborhoodCloud`](../visualizations/neighborhood-cloud.md).

```
nbhd_cloud_files/
├── nbhd_cloud/
│   ├── meta_slice.parquet              # slice_id, z, centroid_x/y/z, cell_count
│   ├── meta_neighborhood.parquet       # neighborhood_id, cluster_id, slice_id, color, area, cell_count, inv_alpha
│   ├── shapes/by_slice/slice_<id>.parquet   # one row per neighborhood, geometry_geojson (XYZ)
│   └── cells/
│       ├── by_cluster/cluster_<id>.parquet  # cell_id, x, y, z, cluster_id, slice_id
│       └── by_gene/<gene>.parquet           # optional top-expressing cells per gene
├── cell_clusters/meta_cluster.parquet
├── meta_gene.parquet
├── neighborhood_cloud.json             # manifest
└── landscape_parameters.json           # same manifest, for older loaders
```

The neighborhood `GeoDataFrame` needs unique ids (`name`, or
`neighborhood_id` / `nbhd_id`) and `slice_id`, `cluster_id`, `color`, and
`cell_count` columns. Geometry is stored as a GeoJSON string column rather than
GeoParquet so the browser can hand it straight to a deck.gl `GeoJsonLayer`.
`cells/by_gene/` is written by `celldega.pre.write_gene_cell_scatter`, with
`cells/by_gene/available_gene_scatter.json` listing the genes it covers.
