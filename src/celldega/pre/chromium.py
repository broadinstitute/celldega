from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

import pandas as pd
import numpy as np
import scipy.sparse as sp
from anndata import AnnData

from .landscape import calc_meta_gene_data, save_cbg_gene_parquets
from . import _create_cluster_colors


def make_landscape_from_anndata(
    adata: AnnData,
    path_landscape_files: str | Path,
    *,
    use_int_index: bool = False,
) -> None:
    """Generate landscape files from an AnnData object.

    Parameters
    ----------
    adata : AnnData
        Input AnnData with ``X_umap`` coordinates and optional ``leiden``
        clustering in ``.obs``.
    path_landscape_files : str or Path
        Output directory for landscape files.
    use_int_index : bool, optional
        Whether to convert cell names to integer indices when saving gene
        matrices. Defaults to ``False``.
    """
    path = Path(path_landscape_files)
    path.mkdir(parents=True, exist_ok=True)

    if "X_umap" not in adata.obsm:
        raise ValueError("AnnData must contain 'X_umap' coordinates")

    # --- meta cell ---
    cells = adata.obs_names.astype(str)
    umap = adata.obsm["X_umap"]
    meta_cell = pd.DataFrame({"name": cells, "geometry": umap.tolist()})

    if "leiden" in adata.obs:
        meta_cell["cluster"] = adata.obs["leiden"].astype(str).values
    else:
        meta_cell["cluster"] = "0"

    meta_cell.to_parquet(path / "cell_metadata.parquet", index=False)

    # --- cell clusters ---
    counts = meta_cell["cluster"].value_counts().sort_index()
    clusters = counts.index.tolist()
    colors = adata.uns.get("leiden_colors")
    if colors is None:
        colors = _create_cluster_colors(clusters)

    cell_clusters_dir = path / "cell_clusters"
    cell_clusters_dir.mkdir(exist_ok=True)
    meta_cell[["name", "cluster"]].rename(columns={"cluster": "cluster"}).set_index("name").to_parquet(
        cell_clusters_dir / "cluster.parquet"
    )
    meta_cluster = pd.DataFrame({"color": colors[: len(clusters)], "count": counts.values}, index=clusters)
    meta_cluster.to_parquet(cell_clusters_dir / "meta_cluster.parquet")

    # --- cell by gene matrix ---
    if sp.issparse(adata.X):
        cbg = pd.DataFrame.sparse.from_spmatrix(adata.X, index=cells, columns=adata.var_names.astype(str))
    else:
        cbg = pd.DataFrame(adata.X, index=cells, columns=adata.var_names.astype(str))

    meta_gene = calc_meta_gene_data(cbg)
    meta_gene.to_parquet(path / "meta_gene.parquet")

    save_cbg_gene_parquets(path, cbg, verbose=False)

    # cluster gene expression
    df_sig = cbg.groupby(meta_cell["cluster"]).mean().T
    df_sig.to_parquet(path / "df_sig.parquet")

    # --- landscape parameters ---
    params = {
        "technology": "Chromium",
        "segmentation_approach": ["default"],
        "max_pyramid_zoom": None,
        "tile_size": None,
        "image_info": [],
        "image_format": "",
        "use_int_index": use_int_index,
    }
    with open(path / "landscape_parameters.json", "w") as fh:
        json.dump(params, fh, indent=4)

