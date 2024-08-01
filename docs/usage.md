# Getting Started

Welcome to the Celldega documentation! Here you will find information on how to get started with using Celldega.

## Visualization Example

Below is an embedded Celldega visualization:

<iframe width="100%" height="575" frameborder="0"
  src="https://observablehq.com/embed/@cornhundred/celldega-xenium-bone-marrow-example?cells=root"></iframe>

<!-- <div id="app" style="width: 800px; height: 800px; overflow: hidden;"></div>

<script type="module">
    import('https://unpkg.com/celldega@0.2.2/src/celldega/static/widget.js?module').then(celldega => {
        // use the imported functions
        const token = '';
        const ini_x = 4500;
        const ini_y = 3200;
        const ini_z = 0;
        const ini_zoom = -2.5;

        const base_url = 'https://raw.githubusercontent.com/broadinstitute/celldega_data_human-bone-and-bone-marrow/main/Xenium_V1_hBoneMarrow_nondiseased_section_outs_landscape_files';

        // create and append the visualization.
        let el = document.querySelector("#app");

        // Add container styles to ensure it respects the parent size
        const containerStyles = `
            #app * {
                max-width: 100%;
                max-height: 100%;
                box-sizing: border-box;
                overflow: hidden;
            }
        `;
        const styleSheet = document.createElement("style");
        styleSheet.type = "text/css";
        styleSheet.innerText = containerStyles;
        document.head.appendChild(styleSheet);

        celldega.default.landscape_ist(
            el,
            {},
            token,
            ini_x,
            ini_y,
            ini_z,
            ini_zoom,
            base_url,
            'Xenium_Prime_Human_Lymph_Node_Reactive_FFPE_outs',
            0.25
        );
    }).catch(error => {
        console.error('Error loading module:', error);
    });
</script> -->
