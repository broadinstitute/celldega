// import { arrayBufferToArrowTable } from "./arrayBufferToArrowTable.js";

// export const get_arrow_table_and_cache = async (cache, url, options) => {

//     const MAX_CACHE_SIZE = 20; //' Example size

//     // Function to access (fetch or retrieve from cache) and cache the table
//     let data;

//     if (cache.has(url)) {
//         // console.log('Using cached data for:', url);
//         // Accessing the item, so move it to the end to mark it as most recently used
//         data = cache.get(url);
//         cache.delete(url); // Remove the item
//         cache.set(url, data); // Re-insert to update its position
//     } else {
//         // Item is not in the cache, fetch it
//         const response = await fetch(url, options.fetch);
//         const arrayBuffer = await response.arrayBuffer();
//         data = arrayBufferToArrowTable(arrayBuffer);

//         // Check if the cache is exceeding the size limit before adding the new item
//         if (cache.size >= MAX_CACHE_SIZE) {
//             // Evict the least recently used item, which is the first item in the Map
//             const leastRecentlyUsedKey = cache.keys().next().value;
//             cache.delete(leastRecentlyUsedKey);
//             // console.log(`Evicted ${leastRecentlyUsedKey}`);
//         }

//         // Add the new item to the cache
//         cache.set(url, data);
//     }

//     // console.log(`Cache size: ${cache.size}`);
//     return data;
// };

import { arrayBufferToArrowTable } from "./arrayBufferToArrowTable.js";
import { getTrxCache, setTrxCache } from '../global_variables/cache_trx.js';
import { getCellCache, setCellCache } from '../global_variables/cache_cell.js';

export async function get_arrow_table_and_cache(cacheType, url, options) {

    console.log('updated caching functions')
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
