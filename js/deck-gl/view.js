import { OrthographicView } from 'deck.gl';

export let view 

export const update_view = () => {
    view = new OrthographicView({id: 'ortho'})
}