"""Neighborhood feature and relation calculations.

Every function takes neighborhood geometry (a ``GeoDataFrame`` with one row per
neighborhood, or any object exposing ``to_geodataframe()``) and, where cells are
involved, a cell-level ``AnnData`` or ``MuData``. Results are returned as new
``AnnData``/``MuData``/``DataFrame`` objects whose observations are the
neighborhoods, ready for :class:`celldega.clust.Matrix`.
"""

# Standard library imports
from itertools import combinations
from typing import Any
import warnings

from anndata import AnnData

# Third-party imports
import geopandas as gpd
from mudata import MuData
import numpy as np
import pandas as pd
from scipy import sparse

from celldega.nbhd.utils import (
    _as_nbhd_gdf,
    _category_colors,
    _cell_coords,
    _cell_obs_column,
    _is_multimodal,
    _unwrap_mudata,
    read_transcripts,
)


_NBHD_ENTITY = {"entity": "nbhd", "attr": "name"}
_GENE_LIKE_MODALITIES = {"rna", "gene", "genes", "expression"}


def _nbhd_geometry_for_join(gdf_nbhd: gpd.GeoDataFrame, nbhd_col: str) -> gpd.GeoDataFrame:
    return gdf_nbhd[[nbhd_col, "geometry"]].reset_index(drop=True)


def _nbhd_membership(
    gdf_nbhd: gpd.GeoDataFrame, nbhd_col: str, coords: pd.DataFrame
) -> sparse.csr_matrix:
    """Sparse neighborhood-by-cell indicator from one spatial join.

    Rows follow ``gdf_nbhd`` order and columns follow ``coords`` order. A cell
    inside several overlapping neighborhoods is counted in each of them.
    """
    gdf_cell = gpd.GeoDataFrame(
        index=pd.RangeIndex(len(coords)),
        geometry=gpd.points_from_xy(coords["x"].to_numpy(), coords["y"].to_numpy()),
    )
    joined = gdf_cell.sjoin(
        _nbhd_geometry_for_join(gdf_nbhd, nbhd_col), how="inner", predicate="within"
    )
    rows = joined["index_right"].to_numpy()
    cols = joined.index.to_numpy()
    return sparse.csr_matrix((np.ones(len(rows)), (rows, cols)), shape=(len(gdf_nbhd), len(coords)))


def _add_nbhd_metadata(adata_nbhd: AnnData, gdf_nbhd: gpd.GeoDataFrame, nbhd_col: str) -> None:
    """Copy neighborhood ``cat``/``color`` columns from the geometry onto ``obs``."""
    ids = gdf_nbhd[nbhd_col].astype(str)
    if "cat" in gdf_nbhd.columns:
        cat_lookup = dict(zip(ids, gdf_nbhd["cat"].astype(str), strict=False))
        adata_nbhd.obs["cat"] = [cat_lookup.get(n, n) for n in adata_nbhd.obs.index]

    if "color" in gdf_nbhd.columns:
        color_lookup = dict(zip(ids, gdf_nbhd["color"], strict=False))
        colors = [color_lookup.get(n, "#808080") for n in adata_nbhd.obs.index]
        adata_nbhd.obs["color"] = colors
        adata_nbhd.uns["nbhd_colors"] = colors


def _default_feature_type(modality: str | None) -> str:
    if modality is None or modality.lower() in _GENE_LIKE_MODALITIES:
        return "gene"
    return modality


