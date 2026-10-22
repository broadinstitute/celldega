/**
 * The TRX button as a handle for loading transcripts (and cell boundaries) at
 * intermediate zoom. Below `max_tiles_to_view` tiles they load automatically
 * (close-up). Up to TRX_FORCE_TILE_FACTOR times that, clicking TRX loads them
 * anyway; beyond it, nothing loads.
 *
 * Button colors: faded light gray = too far out (not clickable), gray = click
 * to load, blue = loaded (automatically or by the click), dimmed while loading.
 *
 * The TRX slider follows the same split: in close-up it sets transcript size;
 * zoomed out it sets the expression at which cells reach full opacity
 * (`trx_slider_mode` 'size' / 'opacity', see ini_trx_slider_modes).
 */

/** How many times `max_tiles_to_view` a click on TRX may load. */
export const TRX_FORCE_TILE_FACTOR = 4;

const TRX_DISABLED_COLOR = '#c8c8c8';
const TRX_DISABLED_OPACITY = 0.45;

/**
 * @param {number} num_tiles - Tiles in view.
 * @param {number} max_tiles - `viz_state.max_tiles_to_view`.
 * @returns {'auto'|'forceable'|'far'}
 */
export const trx_zone = (num_tiles, max_tiles) => {
  if (num_tiles < max_tiles) return 'auto';
  if (num_tiles < max_tiles * TRX_FORCE_TILE_FACTOR) return 'forceable';
  return 'far';
};

/** Tile count below which transcripts and boundaries load. */
export const trx_load_tile_limit = (viz_state) =>
  viz_state.max_tiles_to_view *
  (viz_state.trx_forced ? TRX_FORCE_TILE_FACTOR : 1);

const has_gene_selection = (viz_state) =>
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
    button.style('cursor', 'pointer').style('opacity', 1);
  } else {
    const active = zone === 'forceable' && Boolean(viz_state.trx_forced);
    let opacity = 1;
    if (zone === 'far') opacity = TRX_DISABLED_OPACITY;
    else if (active && viz_state.trx_loading) opacity = 0.5;
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
