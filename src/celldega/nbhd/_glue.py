"""Collection bookkeeping for :class:`NeighborhoodCollection`.

Keeps a collection's MuData, geometry, relations, and memberships aligned when
its observation axis changes, and maps square neighborhood relations onto that
axis.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from anndata import AnnData
import geopandas as gpd
import numpy as np
import pandas as pd
from scipy import sparse


if TYPE_CHECKING:
    from celldega.nbhd.collection import NeighborhoodCollection


def _subset_gdf_to_obs(
    gdf: gpd.GeoDataFrame | None,
    obs_names: pd.Index,
    id_col: str,
) -> gpd.GeoDataFrame | None:
    if gdf is None:
        return None

    subset = gdf.copy()
    subset.index = subset.index.astype(str)
    if obs_names.isin(subset.index).all():
        return subset.loc[obs_names].copy()

    if id_col in subset.columns:
        subset["_celldega_obs_id"] = subset[id_col].astype(str)
        subset = subset.set_index("_celldega_obs_id", drop=False)
        result = subset.loc[obs_names].copy()
        return result.drop(columns="_celldega_obs_id", errors="ignore")

    missing = obs_names.difference(subset.index)
    raise ValueError(f"Cannot subset neighborhood geometry; missing IDs: {list(missing)}")


def _subset_neighborhood_collection_to_obs(
    collection: NeighborhoodCollection,
    obs_names: pd.Index,
) -> None:
    obs_names = pd.Index(obs_names.astype(str))
    current_index = pd.Index(collection.obs.index.astype(str))
    if list(obs_names) == list(current_index):
        return

    missing = obs_names.difference(current_index)
    if len(missing):
        raise ValueError(f"Cannot subset collection; missing observation IDs: {list(missing)}")

    keep_positions = [current_index.get_loc(name) for name in obs_names]
    # MuData slicing cuts obsp along one axis only, so relations are taken out
    # and sliced on both axes here.
    relations = list(collection.relations.items())
    for key, _relation in relations:
        del collection.relations[key]
    if collection.mod:
        collection.mdata = collection.mdata[obs_names, :].copy()
    else:
        from celldega.collection import _empty_mudata

        obs = collection.obs.loc[obs_names].copy()
        uns = dict(collection.mdata.uns)
        collection.mdata = _empty_mudata(obs)
        collection.mdata.uns.update(uns)
    for key, relation in relations:
        if relation.shape != (len(current_index), len(current_index)):
            continue
        if sparse.issparse(relation):
            collection.relations[key] = relation[keep_positions, :][:, keep_positions]
        else:
            values = np.asarray(relation)
            collection.relations[key] = values[np.ix_(keep_positions, keep_positions)]

    collection.gdf = _subset_gdf_to_obs(collection.gdf, obs_names, collection.nbhd_col)

    for key, membership in list(collection.memberships.items()):
        if membership.shape[1] != len(current_index):
            continue
        if sparse.issparse(membership):
            collection.memberships[key] = membership[:, keep_positions]
        else:
            collection.memberships[key] = np.asarray(membership)[:, keep_positions]


def _relation_from_square_adata(
    adata: AnnData,
    collection: NeighborhoodCollection,
) -> sparse.csr_matrix:
    """Align a square (obs-by-obs) relation matrix to the collection obs axis.

    Both axes are reindexed to ``collection.obs.index``; neighborhoods absent
    from ``adata`` become all-zero rows/columns. The reindex is done by mapping
    source positions to target positions on the sparse COO triplets, so the
    matrix is never densified.
    """
    target_index = collection.obs.index.astype(str)
    target_pos = {name: i for i, name in enumerate(target_index)}
    n = len(target_index)

    src = adata.X.tocoo() if sparse.issparse(adata.X) else sparse.coo_matrix(np.asarray(adata.X))
    obs_to_target = np.fromiter(
        (target_pos.get(name, -1) for name in adata.obs_names.astype(str)),
        dtype=int,
        count=adata.n_obs,
    )
    var_to_target = np.fromiter(
        (target_pos.get(name, -1) for name in adata.var_names.astype(str)),
        dtype=int,
        count=adata.n_vars,
    )

    rows = obs_to_target[src.row]
    cols = var_to_target[src.col]
    keep = (rows >= 0) & (cols >= 0)
    return sparse.csr_matrix(
        (src.data[keep], (rows[keep], cols[keep])),
        shape=(n, n),
    )