def _aggregate_cells(
    adata_mod: AnnData,
    coords: pd.DataFrame,
    membership: sparse.csr_matrix,
    gdf_nbhd: gpd.GeoDataFrame,
    nbhd_col: str,
    *,
    min_cells: int,
    include_variance: bool,
    layer: str | None,
    feature_type: str,
) -> AnnData:
    """Mean (and optionally variance) of one feature matrix per neighborhood."""
    positions = coords.index.get_indexer(pd.Index(adata_mod.obs_names.astype(str)))
    has_coords = positions >= 0
    features = adata_mod.layers[layer] if layer is not None else adata_mod.X
    features = features[has_coords]
    member = membership[:, positions[has_coords]]

    counts = np.asarray(member.sum(axis=1)).ravel()
    valid = counts >= max(min_cells, 1)
    member = member[valid]
    counts = counts[valid]
    nbhd_ids = gdf_nbhd[nbhd_col].astype(str).to_numpy()[valid]

    def _dense(values: Any) -> np.ndarray:
        return values.toarray() if sparse.issparse(values) else np.asarray(values)

    sums = _dense(member @ features)
    mean = sums / counts[:, None] if len(counts) else sums

    adata_nbg = AnnData(
        X=mean,
        obs=pd.DataFrame(index=pd.Index(nbhd_ids)),
        var=pd.DataFrame(index=pd.Index(adata_mod.var_names.astype(str))),
    )
    if include_variance:
        squared = features.multiply(features) if sparse.issparse(features) else features**2
        variance = _dense(member @ squared) / counts[:, None] - mean**2
        adata_nbg.layers["variance"] = np.clip(variance, 0, None)

    adata_nbg.obs["n_cells"] = counts.astype(int)
    adata_nbg.var["entity_type"] = feature_type
    adata_nbg.uns["by"] = "cell"
    adata_nbg.uns["axis_entities"] = {
        "row_entity": {"entity": feature_type, "attr": "name"},
        "col_entity": dict(_NBHD_ENTITY),
    }
    _add_nbhd_metadata(adata_nbg, gdf_nbhd[valid], nbhd_col)
    return adata_nbg


def calc_nbhd_by_gene(
    gdf_nbhd: Any,
    by: str = "cell",
    adata: Any = None,
    data_dir: str | None = None,
    nbhd_col: str = "name",
    min_cells: int = 1,
    *,
    include_variance: bool = False,
    modality: str | None = None,
    layer: str | None = None,
    feature_type: str | None = None,
    spatial_key: str = "spatial",
    gdf_trx: gpd.GeoDataFrame | None = None,
) -> AnnData | MuData:
    """
    Calculate a neighborhood-by-gene expression matrix.

    Computes gene expression for each neighborhood, either from cell-level
    expression (mean expression of the cells within each neighborhood) or from
    raw transcript counts (cell-free mode).

    Parameters
    ----------
    gdf_nbhd : GeoDataFrame or neighborhood-like object
        Neighborhood geometries with an identifier column (`nbhd_col`). Objects
        exposing ``to_geodataframe()`` are accepted too.
    by : str, default "cell"
        - "cell": mean expression of cells within each neighborhood (requires `adata`)
        - "cell-free": transcript counts within each neighborhood (requires
          `gdf_trx` or `data_dir`)
    adata : AnnData or MuData, optional
        Cell-level data with spatial coordinates in `obsm[spatial_key]`.
        Required when `by="cell"`. For a MuData, every modality is aggregated
        (one output modality per input modality) unless `modality` is given.
    data_dir : str, optional
        Directory containing `transcripts.parquet`, used for `by="cell-free"`
        when `gdf_trx` is not given.
    nbhd_col : str, default "name"
        Column in `gdf_nbhd` with neighborhood identifiers (falls back to
        `neighborhood_id`/`nbhd_id`).
    min_cells : int, default 1
        Minimum cells (or, for `by="cell-free"`, transcripts) a neighborhood
        needs to be included.
    include_variance : bool, default False
        With `by="cell"`, also store per-neighborhood, per-gene variance
        (population variance) in `layers["variance"]`.
    modality : str, optional
        For a MuData input, aggregate only this modality and return an AnnData.
    layer : str, optional
        Aggregate this layer instead of `X`.
    feature_type : str, optional
        Entity type of the features (written to `var["entity_type"]` and
        `uns["axis_entities"]`). Defaults to "gene" for AnnData and gene-like
        modalities (`rna`, `gene`, `expression`), else the modality name.
    spatial_key : str, default "spatial"
        Key of the cell coordinates in `obsm`.
    gdf_trx : GeoDataFrame, optional
        Transcript points with a `feature_name` column (see
        :func:`read_transcripts`), for `by="cell-free"`.

    Returns
    -------
    AnnData or MuData
        Neighborhoods x features, with `obs["n_cells"]` (or
        `obs["n_transcripts"]`), `uns["by"]`, `uns["axis_entities"]`, and the
        neighborhood `cat`/`color` columns when the geometry has them. A MuData
        input without `modality` returns a MuData with one modality per input
        modality.
    """
    gdf_nbhd, nbhd_col = _as_nbhd_gdf(gdf_nbhd, nbhd_col)

    if include_variance and by != "cell":
        raise ValueError("include_variance is only supported when by='cell'")

    if by == "cell":
        if adata is None:
            raise ValueError("adata is required when by='cell'")
        data = _unwrap_mudata(adata)
        coords = _cell_coords(data, spatial_key=spatial_key, modality=modality)
        membership = _nbhd_membership(gdf_nbhd, nbhd_col, coords)

        def _aggregate(adata_mod: AnnData, name: str | None) -> AnnData:
            return _aggregate_cells(
                adata_mod,
                coords,
                membership,
                gdf_nbhd,
                nbhd_col,
                min_cells=min_cells,
                include_variance=include_variance,
                layer=layer,
                feature_type=feature_type or _default_feature_type(name),
            )

        if not _is_multimodal(data):
            return _aggregate(data, None)
        if modality is not None:
            return _aggregate(data.mod[modality], modality)
        return MuData({name: _aggregate(data.mod[name], name) for name in data.mod})

    if by != "cell-free":
        raise ValueError("by must be 'cell' or 'cell-free'")

    if gdf_trx is None:
        if data_dir is None:
            raise ValueError("gdf_trx or data_dir is required when by='cell-free'")
        gdf_trx = read_transcripts(data_dir, cell_id=False)

    joined = gdf_trx[["feature_name", "geometry"]].sjoin(
        _nbhd_geometry_for_join(gdf_nbhd, nbhd_col), how="inner", predicate="within"
    )
    nbhd_ids = gdf_nbhd[nbhd_col].astype(str)
    df_result = (
        joined.assign(**{nbhd_col: joined[nbhd_col].astype(str)})
        .groupby([nbhd_col, "feature_name"])
        .size()
        .unstack(fill_value=0)
        .rename_axis(None, axis=1)
        .reindex(nbhd_ids)
        .fillna(0)
        .astype(int)
    )

    trx_counts = df_result.sum(axis=1)
    valid = (trx_counts >= max(min_cells, 1)).to_numpy()
    df_result = df_result.loc[valid]

    resolved_feature_type = feature_type or "gene"
    adata_nbg = AnnData(
        X=df_result.to_numpy(),
        obs=pd.DataFrame(index=pd.Index(df_result.index.astype(str))),
        var=pd.DataFrame(index=pd.Index(df_result.columns.astype(str))),
    )
    adata_nbg.obs["n_transcripts"] = trx_counts.to_numpy()[valid]
    adata_nbg.var["entity_type"] = resolved_feature_type
    adata_nbg.uns["by"] = "cell-free"
    adata_nbg.uns["axis_entities"] = {
        "row_entity": {"entity": resolved_feature_type, "attr": "name"},
        "col_entity": dict(_NBHD_ENTITY),
    }
    _add_nbhd_metadata(adata_nbg, gdf_nbhd.loc[valid], nbhd_col)
    return adata_nbg


