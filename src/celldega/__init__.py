import importlib.metadata  # temporary fix for libpysal warning
import warnings

from celldega import clust
from celldega.clust import Network, hc
from celldega.nbhd import alpha_shape
from celldega.pre import landscape
from celldega.qc import qc_segmentation
from celldega.viz import Landscape, Matrix


warnings.filterwarnings("ignore", category=FutureWarning)

try:
    __version__ = importlib.metadata.version("celldega")
except importlib.metadata.PackageNotFoundError:
    __version__ = "unknown"

__all__ = [
    "Landscape",
    "Matrix",
    "Network",
    "alpha_shape",
    "clust",
    "hc",
    "landscape",
    "qc_segmentation",
]
