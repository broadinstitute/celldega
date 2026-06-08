"""MuData-backed Celldega collection schema objects."""

from celldega.collections.collection import (
    CELLDEGA_SCHEMA_VERSION,
    CELLDEGA_UNS_KEY,
    CelldegaCollection,
    HierarchyResult,
    NeighborhoodCollection,
    _empty_mudata,
)


for _cls in (CelldegaCollection, HierarchyResult, NeighborhoodCollection):
    _cls.__module__ = __name__
del _cls


__all__ = [
    "CELLDEGA_SCHEMA_VERSION",
    "CELLDEGA_UNS_KEY",
    "CelldegaCollection",
    "HierarchyResult",
    "NeighborhoodCollection",
]