def calc_nbhd_by_pop(
    adata: Any,
    gdf_nbhd: Any,
    category: str = "leiden",
    nbhd_col: str = "name",
    min_cells: int = 5,
    output: str = "proportion",
    *,
    modality: str | None = None,
    spatial_key: str = "spatial",
) -> AnnData:
    """
    Calculate the cell population distribution of each neighborhood.

    Computes a neighborhood-by-population matrix showing the distribution of cell
    categories (e.g., clusters, cell types) within each neighborhood.

    Parameters
    ----------
    adata : AnnData or MuData
        Cell-level data with spatial coordinates in `obsm[spatial_key]` and the
        `category` column in `obs`. For a MuData, `category` is looked up in the
        global `obs` (also as `"<modality>:<category>"`) and then in the
        modalities' own `obs`.
    gdf_nbhd : GeoDataFrame or neighborhood-like object
        Neighborhood geometries with an identifier column (`nbhd_col`).
    category : str, default "leiden"
        Cell category column (e.g. "leiden", "cell_type").
    nbhd_col : str, default "name"
        Column in `gdf_nbhd` with neighborhood identifiers.
    min_cells : int, default 5
        Minimum number of cells a neighborhood needs to be included.
    output : str, default "proportion"
        - "proportion": fraction of cells per category (sums to 1 per neighborhood)
        - "counts": raw cell counts per category
    modality : str, optional
        For a MuData input, the modality to take coordinates and `category` from.
    spatial_key : str, default "spatial"
        Key of the cell coordinates in `obsm`.

    Returns
    -------
    AnnData
        Neighborhoods x categories with `obs["n_cells"]`, `uns["category"]`,
        `uns["output"]`, `var["entity_type"] = "cell_population"`, and category
        colors (`var["color"]`, `uns[f"{category}_colors"]`) when the cell data
        has them.
    """
    if gdf_nbhd is None:
        raise ValueError("gdf_nbhd is required to calculate a neighborhood population")
    gdf_nbhd, nbhd_col = _as_nbhd_gdf(gdf_nbhd, nbhd_col)
    if output not in {"proportion", "counts"}:
        raise ValueError("output must be 'proportion' or 'counts'")

    data = _unwrap_mudata(adata)
    labels = _cell_obs_column(data, category, modality=modality)
    coords = _cell_coords(data, spatial_key=spatial_key, modality=modality)
    labels = labels.reindex(coords.index)

    # No CRS: micron imaging coordinates, not geospatial
    gdf_cell = gpd.GeoDataFrame(
        {category: labels.to_numpy()},
        geometry=gpd.points_from_xy(coords["x"].to_numpy(), coords["y"].to_numpy()),
    )
    sjoin_df = gdf_cell.sjoin(
        _nbhd_geometry_for_join(gdf_nbhd, nbhd_col), how="left", predicate="within"
    )

    cell_counts_per_nbhd = sjoin_df[nbhd_col].value_counts()
    valid_nbhd_names = cell_counts_per_nbhd[cell_counts_per_nbhd >= min_cells].index
    sjoin_df = sjoin_df[sjoin_df[nbhd_col].isin(valid_nbhd_names)]

    counts = (
        sjoin_df.groupby([nbhd_col, category], observed=False)
        .size()
        .unstack(fill_value=0)
        .pipe(lambda df: df.set_axis(df.columns.astype(str), axis=1))
    )

    filtered_gdf_nbhd = gdf_nbhd[gdf_nbhd[nbhd_col].isin(valid_nbhd_names)].reset_index(drop=True)
    counts = counts.reindex(filtered_gdf_nbhd[nbhd_col]).fillna(0).astype(int)
    counts.index = counts.index.astype(str)

    if output == "proportion":
        values = counts.div(counts.sum(axis=1), axis=0).fillna(0).to_numpy()
    else:
        values = counts.to_numpy()

    adata_nbp = AnnData(
        X=values,
        obs=pd.DataFrame(index=counts.index),
        var=pd.DataFrame(index=counts.columns),
    )
    adata_nbp.obs["n_cells"] = counts.sum(axis=1).to_numpy()
    adata_nbp.uns["category"] = category
    adata_nbp.uns["output"] = output
    adata_nbp.var[category] = adata_nbp.var.index.astype(str)
    adata_nbp.var["entity_type"] = "cell_population"
    adata_nbp.uns["axis_entities"] = {
        "row_entity": {"entity": "cell", "attr": category},
        "col_entity": dict(_NBHD_ENTITY),
    }

    # Neighborhoods built per category (e.g. alpha shapes) carry it in `cat`
    if "cat" in filtered_gdf_nbhd.columns:
        nbhd_cat_lookup = dict(
            zip(
                filtered_gdf_nbhd[nbhd_col].astype(str),
                filtered_gdf_nbhd["cat"].astype(str),
                strict=False,
            )
        )
        adata_nbp.obs[category] = [nbhd_cat_lookup.get(n, n) for n in adata_nbp.obs.index]
    else:
        adata_nbp.obs[category] = adata_nbp.obs.index.astype(str)

    color_dict = _category_colors(data, category, modality=modality)
    if color_dict:
        adata_nbp.var["color"] = [color_dict.get(str(c), "#808080") for c in adata_nbp.var.index]
        adata_nbp.uns[f"{category}_colors"] = list(adata_nbp.var["color"])
        adata_nbp.obs["color"] = [
            color_dict.get(str(c), "#808080") for c in adata_nbp.obs[category]
        ]

    return adata_nbp


