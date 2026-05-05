import importlib.metadata  # temporary fix for libpysal warning
import warnings

from celldega import clust, datasets
from celldega.collections import (
    CelldegaCollection,
    DatasetCollection,
    HierarchyResult,
    NeighborhoodCollection,
)
from celldega.datasets import calc_dataset_by_pop, dataset_collection_from_adata
from celldega.nbhd import alpha_shape
from celldega.pre import landscape
from celldega.qc import qc_segmentation
from celldega.viz import Clustergram, Landscape, Yearbook


warnings.filterwarnings("ignore", category=FutureWarning)

try:
    __version__ = importlib.metadata.version("celldega")
except importlib.metadata.PackageNotFoundError:
    __version__ = "unknown"

__all__ = [
    "CelldegaCollection",
    "Clustergram",
    "DatasetCollection",
    "HierarchyResult",
    "Landscape",
    "NeighborhoodCollection",
    "Yearbook",
    "alpha_shape",
    "calc_dataset_by_pop",
    "clust",
    "dataset_collection_from_adata",
    "datasets",
    "landscape",
    "qc_segmentation",
]
