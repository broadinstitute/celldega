import { apply_reorder } from '../../ui/text_buttons';

import { refresh_filtered_layers } from './crop';
import { get_mat_layers_list } from './matrix_layers';
import { on_view_state_change } from './on_view_state_change';

/** Wire the Viz API to the same crop, reorder and camera paths as user controls. */
export const initialize_state_controls = (deck, layers, state) => {
  state.state_controls = {
    order: (orders) => {
      for (const [axis, spec] of Object.entries(orders)) {
        if (Array.isArray(spec)) {
          const ranks = new Array(spec.length);
          spec.forEach((index, position) => {
            ranks[index] = spec.length - position;
          });
          state.mat.orders[axis].custom = ranks;
          state.labels.reorder_driver = null;
        }
        apply_reorder(
          axis,
          Array.isArray(spec) ? 'custom' : spec,
          deck,
          layers,
          state
        );
      }
      // Rebuilding also refreshes positions for consecutive custom orders.
      refresh_filtered_layers(deck, layers, state);
      deck.setProps({ layers: get_mat_layers_list(layers) });
    },
    crop: (filter) =>
      state.crop.apply_filter({ ...state.crop.filter, ...filter }),
    view: (view) => {
      const current = state.zoom.zoom_data.matrix;
      const zoom = view.zoom || [current.zoom_x, current.zoom_y];
      const target = view.target || [current.pan_x, current.pan_y];
      clearTimeout(state.zoom._programmatic_transition_timer);
      state.zoom._programmatic_view_transition = false;
      // The gesture handler accumulates deltas, so seed its total to the current camera.
      state.zoom.zoom_data.total_zoom = {
        x: current.zoom_x,
        y: current.zoom_y,
      };
      on_view_state_change(
        { viewId: 'matrix', viewState: { zoom, target } },
        deck,
        layers,
        state
      );
    },
  };
};
