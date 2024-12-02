import * as d3 from 'd3'
import { EditableGeoJsonLayer, DrawPolygonMode,  ModifyMode, ViewMode} from '@deck.gl-community/editable-layers'
import { get_layers_list } from './layers_ist'
import { View } from 'deck.gl';



const edit_layer_on_edit = (deck_ist, layers_obj, viz_state, edit_info) => {

    const { updatedData, editType, featureIndexes, editContext } = edit_info;

    viz_state.edit.feature_collection = updatedData;

    layers_obj.edit_layer = layers_obj.edit_layer.clone({
        data: viz_state.edit.feature_collection,
    })

    console.log(viz_state.edit.feature_collection)
    // console.log(editType)

    if (editType === 'addFeature') {

        console.log('done drawing')

        // if (viz_state.edit.feature_collection.features.length > 3) {
        //     console.log('switching to view mode')
        // }

        update_edit_layer_mode(layers_obj, ViewMode)

        // viz_state.edit.buttons.rgn.style.color = 'gray'

        d3.select(viz_state.edit.buttons.sktch)
          .style('color', 'gray')
          .classed('active', false)
    }

    const layers_list = get_layers_list(layers_obj, viz_state.close_up)

    deck_ist.setProps({layers: layers_list})

}

const edit_layer_on_click = (event, deck_ist, layers_obj, viz_state) => {

        if (event.featureType === 'polygons') {
            console.log('polygon clicked', event.index)
        }

        // const { picks, screenCoords } = event;

        // if (picks.length > 0) {
        //     const pick = picks[0];
        //     const feature = pick.object;

        //     if (feature) {
        //         console.log('Feature clicked:', feature)
        //     }
        // }
}

export const ini_edit_layer = (viz_state) => {

    const edit_layer = new EditableGeoJsonLayer({
        id: 'edit-layer',
        data: viz_state.edit.feature_collection,
        selectedFeatureIndexes: [],
        // selectedFeatureIndexes: [0],

        mode: ViewMode,
        // mode: DrawPolygonMode,

        // mode: new ModifyMode(),

        // Styles
        filled: true,
        pointRadiusMinPixels: 2,
        pointRadiusScale: 2000,
        extruded: true,
        getElevation: 1000,
        getFillColor: [200, 0, 80, 180],

        // Interactive props
        pickable: true,
        autoHighlight: true,

        // onEdit: (edit_info) => on_edit(deck_ist, layers_obj, viz_state, edit_info)
    })

    return edit_layer
}

export const set_edit_layer_on_edit = (deck_ist, layers_obj, viz_state) => {
    layers_obj.edit_layer = layers_obj.edit_layer.clone({
        onEdit: (edit_info) => edit_layer_on_edit(deck_ist, layers_obj, viz_state, edit_info)
    })
}

export const set_edit_layer_on_click = (deck_ist, layers_obj, viz_state) => {
    layers_obj.edit_layer = layers_obj.edit_layer.clone({
        onClick: (event) => edit_layer_on_click(event, deck_ist, layers_obj, viz_state)
    })
}

export const update_edit_layer_mode = (layers_obj, mode) => {
    layers_obj.edit_layer = layers_obj.edit_layer.clone({
        mode: mode,
    })
}