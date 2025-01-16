import * as d3 from 'd3'
import { EditableGeoJsonLayer, ModifyMode, ViewMode} from '@deck.gl-community/editable-layers'
import { get_layers_list } from './layers_ist'
import { update_cell_pickable_state } from './cell_layer'
import { update_trx_pickable_state } from './trx_layer';
import { update_path_pickable_state } from './path_layer';
import { bar_callback_rgn, update_bar_graph } from '../ui/bar_plot';

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
          name: feature.properties.name || `Feature ${index + 1}`, // Default name if not set
          color: feature.properties.color || [Math.random() * 255, Math.random() * 255, Math.random() * 255] // Default color if not set
        };
      } else {
        console.warn(`Feature ${index} is not a Polygon.`);
      }
    });

    return featureCollection; // Return updated FeatureCollection
}

export const sync_region_to_model = (viz_state) => {
    if (Object.keys(viz_state.model).length > 0) {
        viz_state.model.set('region', {})
        viz_state.model.set('region', viz_state.edit.feature_collection)
        viz_state.model.save_changes()
    }
}

export const calc_and_update_rgn_bar_graph = (viz_state, deck_ist, layers_obj) => {

    // Calculate areas
    viz_state.edit.feature_collection = calc_region_areas(viz_state.edit.feature_collection)

    viz_state.edit.rgn_areas = viz_state.edit.feature_collection.features.map((feature, index) => ({
        name: (index + 1).toString(), // Assign numeric names starting from 1
        value: feature.properties.area // Use the "area" property for the bar height
    }))
    .sort((a, b) => b.value - a.value);

    viz_state.edit.color_dict_rgn = viz_state.edit.feature_collection.features.reduce((acc, feature, index) => {
        acc[(index + 1).toString()] = feature.properties.color; // Use the "color" property
        return acc;
    }, {});

    update_bar_graph(
        viz_state.edit.svg_bar_rgn,
        viz_state.edit.rgn_areas,
        viz_state.edit.color_dict_rgn,
        bar_callback_rgn,
        [], // selected_cats
        deck_ist,
        layers_obj,
        viz_state
    )
}

const edit_layer_on_edit = (deck_ist, layers_obj, viz_state, edit_info) => {

    // const { updatedData, editType, featureIndexes, editContext } = edit_info;
    const { updatedData, editType } = edit_info;

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

        calc_and_update_rgn_bar_graph(viz_state, deck_ist, layers_obj)

        sync_region_to_model(viz_state)

    }

    const layers_list = get_layers_list(layers_obj, viz_state)
    deck_ist.setProps({layers: layers_list})
    calc_and_update_rgn_bar_graph(viz_state, deck_ist, layers_obj)
    sync_region_to_model(viz_state)

}

const edit_layer_on_click = (event, deck_ist, layers_obj, viz_state) => {

    if (event.featureType === 'polygons' && viz_state.edit.mode === 'view') {

        // switch to modify mode
        layers_obj.edit_layer = layers_obj.edit_layer.clone({
            id: 'edit-layer-modify',
            mode: ModifyMode,
            selectedFeatureIndexes: [event.index],
            modeConfig: {
                dragToAddNew: true, // Enable dragging along edges to create new nodes
                enableSnapping: false // Disable snapping to nearby nodes
            },
        })

        const layers_list = get_layers_list(layers_obj, viz_state)
        deck_ist.setProps({layers: layers_list})

        viz_state.edit.mode = 'modify'

        viz_state.edit.modify_index = event.index

        // make the DEL button red and active
        d3.select(viz_state.edit.buttons.del)
          .classed('active', true)
          .style('display', 'inline-flex')

        // hide the RGN and SKTCH buttons
        d3.select(viz_state.edit.buttons.rgn)
          .style('display', 'none');

        d3.select(viz_state.edit.buttons.sktch)
            .style('display', 'none');


    } else if (event.featureType === 'polygons' && viz_state.edit.mode === 'modify') {

        // switch to view mode
        layers_obj.edit_layer = layers_obj.edit_layer.clone({
            id: 'edit-layer-view',
            mode: ViewMode,
            selectedFeatureIndexes: [],
        })

        const layers_list = get_layers_list(layers_obj, viz_state)
        deck_ist.setProps({layers: layers_list})

        viz_state.edit.mode = 'view'

        viz_state.edit.modify_index = null

        // hide the DEL button
        d3.select(viz_state.edit.buttons.del)
            .classed('active', false)
            .style('display', 'none')

        // hide the RGN and SKTCH buttons
        d3.select(viz_state.edit.buttons.rgn)
          .style('display', 'inline-flex');

        d3.select(viz_state.edit.buttons.sktch)
            .style('display', 'inline-flex');

    }

}

export const ini_edit_layer = (viz_state) => {

    const edit_layer = new EditableGeoJsonLayer({
        id: 'edit-layer',
        data: viz_state.edit.feature_collection,
        selectedFeatureIndexes: [],
        mode: ViewMode,
        filled: true,
        pointRadiusMinPixels: 2,
        pointRadiusScale: 2000,
        extruded: true,
        getElevation: 1000,
        getFillColor: (d) => d.properties.color,
        pickable: true,
        autoHighlight: true,
        modeConfig: {
            preventOverlappingLines: true
        },
        visible: false
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

export const update_edit_visitility = (layers_obj, visible) => {
    layers_obj.edit_layer = layers_obj.edit_layer.clone({
        visible: visible,
    })
}