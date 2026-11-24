"""Set-level collections: sets of cells (clusters, domains, annotations) as observations.

``SetCollection`` builds one row per set from a cell-level label column, and
keeps a sparse ``sets x cells`` ``membership`` modality recording exactly which
cells are in each set. From it, ``calc_signature`` (gene or protein signatures),
``calc_population`` (composition) and ``calc_overlap`` (set-to-set overlap)
derive further feature spaces. ``concat_sets`` stacks collections from several
clusterings or algorithms to compare them. See ``celldega.collection`` for the
shared collection model.
"""

from celldega.set.collection import SetCollection, concat_sets


SetCollection.__module__ = __name__


__all__ = [
    "SetCollection",
    "concat_sets",
]
