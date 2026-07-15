import celldega from './celldega.js';

document.addEventListener("DOMContentLoaded", async () => {

    const landscape_el = document.getElementById('landscape-mouse-cranium-e14');

    if (window.location.pathname.endsWith('gallery_mouse_cranium_e14/')) {

        // Local-only example: DegaFiles aren't hosted publicly yet.
        // Serve them yourself, e.g.:
        //   npx http-server notebooks/data/michal_landscape_files/E14_62_together_raw_v2_point-cloud -p 8080 --cors
        const token = '';
        const ini_x = 9980;
        const ini_y = -40;
        const ini_z = 0;
        const ini_zoom = -5;
        const base_url = 'http://localhost:8080';

        const landscape = await celldega.landscape_ist(
            landscape_el,
            {},              // ini_model
            token,
            ini_x,
            ini_y,
            ini_z,
            ini_zoom,
            base_url,
            '',              // dataset_name
            0.25,            // trx_radius
            0,               // width (0 = 100%)
            700,             // height in pixels
            {},              // meta_cell
            [],              // meta_cell_attr
            {},              // meta_cluster
            [],              // meta_cluster_attr
            {},              // umap
            {},              // nbhd
            false,           // nbhd_edit
            'spatial',       // landscape_state
            'default',       // segmentation
            {},              // creds
            null,            // view_change_custom_callback
            0,               // rotation_orbit
            90               // rotation_x -- tip the z-stack onto its side
        );

    }

});
