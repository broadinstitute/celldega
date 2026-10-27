"""Set-level Celldega collection objects."""

from celldega.set.collection import SetCollection, concat_sets


SetCollection.__module__ = __name__


__all__ = [
    "SetCollection",
    "concat_sets",
]
