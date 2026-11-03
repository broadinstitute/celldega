# Broad-Allen Developing Mouse Brain E15.5: 3D { .gallery-title-compact }

<div id="cell-cloud-container" style="position: relative; display: flex; width: 100%; height: 700px; overflow: hidden; border: 1px solid #ccc;">
    <p id="cell-cloud-broad-allen-status" role="status" style="position: absolute; top: 10px; left: 15px; z-index: 1;">Loading 3.8 million cells. The first load may take a minute or more…</p>
    <div id="cell-cloud-broad-allen" style="height: 700px; width: 100%;"></div>
</div>

<div style="text-align: justify; font-size: 0.9em; color: gray; margin-top: 10px;">
    Celldega CellCloud of a whole E15.5 mouse embryo brain: 3.8 million cells from 43 coronal Xenium sections
    (480-gene panel), aligned in 3D in two steps (Leiden cluster centroids, then neighborhood overlap) and colored
    by Leiden cluster. Drag to orbit around the brain and scroll to zoom. Data generated in collaboration with the
    <a href="https://alleninstitute.org/" target="_blank">Allen Institute</a>. See the
    <a href="../../visualizations/cell-cloud/">CellCloud guide</a> and the
    <a href="https://github.com/broadinstitute/celldega_xenium_E15.5_cell_cloud" target="_blank">celldega_xenium_E15.5_cell_cloud</a>
    DegaFiles repository.
</div>

Follow the [preprocessing and alignment notebook](../examples/tutorial_notebooks/Broad-Allen_Dev-Mouse-Brain_E15.5_Align.ipynb)
to prepare the stack, then the
[visualization notebook](../examples/tutorial_notebooks/Broad-Allen_Dev-Mouse-Brain_E15.5_Viz.ipynb)
to explore slice composition and link the CellCloud to a Clustergram.
