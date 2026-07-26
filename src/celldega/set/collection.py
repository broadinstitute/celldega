"""Set-level Celldega collection objects.

A :class:`SetCollection` is the Celldega entity for collections that are
*literally defined as sets* of some base element (most commonly cells) with no
intrinsic geometry of their own — clustering results, spatial-domain algorithm
outputs (SpaGCN, GraphST, GASTON, Points2Regions), manual annotations projected
back to cells, and so on. Each observation is one *set*; the defining modality
``membership`` is a sparse ``sets x elements`` incidence matrix, so a set never
loses track of exactly which elements belong to it.

This is deliberately the most generic aggregate collection: the element axis is
usually cells, but the same structure describes sets over genes (a gene-set
library / ``GeneCollection``, a future use case). Where ``DatasetCollection``
and ``NeighborhoodCollection`` make a *derived* feature (an expression signature,
a geometry) first-class, ``SetCollection`` makes *membership itself* the
first-class modality, from which signatures and overlaps are derived.

Status: initial sketch (branch DEGA-487). The constructor, ``calc_signature``,
``calc_population``, ``calc_overlap``, and ``concat_sets`` are implemented;
``to_nbhd`` (graduation to a ``NeighborhoodCollection``) is stubbed with its
intended API.
"""

from __future__ import annotations

from typing import Any

from anndata import AnnData
from mudata import MuData
import numpy as np
import pandas as pd
from scipy import sparse

from celldega.collection import CelldegaCollection


__all__ = [
    "SetCollection",
    "concat_sets",
]


_COORD_CANDIDATES = (
    ("center_x", "center_y"),
    ("centroid_x", "centroid_y"),
    ("x", "y"),
)


def _to_dense(matrix: Any) -> np.ndarray:
    """Return a dense ``ndarray`` for a sparse or dense matrix."""
    return np.asarray(matrix.todense()) if sparse.issparse(matrix) else np.asarray(matrix)


def _normalize_rows(values: np.ndarray, normalization: str | None) -> np.ndarray:
    """Apply per-row library-size normalization (shared shape with the dataset kernel).

    TODO(DEGA-487): factor this and the dataset module's copy into one shared
    aggregation-helpers module rather than maintaining two implementations.
    """
    if normalization is None:
        return values
    norm = normalization.lower().replace("-", "_").replace(" ", "_")
    if norm in {"none", "raw"}:
        return values
    if norm not in {"cpm", "log1p_cpm"}:
        raise ValueError("normalization must be None, 'cpm', or 'log1p_cpm'")

    normalized = values.astype(float, copy=True)
    library_size = normalized.sum(axis=1)
    valid = library_size > 0
    normalized[~valid, :] = 0
    if valid.any():
        normalized[valid, :] = normalized[valid, :] / library_size[valid, None] * 1_000_000
    if norm == "log1p_cpm":
        normalized = np.log1p(normalized)
    return normalized


def _cell_coords(adata: AnnData) -> pd.DataFrame | None:
    """Best-effort spatial coordinates per cell, tagged onto ``membership.var``.

    Carrying x/y on the element axis is what lets a ``SetCollection`` graduate to
    geometry (:meth:`SetCollection.to_nbhd`) without a round-trip to the original
    ``adata``. Looks in ``obsm['spatial']`` first, then common centroid columns.
    """
    index = pd.Index(adata.obs_names.astype(str), name="cell")
    if "spatial" in adata.obsm and np.asarray(adata.obsm["spatial"]).shape[1] >= 2:
        xy = np.asarray(adata.obsm["spatial"])[:, :2]
        return pd.DataFrame({"center_x": xy[:, 0], "center_y": xy[:, 1]}, index=index)
    for x_col, y_col in _COORD_CANDIDATES:
        if x_col in adata.obs.columns and y_col in adata.obs.columns:
            return pd.DataFrame(
                {"center_x": adata.obs[x_col].to_numpy(), "center_y": adata.obs[y_col].to_numpy()},
                index=index,
            )
    return None


