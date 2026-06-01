"""MuData-backed schema containers for Celldega collection objects.

Celldega treats ``AnnData`` as the unit of a feature space and ``MuData`` as
the unit of a collection. The classes in this module are thin typed wrappers
around a ``MuData`` object, plus Celldega conventions for entity typing,
hierarchies, provenance, geometry, and view-linking metadata.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import warnings

from anndata import AnnData
import geopandas as gpd
from mudata import MuData, read_h5mu
import numpy as np
import pandas as pd
from scipy import sparse


__all__ = [
    "CELLDEGA_SCHEMA_VERSION",
    "CELLDEGA_UNS_KEY",
    "CelldegaCollection",
    "HierarchyResult",
    "NeighborhoodCollection",
]


CELLDEGA_UNS_KEY = "celldega"
CELLDEGA_SCHEMA_VERSION = "0.1.0"
_EMPTY_MODALITY_KEY = "_celldega_obs"


@dataclass
class HierarchyResult:
    """Serializable clustering or hierarchy result metadata.

    The result is tied to either a MuData modality, a global observation
    relation, or a modality-specific relation. Tree state for biclustering can
    store both the observation axis and the modality variable axis.

    Attributes:
        id: Stable result identifier, often ``"mod:<input_mod>__<method>"``.
        input_mod: Source modality key in ``mdata.mod`` when the hierarchy is
            derived from a feature space.
        input_relation: Source relation key in ``mdata.obsp`` or in
            ``mdata.mod[input_mod].obsp``.
        method: Method name, such as ``"hierarchical"`` or
            ``"matrix_biclustering"``.
        axis: Clustered axis. Use ``"obs"`` for observation-only results,
            ``"var"`` for feature/entity-only results, and ``"bicluster"``
            when both axes are clustered.
        params: Method parameters.
        preprocessing: Preprocessing steps used before clustering.
        obs_leaf_order: Optional ordered list of observation IDs.
        obs_linkage_matrix: Optional observation-axis SciPy linkage matrix with
            shape ``(n_obs - 1, 4)``.
        var_leaf_order: Optional ordered list of feature/entity IDs.
        var_linkage_matrix: Optional feature/entity-axis SciPy linkage matrix
            with shape ``(n_vars - 1, 4)``.
        provenance: Free-form provenance metadata for this result.
        uns: Free-form method-specific metadata.
    """

    id: str
    method: str
    input_mod: str | None = None
    input_relation: str | None = None
    axis: str = "obs"

    params: dict[str, Any] = field(default_factory=dict)
    preprocessing: dict[str, Any] = field(default_factory=dict)

    obs_leaf_order: list[str] | None = None
    obs_linkage_matrix: Any | None = None
    var_leaf_order: list[str] | None = None
    var_linkage_matrix: Any | None = None

    provenance: dict[str, Any] = field(default_factory=dict)
    uns: dict[str, Any] = field(default_factory=dict)

    @property
    def source_key(self) -> str:
        """Unique source reference for the result within a collection."""
        if self.input_mod is not None and self.input_relation is not None:
            return f"mod:{self.input_mod}.obsp:{self.input_relation}"
        if self.input_mod is not None:
            return f"mod:{self.input_mod}"
        if self.input_relation is not None:
            return f"obsp:{self.input_relation}"
        return "unknown"

    def to_dict(self) -> dict[str, Any]:
        """Return a MuData-serializable hierarchy registry payload.

        Hierarchical state is stored as plain SciPy-compatible linkage matrices
        under ``obs_linkage`` and ``var_linkage``. Flat cluster labels should be
        mirrored to ``obs`` or modality ``var`` instead of stored here.
        """
        payload: dict[str, Any] = {
            "id": self.id,
            "method": self.method,
            "axis": self.axis,
            "params": self.params,
            "preprocessing": self.preprocessing,
            "provenance": self.provenance,
            "uns": self.uns,
        }
        optional = {
            "input_mod": self.input_mod,
            "input_relation": self.input_relation,
            "obs_leaf_order": self.obs_leaf_order,
            "obs_linkage": _coerce_linkage_matrix(self.obs_linkage_matrix),
            "var_leaf_order": self.var_leaf_order,
            "var_linkage": _coerce_linkage_matrix(self.var_linkage_matrix),
        }
        payload.update({key: value for key, value in optional.items() if value is not None})
        return payload


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


def _align_mod_to_obs(adata: AnnData, obs: pd.DataFrame) -> AnnData:
    target_index = obs.index.astype(str)
    source_index = pd.Index(adata.obs_names.astype(str))

    if list(source_index) == list(target_index):
        aligned = adata.copy()
        aligned.obs = obs.copy()
        return aligned

    shape = (len(target_index), adata.n_vars)
    source_lookup = {name: i for i, name in enumerate(source_index)}
    target_rows = [i for i, name in enumerate(target_index) if name in source_lookup]
    source_rows = [source_lookup[name] for name in target_index if name in source_lookup]

    if sparse.issparse(adata.X):
        X = sparse.lil_matrix(shape, dtype=adata.X.dtype)
        if source_rows:
            X[target_rows, :] = adata.X[source_rows, :]
        X = X.tocsr()
    else:
        X = np.zeros(shape, dtype=adata.X.dtype)
        if source_rows:
            X[target_rows, :] = np.asarray(adata.X[source_rows, :])

    return AnnData(X=X, obs=obs.copy(), var=adata.var.copy(), uns=dict(adata.uns))


def _coerce_hierarchy(value: HierarchyResult | dict[str, Any]) -> dict[str, Any]:
    if isinstance(value, HierarchyResult):
        return value.to_dict()
    payload = dict(value)
    if "obs_linkage" in payload:
        payload["obs_linkage"] = _coerce_linkage_matrix(payload["obs_linkage"])
    if "var_linkage" in payload:
        payload["var_linkage"] = _coerce_linkage_matrix(payload["var_linkage"])
    return payload


def _coerce_linkage_matrix(linkage_matrix: Any | None) -> np.ndarray | None:
    if linkage_matrix is None:
        return None

    linkage = np.asarray(linkage_matrix, dtype=float)
    if linkage.size == 0:
        return linkage.reshape((0, 4))
    if linkage.ndim != 2 or linkage.shape[1] != 4:
        raise ValueError("linkage matrices must have shape (n - 1, 4)")
    return linkage


def _resolve_neighborhood_col(gdf: gpd.GeoDataFrame, nbhd_col: str = "name") -> str:
    if nbhd_col in gdf.columns:
        return nbhd_col
    for candidate in ("neighborhood_id", "nbhd_id"):
        if candidate in gdf.columns:
            return candidate
    raise ValueError(
        f"gdf must include '{nbhd_col}', 'neighborhood_id', or 'nbhd_id' to identify neighborhoods"
    )


def _neighborhood_obs_geometry_from_gdf(
    gdf: gpd.GeoDataFrame,
    nbhd_type: str,
    nbhd_col: str = "name",
) -> tuple[pd.DataFrame, gpd.GeoDataFrame, str]:
    resolved_nbhd_col = _resolve_neighborhood_col(gdf, nbhd_col)
    geometry = gdf.copy()
    geometry.index = geometry[resolved_nbhd_col].astype(str)

    if not geometry.index.is_unique:
        raise ValueError(f"Neighborhood IDs in '{resolved_nbhd_col}' must be unique")

    obs = pd.DataFrame(geometry.drop(columns="geometry", errors="ignore"))
    obs.index = geometry.index.copy()
    obs.index.name = "neighborhood_id"

    if "neighborhood_id" not in obs.columns:
        obs.insert(0, "neighborhood_id", obs.index)
    if "neighborhood_type" not in obs.columns:
        obs["neighborhood_type"] = nbhd_type
    if "method" not in obs.columns:
        obs["method"] = nbhd_type

    geom = geometry.geometry
    if "area" not in obs.columns:
        obs["area"] = geom.area
    if "area_um2" not in obs.columns:
        obs["area_um2"] = geom.area
    if "centroid_x" not in obs.columns:
        obs["centroid_x"] = geom.centroid.x
    if "centroid_y" not in obs.columns:
        obs["centroid_y"] = geom.centroid.y

    return obs, geometry, resolved_nbhd_col


class CelldegaCollection:
    """Base Celldega collection profile backed by ``MuData``.

    Attributes:
        mdata: The underlying multimodal object.
        mod: MuData modalities. Each modality is a clusterable ``AnnData``
            feature space.
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
        hierarchies: dict[str, HierarchyResult | dict[str, Any]] | None = None,
        provenance: dict[str, Any] | None = None,
        uns: dict[str, Any] | None = None,
        collection_type: str | None = None,
        obs_entity_type: str | None = None,
    ) -> None:
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
        for key, hierarchy in (hierarchies or {}).items():
            self.hierarchies[key] = _coerce_hierarchy(hierarchy)

    @property
    def obs(self) -> pd.DataFrame:
        """Canonical collection observation table."""
        return self.mdata.obs

    @obs.setter
    def obs(self, value: pd.DataFrame) -> None:
        self.mdata.obs = value.copy()

    @property
    def mod(self) -> dict[str, AnnData]:
        """Named feature-space modalities."""
        return self.mdata.mod

    @property
    def relations(self) -> Any:
        """Global observation-by-observation relations."""
        return self.mdata.obsp

    @property
    def hierarchies(self) -> dict[str, dict[str, Any]]:
        """Celldega hierarchy registry stored in MuData metadata."""
        return self.uns.setdefault("hierarchies", {})

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
        celldega.setdefault("hierarchies", {})
        celldega.setdefault("provenance", {})
        celldega["provenance"].update(provenance or {})
        celldega.update(uns or {})

    def add_mod(
        self,
        key: str,
        adata: AnnData,
        entity_type: str | None = None,
    ) -> AnnData:
        """Add an aligned modality and return the stored ``AnnData`` object."""
        aligned = _align_mod_to_obs(adata, self.obs)
        if entity_type is not None:
            aligned.var["entity_type"] = entity_type

        obs = self.obs.copy()
        self.mdata.mod[key] = aligned
        _with_mudata_warnings_suppressed(self.mdata.update)
        self.mdata.obs = obs
        return self.mdata.mod[key]

    def add_relation_modality(
        self,
        relation_key: str,
        key: str | None = None,
        entity_type: str | None = None,
    ) -> AnnData:
        """Materialize a square observation relation as a clusterable modality.

        Relations belong canonically in ``mdata.obsp``. Use this method when a
        workflow needs the relation matrix to be an ``AnnData.X`` matrix, such
        as Matrix-style heatmap clustering of an observation-by-observation
        similarity or distance matrix.
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

        resolved_entity_type = entity_type or str(self.uns.get("obs_entity_type", "observation"))
        adata = AnnData(
            X=X,
            obs=self.obs.copy(),
            var=var,
            uns={"feature_type": "relation", "relation_key": relation_key},
        )
        return self.add_mod(
            key or f"{relation_key}_relation",
            adata,
            entity_type=resolved_entity_type,
        )

    def add_hierarchy(self, hierarchy: HierarchyResult | dict[str, Any]) -> dict[str, Any]:
        """Add hierarchy metadata to the Celldega registry."""
        payload = _coerce_hierarchy(hierarchy)
        self.hierarchies[str(payload["id"])] = payload
        return payload

    def write(self, filename: str | Path, **kwargs: Any) -> None:
        """Write the underlying ``MuData`` object to disk."""
        _with_mudata_warnings_suppressed(self.mdata.write, filename, **kwargs)

    @classmethod
    def read(cls, filename: str | Path) -> CelldegaCollection:
        """Read a Celldega ``MuData`` collection from disk."""
        return cls(mdata=_with_mudata_warnings_suppressed(read_h5mu, filename))


class NeighborhoodCollection(CelldegaCollection):
    """Neighborhood-level or spatial-region MuData collection.

    Observations are neighborhoods or spatial regions. Feature spaces live in
    ``mod`` and global observation relations live in ``relations``/``mdata.obsp``.
    Geometry is kept as a live ``GeoDataFrame`` in memory; durable geometry
    storage can be layered on later with WKB columns or GeoParquet sidecars.
    """

    def __init__(
        self,
        obs: pd.DataFrame | None = None,
        mod: dict[str, AnnData] | None = None,
        mdata: MuData | None = None,
        gdf: gpd.GeoDataFrame | None = None,
        nbhd_type: str | None = None,
        adata: AnnData | None = None,
        data_dir: str | None = None,
        path_landscape_files: str | None = None,
        source: str | dict[str, Any] | None = None,
        name: str | None = None,
        meta: dict[str, Any] | None = None,
        nbhd_col: str = "name",
        geometry: gpd.GeoDataFrame | None = None,
        relations: dict[str, sparse.spmatrix] | None = None,
        hierarchies: dict[str, HierarchyResult | dict[str, Any]] | None = None,
        provenance: dict[str, Any] | None = None,
        uns: dict[str, Any] | None = None,
        memberships: dict[str, sparse.spmatrix] | None = None,
    ) -> None:
        if gdf is not None:
            if obs is not None:
                raise ValueError("obs cannot be provided when gdf is provided")
            if geometry is not None:
                raise ValueError("geometry cannot be provided separately when gdf is provided")
            resolved_nbhd_type = nbhd_type or "neighborhood"
            obs, geometry, nbhd_col = _neighborhood_obs_geometry_from_gdf(
                gdf,
                nbhd_type=resolved_nbhd_type,
                nbhd_col=nbhd_col,
            )
            self.gdf = geometry.copy()
        else:
            resolved_nbhd_type = nbhd_type or "neighborhood"
            self.gdf = geometry.copy() if geometry is not None else None

        self.nbhd_type = resolved_nbhd_type
        self.adata = adata
        self.data_dir = data_dir
        self.path_landscape_files = path_landscape_files
        self.source = source
        self.name = name
        self.meta = meta or {}
        self.nbhd_col = nbhd_col
        self.geometry = geometry
        self.memberships = memberships or {}

        collection_provenance = {"source": source} if source is not None else {}
        collection_provenance.update(provenance or {})
        collection_uns = {"name": name, **self.meta}
        collection_uns.update(uns or {})

        super().__init__(
            obs=obs,
            mod=mod,
            mdata=mdata,
            relations=relations,
            hierarchies=hierarchies,
            provenance=collection_provenance,
            uns=collection_uns,
            collection_type="neighborhood",
            obs_entity_type="neighborhood",
        )

    @classmethod
    def from_gdf(
        cls,
        gdf: gpd.GeoDataFrame,
        nbhd_type: str = "neighborhood",
        **kwargs: Any,
    ) -> NeighborhoodCollection:
        """Create a ``NeighborhoodCollection`` from a neighborhood GeoDataFrame."""
        return cls(gdf=gdf, nbhd_type=nbhd_type, **kwargs)

    @property
    def neighborhood_collection(self) -> NeighborhoodCollection:
        """Return ``self`` for API symmetry with legacy neighborhood helpers."""
        return self

    def to_collection(self) -> NeighborhoodCollection:
        """Return ``self``."""
        return self

    def construct_population_space(
        self,
        category: str = "leiden",
        key: str = "population",
        min_cells: int = 5,
        output: str = "percentage",
        adata: AnnData | None = None,
    ) -> AnnData:
        """Construct and attach a neighborhood-by-population modality."""
        source_adata = adata if adata is not None else self.adata
        if source_adata is None:
            raise ValueError("adata is required to construct a population space")
        if self.gdf is None:
            raise ValueError("gdf or geometry is required to construct a population space")

        from celldega.nbhd.neighborhoods import _align_space_to_collection, calc_nbhd_by_pop

        space = calc_nbhd_by_pop(
            source_adata,
            self.gdf,
            category=category,
            nbhd_col=self.nbhd_col,
            min_cells=min_cells,
            output=output,
        )
        space = _align_space_to_collection(space, self)
        return self.add_mod(key, space, entity_type="cell_population")
