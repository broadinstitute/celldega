import { get_arrow_table_and_cache_new } from "./get_arrow_table_and_cache";

export const fetch_all_tables_new = async (cache, urls, options, aws) => {
    return Promise.all(urls.map(url => get_arrow_table_and_cache_new(cache, url, options, aws)));
}