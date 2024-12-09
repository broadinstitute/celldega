import celldega from './widget.js';

document.addEventListener("DOMContentLoaded", async () => {

    console.log("hello hello");

    console.log('checking celldega using import in index.js')
    console.log('celldega', celldega)

    console.log('here!')


    // Use the imported functions
    const token = '';
    const ini_x = 21500;
    const ini_y = 14200;
    const ini_z = 0;
    const ini_zoom = -6;
    const base_url = 'http://127.0.0.1:8080/notebooks/data/xenium_landscapes/Xenium_Prime_Human_Skin_FFPE_outs';

    // // make a DOM element with the id 'landscape'
    // document.body.innerHTML = '<div id="landscape"></div>';

    let el = document.querySelector("#landscape");

    // const ist_callback = () => {
    //     console.log('custom callback for ist');
    // }

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



{/* <script type="module">
  console.log('**************************')
  console.log('**************************')
  import celldega from './assets/js/widget.js';
  console.log(celldega)
</script> */}