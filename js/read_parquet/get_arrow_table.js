import { arrayBufferToArrowTable } from "./arrayBufferToArrowTable.js";

export const get_arrow_table = async (url, fetch_options) => {
    try {
        const response = await fetch(url, fetch_options);
        const arrayBuffer = await response.arrayBuffer();
        const arrowTable = arrayBufferToArrowTable(arrayBuffer)
        return arrowTable
    } catch (error) {
        console.error("Error loading data:", error);
        return [];
    }
}