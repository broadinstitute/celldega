"""Schema containers for Celldega collection objects.

The collection schema is intentionally lightweight. These dataclasses describe
the canonical in-memory structure for aligned observations, feature spaces,
pairwise relations, hierarchy results, and metadata. They do not perform
analysis, validation, or file I/O.

Core concepts:
    Observation unit:
        The canonical row axis stored in ``obs``. In a dataset object the rows
        are datasets, samples, tissue sections, patients, or similar
        dataset-level units. In a ``NeighborhoodCollection`` the rows are
        neighborhoods or spatial regions.
    Space:
        An observation-by-feature ``AnnData`` whose ``obs_names`` are expected
        to match the parent collection's ``obs.index``.
    Relation:
        An observation-by-observation sparse matrix. Relations are separate from
        spaces because both axes are observations.
    Hierarchy:
        A lightweight result container for clustering or tree results derived
        from a named space or relation.

Expected invariants:
    - ``obs.index`` is unique and stable.
    - Every space has ``n_obs == len(obs)`` and ``obs_names == obs.index``.
    - Every relation has shape ``(len(obs), len(obs))``.
    - Every hierarchy references an existing space or relation by key.
    - ``NeighborhoodCollection.geometry``, when present, has the same index as
      ``obs``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from anndata import AnnData
import geopandas as gpd
import pandas as pd
from scipy import sparse


__all__ = [
    "CelldegaCollection",
    "HierarchyResult",
    "NeighborhoodCollection",
]


@dataclass
class HierarchyResult:
    """Clustering or hierarchy result derived from a collection input.

    This is a lightweight result container, not a live matrix object. It stores
    the identity of the input that produced the result, the method and
    parameters used, optional labels or tree ordering, and any method-specific
    payloads.

    Attributes:
        id: Stable result identifier, often ``"<input_key>__<method>"``.
        input_kind: Source type, expected to be ``"space"`` or ``"relation"``.
        input_key: Key in the parent collection's ``spaces`` or ``relations``.
        method: Method name, such as ``"hierarchical"`` or ``"leiden"``.
        params: Method parameters.
        preprocessing: Preprocessing steps used before clustering.
        labels: Optional observation-level labels indexed by observation ID.
        leaf_order: Optional ordered list of observation IDs.
        linkage_matrix: Optional linkage/tree payload, such as a SciPy linkage
            matrix.
        graph_key: Optional graph identifier when the result was derived from a
            graph stored elsewhere.
        provenance: Free-form provenance metadata for this result.
        uns: Free-form method-specific metadata.
    """

    id: str
    input_kind: str
    input_key: str
    method: str

    params: dict[str, Any] = field(default_factory=dict)
    preprocessing: dict[str, Any] = field(default_factory=dict)

    labels: pd.Series | None = None
    leaf_order: list[str] | None = None
    linkage_matrix: Any | None = None
    graph_key: str | None = None

    provenance: dict[str, Any] = field(default_factory=dict)
    uns: dict[str, Any] = field(default_factory=dict)


@dataclass
class CelldegaCollection:
    """Base schema for collection objects with a canonical observation axis.

    The base class does not know whether observations are datasets, samples,
    neighborhoods, or spatial regions. It only defines the shared structure
    used by higher-level collection types.

    Attributes:
        obs: Canonical observation table. The index is the expected row axis for
            every space and relation.
        spaces: Named observation-by-feature ``AnnData`` objects aligned to
            ``obs``. Examples include ``"gene"``, ``"population"``,
            ``"expression"``, ``"image"``, and ``"joint"``.
        relations: Named observation-by-observation sparse matrices. Examples
            include ``"similarity"``, ``"distance"``, ``"adjacency"``,
            ``"bordering"``, and ``"overlap"``.
        hierarchies: Named clustering/tree results derived from spaces or
            relations.
        provenance: Free-form collection-level provenance metadata.
        uns: Free-form collection-level metadata.
    """

    obs: pd.DataFrame

    spaces: dict[str, AnnData] = field(default_factory=dict)
    relations: dict[str, sparse.spmatrix] = field(default_factory=dict)
    hierarchies: dict[str, HierarchyResult] = field(default_factory=dict)

    provenance: dict[str, Any] = field(default_factory=dict)
    uns: dict[str, Any] = field(default_factory=dict)


@dataclass
class NeighborhoodCollection(CelldegaCollection):
    """Neighborhood-level or spatial-region collection schema.

    Observations are neighborhoods or spatial regions. A neighborhood may be a
    hex tile, alpha-shape region, manual region, gradient ring, or another
    spatial unit with geometry and associated features.

    Recommended ``obs`` columns include:
        ``neighborhood_id``, ``sample_id``, ``dataset_id``, ``cohort_id``,
        ``neighborhood_type``, ``method``, ``area``, ``area_um2``,
        ``centroid_x``, ``centroid_y``, ``n_cells``, ``n_transcripts``,
        ``annotation``, and ``qc_pass``.

    Recommended space names include:
        ``gene``, ``population``, ``image``, ``morphology``, ``gradient``, and
        ``joint``.

    Recommended relation names include:
        ``adjacency``, ``bordering``, ``overlap``, ``distance``, ``gene_knn``,
        ``population_knn``, and ``image_knn``. Use ``bordering`` for
        boundary-sharing relationships.

    Recommended membership names include:
        ``cell_to_neighborhood``, ``transcript_to_neighborhood``,
        ``spot_to_neighborhood``, and ``pixel_to_neighborhood``.

    Attributes:
        collection_type: Literal collection type marker, defaulting to
            ``"neighborhood"``.
        geometry: Optional ``GeoDataFrame`` aligned to ``obs.index``. The
            geometry column may contain polygons, multipolygons, or points,
            depending on the neighborhood type.
        memberships: Optional sparse matrices mapping lower-level entities to
            neighborhoods. For example, ``cell_to_neighborhood`` has shape
            ``n_cells x n_neighborhoods``.
    """

    collection_type: str = "neighborhood"
    geometry: gpd.GeoDataFrame | None = None
    memberships: dict[str, sparse.spmatrix] = field(default_factory=dict)
