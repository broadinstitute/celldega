import { update_dendro_from_slider } from '../../ui/dendro_slider';
import { set_slider_value } from '../../ui/sliders';
import { apply_reorder } from '../../ui/text_buttons';

import { refresh_filtered_layers } from './crop';
import { restore_dendro_selection } from './dendro_layers';
import { get_mat_layers_list } from './matrix_layers';
import { on_view_state_change } from './on_view_state_change';

/** Wire the Viz API to the same crop, reorder and camera paths as user controls. */
export const initialize_state_controls = (deck, layers, state) => {
  state.state_controls = {
    dendrogram: (cuts) => {
      const filter = { ...state.crop.filter };
      // A manual crop pins its slice: recompute the cut on the full axis first.
      state.crop.apply_filter({
        ...filter,
        ...Object.fromEntries(Object.keys(cuts).map((axis) => [axis, null])),
      });
      for (const [axis, value] of Object.entries(cuts)) {
        const slider = state.dendro.sliders[axis];
        set_slider_value(slider, value);
        if (
          !update_dendro_from_slider(deck, layers, state, axis, {
            target: { value },
          })
        )
          throw new Error(`Could not apply ${axis} dendrogram cut`);
      }
      state.crop.apply_filter(filter);
    },
    selection: (selection) => {
      if ('dendrogram' in selection)
        restore_dendro_selection(deck, layers, state, selection.dendrogram);
      for (const [key, trait] of [
        ['rows', 'selected_rows'],
        ['cols', 'selected_cols'],
        ['genes', 'selected_genes'],
        ['highlighted_genes', 'highlighted_genes'],
      ]) {
        if (key in selection) state.model.set(trait, selection[key]);
      }
      state.model.save_changes?.();
    },
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
