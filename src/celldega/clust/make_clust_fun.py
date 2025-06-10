from . import calc_clust, enrichr_functions as enr_fun, make_sim_mat


def make_clust(
    net,
    dist_type="cosine",
    run_clustering=True,
    dendro=True,
    requested_views=None,
    linkage_type="average",
    sim_mat=False,
    filter_sim=0.0,
    calc_cat_pval=False,
    sim_mat_views=None,
    run_enrichr=None,
    enrichrgram=None,
    clust_library="scipy",
    min_samples=1,
    min_cluster_size=2,
):
    """
    This will perform hierarchical clustering
    """
    if requested_views is None:
        requested_views = ["pct_row_sum", "N_row_sum"]

    if sim_mat_views is None:
        sim_mat_views = ["N_row_sum"]

    # threshold = 0.0001
    # df = run_filter.df_filter_row_sum(df, threshold)
    # df = run_filter.df_filter_col_sum(df, threshold)

    if run_enrichr is not None:
        df = net.dat_to_df()
        df = enr_fun.add_enrichr_cats(df, "row", run_enrichr)
        net.df_to_dat(df, define_cat_colors=True)

    inst_dm = calc_clust.cluster_row_and_col(
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

    which_sim = []

    if sim_mat is True:
        which_sim = ["row", "col"]
    elif sim_mat == "row":
        which_sim = ["row"]
    elif sim_mat == "col":
        which_sim = ["col"]

    if sim_mat is not False:
        sim_net = make_sim_mat.main(net, inst_dm, which_sim, filter_sim, sim_mat_views)

        net.sim = {}

        for inst_rc in which_sim:
            net.sim[inst_rc] = sim_net[inst_rc].viz

            other_rc = "col" if inst_rc == "row" else "row"

            # keep track of cat_colors
            net.sim[inst_rc]["cat_colors"][inst_rc] = net.viz["cat_colors"][inst_rc]
            net.sim[inst_rc]["cat_colors"][other_rc] = net.viz["cat_colors"][inst_rc]

    else:
        net.sim = {}

    net.viz["views"] = []

    if enrichrgram is not None:
        # toggle enrichrgram functionality from back-end
        net.viz["enrichrgram"] = enrichrgram

    if "enrichrgram_lib" in net.dat:
        net.viz["enrichrgram"] = True
        net.viz["enrichrgram_lib"] = net.dat["enrichrgram_lib"]

    if "row_cat_bars" in net.dat:
        net.viz["row_cat_bars"] = net.dat["row_cat_bars"]
