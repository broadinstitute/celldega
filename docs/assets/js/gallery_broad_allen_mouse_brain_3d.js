import celldega from './celldega.js';

document.addEventListener("DOMContentLoaded", async () => {

    const cloud_el = document.getElementById('cell-cloud-broad-allen');

    if (window.location.pathname.endsWith('gallery_broad_allen_mouse_brain_3d/')) {

        // Point-cloud DegaFiles: the neighborhood-aligned positions of every cell
        const base_url = 'https://raw.githubusercontent.com/broadinstitute/celldega_xenium_E15.5_cell_cloud/main/xenium_E15.5_cell_cloud';

        await celldega.landscape_ist(
            cloud_el,
            {},
            '',     // token
            0,      // ini_x
            0,      // ini_y
            0,      // ini_z
            -3.05,  // ini_zoom: wider than the auto-fit (~ -2.6) so the tilted brain fits
            base_url,
            '',     // dataset_name
            0.25,   // trx_radius
            0,      // width (0 = 100%)
            700,    // height in pixels
            {}, [], {}, [], {}, {}, false,
            'spatial',
            'default',
            {},     // creds
            null,   // view_change_custom_callback
            -25,    // rotation_orbit: swing around the vertical axis
            20,     // rotation_x: tilt from side-on (0) toward top-down (90)
            0,      // rotate
            50,     // max_tiles_to_view
            null,   // scale_bar_microns_per_pixel
            [],     // base_urls
            false,  // cell_name_prefix
            {},     // centroids
            false,  // use_adata_3d_centroids
            10      // cell_size
        );

    }

});
