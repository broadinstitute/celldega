"""
Main clustering function for celldega network analysis.

This module provides hierarchical clustering functionality with similarity
matrix generation and gene enrichment analysis integration.
"""

from typing import Any

from . import calc_clust, enrichr_functions as enr_fun, make_sim_mat


def make_clust(
    net: Any,
    dist_type: str = "cosine",
    run_clustering: bool = True,
    dendro: bool = True,
    requested_views: list[str] | None = None,
    linkage_type: str = "average",
    sim_mat: bool | str = False,
    filter_sim: float = 0.0,
    calc_cat_pval: bool = False,
    sim_mat_views: list[str] | None = None,
    run_enrichr: str | None = None,
    enrichrgram: bool | None = None,
    clust_library: str = "scipy",
    min_samples: int = 1,
    min_cluster_size: int = 2,
) -> None:
    """
    Perform hierarchical clustering on network data with optional enhancements.

    This function performs hierarchical clustering on both rows and columns of the
    network's data matrix, with optional similarity matrix generation and gene
    enrichment analysis. The network object is modified in place.

    Parameters
    ----------
    net : Network
        Network object containing the data matrix and metadata structures.
        Must have 'dat' and 'viz' attributes with expected internal structure.
    dist_type : str, default='cosine'
        Distance metric for clustering. Common options:
        'cosine', 'euclidean', 'manhattan', 'correlation'.
    run_clustering : bool, default=True
        Whether to perform hierarchical clustering. If False, maintains original ordering.
    dendro : bool, default=True
        Whether to generate dendrogram visualization components.
    requested_views : list[str] | None, default=None
        Views for clustering processing. Defaults to ['pct_row_sum', 'N_row_sum'].
        These views are cleared from the final visualization output.
    linkage_type : str, default='average'
        Hierarchical clustering linkage method:
        'average', 'ward', 'complete', 'single'.
    sim_mat : bool | str, default=False
        Similarity matrix generation control:
        - False: No similarity matrices
        - True: Generate for both rows and columns
        - 'row': Generate only for rows
        - 'col': Generate only for columns
        Invalid values are silently ignored.
    filter_sim : float, default=0.0
        Similarity filtering threshold [0.0, 1.0]. Values below threshold are zeroed.
    calc_cat_pval : bool, default=False
        Whether to calculate statistical significance (p-values) for categories.
    sim_mat_views : list[str] | None, default=None
        Views for similarity matrices. Defaults to ['N_row_sum'].
    run_enrichr : str | None, default=None
        Enrichr library name for gene enrichment analysis.
        Examples: 'KEGG_2016', 'GO_Biological_Process_2015'.
    enrichrgram : bool | None, default=None
        Whether to enable enrichrgram visualization interface mode.
    clust_library : str, default='scipy'
        Clustering library: 'scipy', 'fastcluster', 'hdbscan'.
    min_samples : int, default=1
        Minimum samples for HDBSCAN clustering (ignored for other libraries).
    min_cluster_size : int, default=2
        Minimum cluster size for HDBSCAN clustering (ignored for other libraries).

    Returns
    -------
    None
        Function modifies the network object in place.
    """

    # Apply parameter defaults for backward compatibility
    if requested_views is None:
        requested_views = ["pct_row_sum", "N_row_sum"]
    if sim_mat_views is None:
        sim_mat_views = ["N_row_sum"]

    # Gene enrichment analysis preprocessing
    if run_enrichr is not None:
        df = net.dat_to_df()
        df = enr_fun.add_enrichr_cats(df, "row", run_enrichr)
        net.df_to_dat(df, define_cat_colors=True)

    # Core hierarchical clustering operation
    distance_matrices = calc_clust.cluster_row_and_col(
        net,
        dist_type=dist_type,
        linkage_type=linkage_type,
        run_clustering=run_clustering,
        dendro=dendro,
        ignore_cat=False,
        calc_cat_pval=calc_cat_pval,
        clust_library=clust_library,
        min_samples=min_samples,
        min_cluster_size=min_cluster_size,
    )

    # Determine similarity matrix axes based on sim_mat parameter
    similarity_axes: list[str] = []
    if sim_mat is True:
        similarity_axes = ["row", "col"]
    elif sim_mat == "row":
        similarity_axes = ["row"]
    elif sim_mat == "col":
        similarity_axes = ["col"]

    # Generate similarity matrices and visualizations
    if sim_mat is not False and similarity_axes:
        similarity_networks = make_sim_mat.main(
            net, distance_matrices, similarity_axes, filter_sim, sim_mat_views
        )

        # Initialize and populate similarity matrix data
        net.sim = {}
        for axis in similarity_axes:
            net.sim[axis] = similarity_networks[axis].viz

            # Fixed color assignment: each axis gets its own colors
            other_axis = "col" if axis == "row" else "row"
            net.sim[axis]["cat_colors"][axis] = net.viz["cat_colors"][axis]
            net.sim[axis]["cat_colors"][other_axis] = net.viz["cat_colors"][other_axis]
    else:
        net.sim = {}

    # Reset visualization views
    net.viz["views"] = []

    # Configure enrichrgram visualization settings
    if "enrichrgram_lib" in net.dat:
        net.viz["enrichrgram"] = True
        net.viz["enrichrgram_lib"] = net.dat["enrichrgram_lib"]
    elif enrichrgram is not None:
        net.viz["enrichrgram"] = enrichrgram

    # Transfer enrichment visualization data from dat to viz
    if "row_cat_bars" in net.dat:
        net.viz["row_cat_bars"] = net.dat["row_cat_bars"]
