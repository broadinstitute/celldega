import { arrayBufferToArrowTable } from "./arrayBufferToArrowTable";

export const get_arrow_table = async (url, fetch_options, aws) => {
    try {
        const response = aws !== null
            ? await aws.fetch(url)
            : await fetch(url, fetch_options);

        const arrayBuffer = await response.arrayBuffer();
        const arrowTable = arrayBufferToArrowTable(arrayBuffer);
        return arrowTable;
    } catch (error) {
        console.error("Error loading data:", error);
        return [];
    }
};
