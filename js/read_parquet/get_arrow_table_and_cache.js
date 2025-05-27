import { arrayBufferToArrowTable } from "./arrayBufferToArrowTable";

export const get_arrow_table_and_cache_new = async (cache, url, options, aws = null) => {
    let data;

    if (cache.get(url)) {
        data = cache.get(url);
    } else {
        try {
            const response = aws !== null
                ? await aws.fetch(url)
                : await fetch(url, options.fetch);

            if (!response.ok) {
                throw new Error(`Network response was not ok: ${response.statusText}`);
            }

            const arrayBuffer = await response.arrayBuffer();
            data = arrayBufferToArrowTable(arrayBuffer);
            cache.set(url, data);
        } catch (error) {
            console.error(`Error fetching or parsing Arrow data from ${url}:`, error);
            data = null;
        }
    }

    return data;
};
