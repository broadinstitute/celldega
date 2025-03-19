import { OrthographicView, OrbitView } from 'deck.gl';

export const set_views = (viz_state) => {

    if (viz_state.landscape_type === '2D'){
        console.log(' ************************************* 2D')
        return [ new OrthographicView({id: 'ortho'})]
    } else if (viz_state.landscape_type === 'point-cloud'){
        console.log(' ************************************* point-cloud')
        return [ new OrbitView({id: 'ortho'})]
    }
}