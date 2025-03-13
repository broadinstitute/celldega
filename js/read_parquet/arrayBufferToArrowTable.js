import * as arrow from "apache-arrow";
import { getPq } from './pqInitializer.js';

export const arrayBufferToArrowTable = async (arrayBuffer) => {
    try {


        console.log('^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^')
        console.log('awaiting getPq')

        const pq = await getPq();
        console.log('pq', pq)
        console.log('^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^')

        console.log('make new arr')
        const arr = new Uint8Array(arrayBuffer);
        console.log('post make new arr')

        console.log('readParquet')
        const arrowIPC = pq.readParquet(arr);
        console.log('post readParquet')

        console.log('tableFromIPC')
        const tmp = arrow.tableFromIPC(arrowIPC);
        console.log('post tableFromIPC')

        return tmp

    } catch (error) {
        // console.error("Failed to convert ArrayBuffer to Arrow Table:", error);
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

    console.log('***********')
    console.log('pq')
    console.log('***********')
    console.log(pq)



    const arr = new Uint8Array(arrayBuffer);

    // console.log(arr)

    var ReaderOptions = {
        rowGroups: [0, 1]
    }

    const arrowIPC = pq.readParquet(arr, ReaderOptions);

    const arrowTable = arrow.tableFromIPC(arrowIPC)

    console.log('after using ReaderOptions')
    console.log(arrowTable)

    // const parquetFile = pq.ParquetFile.fromBuffer(arr);

    // console.log("Parquet Metadata:", parquetFile);
    // console.log("Detected Number of Row Groups in parquet-wasm:", parquetFile.row_group_count());

    // return parquetFile.row_group_count();

};
