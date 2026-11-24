"""Celldega: linked, interactive visualization and analysis of spatial and single-cell omics.

Celldega pairs Python analysis with browser-based widgets for human-in-the-loop
work: you explore, select and annotate in the widgets, and the results come back
to Python for the next step. It sits downstream of Scanpy and Squidpy: most
functions take ``AnnData``, ``MuData`` or ``GeoDataFrame`` objects. It handles
Xenium (including Atera), MERSCOPE, Visium HD, CosMx and any single-cell
AnnData. Documentation: https://broadinstitute.github.io/celldega/ (an index for
AI agents is at https://broadinstitute.github.io/celldega/llms.txt).

Widgets (``celldega.viz``; the main ones are also on ``celldega``):

- ``Landscape``: the tissue (image, cells, transcripts, neighborhoods) or a UMAP.
- ``Clustergram``: an interactive clustered heatmap of a ``clust.Matrix``.
- ``Yearbook``: a grid of cell portraits for reviewing selected cells.
- ``Composition``: category counts or proportions compared across groups.
- ``CellCloud`` / ``NeighborhoodCloud``: 3D views of cells or neighborhood shapes.
- ``Enrich``: Enrichr gene-set enrichment of a gene list.
- ``Clerk``: an AI tool that interprets the linked widgets with Claude.

Link widgets with ``viz.spatial_clustergram``, ``viz.landscape_yearbook``,
``viz.landscape_yearbook_clustergram``, ``viz.clustergram_enrich`` or
``viz.link_clerk``. Save a view as a reproducible PNG with ``viz.snapshot`` and
rebuild it with ``viz.from_png``.

Analysis modules:

- ``pre``: instrument output to DegaFiles, which the browser streams a piece at a
  time (``pre.main``); 3D point-cloud and aligned H&E writers.
- ``clust``: ``Matrix``, hierarchical bi-clustering of any feature matrix for a
  Clustergram (``Matrix(adata, groupby="leiden")`` for cluster signatures).
- ``nbhd``: neighborhoods (alpha shapes, hextiles, gradients) and their
  composition, expression, overlap and bordering.
- ``set``, ``dataset``, ``collection``: collections of entities above the single
  cell (``SetCollection``, ``DatasetCollection``, ``NeighborhoodCollection``)
  and their feature spaces.
- ``select``: ``Selector`` queries and samples cells, for example for Yearbook.
- ``align``: stacks serial sections in 3D using the clusters they share.
- ``clerk``: the prompts and model calls behind the ``Clerk`` widget.

Example: a tissue linked to a heatmap of cluster signatures::

    import celldega as dega

    landscape = dega.Landscape(base_url=degafiles_url, adata=adata)
    mat = dega.clust.Matrix(adata, groupby="leiden")
    mat.cluster()
    cgm = dega.Clustergram(matrix=mat)
    dega.viz.spatial_clustergram(landscape, cgm)  # clicks in one update the other
"""

from importlib import import_module
import importlib.metadata  # temporary fix for libpysal warning
import warnings

from celldega import align, clerk, clust, collection, dataset, nbhd, select, set, viz
from celldega.align import align_serial_slices
from celldega.collection import CelldegaCollection
from celldega.dataset import DatasetCollection
from celldega.nbhd import NeighborhoodCollection, alpha_shape
from celldega.pre import landscape
from celldega.qc import qc_segmentation
from celldega.set import SetCollection, concat_sets
from celldega.viz import (
    CellCloud,
    Clerk,
    Clustergram,
    Composition,
    Landmark,
    Landscape,
    NeighborhoodCloud,
    Yearbook,
)


warnings.filterwarnings("ignore", category=FutureWarning)

try:
    __version__ = importlib.metadata.version("celldega")
except importlib.metadata.PackageNotFoundError:
    __version__ = "unknown"


def __dir__() -> list[str]:
    return sorted([*globals(), *__all__])


__all__ = [
    "CellCloud",
    "CelldegaCollection",
    "Clerk",
    "Clustergram",
    "Composition",
    "DatasetCollection",
    "Landmark",
    "Landscape",
    "NeighborhoodCloud",
    "NeighborhoodCollection",
    "SetCollection",
    "Yearbook",
    "align",
    "align_serial_slices",
    "alpha_shape",
    "clerk",
    "clust",
    "collection",
    "concat_sets",
    "dataset",
    "landscape",
    "nbhd",
    "qc_segmentation",
    "select",
    "set",
    "viz",
]
