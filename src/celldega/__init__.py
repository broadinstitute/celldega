import importlib.metadata

from celldega.viz import Landscape, Toy
from celldega.pre import landscape

try:
    __version__ = importlib.metadata.version("celldega")
except importlib.metadata.PackageNotFoundError:
    __version__ = "unknown"

__all__ = ["Landscape", "Toy", "landscape"]