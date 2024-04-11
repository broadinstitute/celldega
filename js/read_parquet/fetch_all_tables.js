import { get_arrow_table_and_cache } from "./get_arrow_table_and_cache.js";

export const fetch_all_tables = async (cache_trx, urls, options) => {
    return Promise.all(urls.map(url => get_arrow_table_and_cache(cache_trx, url, options)));
};