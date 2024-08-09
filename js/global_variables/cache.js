

export const set_cache = (cache, url, data) => {
    const MAX_CACHE_SIZE = 20
    if (cache.size >= MAX_CACHE_SIZE) {
        const firstKey = cache.keys().next().value;
        cache.delete(firstKey);
    }
    cache.set(url, data);
}

export const get_cache = (cache, url) => {
    const item = cache.get(url);
    if (item) {
        cache.delete(url);
        cache.set(url, item);
    }
    return item;
}

export const clear_cache = (cache) => {
    cache.clear();
}

// Function to initialize a new cache
export const ini_cache = () => {
    const cache_new = new Map();  // Create a new Map instance

    // Override methods to use the custom functions
    return {
        set: (url, data) => set_cache(cache_new, url, data),
        get: (url) => get_cache(cache_new, url),
        clear: () => clear_cache(cache_new)
    };
};