import celldega from './widget.js';
document.addEventListener("DOMContentLoaded", async () => {

    console.log("gallery mouse brain");

    console.log(celldega)
    console.log(window.location.pathname)

    if (window.location.pathname.endsWith('gallery_xenium_mouse_brain/')){

        // Use the imported functions
        const token = '';
        const ini_x = 21500;
        const ini_y = 14200;
        const ini_z = 0;
        const ini_zoom = -6;
        const base_url = 'https://raw.githubusercontent.com/broadinstitute/celldega_Xenium_Prime_Mouse_Brain_Coronal_FF_outs/main/Xenium_Prime_Mouse_Brain_Coronal_FF_outs';

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

    } else {
        console.log('Not on the mouse brain gallery, skipping visualization initialization.');
    }

});
