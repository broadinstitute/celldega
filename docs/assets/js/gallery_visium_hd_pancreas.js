import celldega from './widget.js';
document.addEventListener("DOMContentLoaded", async () => {

    const landscape_el = document.getElementById('landscape-visium-hd-pancreas');

    if (window.location.pathname.endsWith('gallery_visium_hd_pancreas/')){

        console.log('hi!')

        // Use the imported functions
        const token = '';
        const ini_zoom = -3.5;
        const ini_x = 3000;
        const ini_y = 3000;
        const ini_z = 0;
        const base_url = 'https://raw.githubusercontent.com/broadinstitute/celldega_Visium_HD_Human_Pancreas_binned_outputs/main/Visium_HD_Human_Pancreas_binned_outputs';

        const landscape = await celldega.landscape_sst(
            // ini_model
            {},
            // element
            landscape_el,
            // base_url
            base_url,
            // token
            token,
            // initial coordinates
            ini_x,
            ini_y,
            ini_z,
            ini_zoom,
            // square_tile_size (hardwired to 1.4 for this dataset)
            1.4,
            // dataset_name
            '',
            // width
            '100%',
            // height
            '100%',
            // creds
            {},
        );

    }

});