def calc_nbhd_transcript_assignment(
    gdf_nbhd: Any,
    gdf_trx: gpd.GeoDataFrame | None = None,
    *,
    data_dir: str | None = None,
    nbhd_col: str = "name",
) -> pd.DataFrame:
    """Per-neighborhood transcript counts and cell-assignment proportion.

    A transcript counts as assigned when its ``cell_id`` is not ``"UNASSIGNED"``.

    Assumption: transcript-to-cell assignment is **not computed here** — it must
    already be present in the instrument data, with unassigned transcripts marked
    by the ``"UNASSIGNED"`` sentinel (Xenium convention). A missing ``cell_id``
    column raises ``ValueError``; a complete absence of the sentinel warns (it may
    be genuinely fully assigned, or use a different convention).

    Parameters
    ----------
    gdf_nbhd : GeoDataFrame or neighborhood-like object
        Neighborhood geometries with an identifier column (`nbhd_col`).
    gdf_trx : GeoDataFrame, optional
        Transcript points with a ``cell_id`` column (see :func:`read_transcripts`).
    data_dir : str, optional
        Directory containing ``transcripts.parquet``, used when `gdf_trx` is not given.
    nbhd_col : str, default "name"
        Column in `gdf_nbhd` with neighborhood identifiers.

    Returns
    -------
    pd.DataFrame
        Indexed by neighborhood id with columns ``total_transcripts``,
        ``unassigned_transcripts``, and ``transcript_assignment_proportion``
        (assigned / total; ``0.0`` when a neighborhood has no transcripts).
    """
    gdf_nbhd, nbhd_col = _as_nbhd_gdf(gdf_nbhd, nbhd_col)
    if gdf_trx is None:
        if data_dir is None:
            raise ValueError("gdf_trx or data_dir is required")
        gdf_trx = read_transcripts(data_dir)

    if "cell_id" not in gdf_trx.columns:
        raise ValueError(
            "transcripts have no 'cell_id' column. Transcript-to-cell assignment is "
            "not computed by Celldega; it must already be present in the instrument "
            "data before calculating neighborhood transcript assignment."
        )
    if not (gdf_trx["cell_id"].astype(str) == "UNASSIGNED").any():
        warnings.warn(
            "no transcripts are labeled 'UNASSIGNED' in 'cell_id'. This method assumes "
            "transcript-to-cell assignment is pre-calculated in the instrument data, "
            "with unassigned transcripts marked by the 'UNASSIGNED' sentinel (Xenium "
            "convention). If the data is genuinely fully assigned this is fine; "
            "otherwise verify the assignment is present and uses this sentinel.",
            stacklevel=2,
        )

    nbhd_ids = pd.Index(gdf_nbhd[nbhd_col].astype(str))
    joined = gdf_trx.sjoin(
        _nbhd_geometry_for_join(gdf_nbhd, nbhd_col),
        how="left",
        predicate="within",
    )
    joined[nbhd_col] = joined[nbhd_col].astype(str)
    grouped = joined.groupby(nbhd_col)["cell_id"]
    total = grouped.size()
    unassigned = grouped.apply(lambda ids: (ids == "UNASSIGNED").sum())

    stats = (
        pd.DataFrame({"total_transcripts": total, "unassigned_transcripts": unassigned})
        .reindex(nbhd_ids)
        .fillna(0)
    )
    stats = stats.astype({"total_transcripts": int, "unassigned_transcripts": int})

    assigned = stats["total_transcripts"] - stats["unassigned_transcripts"]
    stats["transcript_assignment_proportion"] = assigned / stats["total_transcripts"].where(
        stats["total_transcripts"] > 0, 1
    )
    stats.index = stats.index.astype(str)
    return stats


