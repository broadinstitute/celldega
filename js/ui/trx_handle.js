/**
 * The TRX button as a handle for loading transcripts (and cell boundaries) at
 * intermediate zoom. Below `max_tiles_to_view` tiles they load automatically
 * (close-up). Up to the Landscape's `intermediate_zoom_limit` times that (see
 * trx_force_tile_factor), clicking TRX loads them anyway; beyond it, nothing
 * loads.
 *
 * Button colors: faded light gray = too far out (not clickable), gray = click
 * to load, blue = loaded (automatically or by the click), dimmed while loading
 * (see with_trx_loading), in close-up as well.
 *
 * The TRX slider follows the same split: in close-up it sets transcript size;
 * zoomed out it sets the expression at which cells reach full opacity
 * (`trx_slider_mode` 'size' / 'opacity', see ini_trx_slider_modes).
 *
 * Intermediate zoom with transcripts loaded by a click is its own view (see
 * is_trx_force_shown): cells keep their cluster colors, since the transcripts
 * show the selected genes, and the slider can make transcripts up to
 * trx_forced_size_scale times larger than in close-up.
 */

/**
 * Default `intermediate_zoom_limit`: how many times `max_tiles_to_view` a
 * click on TRX may load. Tile count scales with area, so 9 allows a view 3x
 * wider than close-up.
 */
export const TRX_FORCE_TILE_FACTOR = 9;

/**
 * The Landscape's `intermediate_zoom_limit` (`viz_state`), at least 1; 1
 * leaves no intermediate zoom, so TRX never loads past close-up.
 */
export const trx_force_tile_factor = (viz_state) => {
  const factor = viz_state?.intermediate_zoom_limit;
  return typeof factor === 'number' && Number.isFinite(factor)
    ? Math.max(1, factor)
    : TRX_FORCE_TILE_FACTOR;
};

/**
 * Largest transcript size while forced, relative to close-up's: the view's
 * width ratio, so at the far edge transcripts can look as large on screen as
 * at full size in close-up.
 */
export const trx_forced_size_scale = (viz_state) =>
  Math.sqrt(trx_force_tile_factor(viz_state));

const TRX_DISABLED_COLOR = '#c8c8c8';
const TRX_DISABLED_OPACITY = 0.45;
const TRX_LOADING_OPACITY = 0.5;

/**
 * @param {number} num_tiles - Tiles in view.
 * @param {number} max_tiles - `viz_state.max_tiles_to_view`.
 * @param {number} [factor] - trx_force_tile_factor.
 * @returns {'auto'|'forceable'|'far'}
 */
export const trx_zone = (
  num_tiles,
  max_tiles,
  factor = TRX_FORCE_TILE_FACTOR
) => {
  if (num_tiles < max_tiles) return 'auto';
  if (num_tiles < max_tiles * factor) return 'forceable';
  return 'far';
};

/** Tile count below which transcripts and boundaries load. */
export const trx_load_tile_limit = (viz_state) =>
  viz_state.max_tiles_to_view *
  (viz_state.trx_forced ? trx_force_tile_factor(viz_state) : 1);

/** Intermediate zoom, with transcripts loaded by a TRX click. */
export const is_trx_force_shown = (viz_state) =>
  viz_state.trx_zone === 'forceable' && Boolean(viz_state.trx_forced);

export const has_gene_selection = (viz_state) =>
  (viz_state.genes?.selected_genes ?? []).length > 0;

/**
 * Zoomed out, the TRX slider scales cell opacity, which only means something
 * with a gene selected. (In close-up its enabled state follows the TRX layer,
 * as set by the controls that show/hide transcripts.)
 */
export const sync_trx_slider = (viz_state) => {
  const slider = viz_state.sliders?.trx;
  if (!slider || viz_state.trx_slider_mode !== 'opacity') return;
  slider.disabled = !has_gene_selection(viz_state);
};

/**
 * Paint the TRX button for the current zoom zone. In close-up ('auto') the
 * button keeps its usual on/off colors, which other controls also set; it is
 * only repainted (from the layer's visibility) when arriving from further out.
 * While on (blue), it's dimmed as transcripts load, as at intermediate zoom.
 */
export const sync_trx_button = (viz_state, layers_obj) => {
  const button = viz_state.buttons?.buttons?.trx;
  const zone = viz_state.trx_zone;
  if (!button?.style || !zone) return;

  const previous_zone = viz_state.trx_button_zone;
  viz_state.trx_button_zone = zone;

  if (zone === 'auto') {
    if (previous_zone && previous_zone !== 'auto') {
      const visible = layers_obj?.trx_layer?.props?.visible !== false;
      button.style('color', visible ? 'blue' : 'gray');
    }
    const loading =
      Boolean(viz_state.trx_loading) && button.style('color') === 'blue';
    button
      .style('cursor', 'pointer')
      .style('opacity', loading ? TRX_LOADING_OPACITY : 1);
  } else {
    const active = is_trx_force_shown(viz_state);
    let opacity = 1;
    if (zone === 'far') opacity = TRX_DISABLED_OPACITY;
    else if (active && viz_state.trx_loading) opacity = TRX_LOADING_OPACITY;
    button
      .style(
        'color',
        zone === 'far' ? TRX_DISABLED_COLOR : active ? 'blue' : 'gray'
      )
      .style('cursor', zone === 'far' ? 'default' : 'pointer')
      .style('opacity', opacity);
  }

  sync_trx_slider(viz_state);
};

/**
 * Run `load` (fetching the view's transcripts and boundaries) with TRX dimmed
 * until it finishes (see sync_trx_button). When views change faster than
 * tiles load, only the latest load undims it.
 *
 * @param {object} viz_state
 * @param {object} layers_obj
 * @param {() => Promise<void>} load
 */
export const with_trx_loading = async (viz_state, layers_obj, load) => {
  const load_id = (viz_state.trx_load_id ?? 0) + 1;
  viz_state.trx_load_id = load_id;
  viz_state.trx_loading = true;
  sync_trx_button(viz_state, layers_obj);
  try {
    await load();
  } finally {
    if (viz_state.trx_load_id === load_id) {
      viz_state.trx_loading = false;
      sync_trx_button(viz_state, layers_obj);
    }
  }
};

const format_count = (value) =>
  value >= 10 ? Math.round(value).toLocaleString() : value.toFixed(1);

/**
 * One line at the top of the gene panel, shown while the slider scales cell
 * opacity: the (summed) expression drawn at full opacity.
 */
export const update_expression_note = (viz_state) => {
  const box = viz_state.genes?.gene_text_box;
  if (!box) return;

  const { cats } = viz_state;
  const full_at = (cats.cell_exp_max ?? 0) * (cats.cell_exp_scale ?? 1);
  const show =
    viz_state.trx_slider_mode === 'opacity' &&
    has_gene_selection(viz_state) &&
    Number.isFinite(full_at) &&
    full_at > 0;

  let note = box.querySelector('.expression_note');
  if (!show) {
    note?.remove();
    return;
  }
  if (!note) {
    note = document.createElement('div');
    note.className = 'expression_note';
    note.style.fontSize = '10px';
    note.style.color = '#555555';
    box.prepend(note);
  }
  const summed = viz_state.genes.selected_genes.length > 1 ? ' (summed)' : '';
  note.textContent = `Full opacity at ≥ ${format_count(full_at)}${summed}`;
};
