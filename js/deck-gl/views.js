import { OrthographicView } from 'deck.gl';

export let views = []

export const update_views = () => {
    views = [ new OrthographicView({id: 'ortho'})] 
}