import celldega from './widget.js';
document.addEventListener("DOMContentLoaded", async () => {

    const landscape_el = document.getElementById('landscape-mouse-brain');

    if (window.location.pathname.endsWith('gallery_xenium_mouse_brain/')){

        // Use the imported functions
        const token = '';
        const ini_x = 21500;
        const ini_y = 14200;
        const ini_z = 0;
        const ini_zoom = -5;
        const base_url = 'https://raw.githubusercontent.com/broadinstitute/celldega_Xenium_Prime_Mouse_Brain_Coronal_FF_outs/main/Xenium_Prime_Mouse_Brain_Coronal_FF_outs';

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
            '100%',
            '100%',
            // ist_callback
        );

    }

});
