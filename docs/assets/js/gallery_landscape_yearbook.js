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

        // Initialize Yearbook with a query for cluster 1 cells ranked by gene expression
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

        console.log('Landscape-Yearbook linked visualization initialized');
    }
});
