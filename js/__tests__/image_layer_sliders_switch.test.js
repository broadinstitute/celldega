/* global require */

// A dataset switch rebuilds `img.image_layer_sliders`. It must reuse the
// slider elements already on the page: a replacement `<input>` has no value
// and is not attached, so the intensity callback computed opacity 0 from it
// and the stains disappeared (issue #391).
describe('image layer sliders across a dataset switch', () => {
  let set_image_layer_sliders;
  let save_image_slider_values;
  let restore_image_slider_values;
  let set_slider_accent_color;
  let update_opacity_single_image_layer;

  beforeEach(() => {
    const fs = require('fs');
    const path = require('path');
    const source = fs.readFileSync(
      path.join(__dirname, '../ui/sliders.js'),
      'utf8'
    );

    const extract = (name) => {
      const start = source.indexOf(`export const ${name} = `);
      const end = source.indexOf('\n};\n', start) + 3;
      return source.slice(start, end).replace(/^export const /, 'const ');
    };

    set_slider_accent_color = jest.fn();
    update_opacity_single_image_layer = jest.fn();

    const factory = new Function(
      'set_slider_accent_color',
      'update_opacity_single_image_layer',
      'set_slider_value',
      `const DEFAULT_IMG_SLIDER_VALUE = 50;
       ${extract('set_image_layer_sliders')}
       ${extract('save_image_slider_values')}
       ${extract('restore_image_slider_values')}
       return { set_image_layer_sliders, save_image_slider_values, restore_image_slider_values };`
    );
    ({
      set_image_layer_sliders,
      save_image_slider_values,
      restore_image_slider_values,
    } = factory(
      set_slider_accent_color,
      update_opacity_single_image_layer,
      (slider, value) => {
        slider.value = String(value);
      }
    ));
  });

  const make_slider = (name, value) => {
    const slider = document.createElement('input');
    slider.type = 'range';
    slider.name = name;
    slider.value = String(value);
    return slider;
  };

  test('creates sliders on first build', () => {
    const img = {
      image_layer_sliders: {},
      image_info: [
        { button_name: 'DAPI', color: [0, 0, 255] },
        { button_name: 'BOUND', color: [0, 255, 0] },
      ],
    };

    set_image_layer_sliders(img);

    expect(img.image_layer_sliders.map((s) => s.name)).toEqual([
      'DAPI',
      'BOUND',
    ]);
  });

  test('reuses existing slider elements for matching channels', () => {
    const dapi = make_slider('DAPI', 100);
    const bound = make_slider('BOUND', 80);
    const img = {
      image_layer_sliders: [dapi, bound],
      image_info: [
        { button_name: 'DAPI', color: [0, 0, 255] },
        { button_name: 'BOUND', color: [0, 255, 0] },
      ],
    };

    set_image_layer_sliders(img);

    expect(img.image_layer_sliders[0]).toBe(dapi);
    expect(img.image_layer_sliders[1]).toBe(bound);
    expect(img.image_layer_sliders[0].value).toBe('100');
    expect(set_slider_accent_color).toHaveBeenCalledWith(dapi, [0, 0, 255]);
  });

  test('creates a slider only for a channel that had none', () => {
    const dapi = make_slider('DAPI', 70);
    const img = {
      image_layer_sliders: [dapi],
      image_info: [
        { button_name: 'DAPI', color: [0, 0, 255] },
        { button_name: 'PROT', color: [255, 255, 255] },
      ],
    };

    set_image_layer_sliders(img);

    expect(img.image_layer_sliders[0]).toBe(dapi);
    expect(img.image_layer_sliders[1]).not.toBe(dapi);
    expect(img.image_layer_sliders[1].name).toBe('PROT');
  });

  const make_viz_state = (sliders) => ({
    img: {
      image_layer_sliders: sliders,
      image_layer_colors: { DAPI: [0, 0, 255], RNA: [255, 0, 0] },
    },
  });

  test('saves slider values per dataset', () => {
    const viz_state = make_viz_state([
      make_slider('DAPI', 100),
      make_slider('RNA', 40),
    ]);

    save_image_slider_values(viz_state, 0);

    expect(viz_state.img.slider_values_by_dataset[0]).toEqual({
      DAPI: '100',
      RNA: '40',
    });
  });

  test("restores a dataset's own values when switching back", () => {
    const dapi = make_slider('DAPI', 100);
    const rna = make_slider('RNA', 100);
    const viz_state = make_viz_state([dapi, rna]);
    const layers_obj = {};

    // Dataset 0 at 100/100, then leave it for dataset 1 (never visited).
    save_image_slider_values(viz_state, 0);
    restore_image_slider_values(viz_state, layers_obj, 1);
    expect([dapi.value, rna.value]).toEqual(['50', '50']);

    // Adjust dataset 1, leave it, and come back to dataset 0.
    dapi.value = '20';
    save_image_slider_values(viz_state, 1);
    restore_image_slider_values(viz_state, layers_obj, 0);
    expect([dapi.value, rna.value]).toEqual(['100', '100']);

    // Dataset 1 still has its own values.
    restore_image_slider_values(viz_state, layers_obj, 1);
    expect([dapi.value, rna.value]).toEqual(['20', '50']);
  });

  test('applies the restored values to the image layers', () => {
    const viz_state = make_viz_state([
      make_slider('DAPI', 100),
      make_slider('RNA', 40),
    ]);
    const layers_obj = {};

    save_image_slider_values(viz_state, 0);
    restore_image_slider_values(viz_state, layers_obj, 0);

    expect(update_opacity_single_image_layer).toHaveBeenCalledWith(
      viz_state,
      layers_obj,
      'DAPI',
      10,
      viz_state.img.image_layer_colors
    );
    expect(update_opacity_single_image_layer).toHaveBeenCalledWith(
      viz_state,
      layers_obj,
      'RNA',
      4,
      viz_state.img.image_layer_colors
    );
  });

  test('ignores a slider list that is not an array', () => {
    const viz_state = { img: { image_layer_sliders: {} } };

    expect(() => save_image_slider_values(viz_state, 0)).not.toThrow();
    expect(() => restore_image_slider_values(viz_state, {}, 0)).not.toThrow();
    expect(update_opacity_single_image_layer).not.toHaveBeenCalled();
  });
});
