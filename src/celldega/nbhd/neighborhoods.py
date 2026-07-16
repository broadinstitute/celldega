"""Spatial computation kernels and helpers for neighborhood feature calculation.

Public neighborhood feature/relation calculation lives on
:class:`celldega.nbhd.collection.NeighborhoodCollection`; the functions here are
its internal spatial kernels (``_calc_nbhd_by_pop``, ``_calc_nbhd_by_gene``,
``_calc_nbhd_overlap``, ``_calc_nbhd_bordering``,
``_calc_nbhd_transcript_assignment``) plus
geometry/subsetting helpers.
"""

# Standard library imports
from itertools import combinations
import warnings

from anndata import AnnData

# Third-party imports
import geopandas as gpd
import numpy as np
import pandas as pd
from scipy import sparse

from celldega.nbhd.collection import NeighborhoodCollection
from celldega.nbhd.utils import df_to_anndata


def _nbhd_geometry_for_join(gdf_nbhd: gpd.GeoDataFrame, nbhd_col: str) -> gpd.GeoDataFrame:
    return gdf_nbhd[[nbhd_col, "geometry"]].reset_index(drop=True)


def _calc_nbhd_by_gene(
    gdf_nbhd: gpd.GeoDataFrame,
    by: str = "cell",
    adata: AnnData | None = None,
    data_dir: str | None = None,
    gdf_trx: gpd.GeoDataFrame | None = None,
    feature_col: str = "feature_name",
    trx_parquet_path: str | None = None,
    x_col: str = "x",
    y_col: str = "y",
    batch_size: int = 1_000_000,
    nbhd_col: str = "name",
    min_cells: int = 1,
) -> AnnData:
    """
    Calculate neighborhood-by-gene expression matrix.

    Internal spatial-computation kernel. The public entry point is
    :meth:`NeighborhoodCollection.calc_signature`.

    Computes gene expression values for each neighborhood, either from cell-level
    expression data (mean expression of cells within each neighborhood, `by="cell"`)
    or from raw transcript counts (`by="cell-free"`).

    Parameters
    ----------
    gdf_nbhd : gpd.GeoDataFrame
        GeoDataFrame containing neighborhood geometries. Must have a geometry column
        and a column specified by `nbhd_col` for neighborhood identifiers.
    by : str, default "cell"
        "cell" (requires `adata`) or "cell-free" (requires one of `gdf_trx`,
        `trx_parquet_path`, `data_dir`).
    adata : AnnData, optional
        AnnData object with cell data. Required when `by="cell"`. Must have spatial
        coordinates in `obsm["spatial"]`.
    data_dir : str, optional
        Directory with a Xenium-convention `transcripts.parquet`
        (`feature_name`/`x_location`/`y_location` columns). Used for `by="cell-free"`
        when neither `gdf_trx` nor `trx_parquet_path` is given.
    gdf_trx : gpd.GeoDataFrame, optional
        Pre-loaded transcript points for `by="cell-free"` (custom paths/column
        names); a `geometry` column plus a gene column named `feature_col`. Takes
        precedence over `trx_parquet_path` and `data_dir`.
    feature_col : str, default "feature_name"
        Gene/feature column name, used with `gdf_trx` or as `gene_col` when
        streaming from `trx_parquet_path` (`data_dir` always uses `feature_name`).
    trx_parquet_path : str, optional
        Transcripts parquet path to stream in batches for `by="cell-free"`
        instead of loading into memory (see `celldega.nbhd.trx_streaming`); takes
        precedence over `data_dir` but not `gdf_trx`.
    x_col, y_col : str, default "x", "y"
        Transcript coordinate columns in `trx_parquet_path`.
    batch_size : int, default 1_000_000
        Rows read per streamed batch when using `trx_parquet_path`.
    nbhd_col : str, default "name"
        Column in `gdf_nbhd` containing neighborhood identifiers.
    min_cells : int, default 1
        Minimum number of cells/transcripts required within a neighborhood to
        include it in the output.

    Returns
    -------
    AnnData
        Shape (n_neighborhoods, n_genes): `X` = expression values (mean for
        cell-derived, counts for cell-free), `obs`/`var` indexed by neighborhood/
        gene, plus `obs["n_cells"]` (`by="cell"`) or `obs["n_transcripts"]`
        (`by="cell-free"`) and `uns["by"]`.
    """
    if by == "cell":
        if adata is None:
            raise ValueError("adata is required when by='cell'")

        print("Calculating neighborhood-by-gene (cell-derived)")

        gene_list = adata.var.index
        gene_exp = pd.DataFrame(
            adata.X.toarray() if hasattr(adata.X, "toarray") else adata.X,
            columns=gene_list,
            index=adata.obs_names,
        )

        gdf_cell = gpd.GeoDataFrame(
            data=gene_exp,
            geometry=gpd.points_from_xy(*adata.obsm["spatial"].T[:2]),
        )

        # Spatial join cells to neighborhoods
        joined = gdf_cell.sjoin(
            _nbhd_geometry_for_join(gdf_nbhd, nbhd_col),
            how="left",
            predicate="within",
        )
        joined.drop(columns=["index_right", "geometry"], inplace=True, errors="ignore")

        # Count cells per neighborhood for filtering
        cell_counts = joined[nbhd_col].value_counts()
        valid_nbhds = cell_counts[cell_counts >= min_cells].index
        joined = joined[joined[nbhd_col].isin(valid_nbhds)]

        # Compute mean expression per neighborhood
        df_result = joined.groupby(nbhd_col)[list(gene_list)].mean()

        # Filter gdf_nbhd to only include valid neighborhoods
        filtered_gdf = gdf_nbhd[gdf_nbhd[nbhd_col].isin(valid_nbhds)].reset_index(drop=True)

        # Reindex to preserve order
        df_result = df_result.reindex(filtered_gdf[nbhd_col]).fillna(0)

        adata_nbg = df_to_anndata(df_result)
        adata_nbg.obs["n_cells"] = [cell_counts.get(n, 0) for n in adata_nbg.obs.index]

    elif by == "cell-free":
        if gdf_trx is not None:
            print("Calculating neighborhood-by-gene (cell-free, provided gdf_trx)")
            joined = gdf_trx[[feature_col, "geometry"]].sjoin(
                _nbhd_geometry_for_join(gdf_nbhd, nbhd_col), how="left", predicate="within"
            )
            df_result = (
                joined.groupby([nbhd_col, feature_col])
                .size()
                .unstack(fill_value=0)
                .rename_axis(None, axis=1)
                .reindex(gdf_nbhd[nbhd_col])
                .fillna(0)
                .astype(int)
            )
        elif trx_parquet_path is not None:
            print("Calculating neighborhood-by-gene (cell-free, streaming parquet)")
            from celldega.nbhd.trx_streaming import _assign_trx_to_entity_streaming_parquet

            df_result = (
                _assign_trx_to_entity_streaming_parquet(
                    trx_parquet_path,
                    gdf_nbhd,
                    id_col=nbhd_col,
                    x_col=x_col,
                    y_col=y_col,
                    gene_col=feature_col,
                    batch_size=batch_size,
                )
                .reindex(gdf_nbhd[nbhd_col])
                .fillna(0)
                .astype(int)
            )
        elif data_dir is not None:
            print("Calculating neighborhood-by-gene (cell-free)")

            df_trx = pd.read_parquet(
                f"{data_dir}/transcripts.parquet",
                columns=["feature_name", "x_location", "y_location"],
                engine="pyarrow",
            )
            geometry = gpd.points_from_xy(df_trx["x_location"], df_trx["y_location"])
            feature_col = "feature_name"
            joined = gpd.GeoDataFrame(df_trx[[feature_col]], geometry=geometry).sjoin(
                _nbhd_geometry_for_join(gdf_nbhd, nbhd_col), how="left", predicate="within"
            )
            df_result = (
                joined.groupby([nbhd_col, feature_col])
                .size()
                .unstack(fill_value=0)
                .rename_axis(None, axis=1)
                .reindex(gdf_nbhd[nbhd_col])
                .fillna(0)
                .astype(int)
            )
        else:
            raise ValueError(
                "data_dir, gdf_trx, or trx_parquet_path is required when by='cell-free'"
            )

        # Filter by min_cells (here it's min transcripts total)
        trx_counts = df_result.sum(axis=1)
        valid_nbhds = trx_counts[trx_counts >= min_cells].index
        df_result = df_result.loc[valid_nbhds]

        filtered_gdf = gdf_nbhd[gdf_nbhd[nbhd_col].isin(valid_nbhds)].reset_index(drop=True)

        adata_nbg = df_to_anndata(df_result)
        adata_nbg.obs["n_transcripts"] = trx_counts.loc[valid_nbhds].values

    else:
        raise ValueError("by must be 'cell' or 'cell-free'")

    # Store metadata common to both modes
    adata_nbg.uns["by"] = by

    # Add neighborhood category and colors from gdf_nbhd if available
    if "cat" in filtered_gdf.columns:
        nbhd_cat_lookup = dict(
            zip(filtered_gdf[nbhd_col], filtered_gdf["cat"].astype(str), strict=False)
        )
        adata_nbg.obs["cat"] = [nbhd_cat_lookup.get(n, str(n)) for n in adata_nbg.obs.index]

    if "color" in filtered_gdf.columns:
        nbhd_color_lookup = dict(zip(filtered_gdf[nbhd_col], filtered_gdf["color"], strict=False))
        adata_nbg.obs["color"] = [nbhd_color_lookup.get(n, "#808080") for n in adata_nbg.obs.index]
        # Store colors in uns as well
        adata_nbg.uns["nbhd_colors"] = [
            nbhd_color_lookup.get(n, "#808080") for n in adata_nbg.obs.index
        ]

    return adata_nbg


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
    if collection.mod:
        collection.mdata = collection.mdata[obs_names, :].copy()
    else:
        from celldega.collection import _empty_mudata

        obs = collection.obs.loc[obs_names].copy()
        uns = dict(collection.mdata.uns)
        relations = list(collection.relations.items())
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


