import { EditableGeoJsonLayer, DrawPolygonMode,  ModifyMode} from '@deck.gl-community/editable-layers'
import { get_layers_list } from './layers_ist'

const edit_layer_on_edit = (deck_ist, layers_obj, viz_state, edit_info) => {

    const { updatedData, editType, featureIndexes, editContext } = edit_info;

    viz_state.edit.feature_collection = updatedData;

    layers_obj.edit_layer = layers_obj.edit_layer.clone({
        data: viz_state.edit.feature_collection,
    })

    // console.log(viz_state.edit.feature_collection)

    const layers_list = get_layers_list(layers_obj, viz_state.close_up)

    deck_ist.setProps({layers: layers_list})

  }

export const ini_edit_layer = (viz_state) => {

    const edit_layer = new EditableGeoJsonLayer({
        id: 'edit-layer',
        data: viz_state.edit.feature_collection,
        selectedFeatureIndexes: [],
        // selectedFeatureIndexes: [0],
        mode: DrawPolygonMode,
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