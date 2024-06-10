import { tile_cats_array } from "../global_variables/tile_cats_array";

export const make_tile_tooltip = (info) => {

    let inst_name

    if (info.index === -1 || !info.layer) return null;

    inst_name = tile_cats_array[info.index]

    return {
        html: `<div>${inst_name}</div?`,
    };

}