def _calc_nbhd_by_pop(
    adata: AnnData,
    gdf_nbhd: gpd.GeoDataFrame,
    category: str = "leiden",
    nbhd_col: str = "name",
    min_cells: int = 5,
    output: str = "proportion",
) -> AnnData:
    """
    Calculate cell-level population distribution of neighborhoods.

    Internal spatial-computation kernel. The public entry point is
    :meth:`NeighborhoodCollection.calc_population`.

    Computes a neighborhood-by-population matrix showing the distribution of cell
    categories (e.g., clusters, cell types) within each neighborhood.

    Parameters
    ----------
    adata : AnnData
        Cell-level AnnData containing spatial coordinates in `obsm["spatial"]`
        and the category column in `obs`.
    gdf_nbhd : gpd.GeoDataFrame
        GeoDataFrame containing neighborhood geometries.
    category : str, default "leiden"
        Column name in `adata.obs` containing cell category labels (e.g., "leiden",
        "cell_type", "cluster").
    nbhd_col : str, default "name"
        Column name in `gdf_nbhd` containing neighborhood identifiers.
    min_cells : int, default 5
        Minimum number of cells required within a neighborhood to include it in
        the output. Neighborhoods with fewer cells are filtered out.
    output : str, default "proportion"
        Type of values in the output matrix:
        - "proportion": Fraction of cells per category (sums to 1 per neighborhood)
        - "counts": Raw cell counts per category
    Returns
    -------
    AnnData
        AnnData object with shape (n_neighborhoods, n_categories) where:
        - `X`: Matrix of population distributions (proportions or counts)
        - `obs`: DataFrame indexed by neighborhood names
        - `var`: DataFrame indexed by category names
        - `obs["n_cells"]`: Total cell count per neighborhood

    Internal spatial-computation kernel. The public entry point is
    :meth:`NeighborhoodCollection.calc_population`.
    """
    print("Calculating NBP")

    source_adata = adata

    if gdf_nbhd is None:
        raise ValueError("gdf_nbhd is required to calculate a neighborhood population modality")

    # Validate inputs
    required_nbhd = {"geometry", nbhd_col}
    if not required_nbhd.issubset(gdf_nbhd.columns):
        raise ValueError(
            f"gdf_nbhd missing required columns: {required_nbhd - set(gdf_nbhd.columns)}"
        )
    if category not in source_adata.obs.columns:
        raise ValueError(f"adata.obs missing required '{category}' column")
    if "spatial" not in source_adata.obsm:
        raise ValueError("adata.obsm missing 'spatial' coordinates")
    if output not in {"proportion", "counts"}:
        raise ValueError("output must be 'proportion' or 'counts'")

    # Build GeoDataFrame from adata with the specified category
    # No CRS set - using micron imaging coordinates, not geospatial
    gdf_cell = gpd.GeoDataFrame(
        {category: source_adata.obs[category].values},
        geometry=gpd.points_from_xy(*source_adata.obsm["spatial"].T[:2]),
    )

    # Spatial join: assign each cell to a neighborhood
    sjoin_df = gdf_cell.sjoin(
        _nbhd_geometry_for_join(gdf_nbhd, nbhd_col),
        how="left",
        predicate="within",
    )

    # Filter neighborhoods with at least min_cells
    cell_counts_per_nbhd = sjoin_df[nbhd_col].value_counts()
    valid_nbhd_names = cell_counts_per_nbhd[cell_counts_per_nbhd >= min_cells].index
    sjoin_df = sjoin_df[sjoin_df[nbhd_col].isin(valid_nbhd_names)]

    # Count cells per (neighborhood, cluster)
    counts = (
        sjoin_df.groupby([nbhd_col, category])
        .size()
        .unstack(fill_value=0)
        .pipe(lambda df: df.set_axis(df.columns.astype(str), axis=1))
    )

    # Reindex to preserve order of filtered gdf_nbhd
    filtered_gdf_nbhd = gdf_nbhd[gdf_nbhd[nbhd_col].isin(valid_nbhd_names)].reset_index(drop=True)
    counts = counts.reindex(filtered_gdf_nbhd[nbhd_col]).fillna(0).astype(int)

    # Calculate output values
    if output == "proportion":
        values = counts.div(counts.sum(axis=1), axis=0).fillna(0).values
    else:
        values = counts.values

    # Build AnnData
    adata_nbp = AnnData(
        X=values,
        obs=pd.DataFrame(index=counts.index),
        var=pd.DataFrame(index=counts.columns),
    )
    adata_nbp.obs["n_cells"] = counts.sum(axis=1).values
    adata_nbp.uns["category"] = category
    adata_nbp.uns["output"] = output

    # Add category as a var column (columns represent categories)
    adata_nbp.var[category] = adata_nbp.var.index.astype(str)

    # Also add category to obs - neighborhoods are named by their cluster
    # Look up category from gdf_nbhd if available
    if "cat" in filtered_gdf_nbhd.columns:
        nbhd_cat_lookup = dict(
            zip(filtered_gdf_nbhd[nbhd_col], filtered_gdf_nbhd["cat"].astype(str), strict=False)
        )
        adata_nbp.obs[category] = [nbhd_cat_lookup.get(n, str(n)) for n in adata_nbp.obs.index]
    else:
        # Default: use the index (neighborhood name) as the category
        adata_nbp.obs[category] = adata_nbp.obs.index.astype(str)

    # Copy colors from source adata if available
    color_key = f"{category}_colors"
    color_dict: dict[str, str] = {}
    if color_key in source_adata.uns:
        # Map colors to the category values
        src_colors = source_adata.uns[color_key]
        if hasattr(source_adata.obs[category], "cat"):
            src_categories = list(source_adata.obs[category].cat.categories.astype(str))
        else:
            src_categories = list(source_adata.obs[category].unique().astype(str))

        color_dict = {
            str(cat): src_colors[i] for i, cat in enumerate(src_categories) if i < len(src_colors)
        }

        # Assign colors to var (columns)
        adata_nbp.var["color"] = [color_dict.get(str(c), "#808080") for c in adata_nbp.var.index]
        adata_nbp.uns[color_key] = [color_dict.get(str(c), "#808080") for c in adata_nbp.var.index]

        # Also assign colors to obs (rows/neighborhoods)
        adata_nbp.obs["color"] = [
            color_dict.get(str(c), "#808080") for c in adata_nbp.obs[category]
        ]

    return adata_nbp


