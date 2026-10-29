/* global require */

const fs = require('fs');
const path = require('path');

const load = (file, names) => {
  const source = fs
    .readFileSync(path.join(__dirname, file), 'utf8')
    .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
    .replace(/^export const /gm, 'const ');
  return new Function(`${source}\nreturn { ${names} };`)();
};

const { make_options_model, link_models } = load(
  '../utils/options_model.js',
  'make_options_model, link_models'
);
const { LANDSCAPE_DEFAULTS, landscape_model_values } = load(
  '../viz/landscape_options.js',
  'LANDSCAPE_DEFAULTS, landscape_model_values'
);

describe('make_options_model', () => {
  it('stores values and fires change events like a widget model', () => {
    const model = make_options_model({ rank_dim: 10 });
    const changes = [];
    const listener = () => changes.push(model.get('rank_dim'));
    model.on('change:rank_dim', listener);

    expect(model.get('rank_dim')).toBe(10);
    expect(model.get('unset')).toBeNull();
    model.set('rank_dim', 25);
    model.set('rank_dim', 25); // unchanged: no event
    model.off('change:rank_dim', listener);
    model.set('rank_dim', 50);
    expect(changes).toEqual([25]);
    expect(model.get('rank_dim')).toBe(50);
  });

  it('links a Clustergram click to a Landscape update trigger', () => {
    const cgm = make_options_model();
    const ls = make_options_model();
    const triggers = [];
    ls.on('change:update_trigger', () =>
      triggers.push(ls.get('update_trigger'))
    );
    const unlink = link_models(cgm, 'click_info', ls, 'update_trigger');

    const click = { type: 'row_label', value: { name: 'CD79B' } };
    // Clustergrams reset click_info first so a repeated click still changes it.
    cgm.set('click_info', null);
    cgm.set('click_info', click);
    unlink();
    cgm.set('click_info', { type: 'col_label', value: { name: '3' } });
    // The reset reaches the Landscape too, which ignores a null trigger.
    expect(triggers).toEqual([null, click]);
  });
});

describe('landscape_model_values', () => {
  it('follows the Python widget defaults', () => {
    const values = landscape_model_values({
      zarr_url: 'https://example.org/pbmc.zarr',
      cluster_attr: 'cell_type',
      ini_zoom: -4.5,
    });
    expect(values).toMatchObject({
      ...LANDSCAPE_DEFAULTS,
      zarr_url: 'https://example.org/pbmc.zarr',
      technology: 'Chromium',
      cluster_attr: 'cell_type',
      cell_attr: ['leiden', 'cell_type'],
      ini_zoom: -4.5,
      height: 600,
    });
    expect(
      landscape_model_values({ base_url: 'https://example.org/dega' })
    ).toMatchObject({ technology: 'Xenium', cell_attr: ['leiden'] });
  });

  it('rejects two data sources and spatial Zarr technologies', () => {
    expect(() =>
      landscape_model_values({ zarr_url: 'a.zarr', base_url: 'dega' })
    ).toThrow(/not both/);
    expect(() =>
      landscape_model_values({ zarr_url: 'a.zarr', technology: 'Xenium' })
    ).toThrow(/Chromium/);
  });
});
