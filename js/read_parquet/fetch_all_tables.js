import { get_arrow_table_and_cache } from "./get_arrow_table_and_cache.js";

export const fetch_all_tables = async (cache_type, urls, options) => {
    return Promise.all(urls.map(url => get_arrow_table_and_cache(cache_type, url, options)));
};