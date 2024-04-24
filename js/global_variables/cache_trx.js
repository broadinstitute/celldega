const cache_trx = new Map();
const MAX_CACHE_SIZE = 20;

export const setTrxCache = (url, data) => {
    // Evict the least recently used (LRU) item if necessary
    if (cache_trx.size >= MAX_CACHE_SIZE) {
        const firstKey = cache_trx.keys().next().value;
        cache_trx.delete(firstKey);
    }
    cache_trx.set(url, data);
}

export const getTrxCache = (url) => {
    const item = cache_trx.get(url);
    if (item) {
        // Move the accessed item to the end to mark it as most recently used
        cache_trx.delete(url);
        cache_trx.set(url, item);
    }
    return item;
}

export const clearTrxCache = () => {
    cache_trx.clear();
}
