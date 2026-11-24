/**
 * The ▾ beside CELL and what it drives, shared by the Landscape and the Yearbook:
 * show cells by their clusters, another per-cell attribute or a label set (see
 * global_variables/cell_attributes.js), kept in step with the model's
 * `cell_attribute` and `label_sets`.
 *
 * Each widget passes how it redraws: `refresh_colors` repaints cells and
 * boundaries, `recount_bars` recounts the cell bars from the (new) categories,
 * and `redraw_bars` regroups the bars as last drawn (a label set).
 */
import {
  force_set_selected_cats,
  set_dict_cell_cats,
} from '../global_variables/cat';
import {
  cell_attribute_options,
  normalize_cell_attribute,
  set_cell_attribute,
} from '../global_variables/cell_attributes';
import { buildCellCompactData } from '../utils/compact_data';

import { make_cell_attribute_menu } from './cell_attribute_menu';

/**
 * @param {object} viz_state
 * @param {object} widget
 * @param {HTMLElement} widget.cell_button - The CELL button.
 * @param {HTMLElement} [widget.slider] - The CELL slider (narrowed beside ▾).
 * @param {boolean} [widget.compact] - Rebuild the per-cell compact data (the
 *   bar counts' source) when a per-cell attribute replaces the categories.
 * @param {() => void} widget.refresh_colors
 * @param {() => void} widget.recount_bars
 * @param {() => void} widget.redraw_bars
 * @param {Array<() => void>} cleanups - Run when the widget is finalized.
 */
export const setup_cell_attribute_controls = (
  viz_state,
  {
    cell_button,
    slider = null,
    compact = true,
    refresh_colors,
    recount_bars,
    redraw_bars,
  },
  cleanups = []
) => {
  let menu = null;
  const show_cell_attribute = (name, { publish = true } = {}) => {
    const { changed_categories } = set_cell_attribute(viz_state, name);
    if (changed_categories) {
      // Selections named the other attribute's values.
      force_set_selected_cats(viz_state.cats, [], viz_state.obs_store);
      if (compact) {
        set_dict_cell_cats(viz_state.cats);
        viz_state.combo_data.cell_compact = buildCellCompactData(
          viz_state.cats.cell_names_array,
          viz_state.combo_data.cell_compact?.positions || new Float64Array(),
          viz_state.combo_data.cell_compact?.size || 2,
          viz_state.cats.dict_cell_cats
        );
      }
    }
    viz_state.selection_token = (viz_state.selection_token || 0) + 1;
    refresh_colors();
    // Bars: a per-cell attribute's own counts; a label set regroups the
    // clusters' bars as last drawn.
    if (changed_categories) recount_bars();
    else redraw_bars();
    menu?.update();
    const value = viz_state.cats.attribute || '';
    if (publish && viz_state.model?.get?.('cell_attribute') !== value) {
      viz_state.model.set('cell_attribute', value);
      viz_state.model.save_changes?.();
    }
  };
  viz_state.show_cell_attribute = show_cell_attribute;
  // A cluster selection or query from elsewhere (a Clustergram, Clerk, a saved
  // view) needs the clusters, not another per-cell attribute.
  viz_state.show_clusters_attribute = () => {
    if (viz_state.cats.attribute_kind === 'cell') show_cell_attribute('');
  };
  menu = make_cell_attribute_menu(
    viz_state,
    cell_button,
    (name) => show_cell_attribute(name),
    { slider }
  );
  viz_state.cell_attribute_menu = menu;

  const known = (name) =>
    cell_attribute_options(viz_state).some(
      (option) => option.value === normalize_cell_attribute(viz_state, name)
    );
  const on_cell_attribute = () => {
    const name = viz_state.model.get('cell_attribute') || '';
    if (
      normalize_cell_attribute(viz_state, name) ===
      (viz_state.cats.attribute || '')
    )
      return;
    if (known(name)) show_cell_attribute(name, { publish: false });
  };
  const on_label_sets = () => {
    const shown = viz_state.cats.attribute || '';
    // The shown set changed (relabeled clusters) or went away.
    if (viz_state.cats.attribute_kind === 'labels')
      show_cell_attribute(known(shown) ? shown : '');
    else menu.update();
    on_cell_attribute(); // a set the model asked for may have just arrived
  };
  if (viz_state.model?.on) {
    viz_state.model.on('change:cell_attribute', on_cell_attribute);
    viz_state.model.on('change:label_sets', on_label_sets);
    cleanups.push(() => {
      viz_state.model.off?.('change:cell_attribute', on_cell_attribute);
      viz_state.model.off?.('change:label_sets', on_label_sets);
    });
    on_cell_attribute();
  }
  return menu;
};
