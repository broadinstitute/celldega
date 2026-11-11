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
  test('accepts a CellCloud Zarr store and preserves its alignment options', () => {
    expect(
      landscape_model_values({
        technology: 'point-cloud',
        zarr_url: 'https://example.org/cells.zarr',
        alignment: 'neighborhood',
      })
    ).toMatchObject({ technology: 'point-cloud', alignment: 'neighborhood' });
  });
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

describe('standalone clustergram()', () => {
  // The constructor, from celldega.js, with its loaders and renderer stubbed.
  const source = fs.readFileSync(
    path.join(__dirname, '../celldega.js'),
    'utf8'
  );
  const constructors = (rendered) => {
    const start = source.indexOf('const static_matrix_model = (');
    const end = source.indexOf(
      '/**\n * Load and render a Clustergram from DegaFiles'
    );
    return new Function(
      'make_options_model',
      'matrix_viz',
      'network_from_zarr',
      'networkFromDegaFiles',
      // landscape() sits between them in the file; it is never called here.
      `${source.slice(start, end).replace('const landscape = async', 'const _landscape = async')}
       return { clustergram };`
    )(
      make_options_model,
      async (model) => {
        rendered.push(model);
        return {};
      },
      async () => ({ row_nodes: [], col_nodes: [] }),
      async () => ({ row_nodes: [], col_nodes: [] })
    );
  };

  test('a declared data_revision and the source reach the model saved views read', async () => {
    const rendered = [];
    const { clustergram } = constructors(rendered);
    const network = { row_nodes: [], col_nodes: [] };
    const viz = await clustergram(null, {
      network,
      data_revision: 'release-1',
    });
    expect(viz.model.get('data_revision')).toBe('release-1');
    await clustergram(null, { url: 'https://example.org/m.zarr' });
    expect(rendered[1].get('url')).toBe('https://example.org/m.zarr');
    expect(rendered[1].get('data_revision')).toBe('');
    await clustergram(null, {
      base_url: 'https://example.org/dega',
      name: 'leiden',
    });
    expect(rendered[2].get('url')).toBe('');
    expect(rendered[2].get('base_url')).toBe('https://example.org/dega');
    expect(rendered[2].get('name')).toBe('leiden');
  });
});
