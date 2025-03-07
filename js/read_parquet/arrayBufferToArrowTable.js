import * as arrow from "apache-arrow";
import { getPq } from './pqInitializer.js';

export const arrayBufferToArrowTable = async (arrayBuffer) => {
    try {
        const pq = await getPq();
        const arr = new Uint8Array(arrayBuffer);
        const arrowIPC = pq.readParquet(arr);
        return arrow.tableFromIPC(arrowIPC);
    } catch (error) {
        console.error("Failed to convert ArrayBuffer to Arrow Table:", error);
        // Handle the error appropriately
        throw error; // Re-throw or handle differently
    }
};

// export const arrayBufferToArrowTable = async (arrayBuffer, readerOptions = {}) => {
//     try {
//         const pq = await getPq();
//         const arr = new Uint8Array(arrayBuffer);

//         // Pass the readerOptions when reading the Parquet file
//         const arrowIPC = pq.readParquet(arr, readerOptions);

//         return arrow.tableFromIPC(arrowIPC);
//     } catch (error) {
//         console.error("Failed to convert ArrayBuffer to Arrow Table:", error);
//         throw error;
//     }
// };


export const get_parquet_metadata = async (url, fetch_options) => {
    console.log('here!!!!!!!!!!!!!!!!!')
    const response = await fetch(url, fetch_options);


    const arrayBuffer = await response.arrayBuffer();

    const pq = await getPq();
    const arr = new Uint8Array(arrayBuffer);

    // console.log(arr)

    const arrowIPC = pq.readParquet(arr, {rowGroups:[0]});
    console.log('tablefromIPC')
    console.log(arrow.tableFromIPC(arrowIPC))

    // const parquetFile = pq.ParquetFile.fromBuffer(arr);

    // console.log("Parquet Metadata:", parquetFile);
    // console.log("Detected Number of Row Groups in parquet-wasm:", parquetFile.row_group_count());

    // return parquetFile.row_group_count();

};
