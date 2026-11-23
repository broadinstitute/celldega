"""Hierarchical bi-clustering of feature matrices, for Clustergrams.

``Matrix`` is the entry point. Give it a ``DataFrame`` (features by observations),
an ``AnnData``, or an ``AnnData`` with ``groupby=`` to aggregate cells into
cluster signatures (with optional marker-gene ranks and dot-plot sizes). Then
normalize (``norm``), filter, and ``cluster`` it, and pass it to
``celldega.viz.Clustergram``. Any feature space clusters the same way: gene
expression, neighborhood composition, or a collection's modality.

Example::

    mat = dega.clust.Matrix(adata, groupby="leiden")
    mat.cluster()
    dega.viz.Clustergram(matrix=mat)

``cut_tree`` cuts the dendrogram into labels. ``compute_marker_ranks`` and the
``marker_ranks_*`` helpers run and store Scanpy's ``rank_genes_groups`` in a tidy
form. ``AxisEntity`` records what the rows and columns represent (genes, cells,
clusters, neighborhoods), which is how linked widgets know what a click means.
"""

# Import main classes and functions
from .constants import AxisEntity, EntityType, normalize_axis_entity
from .matrix import Matrix, marker_ranks_from_uns, marker_ranks_to_uns
from .utils import compute_marker_ranks


# Export list
__all__ = [
    "AxisEntity",
    "EntityType",
    "Matrix",
    "compute_marker_ranks",
    "marker_ranks_from_uns",
    "marker_ranks_to_uns",
    "normalize_axis_entity",
]
