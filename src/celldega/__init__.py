import importlib.metadata  # temporary fix for libpysal warning
import warnings
from importlib import import_module


warnings.filterwarnings("ignore", category=FutureWarning)

try:
    __version__ = importlib.metadata.version("celldega")
except importlib.metadata.PackageNotFoundError:
    __version__ = "unknown"


_LAZY_MODULES = {
    "clust": "celldega.clust",
    "select": "celldega.select",
}

_LAZY_ATTRS = {
    "Clustergram": ("celldega.viz", "Clustergram"),
    "Landscape": ("celldega.viz", "Landscape"),
    "Yearbook": ("celldega.viz", "Yearbook"),
    "alpha_shape": ("celldega.nbhd", "alpha_shape"),
    "landscape": ("celldega.pre", "landscape"),
    "qc_segmentation": ("celldega.qc", "qc_segmentation"),
}


def __getattr__(name: str):
    if name in _LAZY_MODULES:
        module = import_module(_LAZY_MODULES[name])
        globals()[name] = module
        return module

    if name in _LAZY_ATTRS:
        module_name, attr_name = _LAZY_ATTRS[name]
        attr = getattr(import_module(module_name), attr_name)
        globals()[name] = attr
        return attr

    raise AttributeError(f"module 'celldega' has no attribute {name!r}")


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
