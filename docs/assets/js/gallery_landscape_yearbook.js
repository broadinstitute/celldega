import celldega from './widget.js';

document.addEventListener("DOMContentLoaded", async () => {

    const landscape_el = document.getElementById('landscape-yb');
    const yearbook_el = document.getElementById('yearbook-yb');

    if (window.location.pathname.endsWith('gallery_landscape_yearbook/')) {

        if (!landscape_el || !yearbook_el) {
            console.error('Required elements not found');
            return;
        }

        const token = '';
        const ini_x = 20000;
        const ini_y = 20000;
        const ini_z = 0;
        const ini_zoom = -6;
        const base_url = 'https://raw.githubusercontent.com/broadinstitute/celldega_Xenium_Prime_Human_Skin_FFPE_outs/main/Xenium_Prime_Human_Skin_FFPE_outs';

        // Initialize Landscape
        const landscape = await celldega.landscape_ist(
            landscape_el,
            {},
            token,
            ini_x,
            ini_y,
            ini_z,
            ini_zoom,
            base_url,
            '',
            0.25,
            0,    // width (0 = 100%)
            500   // height in pixels
        );

        // Initialize Yearbook with an initial query
        const yearbook = await celldega.yearbook(
            yearbook_el,
            {},
            token,
            base_url,
            'Skin Cancer',   // dataset_name
            [],              // cells (empty = use query)
            2,               // num_rows
            4,               // num_cols
            100,             // portrait_size_um
            4,               // portrait_gap
            0,               // width (0 = 100%)
            500,             // height in pixels
            {},              // meta_cell
            [],              // meta_cell_attr
            {},              // meta_cluster
            [],              // meta_cluster_attr
            'default',       // segmentation
            {},              // creds
            null,            // scale_bar_microns_per_pixel
            0,               // current_page
            {                // query: cells from cluster 1, ranked by S100A1 expression
                cluster: { attr: 'leiden', value: '1' },
                gene: 'S100A1',
                max_cells: 50
            }
        );

        // ==========================================
        // Link Landscape selections to Yearbook
        // ==========================================

        // When a gene is selected in Landscape (via Clustergram callback),
        // update Yearbook to rank cells by that gene's expression
        landscape.on_gene_select((gene_name) => {
            console.log('Gene selected:', gene_name);
            yearbook.update_gene(gene_name);
        });

        // When a cluster is selected in Landscape (via Clustergram callback),
        // update Yearbook to show cells from that cluster
        landscape.on_cluster_select((cluster_id) => {
            console.log('Cluster selected:', cluster_id);
            yearbook.update_cluster(cluster_id);
        });

        // When multiple clusters are selected via dendrogram,
        // update Yearbook to show cells from the first selected cluster
        landscape.on_clusters_select((cluster_ids) => {
            console.log('Clusters selected:', cluster_ids);
            if (cluster_ids.length > 0) {
                yearbook.update_cluster(cluster_ids[0]);
            }
        });

        console.log('Landscape-Yearbook linked visualization initialized');
        console.log('Try selecting genes or clusters to see Yearbook update!');
    }
});
