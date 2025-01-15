document.addEventListener("DOMContentLoaded", async () => {
    // Increase width of notebook and galley pages
    if (window.location.pathname.includes('notebook') || window.location.pathname.includes('gallery_')) {

        // hide primary sidebar
        const sidebar_primary = document.querySelector('.md-sidebar--primary');

        if (sidebar_primary) {
            sidebar_primary.style.width = '8.1rem';
        }

        // hide secondary sidebar
        const sidebar_secondary = document.querySelector('.md-sidebar--secondary');

        if (sidebar_secondary) {
            sidebar_secondary.style.display = 'none';
        }

        // remove max width constraint
        const md_grid = document.querySelector('.md-main__inner');

        if (md_grid) {
            md_grid.style.marginLeft = 'unset';
            md_grid.style.marginRight = 'unset';
            md_grid.style.maxWidth = 'none';
        }


        // You can also add additional logic specific to notebook pages here
        console.log("Notebook page detected. Sidebar hidden.");
    }

});
