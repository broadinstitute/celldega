/* global require */

// TRX button as a handle for loading transcripts at intermediate zoom.

const fs = require('fs');
const path = require('path');

const source = fs
  .readFileSync(path.join(__dirname, '../ui/trx_handle.js'), 'utf8')
  .replace(/^export const /gm, 'const ');
const module_ = { exports: {} };
new Function(
  'module',
  `${source}\nmodule.exports = { TRX_FORCE_TILE_FACTOR, trx_zone, trx_load_tile_limit, sync_trx_button, sync_trx_slider, update_expression_note };`
)(module_);
const {
  TRX_FORCE_TILE_FACTOR,
  trx_zone,
  trx_load_tile_limit,
  sync_trx_button,
  sync_trx_slider,
  update_expression_note,
} = module_.exports;

// Minimal d3-selection stand-in that records styles.
const make_button = (color = 'blue') => {
  const styles = { color };
  const button = {
    styles,
    style: (name, value) => {
      if (value === undefined) return styles[name];
      styles[name] = value;
      return button;
    },
  };
  return button;
};

describe('trx_zone', () => {
  it('splits views into close-up, forceable, and too far', () => {
    expect(trx_zone(49, 50)).toBe('auto');
    expect(trx_zone(50, 50)).toBe('forceable');
    expect(trx_zone(50 * TRX_FORCE_TILE_FACTOR - 1, 50)).toBe('forceable');
    expect(trx_zone(50 * TRX_FORCE_TILE_FACTOR, 50)).toBe('far');
  });

  it('raises the load limit only while forced', () => {
    expect(trx_load_tile_limit({ max_tiles_to_view: 50 })).toBe(50);
    expect(
      trx_load_tile_limit({ max_tiles_to_view: 50, trx_forced: true })
    ).toBe(50 * TRX_FORCE_TILE_FACTOR);
  });
});

describe('sync_trx_button', () => {
  const make_viz_state = (zone, overrides = {}) => ({
    trx_zone: zone,
    buttons: { buttons: { trx: make_button() } },
    ...overrides,
  });

  it('shows light gray (not clickable) when too far out', () => {
    const viz_state = make_viz_state('far');
    sync_trx_button(viz_state, {});
    const { styles } = viz_state.buttons.buttons.trx;
    expect(styles.color).toBe('#c8c8c8');
    expect(styles.cursor).toBe('default');
    expect(styles.opacity).toBeLessThan(0.5);
  });

  it('shows gray until clicked, then blue, dimmed while loading', () => {
    const viz_state = make_viz_state('forceable');
    const { styles } = viz_state.buttons.buttons.trx;
    sync_trx_button(viz_state, {});
    expect(styles.color).toBe('gray');

    viz_state.trx_forced = true;
    viz_state.trx_loading = true;
    sync_trx_button(viz_state, {});
    expect(styles.color).toBe('blue');
    expect(styles.opacity).toBe(0.5);

    viz_state.trx_loading = false;
    sync_trx_button(viz_state, {});
    expect(styles.opacity).toBe(1);
  });

  it('leaves close-up colors alone, except when arriving from further out', () => {
    const viz_state = make_viz_state('auto');
    const button = viz_state.buttons.buttons.trx;
    button.styles.color = 'gray'; // e.g. transcripts toggled off
    sync_trx_button(viz_state, { trx_layer: { props: { visible: true } } });
    expect(button.styles.color).toBe('gray');

    viz_state.trx_zone = 'far';
    sync_trx_button(viz_state, {});
    viz_state.trx_zone = 'auto';
    sync_trx_button(viz_state, { trx_layer: { props: { visible: true } } });
    expect(button.styles.color).toBe('blue');
  });

  it('does nothing without a zone (e.g. Yearbook, point clouds)', () => {
    const viz_state = make_viz_state(undefined);
    sync_trx_button(viz_state, {});
    expect(viz_state.buttons.buttons.trx.styles).toEqual({ color: 'blue' });
  });
});

describe('TRX slider while zoomed out', () => {
  const make_viz_state = (selected_genes, cats = {}) => {
    const box = document.createElement('div');
    box.innerHTML = '<span>gene info</span>';
    return {
      trx_slider_mode: 'opacity',
      sliders: { trx: document.createElement('input') },
      genes: { selected_genes, gene_text_box: box },
      cats: { cell_exp_max: 40, cell_exp_scale: 0.25, ...cats },
    };
  };

  it('is enabled only with a gene selected', () => {
    const viz_state = make_viz_state([]);
    sync_trx_slider(viz_state);
    expect(viz_state.sliders.trx.disabled).toBe(true);
    viz_state.genes.selected_genes = ['UMOD'];
    sync_trx_slider(viz_state);
    expect(viz_state.sliders.trx.disabled).toBe(false);
  });

  it('leaves the slider alone in close-up', () => {
    const viz_state = make_viz_state([]);
    viz_state.trx_slider_mode = 'size';
    sync_trx_slider(viz_state);
    expect(viz_state.sliders.trx.disabled).toBe(false);
  });

  it('notes the expression drawn at full opacity', () => {
    const viz_state = make_viz_state(['UMOD', 'SLC34A1']);
    update_expression_note(viz_state);
    const note = viz_state.genes.gene_text_box.firstChild;
    expect(note.textContent).toBe('Full opacity at ≥ 10 (summed)');
    // The gene info below it is kept.
    expect(viz_state.genes.gene_text_box.textContent).toContain('gene info');

    viz_state.trx_slider_mode = 'size';
    update_expression_note(viz_state);
    expect(
      viz_state.genes.gene_text_box.querySelector('.expression_note')
    ).toBeNull();
  });
});
