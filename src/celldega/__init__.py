from importlib import import_module
import importlib.metadata  # temporary fix for libpysal warning
import warnings

from celldega import clust, collection, dataset, select, viz
from celldega.collection import CelldegaCollection
from celldega.dataset import DatasetCollection
from celldega.nbhd import alpha_shape
from celldega.nbhd.collection import NeighborhoodCollection
from celldega.pre import landscape
from celldega.qc import qc_segmentation
from celldega.viz import Clustergram, Landscape, Yearbook


warnings.filterwarnings("ignore", category=FutureWarning)

try:
    __version__ = importlib.metadata.version("celldega")
except importlib.metadata.PackageNotFoundError:
    __version__ = "unknown"


def __dir__() -> list[str]:
    return sorted([*globals(), *__all__])


__all__ = [
    "CelldegaCollection",
    "Clustergram",
    "DatasetCollection",
    "Landscape",
    "NeighborhoodCollection",
    "Yearbook",
    "alpha_shape",
    "clust",
    "collection",
    "dataset",
    "landscape",
    "qc_segmentation",
    "select",
]
