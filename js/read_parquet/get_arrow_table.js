import { arrayBufferToArrowTable } from "./arrayBufferToArrowTable.js";

export const get_arrow_table = async (url, fetch_options) => {
    try {
        // console.log('url', url)
        // console.log('fetch')
        const response = await fetch(url, fetch_options);
        // console.log('post fetch')

        // console.log('arrayBuffer')
        const arrayBuffer = await response.arrayBuffer();
        // console.log('post arrayBuffer')

        // console.log('arrayBufferToArrowTable')
        const arrowTable = arrayBufferToArrowTable(arrayBuffer)
        // console.log('post arrayBufferToArrowTable')

        // console.log('arrowTable', arrowTable)

        return arrowTable
    } catch (error) {
        console.error("Error loading data:", error);
        return [];
    }
}

export const get_arrow_table_from_row_group = async (url, fetch_options, rowGroupIndex) => {
    try {
        const response = await fetch(url, fetch_options);
        const arrayBuffer = await response.arrayBuffer();

        // Specify row group selection via ReaderOptions
        const readerOptions = { rowGroups: [rowGroupIndex] };

        return await arrayBufferToArrowTable(arrayBuffer, readerOptions);
    } catch (error) {
        console.error("Failed to read specific row group:", error);
        return null;
    }
};
