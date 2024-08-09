import { arrayBufferToArrowTable } from "./arrayBufferToArrowTable.js";
import { getTrxCache, setTrxCache } from '../global_variables/cache_trx.js';
import { getCellCache, setCellCache } from '../global_variables/cache_cell.js';

export const get_arrow_table_and_cache = async (cacheType, url, options) => {
    let data;

    let cache;
    if (cacheType === 'trx') {
        cache = { get: getTrxCache, set: setTrxCache };
    } else if (cacheType === 'cell') {
        cache = { get: getCellCache, set: setCellCache };
    } else {
        throw new Error("Invalid cache type specified");
    }

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


export const get_arrow_table_and_cache_new = async (cache, url, options) => {
    let data;

    console.log('get_arrow_table_and_cache_new', cache)

    if (cache.get(url)) {
        console.log('get')
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
            console.log('set')
        } catch {
            // Handle missing or corrupt file error
            data = null; // You can return null or some default value or handle the error differently
        }
    }
    return data;
}
