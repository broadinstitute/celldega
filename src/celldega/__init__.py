import importlib.metadata

from celldega.viz.widget import Landscape, Toy


try:
    __version__ = importlib.metadata.version("celldega")
except importlib.metadata.PackageNotFoundError:
    __version__ = "unknown"


