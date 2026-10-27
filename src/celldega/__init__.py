from importlib import import_module
import importlib.metadata  # temporary fix for libpysal warning
import warnings

from celldega import align, clust, collection, dataset, nbhd, select, set, viz
from celldega.align import align_serial_slices
from celldega.collection import CelldegaCollection
from celldega.dataset import DatasetCollection
from celldega.nbhd import NeighborhoodCollection, alpha_shape
from celldega.pre import landscape
from celldega.qc import qc_segmentation
from celldega.set import SetCollection, concat_sets
from celldega.viz import (
    CellCloud,
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
