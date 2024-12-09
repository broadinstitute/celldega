import celldega from './widget.js';

document.addEventListener("DOMContentLoaded", async () => {

    // Check if we are on the home page
    const isHomePage = window.location.pathname === '/' || window.location.pathname.endsWith('/index.html');

    if (!isHomePage) {
        console.log('Not on the Home page, skipping visualization initialization.');
        return;
    } else {
        console.log('On the Home page, initializing visualization...');
    }

    // Use the imported functions
    const token = '';
    const ini_x = 21500;
    const ini_y = 14200;
    const ini_z = 0;
    const ini_zoom = -6;
    const base_url = 'https://raw.githubusercontent.com/broadinstitute/celldega_Xenium_Prime_Human_Skin_FFPE_outs/main/Xenium_Prime_Human_Skin_FFPE_outs';

    let el = document.querySelector("#landscape");

    const landscape = await celldega.landscape_ist(
        el,
        {},
        token,
        ini_x,
        ini_y,
        ini_z,
        ini_zoom,
        base_url,
        '',
        0.25,
        '100%',
        '100%',
        // ist_callback
    );

});


