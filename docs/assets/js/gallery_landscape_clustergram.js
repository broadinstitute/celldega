import celldega from './widget.js';

document.addEventListener("DOMContentLoaded", async () => {

    const landscape_el = document.getElementById('landscape-linked');
    const matrix_el = document.getElementById('matrix-linked');

    if (window.location.pathname.endsWith('gallery_landscape_clustergram/')) {

        if (!landscape_el || !matrix_el) {
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
            600   // height in pixels
        );

        // Fetch the network data for the Clustergram
        const net_url = `${base_url}/tmp.json`;
        
        try {
            const response = await fetch(net_url);
            const network = await response.json();

            // Initialize Matrix visualization with callbacks to Landscape
            celldega.matrix_viz(
                {},
                matrix_el,
                network,
                500,
                550,
                landscape.update_matrix_gene,      // Gene click callback
                landscape.update_matrix_col,       // Cluster click callback
                landscape.update_matrix_dendro_col // Dendrogram callback
            );

            console.log('Landscape-Clustergram linked visualization initialized');
        } catch (error) {
            console.error('Error fetching network data:', error);
            matrix_el.innerHTML = '<div style="padding: 20px; color: gray;">Clustergram data not available for this dataset</div>';
        }
    }
});
