// local file from unpkg
// import * as pq from "../vendor/parquet-wasm/parquet-wasm_unpkg.js";

// import * as pq from "../vendor/parquet-wasm/parquet-wasm_0.6.0_jsdeliver.js";

import * as pq from "../vendor/parquet-wasm/parquet_wasm_0.6.1.js"

console.log(pq)


let initialized = false;

async function initPq() {
    if (!initialized) {
        await pq.default();
        initialized = true;
    }
    return pq;
}

export async function getPq() {
    if (!initialized) {
        await initPq();
    }
    return pq;
}





////////////////////////////////////////////
////////////////////////////////////////////
////////////////////////////////////////////
////////////////////////////////////////////
////////////////////////////////////////////
////////////////////////////////////////////
////////////////////////////////////////////


// import initParquet, * as pq from "parquet-wasm";

// console.log(initParquet)

// let initialized = false;

// async function initPq() {
//     if (!initialized) {

//         // console.log('initParquet!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')

//         // const wasmPath = new URL('parquet_wasm_bg.wasm', new URL(import.meta.url).origin).href;
//         // console.log('wasmPath', wasmPath)

//         // // await initParquet();  // No need for manual WASM linking anymore

//         // console.log('trying to set the URL on the outside???')
//         // await initParquet({
//         //     wasmPath: new URL('./parquet_wasm_bg.wasm', import.meta.url).href
//         // });

//         initialized = true;

//         console.log('finished initializing!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
//     }
//     return pq;
// }

// export async function getPq() {

//     console.log('>>>>>>>>>>>>>>> getPq')
//     if (!initialized) {
//         await initPq();
//     }

//     console.log('post await initPq')
//     return pq;
// }
