import importlib.metadata

from celldega.viz import Landscape, Matrix, MatrixNew
from celldega.pre import landscape
from celldega.nbhd import alpha_shape

try:
    __version__ = importlib.metadata.version("celldega")
except importlib.metadata.PackageNotFoundError:
    __version__ = "unknown"

__all__ = ["Landscape", "landscape", "Matrix", "MatrixNew", "alpha_shape"]
