import celldega from './celldega.js';
document.addEventListener("DOMContentLoaded", async () => {

    const landscape_el = document.getElementById('landscape-cosmx-colon');

    if (window.location.pathname.endsWith('gallery_cosmx_human_colon/')){

        // Use the imported functions
        const token = '';
        // All zeros => landscape_ist auto-centers and auto-fits the whole sample
        // (same behavior as dega.viz.Landscape in the notebook). The ini_x/ini_y
        // target is in deck.gl's transformed data frame, not raw global pixels.
        const ini_x = 0;
        const ini_y = 0;
        const ini_z = 0;
        const ini_zoom = 0;
        const base_url = 'https://raw.githubusercontent.com/cornhundred/celldega_cosmx_human_colon_wt/main';

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