def _calc_nbhd_transcript_assignment(
    gdf_nbhd: gpd.GeoDataFrame,
    unique_nbhd_col: str,
    gdf_trx: gpd.GeoDataFrame,
) -> pd.DataFrame:
    """Per-neighborhood transcript counts and cell-assignment proportion.

    A transcript counts as assigned when its ``cell_id`` is not ``"UNASSIGNED"``.

    Assumption: transcript-to-cell assignment is **not computed here** — it must
    already be present in the instrument data, with unassigned transcripts marked
    by the ``"UNASSIGNED"`` sentinel (Xenium convention). A missing ``cell_id``
    column raises ``ValueError``; a complete absence of the sentinel warns (it may
    be genuinely fully assigned, or use a different convention).

    Returns a DataFrame indexed by neighborhood id with columns
    ``total_transcripts``, ``unassigned_transcripts``, and
    ``transcript_assignment_proportion`` (assigned / total; ``0.0`` when a
    neighborhood has no transcripts).

    Internal spatial-computation kernel. The public entry point is
    :meth:`NeighborhoodCollection.calc_transcript_assignment`.
    """
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

    nbhd_ids = pd.Index(gdf_nbhd[unique_nbhd_col].astype(str))
    joined = gdf_trx.sjoin(
        _nbhd_geometry_for_join(gdf_nbhd, unique_nbhd_col),
        how="left",
        predicate="within",
    )
    grouped = joined.groupby(unique_nbhd_col)["cell_id"]
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