def _membership_from_labels(labels: pd.Series, set_col: str) -> tuple[pd.Index, sparse.csr_matrix]:
    """Build a sparse ``sets x cells`` one-hot incidence matrix from a label column.

    Unlabelled cells (``NaN``) are dropped from every set (code ``-1``). Set ids
    follow first-appearance order of the labels.
    """
    notna = labels.notna()
    str_labels = labels.astype(str)
    set_ids = pd.Index(pd.unique(str_labels[notna]), name=set_col)
    categorical = pd.Categorical(str_labels.where(notna, other=None), categories=set_ids)
    codes = categorical.codes
    n_cells = len(labels)
    keep = codes >= 0
    membership = sparse.csr_matrix(
        (np.ones(int(keep.sum()), dtype=float), (codes[keep], np.arange(n_cells)[keep])),
        shape=(len(set_ids), n_cells),
    )
    return set_ids, membership


def _category_colors(adata: AnnData, category: str) -> dict[str, str]:
    """Map each ``category`` value to its color from ``adata.uns[f"{category}_colors"]``.

    Colors align to the categorical's ``categories`` order (scanpy convention), so
    this stays correct even for >9 clusters where a lexicographic string sort would
    not. Falls back to first-appearance order for non-categorical columns; returns
    ``{}`` when no colors are stored.
    """
    colors = adata.uns.get(f"{category}_colors")
    if colors is None or category not in adata.obs:
        return {}
    series = adata.obs[category]
    cats = (
        list(series.cat.categories.astype(str))
        if hasattr(series, "cat")
        else list(pd.unique(series.astype(str)))
    )
    return {str(cat): colors[i] for i, cat in enumerate(cats) if i < len(colors)}


def _resolve_feature_adata(data: AnnData | MuData, feature_type: str | None) -> tuple[AnnData, str]:
    """Resolve the per-cell feature matrix and its label.

    ``feature_type`` is only required when ``data`` is a ``MuData`` — there it
    names which modality to aggregate (and labels the output). For a plain
    ``AnnData`` the single matrix is unambiguous, so ``feature_type`` is optional
    and defaults to ``"gene"``.
    """
    if isinstance(data, MuData):
        if feature_type is None:
            raise ValueError("feature_type is required when data is a MuData (names the modality)")
        if feature_type not in data.mod:
            raise KeyError(f"MuData has no modality '{feature_type}'")
        return data.mod[feature_type], feature_type
    return data, (feature_type or "gene")