def _square_nbhd_adata(
    matrix: pd.DataFrame,
    gdf_nbhd: gpd.GeoDataFrame,
    nbhd_col: str,
    metric: str,
    category: str,
) -> AnnData:
    """Wrap a square neighborhood-by-neighborhood matrix with its metadata."""
    adata_nbn = AnnData(
        X=matrix.to_numpy(),
        obs=pd.DataFrame(index=pd.Index(matrix.index.astype(str))),
        var=pd.DataFrame(index=pd.Index(matrix.columns.astype(str))),
    )
    adata_nbn.uns["metric"] = metric
    adata_nbn.uns["category"] = category
    adata_nbn.uns["axis_entities"] = {
        "row_entity": dict(_NBHD_ENTITY),
        "col_entity": dict(_NBHD_ENTITY),
    }

    nbhd_lookup = gdf_nbhd.set_index(gdf_nbhd[nbhd_col].astype(str))

    if "cat" in gdf_nbhd.columns:
        # Use the category parameter name (e.g., "leiden") instead of "cat"
        for frame, names in (
            (adata_nbn.obs, adata_nbn.obs.index),
            (adata_nbn.var, adata_nbn.var.index),
        ):
            frame[category] = [
                str(nbhd_lookup.loc[n, "cat"]) if n in nbhd_lookup.index else str(n) for n in names
            ]

    if "color" in gdf_nbhd.columns:
        for frame, names in (
            (adata_nbn.obs, adata_nbn.obs.index),
            (adata_nbn.var, adata_nbn.var.index),
        ):
            frame["color"] = [
                nbhd_lookup.loc[n, "color"] if n in nbhd_lookup.index else "#808080" for n in names
            ]
        if "cat" in gdf_nbhd.columns:
            cat_color_map = dict(zip(adata_nbn.obs[category], adata_nbn.obs["color"], strict=False))
            adata_nbn.uns[f"{category}_colors"] = [
                cat_color_map.get(c, "#808080") for c in adata_nbn.obs[category].unique()
            ]

    return adata_nbn


