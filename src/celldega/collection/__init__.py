"""MuData-backed Celldega collection schema objects."""

from celldega.collection.collection import (
    CELLDEGA_SCHEMA_VERSION,
    CELLDEGA_UNS_KEY,
    CelldegaCollection,
    _empty_mudata,
)


CelldegaCollection.__module__ = __name__


__all__ = [
    "CELLDEGA_SCHEMA_VERSION",
    "CELLDEGA_UNS_KEY",
    "CelldegaCollection",
]