class SetCollection(CelldegaCollection):
    """Set-level Celldega collection backed by a ``sets x elements`` membership matrix.

    The canonical observation axis is one row per *set*; the defining modality
    ``membership`` is a sparse ``AnnData`` with sets as observations and elements
    (cells) as variables, carrying per-cell spatial coordinates in ``var`` when
    available. Feature spaces (expression signatures) and relations (set-to-set
    overlap) are derived from this membership.
    """

    def __init__(
        self,
        adata: AnnData | None = None,
        set_col: str | None = None,
        obs: pd.DataFrame | None = None,
        mdata: Any | None = None,
        membership: AnnData | None = None,
        name: str | None = None,
        source: str | dict[str, Any] | None = None,
        element_type: str = "cell",
        meta: dict[str, Any] | None = None,
        mod: dict[str, AnnData] | None = None,
        relations: dict[str, Any] | None = None,
        provenance: dict[str, Any] | None = None,
        uns: dict[str, Any] | None = None,
    ) -> None:
        """Build a set-level collection.

        The set observation axis is established one of three ways: from a
        pre-built ``mdata`` (e.g. via :meth:`read`), from a ready-made
        ``membership`` modality, or — most commonly — by **binning cell-level
        ``adata`` over the categorical ``set_col``** (one row per unique label),
        which also constructs the sparse ``membership`` modality and tags cell
        coordinates onto its ``var``.

        Args:
            adata: Cell-level ``AnnData`` whose ``set_col`` labels define the sets
                (required when neither ``obs``/``membership`` nor ``mdata`` given).
            set_col: ``adata.obs`` column whose categories become the sets (e.g.
                ``"leiden"``, ``"spagcn"``); recorded as the source algorithm.
            obs: Pre-built set observation table (alternative to ``adata``).
            mdata: Pre-built ``MuData`` to wrap (e.g. from ``read``).
            membership: Pre-built ``sets x elements`` membership modality.
            name: Optional collection / algorithm name (e.g. ``"spagcn"``).
            source: Source descriptor recorded in provenance.
            element_type: Entity type of the membership ``var`` axis; ``"cell"``
                today, ``"gene"`` for a future gene-set library.
            meta: Extra metadata merged into ``uns["celldega"]``.
            mod: Feature-space modalities to attach up front.
            relations: Square set-by-set matrices for ``mdata.obsp``.
            provenance: Free-form provenance metadata.
            uns: Extra Celldega metadata.

        Raises:
            ValueError: If no construction input (``adata`` + ``set_col``,
                ``obs``/``membership``, or ``mdata``) is provided.
        """
        built_membership = membership
        if mdata is None and obs is None and membership is None:
            if adata is None or set_col is None:
                raise ValueError("adata and set_col are required when obs/membership/mdata absent")
            set_ids, matrix = _membership_from_labels(adata.obs[set_col], set_col)

            obs = pd.DataFrame(index=set_ids)
            obs[set_col] = obs.index.astype(str)
            obs["n_cells"] = np.asarray(matrix.sum(axis=1)).ravel().astype(int)
            if name is not None:
                obs["set_source"] = name
            # Carry the preferred per-set color (e.g. adata.uns["leiden_colors"]) so it
            # persists with the collection and downstream views (Clustergram via the
            # signature modality's metadata, Landscape) can share one consistent palette.
            colors = _category_colors(adata, set_col)
            if colors:
                obs["color"] = [colors.get(str(s), "#808080") for s in obs.index]

            cell_var = pd.DataFrame(index=pd.Index(adata.obs_names.astype(str), name=element_type))
            cell_var[element_type] = cell_var.index.astype(str)
            coords = _cell_coords(adata)
            if coords is not None:
                cell_var = cell_var.join(coords)
            built_membership = AnnData(X=matrix, obs=obs.copy(), var=cell_var)

        self.set_col = set_col
        self.name = name
        self.source = source
        self.element_type = element_type
        self.meta = meta or {}

        collection_provenance = {"source": source} if source is not None else {}
        collection_provenance.update(provenance or {})
        collection_uns: dict[str, Any] = {"element_type": element_type}
        if set_col is not None:
            collection_uns["set_col"] = set_col
        if name is not None:
            collection_uns["name"] = name
        collection_uns.update(self.meta)
        collection_uns.update(uns or {})

        super().__init__(
            obs=obs,
            mod=mod or {},
            mdata=mdata,
            relations=relations or {},
            provenance=collection_provenance,
            uns=collection_uns,
            collection_type="set",
            obs_entity_type="set",
        )

        if built_membership is not None and "membership" not in self.mod:
            self.add_mod("membership", built_membership, var_entity_type=element_type)

    def calc_signature(
        self,
        data: AnnData | MuData,
        feature_type: str | None = None,
        layer: str | None = None,
        weights: str = "membership",
        aggregate: str = "mean",
        normalization: str | None = "log1p_cpm",
        modality_name: str | None = None,
        expr_threshold: float = 0.0,
    ) -> None:
        """Calculate and attach a set-by-feature signature (pseudobulk).

        Aggregates the per-cell feature matrix of each set's member cells into a
        ``sets x features`` modality, using the stored membership matrix as the
        aggregation operator. Consistent with ``DatasetCollection.calc_signature``
        and ``NeighborhoodCollection.calc_signature`` — the entity is implied by
        the instance, so it is not repeated in the name.

        ``feature_type`` is only needed when ``data`` is a ``MuData`` (it names the
        modality to aggregate and labels the output). For a plain ``AnnData`` the
        matrix is unambiguous and ``feature_type`` defaults to ``"gene"``; pass a
        protein ``AnnData`` (with ``feature_type="protein"`` to label it) for a
        protein signature, or use ``layer`` for an alternative matrix over the same
        features (raw vs. normalized).

        The ``aggregate="fraction"`` mode computes, for each set, the fraction of
        member cells whose feature value exceeds ``expr_threshold`` (the classic
        dot-plot "percent expressing" size channel). The result is already in
        ``[0, 1]`` so library-size ``normalization`` is skipped for that mode.
        Pair a ``mean`` signature (color) with a ``fraction`` signature (dot size)
        to drive a dot-plot :class:`~celldega.viz.Clustergram`.

        Args:
            data: Cell-level ``AnnData``, or a ``MuData`` paired with
                ``feature_type``. Cells are aligned to the membership ``var`` axis.
            feature_type: Output feature label / ``MuData`` modality selector.
                Required for ``MuData``; optional for ``AnnData`` (default
                ``"gene"``).
            layer: ``adata`` layer to aggregate; ``None`` uses ``adata.X``.
            weights: Membership modality driving aggregation — ``"membership"``
                (binary, hard assignment) or ``"weight"`` (soft/probabilistic).
            aggregate: ``"mean"``, ``"sum"``, or ``"fraction"`` across each set's
                member cells. ``"fraction"`` returns the proportion of member
                cells with value ``> expr_threshold``.
            normalization: ``None``, ``"cpm"``, or ``"log1p_cpm"`` per set row.
                Ignored (forced to ``None``) when ``aggregate="fraction"``.
            modality_name: Key for the modality; defaults to ``"expression"`` for
                gene ``mean``/``sum`` signatures, ``"fraction"`` for the
                fraction-expressing mode, and to ``feature_type`` otherwise.
            expr_threshold: A cell counts as expressing when its feature value is
                strictly greater than this (only used for ``aggregate="fraction"``).

        Returns:
            ``None`` — the modality is attached to ``self.mod``.
        """
        if aggregate not in {"sum", "mean", "fraction"}:
            raise ValueError("aggregate must be 'sum', 'mean', or 'fraction'")
        if weights not in self.mod:
            raise KeyError(f"membership modality '{weights}' not found")
        adata, feature_type = _resolve_feature_adata(data, feature_type)
        if layer is not None and layer not in adata.layers:
            raise ValueError(f"adata.layers missing requested layer '{layer}'")

        membership = self.mod[weights]
        cell_index = pd.Index(membership.var_names.astype(str))
        adata_cells = pd.Index(adata.obs_names.astype(str))
        common = cell_index.intersection(adata_cells)
        if len(common) == 0:
            raise ValueError("no shared cells between membership var axis and adata")

        weight_matrix = membership.X[:, cell_index.get_indexer(common)]
        matrix = adata.X if layer is None else adata.layers[layer]
        features = matrix[adata_cells.get_indexer(common), :]
        if aggregate == "fraction":
            # Binarize to a "detected / not detected" indicator, then the weighted
            # per-set average of that indicator is the fraction of cells expressing.
            features = (features > expr_threshold).astype(float)
        totals = _to_dense(weight_matrix @ features)
        if aggregate in {"mean", "fraction"}:
            per_set = np.asarray(weight_matrix.sum(axis=1)).ravel()
            nonzero = per_set > 0
            totals[nonzero, :] = totals[nonzero, :] / per_set[nonzero, None]
        if aggregate == "fraction":
            values = totals
            normalization_used = None
        else:
            values = _normalize_rows(totals, normalization)
            normalization_used = normalization

        var = adata.var.copy()
        var.index = adata.var_names.astype(str)
        if feature_type not in var.columns:
            var[feature_type] = var.index.astype(str)

        signature = AnnData(
            X=values,
            obs=self.obs.copy(),
            var=var,
            uns={
                "feature_type": feature_type,
                "aggregate": aggregate,
                "normalization": normalization_used,
                "layer": layer,
                "expr_threshold": expr_threshold if aggregate == "fraction" else None,
            },
        )
        # Hint Matrix's axis-entity inference so a Clustergram of this signature
        # (rows=features, cols=sets after transpose) links to a Landscape/Yearbook
        # by the right cell attribute (the set_col), not the hardcoded "leiden".
        if self.set_col is not None:
            signature.uns["axis_entities"] = {
                "row_entity": {"entity": feature_type, "attr": "name"},
                "col_entity": {"entity": self.element_type, "attr": self.set_col},
            }
        if modality_name is not None:
            resolved_name = modality_name
        elif aggregate == "fraction":
            resolved_name = "fraction"
        elif feature_type == "gene":
            resolved_name = "expression"
        else:
            resolved_name = feature_type
        self.add_mod(resolved_name, signature, var_entity_type=feature_type)

    def calc_population(
        self,
        data: AnnData | MuData,
        category: str = "leiden",
        output: str = "proportion",
        weights: str = "membership",
        modality_name: str = "population",
    ) -> None:
        """Calculate a set-by-population composition modality.

        For each set, counts its member cells per ``category`` value (cell type /
        cluster) into a ``sets x populations`` modality — e.g. the cell-type
        composition of each spatial domain. Computed as
        ``membership @ one_hot(category)``. Mirrors
        ``NeighborhoodCollection.calc_population`` / ``DatasetCollection.calc_population``.

        Args:
            data: Cell-level ``AnnData`` (or ``MuData``) carrying ``category`` in
                ``obs``; cells are aligned to the membership ``var`` axis.
            category: ``obs`` column naming the population/cell-type/cluster.
            output: ``"proportion"`` (within-set fractions) or ``"counts"``.
            weights: Membership modality to aggregate.
            modality_name: Key for the modality in ``self.mod``.

        Returns:
            ``None`` — the modality is attached to ``self.mod[modality_name]``.
        """
        if output not in {"proportion", "counts"}:
            raise ValueError("output must be 'proportion' or 'counts'")
        if weights not in self.mod:
            raise KeyError(f"membership modality '{weights}' not found")
        obs = data.obs  # both AnnData and MuData expose the shared obs table
        if category not in obs.columns:
            raise ValueError(f"obs missing required '{category}' column")

        membership = self.mod[weights]
        cell_index = pd.Index(membership.var_names.astype(str))
        data_cells = pd.Index(obs.index.astype(str))
        common = cell_index.intersection(data_cells)
        if len(common) == 0:
            raise ValueError("no shared cells between membership var axis and data")

        weight_matrix = membership.X[:, cell_index.get_indexer(common)]
        labels = obs.loc[common, category].astype(str)
        populations = pd.Index(pd.unique(labels), name=category)
        one_hot = pd.get_dummies(pd.Categorical(labels, categories=populations)).to_numpy(float)
        counts = _to_dense(weight_matrix @ one_hot)
        if output == "proportion":
            totals = counts.sum(axis=1)
            nonzero = totals > 0
            counts[nonzero, :] = counts[nonzero, :] / totals[nonzero, None]

        var = pd.DataFrame(index=populations)
        var[category] = var.index.astype(str)
        population = AnnData(
            X=counts,
            obs=self.obs.copy(),
            var=var,
            uns={"feature_type": "cell_population", "category": category, "output": output},
        )
        # Carry the category palette (e.g. adata.uns["cell_type_colors"]) so a
        # StackedBar / Clustergram of this composition reuses the same colors as
        # the source AnnData instead of falling back to an auto palette.
        colors = _category_colors(data, category)
        if colors:
            resolved = [colors.get(str(c), "#808080") for c in population.var_names]
            population.var["color"] = resolved
            population.uns[f"{category}_colors"] = resolved
        self.add_mod(modality_name, population, var_entity_type="cell_population")

    def calc_overlap(
        self,
        other: SetCollection | None = None,
        weights: str = "membership",
        metric: str = "iou",
        key: str = "overlap",
        modality_name: str | None = None,
        var_entity_type: str = "set",
    ) -> np.ndarray:
        """Calculate set-to-set membership overlap (the cross-algorithm comparison engine).

        Computes overlap between this collection's sets and ``other``'s sets over
        their shared element (cell) axis as ``A.X @ B.X.T``. One engine, two
        outputs:

        * ``other is None`` (self-overlap, e.g. on a concatenated collection) →
          a **square relation** stored in ``self.relations[key]``; convert it to a
          clusterable modality with :meth:`add_relation_modality` and hierarchically
          cluster to find consensus sets (Fig 4C-i).
        * ``other`` given → a **rectangular modality** ``self_sets x other_sets``
          attached to ``self.mod`` (e.g. domains vs. manual annotation, Fig 4C-ii).

        Args:
            other: Another ``SetCollection`` sharing the element axis; defaults to
                ``self``.
            weights: Membership modality to compare on.
            metric: ``"iou"`` (Jaccard) or ``"intersection"`` (raw shared count).
            key: Relation key (self-overlap) or default modality stem.
            modality_name: Modality key for the cross-collection case.
            var_entity_type: Entity type for the rectangular modality's ``var``.

        Returns:
            The dense overlap matrix (also stored as a relation or modality).
        """
        if metric not in {"iou", "intersection"}:
            raise ValueError("metric must be 'iou' or 'intersection'")
        target = other if other is not None else self
        if weights not in self.mod or weights not in target.mod:
            raise KeyError(f"membership modality '{weights}' not found on both collections")

        a_mod, b_mod = self.mod[weights], target.mod[weights]
        a_cells = pd.Index(a_mod.var_names.astype(str))
        b_cells = pd.Index(b_mod.var_names.astype(str))
        common = a_cells.intersection(b_cells)
        if len(common) == 0:
            raise ValueError("no shared elements between the two collections")

        a = a_mod.X[:, a_cells.get_indexer(common)]
        b = b_mod.X[:, b_cells.get_indexer(common)]
        intersection = _to_dense(a @ b.T)

        if metric == "iou":
            a_sizes = np.asarray(a.sum(axis=1)).ravel()
            b_sizes = np.asarray(b.sum(axis=1)).ravel()
            denom = a_sizes[:, None] + b_sizes[None, :] - intersection
            with np.errstate(divide="ignore", invalid="ignore"):
                overlap = np.where(denom > 0, intersection / denom, 0.0)
        else:
            overlap = intersection

        if other is None:
            self.relations[key] = overlap
        else:
            var = target.obs.copy()
            var["related_set_id"] = var.index.astype(str)
            adata_overlap = AnnData(
                X=overlap,
                obs=self.obs.copy(),
                var=var,
                uns={"feature_type": "set_overlap", "metric": metric},
            )
            self.add_mod(
                modality_name or f"{target.name or 'other'}_overlap",
                adata_overlap,
                var_entity_type=var_entity_type,
            )
        return overlap

    def to_nbhd(self, method: str = "points", **kwargs: Any) -> Any:
        """Graduate set membership to geometry, returning a ``NeighborhoodCollection``.

        For each set, gather its member cells, read their coordinates from the
        ``membership.var`` axis, and materialize geometry: ``"points"`` stores the
        raw ``MultiPoint`` (unopinionated); ``"alpha_shape"`` / ``"convex_hull"``
        build a polygon (opinionated). The inverse operation,
        ``NeighborhoodCollection.to_set``, projects geometry back to cell sets —
        round-tripping ``alpha_shape`` quantifies how faithfully a polygon recovers
        its defining cells (precision/recall).

        TODO(DEGA-487): implement by reusing ``nbhd.alpha_shape_cell_clusters`` and
        constructing a ``NeighborhoodCollection`` (lazy import to avoid a cycle).
        """
        raise NotImplementedError("SetCollection.to_nbhd is planned; see DEGA-487 design notes")