def calc_nbhd_overlap(
    gdf_nbhd: Any,
    metric: str = "iou",
    nbhd_col: str = "name",
    category: str = "leiden",
) -> AnnData:
    """
    Calculate pairwise overlap between all neighborhoods.

    Parameters
    ----------
    gdf_nbhd : GeoDataFrame or neighborhood-like object
        Neighborhood geometries with an identifier column (`nbhd_col`).
    metric : str, default "iou"
        The overlap metric to compute:
        - "iou": intersection over union; symmetric, from 0 (no overlap) to 1
          (identical geometries).
        - "ioa": intersection over the row neighborhood's area; asymmetric,
          useful for containment analysis.
        - "intersection": raw intersection area in square units.
    nbhd_col : str, default "name"
        Column with neighborhood identifiers.
    category : str, default "leiden"
        Name of the category the neighborhoods represent (e.g. "leiden"); used
        for the category column in obs/var and the colors in uns.

    Returns
    -------
    AnnData
        Square neighborhoods x neighborhoods matrix with `obs["area"]`,
        `uns["metric"]`, and the neighborhood category/colors when the geometry
        has `cat`/`color` columns.

    Examples
    --------
    >>> adata_iou = dega.nbhd.calc_nbhd_overlap(gdf_alpha, metric="iou")
    >>> mat = dega.clust.Matrix(adata_iou)
    """
    gdf_nbhd, nbhd_col = _as_nbhd_gdf(gdf_nbhd, nbhd_col)

    valid_metrics = {"iou", "ioa", "intersection"}
    if metric not in valid_metrics:
        raise ValueError(f"metric must be one of {valid_metrics}, got '{metric}'")

    gdf_nbhd = gdf_nbhd.reset_index(drop=True)
    gdf_nbhd["geometry"] = gdf_nbhd["geometry"].buffer(0)

    names = gdf_nbhd[nbhd_col].astype(str).tolist()
    geom_lookup = dict(zip(names, gdf_nbhd["geometry"], strict=True))
    areas = {name: geom.area for name, geom in geom_lookup.items()}

    matrix = pd.DataFrame(0.0, index=names, columns=names)
    for name in names:
        matrix.loc[name, name] = 1.0 if metric in ("iou", "ioa") else round(areas[name], 2)

    for nb1, nb2 in combinations(names, 2):
        geom1 = geom_lookup[nb1]
        geom2 = geom_lookup[nb2]
        intersection = geom1.intersection(geom2)

        if intersection.is_empty or intersection.area == 0:
            continue

        intersection_area = intersection.area
        area1 = areas[nb1]
        area2 = areas[nb2]

        if metric == "iou":
            union_area = geom1.union(geom2).area
            value = intersection_area / union_area if union_area > 0 else 0.0
            matrix.loc[nb1, nb2] = round(value, 4)
            matrix.loc[nb2, nb1] = round(value, 4)
        elif metric == "ioa":
            # Asymmetric: what fraction of the row neighborhood overlaps the column
            matrix.loc[nb1, nb2] = round(intersection_area / area1 if area1 > 0 else 0.0, 4)
            matrix.loc[nb2, nb1] = round(intersection_area / area2 if area2 > 0 else 0.0, 4)
        else:
            matrix.loc[nb1, nb2] = round(intersection_area, 2)
            matrix.loc[nb2, nb1] = round(intersection_area, 2)

    adata_nbn = _square_nbhd_adata(matrix, gdf_nbhd, nbhd_col, metric, category)
    adata_nbn.obs["area"] = [areas[n] for n in matrix.index]
    return adata_nbn


