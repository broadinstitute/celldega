import { arrayBufferToArrowTable } from "./arrayBufferToArrowTable.js";
import { getTrxCache, setTrxCache } from '../global_variables/cache_trx.js';
import { getCellCache, setCellCache } from '../global_variables/cache_cell.js';

export async function get_arrow_table_and_cache(cacheType, url, options) {

    let data;
    // let cache = cacheType === 'trx' ? { get: getTrxCache, set: setTrxCache } : { get: getCellCache, set: setCellCache };

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
