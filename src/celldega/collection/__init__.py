"""MuData-backed Celldega collection schema objects."""

from celldega.collection.collection import (
    CELLDEGA_SCHEMA_VERSION,
    CELLDEGA_UNS_KEY,
    CelldegaCollection,
    HierarchyResult,
    _empty_mudata,
)


for _cls in (CelldegaCollection, HierarchyResult):
    _cls.__module__ = __name__
del _cls


def __getattr__(name: str):
    if name == "NeighborhoodCollection":
        from celldega.nbhd.collection import NeighborhoodCollection

        NeighborhoodCollection.__module__ = __name__
        return NeighborhoodCollection
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


__all__ = [
    "CELLDEGA_SCHEMA_VERSION",
    "CELLDEGA_UNS_KEY",
    "CelldegaCollection",
    "HierarchyResult",
    "NeighborhoodCollection",
]
