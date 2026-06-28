import celldega from './celldega.js';

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

        // Try to load Clustergram from DegaFiles (cgm/default/)
        try {
            const matrix = await celldega.matrix_from_dega_files(
                matrix_el,
                base_url,
                'default',    // Clustergram name
                500,          // width
                550,          // height
                landscape.update_matrix_gene,      // Gene click callback
                landscape.update_matrix_col,       // Cluster click callback
                landscape.update_matrix_dendro_col // Dendrogram callback
            );

            console.log('Landscape-Clustergram linked visualization initialized');
        } catch (error) {
            console.error('Error loading Clustergram from DegaFiles:', error);
            matrix_el.innerHTML = `
                <div style="padding: 20px; color: gray; text-align: center;">
                    <p><strong>Clustergram data not available</strong></p>
                    <p style="font-size: 0.9em;">
                        To enable this visualization, generate Clustergram data using:
                    </p>
                    <pre style="background: #f5f5f5; padding: 10px; text-align: left; font-size: 0.85em;">
mat = dega.clust.Matrix(adata)
mat.clust()
mat.write_dega_files("path/to/dega_files")</pre>
                </div>
            `;
        }
    }
});