def _calc_nbhd_overlap(
    gdf_nbhd: gpd.GeoDataFrame,
    metric: str = "iou",
    name_col: str = "name",
    category: str = "leiden",
) -> AnnData:
    """
    Calculate pairwise overlap between all neighborhoods as a neighborhood-by-neighborhood matrix.

    Parameters
    ----------
    gdf_nbhd : gpd.GeoDataFrame
        GeoDataFrame containing neighborhood geometries. Must have a geometry column
        and a column specified by `name_col` for neighborhood identifiers.
    metric : str, default "iou"
        The overlap metric to compute:
        - "iou": Intersection over Union. Value = intersection_area / union_area.
          Symmetric measure ranging from 0 (no overlap) to 1 (identical geometries).
        - "ioa": Intersection over Area (of self/row). Value = intersection_area / row_area.
          Asymmetric measure showing what fraction of the row neighborhood overlaps
          with the column neighborhood. Useful for containment analysis.
        - "intersection": Raw intersection area in square units.
    name_col : str, default "name"
        Column name containing neighborhood identifiers.
    category : str, default "leiden"
        Name of the category that neighborhoods represent (e.g., "leiden", "cell_type").
        This is used to name the category column in obs/var and the colors in uns.

    Returns
    -------
    AnnData
        AnnData object with shape (n_neighborhoods, n_neighborhoods) where:
        - `X`: Matrix of overlap values
        - `obs`: DataFrame indexed by neighborhood names (rows)
        - `var`: DataFrame indexed by neighborhood names (columns)
        - `obs["area"]`: Area of each neighborhood
        - `obs[category]`: Category value for each neighborhood
        - `uns["metric"]`: The metric used for computation

    Examples
    --------
    Internal spatial-computation kernel. The public entry point is
    :meth:`NeighborhoodCollection.calc_overlap`.
    >>> mat = dega.clust.Matrix(adata_iou, row_entity="nbhd", col_entity="nbhd")
    """
    print(f"Calculating NBN-O ({metric})")

    valid_metrics = {"iou", "ioa", "intersection"}
    if metric not in valid_metrics:
        raise ValueError(f"metric must be one of {valid_metrics}, got '{metric}'")

    gdf_nbhd = gdf_nbhd.copy()
    gdf_nbhd["geometry"] = gdf_nbhd["geometry"].buffer(0)

    names = gdf_nbhd[name_col].tolist()

    # Pre-compute areas for efficiency
    areas = {row[name_col]: row["geometry"].area for _, row in gdf_nbhd.iterrows()}

    # Initialize matrix with zeros
    matrix = pd.DataFrame(0.0, index=names, columns=names)

    # Set diagonal values
    for name in names:
        if metric in ("iou", "ioa"):
            matrix.loc[name, name] = 1.0
        else:  # intersection
            matrix.loc[name, name] = round(areas[name], 2)

    # Build a lookup for geometries
    geom_lookup = {row[name_col]: row["geometry"] for _, row in gdf_nbhd.iterrows()}

    # Compute pairwise overlaps
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
            matrix.loc[nb2, nb1] = round(value, 4)  # Symmetric
        elif metric == "ioa":
            # Asymmetric: row's perspective (what fraction of row overlaps with col)
            value_1_to_2 = intersection_area / area1 if area1 > 0 else 0.0
            value_2_to_1 = intersection_area / area2 if area2 > 0 else 0.0
            matrix.loc[nb1, nb2] = round(value_1_to_2, 4)
            matrix.loc[nb2, nb1] = round(value_2_to_1, 4)
        else:  # intersection
            matrix.loc[nb1, nb2] = round(intersection_area, 2)
            matrix.loc[nb2, nb1] = round(intersection_area, 2)  # Symmetric

    # Build AnnData
    adata_nbn = AnnData(
        X=matrix.values,
        obs=pd.DataFrame(index=matrix.index),
        var=pd.DataFrame(index=matrix.columns),
    )
    adata_nbn.obs["area"] = [areas[n] for n in matrix.index]
    adata_nbn.uns["metric"] = metric
    adata_nbn.uns["category"] = category

    # Add category and color metadata from gdf_nbhd if available
    # Look up by name_col to get cat and color for each neighborhood
    nbhd_lookup = gdf_nbhd.set_index(name_col)

    if "cat" in gdf_nbhd.columns:
        # Use the category parameter name (e.g., "leiden") instead of "cat"
        adata_nbn.obs[category] = [
            str(nbhd_lookup.loc[n, "cat"]) if n in nbhd_lookup.index else str(n)
            for n in matrix.index
        ]
        adata_nbn.var[category] = [
            str(nbhd_lookup.loc[n, "cat"]) if n in nbhd_lookup.index else str(n)
            for n in matrix.columns
        ]

    if "color" in gdf_nbhd.columns:
        obs_colors = [
            nbhd_lookup.loc[n, "color"] if n in nbhd_lookup.index else "#808080"
            for n in matrix.index
        ]
        adata_nbn.obs["color"] = obs_colors
        adata_nbn.var["color"] = [
            nbhd_lookup.loc[n, "color"] if n in nbhd_lookup.index else "#808080"
            for n in matrix.columns
        ]
        # Store colors in uns using the category name (e.g., "leiden_colors")
        if "cat" in gdf_nbhd.columns:
            unique_cats = adata_nbn.obs[category].unique()
            cat_color_map = dict(zip(adata_nbn.obs[category], obs_colors, strict=False))
            adata_nbn.uns[f"{category}_colors"] = [
                cat_color_map.get(c, "#808080") for c in unique_cats
            ]

    return adata_nbn


