document.addEventListener("DOMContentLoaded", async () => {
    // Check if the URL contains 'notebook'
    if (window.location.pathname.includes('notebook')) {
        // Target the sidebar and hide it
        const sidebar = document.querySelector('.md-sidebar--secondary');
        if (sidebar) {
            sidebar.style.display = 'none';
        }

        // You can also add additional logic specific to notebook pages here
        console.log("Notebook page detected. Sidebar hidden.");
    }

    // // Example of existing logic for a specific page
    // const landscape_el = document.getElementById('landscape-skin-cancer');
    // if (window.location.pathname.endsWith('gallery_xenium_skin_cancer/')) {
    //     const token = '';
    //     const ini_x = 21500;
    //     const ini_y = 14200;
    //     const ini_z = 0;
    //     const ini_zoom = -6;
    //     const base_url = 'https://raw.githubusercontent.com/broadinstitute/celldega_Xenium_Prime_Human_Skin_FFPE_outs/main/Xenium_Prime_Human_Skin_FFPE_outs';

    //     const landscape = await celldega.landscape_ist(
    //         landscape_el,
    //         {},
    //         token,
    //         ini_x,
    //         ini_y,
    //         ini_z,
    //         ini_zoom,
    //         base_url,
    //         '',
    //         0.25,
    //         '100%',
    //         '100%',
    //     );
    // }
});
