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