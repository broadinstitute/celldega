"""Query and sample the cells (or other observations) of an AnnData, reproducibly.

``Selector(adata)`` is the entry point. Build a query from metadata and gene
expression (``selector.attr("cell_type") == "B cell"``,
``selector.gene("CD19") > 0``), combine queries with ``&``, ``|`` and ``~``, then
choose or rank the matches with a sampler (random, stratified, quantile bin,
rank, Gaussian). ``selector.select(...)`` returns a ``Selection``: ordered ids
plus the query and sampler that produced them, so the selection can be saved
and reproduced. A ``Yearbook`` pages through a selection's cells.
"""

from .core import (
    Attribute,
    GaussianSampler,
    QuantileBinSampler,
    Query,
    RandomSampler,
    RankSampler,
    Sampler,
    Selection,
    Selector,
    StratifiedSampler,
    query_from_dict,
    sampler_from_dict,
)


__all__ = [
    "Attribute",
    "GaussianSampler",
    "QuantileBinSampler",
    "Query",
    "RandomSampler",
    "RankSampler",
    "Sampler",
    "Selection",
    "Selector",
    "StratifiedSampler",
    "query_from_dict",
    "sampler_from_dict",
]
