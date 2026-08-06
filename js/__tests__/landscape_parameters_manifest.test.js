/* global require */

// set_landscape_parameters fetches a widget-specified manifest filename and
// falls back to landscape_parameters.json when it is absent, so CellCloud /
// NeighborhoodCloud resolve their own manifest while pre-rename DegaFiles
// (only landscape_parameters.json) keep rendering.
describe('set_landscape_parameters manifest name + fallback', () => {
  let set_landscape_parameters;

  beforeAll(() => {
    const fs = require('fs');
    const path = require('path');

    const readStripped = (relPath) =>
      fs
        .readFileSync(path.join(__dirname, relPath), 'utf8')
        .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
        .replace(/^export const /gm, 'const ');

    const source = [
      // landscape_parameters.js imports `options` from ./fetch_options; the
      // import is stripped above, so provide a stub for the non-aws branch.
      'const options = { fetch: {} };',
      readStripped('../global_variables/landscape_parameters.js'),
    ].join('\n');

    const code = `${source}\nmodule.exports = { set_landscape_parameters };`;
    const module = { exports: {} };
    new Function('module', 'exports', code)(module, module.exports);
    ({ set_landscape_parameters } = module.exports);
  });

  afterEach(() => {
    delete global.fetch;
  });

  const mkResponse = (ok, body) => ({
    ok,
    status: ok ? 200 : 404,
    statusText: ok ? 'OK' : 'Not Found',
    json: async () => body,
  });

  test('fetches the requested manifest when present (no fallback)', async () => {
    const calls = [];
    global.fetch = async (url) => {
      calls.push(url);
      return mkResponse(true, { technology: 'point-cloud' });
    };

    const img = {};
    await set_landscape_parameters(
      img,
      'http://x/data',
      null,
      'cell_cloud.json'
    );

    expect(calls).toEqual(['http://x/data/cell_cloud.json']);
    expect(img.landscape_parameters.technology).toBe('point-cloud');
  });

  test('falls back to landscape_parameters.json when requested manifest is absent', async () => {
    const calls = [];
    global.fetch = async (url) => {
      calls.push(url);
      const ok = url.endsWith('landscape_parameters.json');
      return mkResponse(ok, ok ? { technology: 'point-cloud' } : {});
    };

    const img = {};
    await set_landscape_parameters(
      img,
      'http://x/data',
      null,
      'cell_cloud.json'
    );

    expect(calls).toEqual([
      'http://x/data/cell_cloud.json',
      'http://x/data/landscape_parameters.json',
    ]);
    expect(img.landscape_parameters.technology).toBe('point-cloud');
  });

  test('defaults to landscape_parameters.json without a redundant second fetch', async () => {
    const calls = [];
    global.fetch = async (url) => {
      calls.push(url);
      return mkResponse(true, { technology: 'Xenium' });
    };

    const img = {};
    await set_landscape_parameters(img, 'http://x/data', null);

    expect(calls).toEqual(['http://x/data/landscape_parameters.json']);
    expect(img.landscape_parameters.technology).toBe('Xenium');
  });

  test('throws (naming the requested manifest) when neither is present', async () => {
    global.fetch = async () => mkResponse(false, {});

    const img = {};
    await expect(
      set_landscape_parameters(img, 'http://x/data', null, 'cell_cloud.json')
    ).rejects.toThrow(/cell_cloud\.json/);
  });
});
