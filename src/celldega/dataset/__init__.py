"""Dataset-level collections: samples or datasets as observations, in several feature spaces.

``DatasetCollection`` makes one row per sample (from a cell-level ``AnnData``
column such as ``sample_id``) and calculates feature spaces over the samples:
``calc_population`` (cell-type proportions) and ``calc_signature`` (the
expression signature of one population, such as each sample's B cells). Each
space is an ``AnnData`` modality that clusters in a Clustergram. See
``celldega.collection`` for the shared collection model.
"""

from celldega.dataset.collection import DatasetCollection


DatasetCollection.__module__ = __name__


__all__ = [
    "DatasetCollection",
]
