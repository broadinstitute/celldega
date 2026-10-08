import celldega from './celldega.js';

document.addEventListener("DOMContentLoaded", async () => {

    const landscape_el = document.getElementById('landscape-atera');

    if (window.location.pathname.endsWith('gallery_atera/')) {

        // Use the imported functions
        const token = '';
        const ini_x = 25185;
        const ini_y = 14447;
        const ini_z = 0;
        const ini_zoom = -7;
        const base_url = 'https://raw.githubusercontent.com/cornhundred/DegaFiles_WTA_Preview_FFPE_Breast_Cancer_outs/main';

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
            800   // height in pixels
        );

    }

});
