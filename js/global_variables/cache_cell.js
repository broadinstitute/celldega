const cache_cell = new Map();
const MAX_CACHE_SIZE = 20;

export function setCellCache(url, data) {
    if (cache_cell.size >= MAX_CACHE_SIZE) {
        const firstKey = cache_cell.keys().next().value;
        cache_cell.delete(firstKey);
    }
    cache_cell.set(url, data);
}

export function getCellCache(url) {
    const item = cache_cell.get(url);
    if (item) {
        cache_cell.delete(url);
        cache_cell.set(url, item);
    }
    return item;
}

export function clearCellCache() {
    cache_cell.clear();
}
