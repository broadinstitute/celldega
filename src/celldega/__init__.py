from importlib import import_module
import importlib.metadata  # temporary fix for libpysal warning
import warnings

from celldega import clust, select, viz
from celldega.nbhd import alpha_shape
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
    "Clustergram",
    "Landscape",
    "Yearbook",
    "alpha_shape",
    "clust",
    "landscape",
    "qc_segmentation",
    "select",
]
