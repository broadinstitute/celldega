export const curate_pan_y = (target_y, zoom_curated_y, viz_state) => {

    const ini_pan_y = viz_state.zoom.ini_pan_y

    var pan_curated_y

    var zoom_factor_y = Math.pow(2, zoom_curated_y)

    viz_state.zoom.min_pan_y = (ini_pan_y - viz_state.viz.row_offset)/zoom_factor_y + viz_state.viz.row_offset

    // calculating the shift to the min, to re-use for the max
    var min_diff = ini_pan_y - viz_state.zoom.min_pan_y

    viz_state.zoom.max_pan_y = ini_pan_y + min_diff

    if (target_y <= viz_state.zoom.min_pan_y){
      pan_curated_y = viz_state.zoom.min_pan_y
    } else if (target_y > viz_state.zoom.max_pan_y) {
      pan_curated_y = viz_state.zoom.max_pan_y
    } else {
      pan_curated_y = target_y
    }

    return pan_curated_y
  }

export const curate_pan_x = (target_x, zoom_curated_x, viz_state) => {

    const ini_pan_x = viz_state.zoom.ini_pan_x

    var pan_curated_x

    var zoom_factor_x = Math.pow(2, zoom_curated_x)

    viz_state.zoom.min_pan_x = ini_pan_x/zoom_factor_x

    // calculating the shift to the min, to re-use for the max
    var min_diff = ini_pan_x - viz_state.zoom.min_pan_x

    viz_state.zoom.max_pan_x = ini_pan_x + min_diff

    if (target_x <= viz_state.zoom.min_pan_x){
        pan_curated_x = viz_state.zoom.min_pan_x
    } else if (target_x > viz_state.zoom.max_pan_x) {
        pan_curated_x = viz_state.zoom.max_pan_x
    } else {
        pan_curated_x = target_x
    }

    return pan_curated_x

}