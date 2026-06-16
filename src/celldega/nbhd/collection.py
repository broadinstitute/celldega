"""Neighborhood-level collection schema objects."""

from __future__ import annotations

from typing import Any

from anndata import AnnData
import geopandas as gpd
from mudata import MuData
import pandas as pd
from scipy import sparse

from celldega.collection.collection import CelldegaCollection


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


class NeighborhoodCollection(CelldegaCollection):
    """Neighborhood-level or spatial-region MuData collection.

    Observations are neighborhoods or spatial regions. Feature modalities live in
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
        data_dir: str | None = None,
        source: str | dict[str, Any] | None = None,
        name: str | None = None,
        meta: dict[str, Any] | None = None,
        nbhd_col: str = "name",
        geometry: gpd.GeoDataFrame | None = None,
        relations: dict[str, sparse.spmatrix] | None = None,
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
        self.data_dir = data_dir
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

    def calc_nbhd_by_pop(
        self,
        adata: AnnData,
        category: str = "leiden",
        modality_name: str = "population",
        output: str = "proportion",
        min_cells: int = 5,
        drop_missing: bool = True,
    ) -> None:
        """Calculate and attach a neighborhood-by-population modality to ``self.mod``.

        Args:
            drop_missing: When ``True`` (default), neighborhoods with fewer than
                ``min_cells`` cells are removed from the collection entirely so
                the observation axis only contains neighborhoods with data. When
                ``False``, the collection keeps all neighborhoods and the
                modality is attached with zero-filled rows for those that fall
                below ``min_cells``.
        """
        from celldega.nbhd.neighborhoods import (
            _subset_neighborhood_collection_to_obs,
            calc_nbhd_by_pop,
        )

        if self.gdf is None:
            raise ValueError("gdf or geometry is required to calculate a population modality")

        modality = calc_nbhd_by_pop(
            adata,
            self.gdf,
            category=category,
            nbhd_col=self.nbhd_col,
            min_cells=min_cells,
            output=output,
        )
        if drop_missing:
            _subset_neighborhood_collection_to_obs(self, pd.Index(modality.obs_names.astype(str)))
        self.add_mod(modality_name, modality, var_entity_type="cell_population")

    def calc_nbhd_by_gene(
        self,
        adata: AnnData | None = None,
        by: str = "cell",
        modality_name: str | None = None,
        min_cells: int = 1,
        data_dir: str | None = None,
        drop_missing: bool = True,
    ) -> None:
        """Calculate and attach a neighborhood-by-gene modality to ``self.mod``.

        Args:
            drop_missing: When ``True`` (default), neighborhoods with fewer than
                ``min_cells`` cells (or transcripts) are removed from the
                collection entirely. When ``False``, the collection keeps all
                neighborhoods and the modality is attached with zero-filled rows
                for those that fall below ``min_cells``.
        """
        from celldega.nbhd.neighborhoods import (
            _subset_neighborhood_collection_to_obs,
            calc_nbhd_by_gene,
        )

        if self.gdf is None:
            raise ValueError("gdf or geometry is required to calculate a gene modality")

        resolved_data_dir = data_dir if data_dir is not None else self.data_dir
        if by == "cell" and adata is None:
            raise ValueError("adata is required when by='cell'")
        if by == "cell-free" and resolved_data_dir is None:
            raise ValueError("data_dir is required when by='cell-free'")

        modality = calc_nbhd_by_gene(
            self.gdf,
            by=by,
            adata=adata,
            data_dir=resolved_data_dir,
            nbhd_col=self.nbhd_col,
            min_cells=min_cells,
        )
        if drop_missing:
            _subset_neighborhood_collection_to_obs(self, pd.Index(modality.obs_names.astype(str)))
        self.add_mod(
            modality_name or ("gene" if by == "cell" else "gene_cell_free"),
            modality,
            var_entity_type="gene",
        )


__all__ = ["NeighborhoodCollection"]
