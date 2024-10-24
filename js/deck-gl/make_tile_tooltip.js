export const make_tile_tooltip = (info, cats) => {

    let inst_name

    if (info.index === -1 || !info.layer) return null;

    inst_name = cats.tile_cats_array[info.index]

    return {
        html: `<div>${inst_name}</div?`,
    };

}