def _calc_nbhd_bordering(
    gdf_nbhd: gpd.GeoDataFrame,
    metric: str = "border_ratio",
    name_col: str = "name",
    category: str = "leiden",
) -> AnnData:
    """
    Calculate pairwise border relationships between neighborhoods.

    Parameters
    ----------
    gdf_nbhd : gpd.GeoDataFrame
        GeoDataFrame containing neighborhood geometries. Must have a geometry column
        and a column specified by `name_col` for neighborhood identifiers.
    metric : str, default "border_ratio"
        The border metric to compute:
        - "border_ratio": Border length over self (row) perimeter.
          Value = shared_border_length / row_perimeter.
          Asymmetric measure showing what fraction of the row neighborhood's
          perimeter is shared with the column neighborhood.
        - "border_length": Raw shared border length in linear units.
          Symmetric measure of the absolute length of shared boundary.
        - "binary": Binary adjacency (1 if touching, 0 otherwise).
          Symmetric measure indicating whether neighborhoods share a border.
    name_col : str, default "name"
        Column name containing neighborhood identifiers.
    category : str, default "leiden"
        Name of the category that neighborhoods represent (e.g., "leiden", "cell_type").
        This is used to name the category column in obs/var and the colors in uns.

    Returns
    -------
    AnnData
        AnnData object with shape (n_neighborhoods, n_neighborhoods) where:
        - `X`: Matrix of border metric values
        - `obs`: DataFrame indexed by neighborhood names (rows)
        - `var`: DataFrame indexed by neighborhood names (columns)
        - `obs["perimeter"]`: Perimeter of each neighborhood
        - `obs[category]`: Category value for each neighborhood
        - `uns["metric"]`: The metric used for computation

    Notes
    -----
    Shared border length is computed as the length of the intersection of the
    two neighborhood boundaries (perimeters). This works for neighborhoods that
    touch but don't overlap. For overlapping neighborhoods, consider using
    `_calc_nbhd_overlap` instead.

    Examples
    --------
    Internal spatial-computation kernel. The public entry point is
    :meth:`NeighborhoodCollection.calc_bordering`.
    >>> mat = dega.clust.Matrix(adata_border, row_entity="nbhd", col_entity="nbhd")
    """
    print(f"Calculating NBN-B ({metric})")

    valid_metrics = {"border_ratio", "border_length", "binary"}
    if metric not in valid_metrics:
        raise ValueError(f"metric must be one of {valid_metrics}, got '{metric}'")

    gdf_nbhd = gdf_nbhd.copy()
    # Drop the index before the self-join: gdf_nbhd is keyed off name_col (a
    # column), and a named index (e.g. one named "name" mirroring name_col)
    # collides with that column during geopandas' internal reset_index in
    # newer geopandas, raising "cannot insert <name>, already exists".
    gdf_nbhd = gdf_nbhd.reset_index(drop=True)
    gdf_nbhd["geometry"] = gdf_nbhd["geometry"].buffer(0)

    names = gdf_nbhd[name_col].tolist()

    # Pre-compute perimeters for efficiency
    perimeters = {row[name_col]: row["geometry"].length for _, row in gdf_nbhd.iterrows()}

    # Build a lookup for geometries
    geom_lookup = {row[name_col]: row["geometry"] for _, row in gdf_nbhd.iterrows()}

    # Initialize matrix with zeros
    matrix = pd.DataFrame(0.0, index=names, columns=names)

    # Use spatial index to find touching pairs efficiently
    gdf_touches = gpd.sjoin(gdf_nbhd, gdf_nbhd, how="inner", predicate="touches")
    gdf_touches = gdf_touches[gdf_touches[f"{name_col}_left"] != gdf_touches[f"{name_col}_right"]]

    # Get unique pairs
    seen_pairs: set[tuple[str, str]] = set()
    for _, row in gdf_touches.iterrows():
        nb1 = row[f"{name_col}_left"]
        nb2 = row[f"{name_col}_right"]

        # Skip if we've already processed this pair
        pair_key = tuple(sorted((nb1, nb2)))
        if pair_key in seen_pairs:
            continue
        seen_pairs.add(pair_key)

        geom1 = geom_lookup[nb1]
        geom2 = geom_lookup[nb2]

        # Compute shared border length as intersection of boundaries
        boundary1 = geom1.boundary
        boundary2 = geom2.boundary
        shared_border = boundary1.intersection(boundary2)
        border_length = shared_border.length if not shared_border.is_empty else 0.0

        if metric == "binary":
            matrix.loc[nb1, nb2] = 1.0
            matrix.loc[nb2, nb1] = 1.0
        elif metric == "border_length":
            matrix.loc[nb1, nb2] = round(border_length, 2)
            matrix.loc[nb2, nb1] = round(border_length, 2)  # Symmetric
        elif metric == "border_ratio":
            # Asymmetric: what fraction of each neighborhood's perimeter is shared
            perim1 = perimeters[nb1]
            perim2 = perimeters[nb2]
            ratio_1 = border_length / perim1 if perim1 > 0 else 0.0
            ratio_2 = border_length / perim2 if perim2 > 0 else 0.0
            matrix.loc[nb1, nb2] = round(ratio_1, 4)
            matrix.loc[nb2, nb1] = round(ratio_2, 4)

    # Build AnnData
    adata_nbn = AnnData(
        X=matrix.values,
        obs=pd.DataFrame(index=matrix.index),
        var=pd.DataFrame(index=matrix.columns),
    )
    adata_nbn.obs["perimeter"] = [perimeters[n] for n in matrix.index]
    adata_nbn.uns["metric"] = metric
    adata_nbn.uns["category"] = category

    # Add category and color metadata from gdf_nbhd if available
    nbhd_lookup = gdf_nbhd.set_index(name_col)

    if "cat" in gdf_nbhd.columns:
        # Use the category parameter name (e.g., "leiden") instead of "cat"
        adata_nbn.obs[category] = [
            str(nbhd_lookup.loc[n, "cat"]) if n in nbhd_lookup.index else str(n)
            for n in matrix.index
        ]
        adata_nbn.var[category] = [
            str(nbhd_lookup.loc[n, "cat"]) if n in nbhd_lookup.index else str(n)
            for n in matrix.columns
        ]

    if "color" in gdf_nbhd.columns:
        obs_colors = [
            nbhd_lookup.loc[n, "color"] if n in nbhd_lookup.index else "#808080"
            for n in matrix.index
        ]
        adata_nbn.obs["color"] = obs_colors
        adata_nbn.var["color"] = [
            nbhd_lookup.loc[n, "color"] if n in nbhd_lookup.index else "#808080"
            for n in matrix.columns
        ]
        # Store colors in uns using the category name (e.g., "leiden_colors")
        if "cat" in gdf_nbhd.columns:
            unique_cats = adata_nbn.obs[category].unique()
            cat_color_map = dict(zip(adata_nbn.obs[category], obs_colors, strict=False))
            adata_nbn.uns[f"{category}_colors"] = [
                cat_color_map.get(c, "#808080") for c in unique_cats
            ]

    return adata_nbn
