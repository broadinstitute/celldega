# Broad-Allen Developing Mouse Brain E15.5: 3D { .gallery-title-compact }

<p>
    <label for="cell-cloud-broad-allen-source">Data source:</label>
    <select id="cell-cloud-broad-allen-source" aria-label="Data source">
        <option value="degafiles" selected>Compact DegaFiles (Parquet)</option>
        <option value="zarr">AnnData Zarr</option>
    </select>
</p>

<div id="cell-cloud-container" style="position: relative; display: flex; width: 100%; height: 700px; overflow: hidden; border: 1px solid #ccc;">
    <p id="cell-cloud-broad-allen-status" role="status" style="position: absolute; top: 10px; left: 15px; z-index: 1;">Loading 3.8 million cells…</p>
    <div id="cell-cloud-broad-allen" style="height: 700px; width: 100%;"></div>
</div>

- **Dataset:** 3.8 million cells from 43 coronal Xenium sections of a whole E15.5 mouse embryo brain, measured with a 480-gene panel.
- **Alignment:** sections are aligned first by Leiden cluster centroids, then by neighborhood overlap. Colors show Leiden clusters.
- **Controls:** drag to orbit and scroll to zoom. Select a cluster or gene to explore its distribution; see the [CellCloud guide](../visualizations/cell-cloud.md).
- **Data:** generated in collaboration with the [Allen Institute](https://alleninstitute.org/). Choose the [AnnData Zarr on Hugging Face](https://huggingface.co/datasets/broadinstitute/Celldega_Supporting_Data/tree/main/Allen-Broad_Dev-Mouse-Brain/E15.5/cellcloud_v2_1um.zarr) or [compact DegaFiles on GitHub](https://github.com/cornhundred/celldega_xenium_E15.5_cell_cloud/tree/8d3cd06fc1a478f386826c27ba0e900b40703a3a/xenium_E15.5_cell_cloud_compact). The [original DegaFiles](https://github.com/broadinstitute/celldega_xenium_E15.5_cell_cloud/tree/main/xenium_E15.5_cell_cloud) remain available.
- **Prepare the stack:** follow the [preprocessing and alignment notebook](../examples/tutorial_notebooks/Broad-Allen_Dev-Mouse-Brain_E15.5_Align.ipynb).
- **Explore linked views:** the [visualization notebook](../examples/tutorial_notebooks/Broad-Allen_Dev-Mouse-Brain_E15.5_Viz.ipynb) introduces slice composition and links CellCloud to a Clustergram.

## Use DegaFiles or AnnData Zarr

Both hosted sources show the same cells, clusters, and alignments. This gallery
defaults to compact Parquet DegaFiles; the
[visualization notebook](../examples/tutorial_notebooks/Broad-Allen_Dev-Mouse-Brain_E15.5_Viz.ipynb)
uses AnnData Zarr. Use the source picker above to compare them. In Python,
change only the source argument.

For this unreleased checkout, run `npm run build` and start the notebook kernel
with `CELLDEGA_LOCAL_ESM=1` before importing Celldega. This uses the new browser
reader instead of an older published bundle.

```python
import celldega as dega

options = dict(alignment="neighborhood", cluster_attr="leiden_1.0",
               rotation_x=20, rotation_orbit=-25, ini_zoom=-3.6, height=700)

from_zarr = dega.viz.CellCloud(
    zarr_url=(
        "https://huggingface.co/datasets/broadinstitute/Celldega_Supporting_Data/"
        "resolve/main/Allen-Broad_Dev-Mouse-Brain/E15.5/cellcloud_v2_1um.zarr"
    ),
    **options,
)

from_degafiles = dega.viz.CellCloud(
    base_url=(
        "https://raw.githubusercontent.com/cornhundred/celldega_xenium_E15.5_cell_cloud/"
        "8d3cd06fc1a478f386826c27ba0e900b40703a3a/xenium_E15.5_cell_cloud_compact"
    ),
    **options,
)

from_degafiles  # display this widget, or from_zarr
```

The compact DegaFiles are currently served from a fork while
[upstream PR #1](https://github.com/broadinstitute/celldega_xenium_E15.5_cell_cloud/pull/1)
awaits merge. Both sources support cluster colors, gene-expression
coloring, named alignments, and a
[linked Clustergram](../visualizations/cell-cloud-clustergram.md).
See [File Formats](../getting-started/file_formats.md#anndata-zarr-for-cellcloud)
for their storage layout.

### Measured loading performance

Compact Parquet was slightly faster in our hosted comparison, so it is the
gallery default. These are medians from three loads and first Dcx selections
per source, using the same browser renderer and bypassing browser HTTP caching:

| Source | Initial load | First Dcx coloring | Initial transfer / requests |
| --- | ---: | ---: | ---: |
| Compact Parquet on GitHub | 3.6 s | 0.67 s | 31.3 MB / 7 |
| AnnData Zarr on Hugging Face | 4.4 s | 1.08 s | 25.7 MB / 39 |

Parquet uses fewer requests, which can reduce time spent waiting on the network.
Zarr transfers fewer bytes for the initial view. For Dcx, Parquet transfers
3.34 MB in one request, versus 3.43 MB across 28 requests for Zarr. We expect
slightly faster loading with compact Parquet for this hosted example; network
conditions and CDN caching can change the result. Timings include transfer,
decoding, and rendering updates, and exclude the JavaScript bundle startup.

The complete exports are 494 MB for compact Parquet and 583 MB for Zarr, versus
4.59 GB for the original DegaFiles (9.3× and 7.9× smaller, respectively). Both
use positions rounded to 1 µm and preserve original cell IDs and gene counts.

### Prepare your own copy

The [preparation script](https://github.com/broadinstitute/celldega/blob/main/scripts/prepare_allen_mouse_brain_cellcloud.py)
builds new exports of these same cells and alignments, rounding positions to
the nearest 1 µm and using numeric row indices for repeated cell references.
Original cell IDs, gene counts, cluster labels, and colors are retained.
It writes a new local directory and does not upload or change the hosted data:

```bash
python scripts/prepare_allen_mouse_brain_cellcloud.py --download
```

Run this from the checkout to produce the new local exports. Existing hosted
files are not modified. The complete output directories can also be served
from another static host.
