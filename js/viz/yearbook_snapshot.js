import { capture_deck } from '../utils/canvas_capture';

import {
  apply_landscape_state,
  get_landscape_replay_state,
} from './landscape_state';
import {
  create_snapshot_api,
  landscape_identity,
  landscape_source,
  wait_for_canvas,
  wait_for_operation,
} from './snapshot';

/** Reuse shared color/layer controls, with an explicit Yearbook portrait/camera contract. */
export const create_yearbook_snapshot_api = ({
  state,
  deck,
  root,
  layers,
  refresh,
  selection,
  ready,
}) => {
  const yb = state.yearbook;
  const get_replay_state = () => {
    const display = get_landscape_replay_state(state);
    // Yearbook uses one camera per portrait, always in spatial coordinates.
    for (const key of ['space', 'view', 'xy', 'selected_cells'])
      delete display[key];
    return {
      cells: [...yb.cells],
      page: yb.current_page,
      zoom: yb.zoom_level,
      query: { ...yb.query },
      selected_cells: selection.get_selected_cells(),
      display,
    };
  };
  const apply_state = async (saved) => {
    const known = state.cats.cell_name_to_index_map;
    for (const key of ['cells', 'selected_cells']) {
      if (
        !Array.isArray(saved[key]) ||
        saved[key].some((id) => !known.has(String(id)))
      )
        throw new Error(`Unknown Yearbook ${key}`);
    }
    const pages = Math.max(
      1,
      Math.ceil(saved.cells.length / (yb.num_rows * yb.num_cols))
    );
    if (
      !Number.isInteger(saved.page) ||
      saved.page < 0 ||
      saved.page >= pages ||
      !Number.isFinite(saved.zoom)
    )
      throw new Error('Invalid Yearbook page or zoom');
    if (
      !saved.query ||
      typeof saved.query !== 'object' ||
      Array.isArray(saved.query)
    )
      throw new Error('Invalid Yearbook query');
    if (
      !saved.display ||
      typeof saved.display !== 'object' ||
      Array.isArray(saved.display)
    )
      throw new Error('Missing Yearbook display settings');
    const display_keys = [
      'genes',
      'clusters',
      'layers',
      'channels',
      'sliders',
      'image_source',
    ];
    if (Object.keys(saved.display).some((key) => !display_keys.includes(key)))
      throw new Error('Unsupported Yearbook display setting');
    yb.restoring = true;
    try {
      await apply_landscape_state(
        state,
        { deck, layers_obj: layers },
        saved.display
      );
      yb.cells = [...saved.cells];
      yb.current_page = saved.page;
      yb.zoom_level = saved.zoom;
      yb.query = { ...saved.query };
      // Replay the captured cells, never rerun a potentially random query.
      state.model?.set?.('cells', [...saved.cells]);
      state.model?.set?.('current_page', saved.page);
      state.model?.set?.('zoom_level', saved.zoom);
      state.model?.set?.('front_end_query', { ...saved.query });
      selection.set_selected_cells(saved.selected_cells);
      state.model?.save_changes?.();
      await refresh();
      yb.update_pagination_ui?.();
      if (yb.query_ui) {
        yb.query_ui.cluster_input.value = saved.query.cluster?.value || '';
        yb.query_ui.gene_input.value = saved.query.gene || '';
        yb.query_ui.update_status(`${saved.cells.length} captured cells`);
      }
      return [
        'restored Yearbook portraits, page, zoom, selections and display',
      ];
    } finally {
      yb.restoring = false;
    }
  };
  return create_snapshot_api({
    kind: 'yearbook',
    ready: () =>
      wait_for_operation(async () => {
        await ready();
        await wait_for_canvas(deck, () => state.disposed);
      }),
    get_state: get_replay_state,
    get_replay_state,
    capture_raster: (options) => capture_deck(deck, root, options),
    apply_state: (saved) => wait_for_operation(() => apply_state(saved)),
    identity: () => ({
      ...landscape_identity(state),
      grid: {
        rows: yb.num_rows,
        cols: yb.num_cols,
        size: yb.portrait_size_um,
        gap: yb.portrait_gap,
      },
    }),
    source: () => ({ ...landscape_source(state), widget: 'Yearbook' }),
    viewport: () => ({
      width: deck.getCanvas().clientWidth,
      height: deck.getCanvas().clientHeight,
    }),
  });
};
