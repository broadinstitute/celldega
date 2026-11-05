# Usage

Use Celldega in local or cloud notebooks, in a standalone web page, or
through Celldega-App on your desktop.

## In a notebook

Use Celldega downstream of single-cell and spatial analysis workflows, such as
Scanpy and Squidpy, to interactively visualize the results. Bring cluster
annotations, UMAP coordinates, gene expression, and neighborhood summaries from
your analysis into linked Landscape, Clustergram, and Enrich widgets.

### Example workflows

- **[Chromium PBMC: Landscape–Clustergram–Enrich](../../examples/tutorial_notebooks/Scanpy_Chromium.ipynb)**
  — analyze single-cell RNA-seq data with Scanpy, then explore clusters, UMAP/XY
  landscapes, marker-gene dot plots, and gene-set enrichment in linked views.
- **[Scanpy–Squidpy Xenium Pancreas](../../examples/tutorial_notebooks/Scanpy-Squidpy_Xenium_Pancreas.ipynb)**
  — explore Scanpy clusters and expression patterns alongside Squidpy spatial
  neighborhood-enrichment results using Landscapes and Clustergrams.

See [Example Notebooks](../../examples/index.md) for more workflows.

### Notebook options

- **Local Jupyter** — JupyterLab or Jupyter Notebook running on your own
  machine, following the standard [Installation](../installation.md)
  and [Getting Started](../index.md) guides.
