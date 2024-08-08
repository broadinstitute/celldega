import { OrthographicView } from 'deck.gl';

export let views = []

export const update_views = () => {
    views = [ new OrthographicView({id: 'ortho'})]
}

export const ini_viz_state = () => {
    return {
        'close_up': false,
    }
}