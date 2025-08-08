import celldega from './widget.js';
document.addEventListener("DOMContentLoaded", async () => {

    console.log('trying to run visium hd lung cancer script');

    const landscape_el = document.getElementById('landscape-visium-hd-lung-cancer');

    if (window.location.pathname.endsWith('gallery_visium_hd_lung_cancer/')){

        console.log('hi!')

        // Use the imported functions
        const token = '';
        const ini_zoom = -3.5;
        const ini_x = 3000;
        const ini_y = 3000;
        const ini_z = 0;
        const base_url = 'https://raw.githubusercontent.com/broadinstitute/Celldega_Visium_HD_Human_Kidney_FFPE/main/Visium_HD_Human_Kidney_FFPE';

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
