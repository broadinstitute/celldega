import { OrthographicView } from 'deck.gl';

export const set_views = () => {
    return [ new OrthographicView({id: 'ortho'})]
}

export const ini_viz_state = () => {
    return {
        'close_up': false,
    }
}