def concat_sets(
    collections: list[SetCollection],
    names: list[str] | None = None,
    weights: str = "membership",
) -> SetCollection:
    """Stack per-algorithm ``SetCollection`` objects into one comparison collection.

    Unions the element (cell) axis across all inputs, prefixes each set id with its
    collection ``name`` (so ``spagcn::3`` and ``gaston::5`` stay distinct), and
    vstacks the membership matrices. The result is the input to a self
    :meth:`SetCollection.calc_overlap` → ``add_relation_modality`` →
    hierarchical-clustering consensus workflow.

    Args:
        collections: Per-algorithm set collections sharing an element namespace.
        names: Optional prefixes; defaults to each collection's ``name`` or index.
        weights: Membership modality to stack.

    Returns:
        A combined ``SetCollection`` whose ``obs`` carries a ``set_source`` column.
    """
    if not collections:
        raise ValueError("collections must be non-empty")
    labels = names or [c.name or f"set{i}" for i, c in enumerate(collections)]

    union: pd.Index = pd.Index([], name=collections[0].element_type)
    for coll in collections:
        union = union.union(pd.Index(coll.mod[weights].var_names.astype(str)))

    blocks, obs_frames = [], []
    for label, coll in zip(labels, collections, strict=True):
        mod = coll.mod[weights]
        cells = pd.Index(mod.var_names.astype(str))
        col_map = union.get_indexer(cells)  # every cell is in the union, so all >= 0
        coo = sparse.coo_matrix(mod.X)
        aligned = sparse.csr_matrix(
            (coo.data, (coo.row, col_map[coo.col])), shape=(mod.n_obs, len(union))
        )
        blocks.append(aligned)

        obs = coll.obs.copy()
        obs.index = [f"{label}::{idx}" for idx in obs.index.astype(str)]
        obs["set_source"] = label
        obs_frames.append(obs)

    combined_obs = pd.concat(obs_frames)
    var = pd.DataFrame(index=union)
    var[collections[0].element_type] = union.astype(str)
    membership = AnnData(X=sparse.vstack(blocks).tocsr(), obs=combined_obs.copy(), var=var)
    return SetCollection(
        obs=combined_obs,
        membership=membership,
        element_type=collections[0].element_type,
        name="concat",
    )
