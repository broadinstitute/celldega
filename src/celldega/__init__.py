import importlib.metadata

from celldega.viz import Landscape, Matrix, MatrixNew
from celldega.pre import landscape
from celldega.qc import ist_segmentation_metrics

try:
    __version__ = importlib.metadata.version("celldega")
except importlib.metadata.PackageNotFoundError:
    __version__ = "unknown"

__all__ = ["Landscape", "landscape", "Matrix", "MatrixNew"]
