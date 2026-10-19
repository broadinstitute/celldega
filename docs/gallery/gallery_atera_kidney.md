# Atera Kidney non-diseased FFPE

Explore 399,120 cells in an Atera v1 WTA human kidney section, colored by the
dataset's 28 default Leiden clusters. The tissue view streams images, cell
boundaries, and gene expression from the published DegaFiles.

<div id="landscape-container" style="position: relative; display: flex; width: 100%; height: 800px; overflow: hidden; border: 1px solid #ccc;">
    <div id="landscape-atera-kidney" style="height: 800px; width: 100%;"></div>
</div>

Open the [Landscape–Clustergram tutorial](../examples/tutorial_notebooks/Atera_Kidney_Landscape-Clustergram.ipynb)
to compare default cluster signatures and explore cell-type composition by
distance from podocyte-defined glomerular footprints. The tutorial uses plain
AnnData for dotplot Clustergrams and a distance-band Composition linked to a
Landscape, with alpha shapes and gradient bands stored as GeoDataFrames.

[DegaFiles on GitHub](https://github.com/broadinstitute/Celldega_Atera_v1_WTA_Kidney_non_diseased_FFPE)
· [Annotated counts on Hugging Face](https://huggingface.co/datasets/broadinstitute/Celldega_Supporting_Data/blob/main/Atera_v1_WTA_Kidney_non_diseased_FFPE.h5ad)
