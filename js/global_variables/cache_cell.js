
const cache_cell = new Map();
const MAX_CACHE_SIZE = 20;

export const setCellCache = (url, data) => {
    if (cache_cell.size >= MAX_CACHE_SIZE) {
        const firstKey = cache_cell.keys().next().value;
        cache_cell.delete(firstKey);
    }
    cache_cell.set(url, data);
}

export const getCellCache = (url) => {
    const item = cache_cell.get(url);
    if (item) {
        cache_cell.delete(url);
        cache_cell.set(url, item);
    }
    return item;
}

export const clearCellCache = () => {
    cache_cell.clear();
}






export const set_cache_cell = (cache_cell, url, data) => {
    const MAX_CACHE_SIZE = 20
    if (cache_cell.size >= MAX_CACHE_SIZE) {
        const firstKey = cache_cell.keys().next().value;
        cache_cell.delete(firstKey);
    }
    cache_cell.set(url, data);
}

export const get_cache_cell = (cache_cell, url) => {
    const item = cache_cell.get(url);
    if (item) {
        cache_cell.delete(url);
        cache_cell.set(url, item);
    }
    return item;
}

export const clear_cache_cell = (cache_cell) => {
    cache_cell.clear();
}

// Function to initialize a new cache
export const ini_cache_cell_new = () => {
    const cache_cell_new = new Map();  // Create a new Map instance

    // Override methods to use the custom functions
    return {
        set: (url, data) => set_cache_cell(cache_cell_new, url, data),
        get: (url) => get_cache_cell(cache_cell_new, url),
        clear: () => clear_cache_cell(cache_cell_new)
    };
};