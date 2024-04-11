// local file from unpkg
import * as pq from "../vendor/parquet-wasm/parquet-wasm_unpkg.js";

let initialized = false;

async function initPq() {
    if (!initialized) {
        console.log('initialized pq');
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
