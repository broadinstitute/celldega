import celldega from './celldega.js';

document.addEventListener("DOMContentLoaded", async () => {

    // Use a homepage-specific id so section headings such as `## Landscape`
    // on other docs pages cannot be mistaken for the demo container.
    const landscape_el = document.getElementById('home-landscape');

    if (landscape_el) {

        // Use the imported functions
        const token = '';
        const ini_x = 21500;
        const ini_y = 14200;
        const ini_z = 0;
        const ini_zoom = -6;
        const base_url = 'https://raw.githubusercontent.com/broadinstitute/celldega_Xenium_Prime_Human_Skin_FFPE_outs/main/Xenium_Prime_Human_Skin_FFPE_outs';

        // let el = document.querySelector("#landscape");

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

    }

});
