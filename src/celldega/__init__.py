import importlib.metadata

from celldega.viz import Landscape, Matrix
from celldega.pre import landscape
from celldega.nbhd import alpha_shape

from celldega.clust import Network

# temporary fix for libpysal warning
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)

try:
    __version__ = importlib.metadata.version("celldega")
except importlib.metadata.PackageNotFoundError:
    __version__ = "unknown"

__all__ = ["Landscape", "landscape", "Matrix"]
