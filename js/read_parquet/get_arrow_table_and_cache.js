import { arrayBufferToArrowTable } from "./arrayBufferToArrowTable.js";

export const get_arrow_table_and_cache_new = async (cache, url, options) => {
    let data;

    if (cache.get(url)) {
        data = cache.get(url);
    } else {
        try {
            const response = await fetch(url, options.fetch);
            if (!response.ok) {
                throw new Error(`Network response was not ok: ${response.statusText}`);
            }
            const arrayBuffer = await response.arrayBuffer();
            data = arrayBufferToArrowTable(arrayBuffer);
            cache.set(url, data);
        } catch {
            // Handle missing or corrupt file error
            data = null; // You can return null or some default value or handle the error differently
        }
    }
    return data;
}
