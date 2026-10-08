"""MuData-backed schema containers for Celldega collection objects.

Celldega treats each ``AnnData`` modality as one feature matrix and ``MuData``
as the unit of a collection. The classes in this module are thin typed wrappers
around a ``MuData`` object, plus Celldega conventions for entity typing,
provenance, geometry, and view-linking metadata.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
import warnings

from anndata import AnnData
from mudata import MuData, read_h5mu
import numpy as np
import pandas as pd
from scipy import sparse


__all__ = [
    "CELLDEGA_SCHEMA_VERSION",
    "CELLDEGA_UNS_KEY",
    "CelldegaCollection",
]


CELLDEGA_UNS_KEY = "celldega"
CELLDEGA_SCHEMA_VERSION = "0.1.0"
_EMPTY_MODALITY_KEY = "_celldega_obs"


def _with_mudata_warnings_suppressed(func: Any, *args: Any, **kwargs: Any) -> Any:
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="From 0.4 .update\\(\\) will not pull obs/var columns",
            category=FutureWarning,
        )
        return func(*args, **kwargs)


def _create_mudata(mod: dict[str, AnnData]) -> MuData:
    return _with_mudata_warnings_suppressed(MuData, mod)


def _empty_mudata(obs: pd.DataFrame) -> MuData:
    placeholder = AnnData(
        X=np.empty((len(obs), 0)),
        obs=obs.copy(),
        var=pd.DataFrame(index=pd.Index([], name="feature")),
    )
    mdata = _create_mudata({_EMPTY_MODALITY_KEY: placeholder})
    mdata.obs = obs.copy()
    del mdata.mod[_EMPTY_MODALITY_KEY]
    mdata.obsm.clear()
    mdata.varm.clear()
    return mdata


def _is_count_like(series: pd.Series, col: str) -> bool:
    """Whether a missing value in this column should be filled with zero."""
    return pd.api.types.is_numeric_dtype(series) or col.endswith("count") or col.startswith("n_")


def _align_mod_to_obs(adata: AnnData, obs: pd.DataFrame) -> AnnData:
    """Align a modality ``AnnData`` to a collection's canonical ``obs`` axis.

    This is the single alignment helper for every Celldega collection. Rows
    present in ``adata`` but absent from ``obs`` are dropped; rows present in
    ``obs`` but absent from ``adata`` are added with a zero-filled ``X`` row.
    Modality ``obs`` columns are merged in without overwriting canonical
    collection columns, and count-like columns are zero-filled when missing.
    Sparse ``X`` is preserved as sparse.
    """
    target_index = obs.index.astype(str)
    source_index = pd.Index(adata.obs_names.astype(str))
    source_obs = adata.obs.copy()
    source_obs.index = source_index

    aligned_obs = obs.copy()
    for col in source_obs.columns:
        if col in aligned_obs.columns:
            continue
        values = source_obs[col].reindex(target_index)
        if _is_count_like(source_obs[col], col):
            values = values.fillna(0)
        aligned_obs[col] = values

    if list(source_index) == list(target_index):
        aligned = adata.copy()
        aligned.obs = aligned_obs
        return aligned

    shape = (len(target_index), adata.n_vars)
    source_lookup = {name: i for i, name in enumerate(source_index)}
    target_rows = [i for i, name in enumerate(target_index) if name in source_lookup]
    source_rows = [source_lookup[name] for name in target_index if name in source_lookup]

    def _align_matrix(matrix: Any) -> Any:
        if sparse.issparse(matrix):
            aligned_matrix = sparse.lil_matrix(shape, dtype=matrix.dtype)
            if source_rows:
                aligned_matrix[target_rows, :] = matrix[source_rows, :]
            return aligned_matrix.tocsr()
        aligned_matrix = np.zeros(shape, dtype=matrix.dtype)
        if source_rows:
            aligned_matrix[target_rows, :] = np.asarray(matrix[source_rows, :])
        return aligned_matrix

    X = _align_matrix(adata.X)
    layers = {key: _align_matrix(values) for key, values in adata.layers.items()}

    return AnnData(X=X, obs=aligned_obs, var=adata.var.copy(), layers=layers, uns=dict(adata.uns))


class CelldegaCollection:
    """Base Celldega collection profile backed by ``MuData``.

    Celldega defines new biological entities (datasets, neighborhoods, and more
    in the future), which requires both *constructing* the entity and
    *calculating* its feature spaces — neither of which is free for entities
    above the single-cell level. For single-cell data both steps come straight
    off the instrument; for higher-order entities ``DatasetCollection`` and
    ``NeighborhoodCollection`` build the observation axis and attach the feature
    modalities themselves.

    Attributes:
        mdata: The underlying multimodal object.
        mod: MuData modalities. Each modality is a clusterable ``AnnData``
            feature matrix.
        obs: Canonical biological observation axis shared by modalities.
        relations: Global observation-by-observation relations stored in
            ``mdata.obsp``.
        uns: Celldega schema metadata stored in ``mdata.uns["celldega"]``.
    """

    def __init__(
        self,
        obs: pd.DataFrame | None = None,
        mod: dict[str, AnnData] | None = None,
        mdata: MuData | None = None,
        relations: dict[str, sparse.spmatrix] | None = None,
        provenance: dict[str, Any] | None = None,
        uns: dict[str, Any] | None = None,
        collection_type: str | None = None,
        obs_entity_type: str | None = None,
    ) -> None:
        """Build a collection from an observation table, modalities, or a MuData.

        Exactly one of three construction paths is taken, in priority order:

        1. ``mdata`` given — wrap an existing (e.g. freshly read) ``MuData``; if
           ``obs`` is also given it replaces the top-level observation table.
        2. ``mod`` given (no ``mdata``) — each modality is aligned to ``obs``
           (or, when ``obs`` is omitted, to the first modality's own ``obs``) and
           the modalities become the collection's feature spaces.
        3. neither — an empty collection carrying only the ``obs`` axis is built;
           modalities are attached later via ``add_mod`` / ``calc_*`` methods.

        Args:
            obs: Canonical observation table; its index becomes the collection's
                observation axis.
            mod: Named feature-space modalities to attach, each aligned to ``obs``.
            mdata: A pre-built ``MuData`` to wrap directly.
            relations: Square observation-by-observation matrices stored in
                ``mdata.obsp`` (see :attr:`relations`).
            provenance: Free-form provenance merged into
                ``uns["celldega"]["provenance"]``.
            uns: Extra Celldega metadata merged into ``uns["celldega"]``.
            collection_type: Schema tag such as ``"dataset"`` or
                ``"neighborhood"``; defaults to ``"collection"``.
            obs_entity_type: Biological type of each observation (e.g.
                ``"dataset"``, ``"neighborhood"``), recorded in the metadata.

        Raises:
            ValueError: If none of ``obs``, ``mod``, or ``mdata`` is provided.
        """
        if mdata is not None:
            self.mdata = mdata
            if obs is not None:
                self.mdata.obs = obs.copy()
        else:
            mod = mod or {}
            if obs is None:
                if not mod:
                    raise ValueError("obs, mod, or mdata is required")
                obs = next(iter(mod.values())).obs.copy()
            obs = obs.copy()
            obs.index = obs.index.astype(str)
            if mod:
                aligned_mod = {key: _align_mod_to_obs(adata, obs) for key, adata in mod.items()}
                self.mdata = _create_mudata(aligned_mod)
                self.mdata.obs = obs.copy()
            else:
                self.mdata = _empty_mudata(obs)

        self._init_celldega_metadata(
            collection_type=collection_type,
            obs_entity_type=obs_entity_type,
            provenance=provenance,
            uns=uns,
        )

        for key, relation in (relations or {}).items():
            self.relations[key] = relation

    @property
    def obs(self) -> pd.DataFrame:
        """Canonical collection observation table."""
        return self.mdata.obs

    @obs.setter
    def obs(self, value: pd.DataFrame) -> None:
        self.mdata.obs = value.copy()

    @property
    def mod(self) -> dict[str, AnnData]:
        """Named feature modalities."""
        return self.mdata.mod

    @property
    def relations(self) -> Any:
        """Global observation-by-observation relations.

        This is a named accessor for ``mdata.obsp`` (not a separate store):
        relations are square matrices over the *collection's* observation axis,
        shared across all modalities. They live here rather than inside a single
        modality's ``obsp`` because they are properties of the observations
        themselves (e.g. neighborhood overlap or bordering, derived from
        geometry) and are modality-independent. Feature-by-feature relations
        belong in a modality's ``varp`` instead.
        """
        return self.mdata.obsp

    @property
    def provenance(self) -> dict[str, Any]:
        """Collection-level provenance metadata."""
        return self.uns.setdefault("provenance", {})

    @property
    def uns(self) -> dict[str, Any]:
        """Celldega schema metadata namespace."""
        return self.mdata.uns.setdefault(CELLDEGA_UNS_KEY, {})

    @property
    def collection_type(self) -> str | None:
        """Celldega collection type, such as ``"dataset"`` or ``"neighborhood"``."""
        return self.uns.get("collection_type")

    def _init_celldega_metadata(
        self,
        collection_type: str | None,
        obs_entity_type: str | None,
        provenance: dict[str, Any] | None,
        uns: dict[str, Any] | None,
    ) -> None:
        celldega = self.uns
        celldega.setdefault("schema_version", CELLDEGA_SCHEMA_VERSION)
        if collection_type is None:
            celldega.setdefault("collection_type", "collection")
        else:
            celldega["collection_type"] = collection_type
        if obs_entity_type is not None:
            celldega["obs_entity_type"] = obs_entity_type
        celldega.setdefault("provenance", {})
        celldega["provenance"].update(provenance or {})
        celldega.update(uns or {})

    def add_mod(
        self,
        key: str,
        adata: AnnData,
        var_entity_type: str | None = None,
    ) -> AnnData:
        """Attach a feature-space modality, aligned to the collection axis.

        ``adata`` is aligned to the collection's ``obs`` index via
        :func:`_align_mod_to_obs` (observations missing from ``adata`` become
        zero-filled rows, extras are dropped, sparse ``X`` stays sparse), stored
        under ``key`` in ``mod``, and the underlying ``MuData`` is refreshed.

        Args:
            key: Modality name (key in ``collection.mod``).
            adata: Feature matrix to attach; it need not already match the axis.
            var_entity_type: If given, written to the stored modality's
                ``var["entity_type"]``. Used downstream by ``Matrix`` to infer
                axis entities (e.g. ``"gene"`` or ``"cell_population"``).

        Returns:
            The aligned ``AnnData`` exactly as stored in ``collection.mod[key]``.
        """
        aligned = _align_mod_to_obs(adata, self.obs)
        if var_entity_type is not None:
            aligned.var["entity_type"] = var_entity_type

        obs = self.obs.copy()
        self.mdata.mod[key] = aligned
        _with_mudata_warnings_suppressed(self.mdata.update)
        self.mdata.obs = obs
        return self.mdata.mod[key]

    def add_relation_modality(
        self,
        relation_key: str,
        key: str | None = None,
        var_entity_type: str | None = None,
    ) -> AnnData:
        """Materialize a square observation relation as a clusterable modality.

        Relations live canonically in ``mdata.obsp``. Use this when a workflow
        needs the relation as an ``AnnData.X`` matrix — e.g. Matrix-style heatmap
        clustering of an observation-by-observation similarity/distance matrix.
        The resulting modality is labelled by the observation index on both axes
        (``var`` carries a ``related_obs_id`` column).

        Args:
            relation_key: Key of the relation in ``relations`` (``mdata.obsp``).
            key: Name for the new modality; defaults to
                ``f"{relation_key}_relation"``.
            var_entity_type: Entity type for the modality's ``var`` axis;
                defaults to the collection's ``obs_entity_type``.

        Returns:
            The stored relation modality ``AnnData``.

        Raises:
            KeyError: If ``relation_key`` is not present in ``relations``.
            ValueError: If the relation is not square over the observation axis.
        """
        if relation_key not in self.relations:
            raise KeyError(f"relation '{relation_key}' not found")

        relation = self.relations[relation_key]
        if relation.shape != (len(self.obs), len(self.obs)):
            raise ValueError(
                f"relation '{relation_key}' must have shape ({len(self.obs)}, {len(self.obs)})"
            )

        X = relation.copy() if sparse.issparse(relation) else np.asarray(relation).copy()
        var = pd.DataFrame(index=self.obs.index.copy())
        var.index.name = self.obs.index.name
        var["related_obs_id"] = var.index.astype(str)

        resolved_var_entity_type = var_entity_type or str(
            self.uns.get("obs_entity_type", "observation")
        )
        adata = AnnData(
            X=X,
            obs=self.obs.copy(),
            var=var,
            uns={"feature_type": "relation", "relation_key": relation_key},
        )
        return self.add_mod(
            key or f"{relation_key}_relation",
            adata,
            var_entity_type=resolved_var_entity_type,
        )

    def write(self, filename: str | Path, **kwargs: Any) -> None:
        """Write the underlying ``MuData`` to an ``.h5mu`` file.

        Args:
            filename: Destination path.
            **kwargs: Forwarded to ``MuData.write``.

        Note:
            Only the ``MuData`` is persisted. In-memory-only state not stored in
            ``mdata`` — e.g. a ``NeighborhoodCollection``'s ``gdf`` geometry and
            ``memberships`` — does not round-trip through ``write``/``read``.
        """
        _with_mudata_warnings_suppressed(self.mdata.write, filename, **kwargs)

    @classmethod
    def read(cls, filename: str | Path) -> CelldegaCollection:
        """Read a Celldega ``MuData`` collection from an ``.h5mu`` file.

        Args:
            filename: Path to the ``.h5mu`` file.

        Returns:
            An instance of the calling class wrapping the loaded ``MuData``
            (subclasses restore their own metadata from ``uns`` in ``__init__``).
        """
        return cls(mdata=_with_mudata_warnings_suppressed(read_h5mu, filename))
