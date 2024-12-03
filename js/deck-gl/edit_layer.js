import * as d3 from 'd3'
import { EditableGeoJsonLayer, DrawPolygonMode,  ModifyMode, ViewMode} from '@deck.gl-community/editable-layers'
import { get_layers_list } from './layers_ist'
import { View } from 'deck.gl';
import { update_cell_pickable_state } from './cell_layer'
import { update_trx_pickable_state } from './trx_layer';
import { update_path_pickable_state } from './path_layer';

// Function to calculate areas from a FeatureCollection
const calc_region_areas = (featureCollection) => {
    featureCollection.features.forEach((feature, index) => {
      if (feature.geometry.type === "Polygon") {
        // Extract the outer ring of the polygon
        const coordinates = feature.geometry.coordinates[0];

        // Calculate the area
        const area = Math.abs(d3.polygonArea(coordinates));

        // Update the properties
        feature.properties = {
          ...feature.properties,
          area, // Store the calculated area
          name: feature.properties.name || `Feature ${index + 1}` // Default name if not set
        };
      } else {
        console.warn(`Feature ${index} is not a Polygon.`);
      }
    });

    return featureCollection; // Return updated FeatureCollection
  }

const edit_layer_on_edit = (deck_ist, layers_obj, viz_state, edit_info) => {

    const { updatedData, editType, featureIndexes, editContext } = edit_info;

    viz_state.edit.feature_collection = updatedData;

    layers_obj.edit_layer = layers_obj.edit_layer.clone({
        data: viz_state.edit.feature_collection,
    })

    if (editType === 'addFeature') {

        update_edit_layer_mode(layers_obj, ViewMode)

        d3.select(viz_state.edit.buttons.sktch)
          .style('color', 'gray')
          .classed('active', false)

        viz_state.edit.mode = 'view'

        update_cell_pickable_state(layers_obj, true)
        update_path_pickable_state(layers_obj, true)
        update_trx_pickable_state(layers_obj, true)

        // Calculate areas
        // const areas = calculateFeatureCollectionAreas(viz_state.edit.feature_collection);
        viz_state.edit.feature_collection = calc_region_areas(viz_state.edit.feature_collection)

        // Output results
        // console.log("Calculated Areas:", areas);

        console.log(viz_state.edit.feature_collection)
    }

    const layers_list = get_layers_list(layers_obj, viz_state.close_up)
    deck_ist.setProps({layers: layers_list})



}

const edit_layer_on_click = (event, deck_ist, layers_obj, viz_state) => {


    if (event.featureType === 'polygons' && viz_state.edit.mode === 'view') {

        // switch to modify mode

        layers_obj.edit_layer = layers_obj.edit_layer.clone({
            mode: ModifyMode,
            selectedFeatureIndexes: [event.index],
        })

        const layers_list = get_layers_list(layers_obj, viz_state.close_up)
        deck_ist.setProps({layers: layers_list})

        viz_state.edit.mode = 'modify'

    } else if (event.featureType === 'polygons' && viz_state.edit.mode === 'modify') {

        // switch to view mode
        layers_obj.edit_layer = layers_obj.edit_layer.clone({
            mode: ViewMode,
            selectedFeatureIndexes: [],
        })

        const layers_list = get_layers_list(layers_obj, viz_state.close_up)
        deck_ist.setProps({layers: layers_list})

        viz_state.edit.mode = 'view'
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
        modeConfig: {
            preventOverlappingLines: true // Prevent overlapping lines in polygons
        },

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