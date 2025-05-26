import importlib.metadata

# temporary fix for libpysal warning
import warnings

from celldega.pre import landscape
from celldega.viz import Landscape, Matrix


warnings.filterwarnings("ignore", category=FutureWarning)

try:
    __version__ = importlib.metadata.version("celldega")
except importlib.metadata.PackageNotFoundError:
    __version__ = "unknown"

__all__ = ["Landscape", "Matrix", "landscape"]
