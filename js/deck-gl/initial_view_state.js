export let initial_view_state = {}

export const set_initial_view_state = (ini_x, ini_y, ini_z, ini_zoom) => {
    initial_view_state = {
        target: [ini_x, ini_y, ini_z], 
        zoom: ini_zoom
    }
}