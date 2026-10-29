import celldega from './celldega.js';

document.addEventListener("DOMContentLoaded", async () => {

    const landscape_el = document.getElementById('landscape-broad-allen');

    if (window.location.pathname.endsWith('gallery_broad_allen_mouse_brain_2d/')) {

        // Xenium DegaFiles of slice 35
        const base_url = 'https://raw.githubusercontent.com/broadinstitute/celldega_xenium_E15.5_cell_cloud/main/output-XETG00323__0092186__35__20260814__172429';

        await celldega.landscape_ist(
            landscape_el,
            {},
            '',     // token
            11951,  // ini_x: center of the tissue, image pixels
            7679,   // ini_y
            0,      // ini_z
            -4.9,   // ini_zoom: whole section in view
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
            0,      // rotation_orbit
            0,      // rotation_x
            180     // rotate: dorsal side up
        );

    }

});
