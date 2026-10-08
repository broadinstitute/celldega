/* global require */

describe('Dendro slider lifecycle', () => {
  let update_dendro_from_slider;
  let hasCrop;
  let set_slider_value;
  let alt_slice_linkage;
  let calc_dendro_triangles;
  let calc_dendro_polygons;
  let update_dendro_layer_data;

  beforeEach(() => {
    const fs = require('fs');
    const path = require('path');
    const source = fs
      .readFileSync(path.join(__dirname, '../ui/dendro_slider.js'), 'utf8')
      .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
      .replace(/^export const /gm, 'const ');

    hasCrop = false;
    set_slider_value = jest.fn((slider, value) => {
      slider.value = String(value);
      slider.style.setProperty('--val', `${value}%`);
    });
    alt_slice_linkage = jest.fn();
    calc_dendro_triangles = jest.fn();
    calc_dendro_polygons = jest.fn();
    update_dendro_layer_data = jest.fn();

    const factory = new Function(
      'has_axis_crop_filter',
      'set_slider_value',
      'alt_slice_linkage',
      'calc_dendro_triangles',
      'calc_dendro_polygons',
      'update_dendro_layer_data',
      'get_mat_layers_list',
      `${source}; return update_dendro_from_slider;`
    );

    update_dendro_from_slider = factory(
      () => hasCrop,
      set_slider_value,
      alt_slice_linkage,
      calc_dendro_triangles,
      calc_dendro_polygons,
      update_dendro_layer_data,
      () => ['layers']
    );
  });

  const makeState = () => ({
    // A RANK view narrows rows but is deliberately not a crop.
    rank_view: { filter: { row: [1, 3, 5], col: null } },
    crop: { filter: { row: null, col: null } },
    dendro: {
      max_linkage_dist: { row: 2 },
      sliders: { row_percent: 50, row_value: 1 },
    },
  });

  test('updates a row dendrogram while a RANK view is active', () => {
    const deck = { setProps: jest.fn() };
    const state = makeState();
    const slider = document.createElement('input');
    slider.value = '75';

    const updated = update_dendro_from_slider(deck, {}, state, 'row', {
      target: slider,
    });

    expect(updated).toBe(true);
    expect(state.dendro.sliders.row_percent).toBe('75');
    expect(state.dendro.sliders.row_value).toBe(1.5);
    expect(alt_slice_linkage).toHaveBeenCalledWith(state, 'row', 1.5);
    expect(calc_dendro_triangles).toHaveBeenCalledWith(state, 'row');
    expect(calc_dendro_polygons).toHaveBeenCalledWith(state, 'row');
    expect(update_dendro_layer_data).toHaveBeenCalledWith({}, state, 'row');
    expect(deck.setProps).toHaveBeenCalledWith({ layers: ['layers'] });
  });

  test('keeps a cropped dendrogram pinned and restores slider fill', () => {
    hasCrop = true;
    const deck = { setProps: jest.fn() };
    const state = makeState();
    const slider = document.createElement('input');
    slider.value = '90';

    const updated = update_dendro_from_slider(deck, {}, state, 'row', {
      target: slider,
    });

    expect(updated).toBe(false);
    expect(set_slider_value).toHaveBeenCalledWith(slider, 50);
    expect(slider.value).toBe('50');
    expect(slider.style.getPropertyValue('--val')).toBe('50%');
    expect(alt_slice_linkage).not.toHaveBeenCalled();
    expect(deck.setProps).not.toHaveBeenCalled();
  });
});
