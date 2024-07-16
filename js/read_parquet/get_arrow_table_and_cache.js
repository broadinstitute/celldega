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
        const response = await fetch(url, options.fetch);
        const arrayBuffer = await response.arrayBuffer();
        data = arrayBufferToArrowTable(arrayBuffer);
        cache.set(url, data);
    }
    return data;
}
