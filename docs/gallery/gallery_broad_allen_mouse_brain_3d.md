# Broad-Allen Developing Mouse Brain E15.5: 3D { .gallery-title-compact }

<div id="cell-cloud-container" style="position: relative; display: flex; width: 100%; height: 700px; overflow: hidden; border: 1px solid #ccc;">
    <p id="cell-cloud-broad-allen-status" role="status" style="position: absolute; top: 10px; left: 15px; z-index: 1;">Loading 3.8 million cells. The first load may take a minute or more…</p>
    <div id="cell-cloud-broad-allen" style="height: 700px; width: 100%;"></div>
</div>

- **Dataset:** 3.8 million cells from 43 coronal Xenium sections of a whole E15.5 mouse embryo brain, measured with a 480-gene panel.
- **Alignment:** sections are aligned first by Leiden cluster centroids, then by neighborhood overlap. Colors show Leiden clusters.
- **Controls:** drag to orbit and scroll to zoom. Select a cluster or gene to explore its distribution; see the [CellCloud guide](../visualizations/cell-cloud.md).
- **Data:** generated in collaboration with the [Allen Institute](https://alleninstitute.org/). The live view reads the published [DegaFiles repository](https://github.com/broadinstitute/celldega_xenium_E15.5_cell_cloud).
- **Prepare the stack:** follow the [preprocessing and alignment notebook](../examples/tutorial_notebooks/Broad-Allen_Dev-Mouse-Brain_E15.5_Align.ipynb).
- **Explore linked views:** the [visualization notebook](../examples/tutorial_notebooks/Broad-Allen_Dev-Mouse-Brain_E15.5_Viz.ipynb) introduces slice composition and links CellCloud to a Clustergram.

## Use DegaFiles or AnnData Zarr

The [preparation script](https://github.com/broadinstitute/celldega/blob/main/scripts/prepare_allen_mouse_brain_cellcloud.py)
builds new exports of these same cells and alignments, rounding positions to
the nearest 1 µm and using numeric row indices for repeated cell references.
Original cell IDs, gene counts, cluster labels, and colors are retained.
It writes a new local directory and does not upload or change the hosted data:

```bash
python scripts/prepare_allen_mouse_brain_cellcloud.py --download
```

Run this from the checkout, then choose either source in Python. The new
artifacts can be hosted separately after validation; the examples below read
the local exports.

```python
from pathlib import Path
import celldega as dega

artifacts = Path("data/allen_mouse_brain_cellcloud_v2/artifacts")
port = dega.viz.get_local_server()
options = dict(alignment="neighborhood", cluster_attr="leiden_1.0",
               rotation_x=20, rotation_orbit=-25, ini_zoom=-3.6, height=700)

from_degafiles = dega.viz.CellCloud(
    base_url=f"http://localhost:{port}/{artifacts.as_posix()}/github/xenium_E15.5_cell_cloud_v2_1um",
    **options,
)

from_zarr = dega.viz.CellCloud(
    zarr_url=artifacts / "huggingface/Allen-Broad_Dev-Mouse-Brain/E15.5/cellcloud_v2_1um.zarr",
    **options,
)

from_degafiles  # display this widget, or from_zarr
```

Both sources support cluster colors, gene-expression coloring, named
alignments, and a [linked Clustergram](../visualizations/cell-cloud-clustergram.md).
See [File Formats](../getting-started/file_formats.md#anndata-zarr-for-cellcloud)
for their storage layout.