def calc_nbhd_bordering(
    gdf_nbhd: Any,
    metric: str = "border_ratio",
    nbhd_col: str = "name",
    category: str = "leiden",
) -> AnnData:
    """
    Calculate pairwise border relationships between neighborhoods.

    Parameters
    ----------
    gdf_nbhd : GeoDataFrame or neighborhood-like object
        Neighborhood geometries with an identifier column (`nbhd_col`).
    metric : str, default "border_ratio"
        The border metric to compute:
        - "border_ratio": shared border length over the row neighborhood's
          perimeter (asymmetric).
        - "border_length": raw shared border length (symmetric).
        - "binary": 1 if the neighborhoods touch, 0 otherwise (symmetric).
    nbhd_col : str, default "name"
        Column with neighborhood identifiers.
    category : str, default "leiden"
        Name of the category the neighborhoods represent (e.g. "leiden"); used
        for the category column in obs/var and the colors in uns.

    Returns
    -------
    AnnData
        Square neighborhoods x neighborhoods matrix with `obs["perimeter"]`,
        `uns["metric"]`, and the neighborhood category/colors when the geometry
        has `cat`/`color` columns.

    Notes
    -----
    Shared border length is the length of the intersection of the two
    neighborhood boundaries, so this suits neighborhoods that touch without
    overlapping. For overlapping neighborhoods use :func:`calc_nbhd_overlap`.

    Examples
    --------
    >>> adata_border = dega.nbhd.calc_nbhd_bordering(gdf_hex_niche)
    >>> mat = dega.clust.Matrix(adata_border)
    """
    gdf_nbhd, nbhd_col = _as_nbhd_gdf(gdf_nbhd, nbhd_col)

    valid_metrics = {"border_ratio", "border_length", "binary"}
    if metric not in valid_metrics:
        raise ValueError(f"metric must be one of {valid_metrics}, got '{metric}'")

    # Drop the index before the self-join: a named index (e.g. one named "name"
    # mirroring nbhd_col) collides with that column during geopandas' internal
    # reset_index in newer geopandas, raising "cannot insert <name>, already exists".
    gdf_nbhd = gdf_nbhd.reset_index(drop=True)
    gdf_nbhd["geometry"] = gdf_nbhd["geometry"].buffer(0)
    gdf_nbhd[nbhd_col] = gdf_nbhd[nbhd_col].astype(str)

    names = gdf_nbhd[nbhd_col].tolist()
    geom_lookup = dict(zip(names, gdf_nbhd["geometry"], strict=True))
    perimeters = {name: geom.length for name, geom in geom_lookup.items()}

    matrix = pd.DataFrame(0.0, index=names, columns=names)

    gdf_join = gdf_nbhd[[nbhd_col, "geometry"]]
    gdf_touches = gpd.sjoin(gdf_join, gdf_join, how="inner", predicate="touches")
    gdf_touches = gdf_touches[gdf_touches[f"{nbhd_col}_left"] != gdf_touches[f"{nbhd_col}_right"]]

    seen_pairs: set[tuple[str, str]] = set()
    for nb1, nb2 in zip(
        gdf_touches[f"{nbhd_col}_left"], gdf_touches[f"{nbhd_col}_right"], strict=True
    ):
        pair_key = tuple(sorted((nb1, nb2)))
        if pair_key in seen_pairs:
            continue
        seen_pairs.add(pair_key)

        shared_border = geom_lookup[nb1].boundary.intersection(geom_lookup[nb2].boundary)
        border_length = shared_border.length if not shared_border.is_empty else 0.0

        if metric == "binary":
            matrix.loc[nb1, nb2] = 1.0
            matrix.loc[nb2, nb1] = 1.0
        elif metric == "border_length":
            matrix.loc[nb1, nb2] = round(border_length, 2)
            matrix.loc[nb2, nb1] = round(border_length, 2)
        else:
            perim1 = perimeters[nb1]
            perim2 = perimeters[nb2]
            matrix.loc[nb1, nb2] = round(border_length / perim1 if perim1 > 0 else 0.0, 4)
            matrix.loc[nb2, nb1] = round(border_length / perim2 if perim2 > 0 else 0.0, 4)

    adata_nbn = _square_nbhd_adata(matrix, gdf_nbhd, nbhd_col, metric, category)
    adata_nbn.obs["perimeter"] = [perimeters[n] for n in matrix.index]
    return adata_nbn