- **Cloud notebook services** — hosted notebook environments such as
  [Manifold.ai](https://www.manifold.ai/),
  [Google Colab](https://colab.research.google.com/),
  [marimo](https://marimo.io/), and [molab](https://molab.marimo.io/).
  Celldega installs like any other PyPI package (`pip install celldega`); widget rendering depends on the
  service supporting the Jupyter Widgets protocol.

## Prepare DegaFiles from instrument output

For a spatial Landscape, start with the instrument's processed output bundle:
cell-by-gene counts, cell positions and boundaries, transcript coordinates, and
morphology images. Celldega arranges these into **DegaFiles** so that the browser
can load the image tiles and spatial regions needed for the current view.

### 1. Install the preprocessing dependencies

```bash
pip install "celldega[pre]"
```

Image preprocessing also requires a native
[libvips installation](https://www.libvips.org/install.html).
See [Installation](../installation.md) for the available extras.

### 2. Convert a sample into DegaFiles

Place your Xenium output folder at `data/instrument/Xenium_Sample`, then run:

```python
import celldega as dega

dega.pre.main(
    sample="Xenium_Sample",
    data_root_dir="data/instrument",
    path_dega_files="data/DegaFiles/Xenium_Sample",
    tile_size=250,
    image_tile_layer="all",
)
```

`pre.main` detects Xenium (including Atera) and MERSCOPE bundles. The exact
input files depend on the instrument; see the [pre API](../../python/pre/api.md)
and [Atera preprocessing notebook](../../examples/brief_notebooks/Atera_Pre-process.ipynb).
The output includes a manifest, cell metadata, gene expression, image pyramids,
and tiled transcripts and boundaries. See [DegaFiles](../file_formats.md#degafiles)
for the layout and optional row-group storage.

To add a histology background to existing DegaFiles, follow the
[aligned H&E workflow](../../python/aligned_he.md). For an alternative cell
segmentation, see the [custom segmentation notebook](../../examples/brief_notebooks/Custom_Segmentation.ipynb).

### 3. View the prepared data locally

For the individual-tile layout written above, start a file server at the
DegaFiles directory and pass its HTTP URL to Landscape:

```python
port = dega.viz.get_local_server(
    file_server_root="data/DegaFiles/Xenium_Sample"
)

landscape = dega.viz.Landscape(
    base_url=f"http://localhost:{port}",
    height=600,
)
landscape
```

Keep the notebook kernel running while this server is in use. For remote
notebook kernels, use the environment's browser-accessible forwarded URL.
The [local server notebook](../../examples/brief_notebooks/Landscape_Local_Server.ipynb)
explains the working-directory and URL conventions.

Analysis and visualization preparation can run separately. Pass an analyzed
`adata` to Landscape to supply cluster labels, colors, and UMAP coordinates;
its cell IDs must match the DegaFiles. A single-cell UMAP/XY Landscape can
instead use [AnnData Zarr](../../visualizations/landscape/umap-xy.md#single-cell-landscapes-from-anndata-zarr)
directly, without spatial DegaFiles.

## Host and share prepared data

Upload the **complete DegaFiles directory**, preserving its subdirectories, and
set `base_url` to the browser-readable HTTP(S) URL of that directory. The root
must contain `landscape_parameters.json`. Prepared Zarr stores are likewise
served as directories containing their metadata and chunks.

| Hosting option | How to use it |
| --- | --- |
| Local machine | Serve the directory with `viz.get_local_server` as above for individual tile files. Other users need a shared host to view the same data. |
| GitHub | Use a raw-content directory URL, as in the [Xenium example](../../examples/brief_notebooks/Landscape_View_Xenium.ipynb). Suitable for smaller prepared examples; consider [GitHub's file and repository limits](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github) when choosing a host. |
| Hugging Face dataset repository | Upload the prepared files and use a `https://huggingface.co/datasets/ORG/REPO/resolve/REVISION/FOLDER` URL. See [uploading datasets](https://huggingface.co/docs/hub/datasets-adding), our [supporting data](https://huggingface.co/datasets/broadinstitute/Celldega_Supporting_Data/tree/main), and the [PBMC notebook](../../examples/tutorial_notebooks/Scanpy_Chromium.ipynb) for hosted AnnData and Matrix Zarr examples. |
| Cloud object-storage bucket | Upload under one prefix and use its HTTPS endpoint, such as an S3, Google Cloud Storage, or Azure Blob endpoint. Configure browser access and, for packed row-group files, byte-range reads. [S3's CORS guide](https://docs.aws.amazon.com/AmazonS3/latest/userguide/enabling-cors-examples.html) explains one provider's configuration. |
| Manifold-managed storage or bucket | Use a browser-readable data endpoint supported by your Manifold workspace, with the workspace's access permissions. [Manifold's Celldega example](https://www.manifold.ai/resources/your-old-data-has-new-stories-to-tell) describes running Celldega on the platform; the bucket endpoint and access setup depend on the workspace. |

The browser fetches the data directly. A path such as `s3://bucket/prefix` or a
local filesystem path is not a `base_url`; use the corresponding HTTP(S)
endpoint. Cross-origin hosts must allow requests from the notebook or web page,
and access permissions must work for browser requests as well as Python downloads.

**Packed row-group DegaFiles require HTTP byte-range support**, including
`206 Partial Content` responses. Celldega's simple local file-server helper adds
CORS headers but does not implement byte ranges; use the individual-tile layout
with that helper, or a range-capable host for packed files. See
[row-group hosting requirements](../file_formats.md#row-group-storage-mode-optional)
and the [HTTP range-request guide](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/Range_requests).

For reproducible examples, link a fixed data revision and include the source
dataset, license, and preparation steps with the hosted files.

For example, after creating a Hugging Face dataset repository and setting up
the [Hugging Face CLI](https://huggingface.co/docs/huggingface_hub/en/guides/cli),
upload the entire prepared sample folder:

```bash
hf upload ORG/REPO data/DegaFiles/Xenium_Sample Xenium_Sample --repo-type dataset
```

Its Landscape URL would be
`https://huggingface.co/datasets/ORG/REPO/resolve/main/Xenium_Sample`.
Replace `main` with the uploaded commit ID when publishing a fixed example,
and check the browser and range-request requirements above for your layout.

## On a web page

Celldega's visualizations also run outside of a notebook entirely, as a
stand-alone JavaScript library against publicly hosted data — see the
[JavaScript API](../../javascript/index.md). The [Gallery](../../gallery/index.md)
is a collection of such stand-alone web pages showcasing datasets across
technologies (Xenium, CosMx, Visium HD, and more).

<span id="desktop-app-alpha"></span>

## Desktop app

[Celldega-App](../desktop-app.md) opens local or remote DegaFiles and prepared
single-cell examples. The current [0.7.1 build](https://github.com/broadinstitute/celldega-app/releases/tag/v0.7.1)
provides linked Landscape–Clustergram panels in one window or separate windows,
Yearbook cell portraits, and saved Clustergrams that reopen without recomputing.
Viewing examples and saved results needs no notebook or Python installation;
the app can provision a matching runtime for new analyses and preprocessing.

[Download the latest build](https://github.com/broadinstitute/celldega-app/releases/latest)
or follow the [desktop guide with screenshots](../desktop-app.md).
