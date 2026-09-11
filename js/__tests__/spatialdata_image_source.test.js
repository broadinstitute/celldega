/**
 * The pure parts of the OME-Zarr image path.
 *
 * The loader itself is covered against a real store by integration/probes/viv_probe.mjs in
 * the workspace repo; what is pinned here is the arithmetic that would silently render the
 * wrong pyramid level or blow out the intensities.
 */

/* global require */

describe('OME-Zarr image source', () => {
  let zoomToLevel;
  let defaultWindow;
  let tileToRgba;

  beforeAll(() => {
    const fs = require('fs');
    const path = require('path');

    const source = fs
      .readFileSync(
        path.join(__dirname, '../spatialdata/image_source.js'),
        'utf8'
      )
      .replace(/^import \{[^}]*\} from '[^']+';$/gm, '')
      .replace(/^export const /gm, 'const ')
      .replace(/^export class /gm, 'class ');

    const code = `${source}\nmodule.exports = { zoomToLevel, defaultWindow, tileToRgba };`;
    const module = { exports: {} };
    new Function('module', 'exports', code)(module, module.exports);
    ({ zoomToLevel, defaultWindow, tileToRgba } = module.exports);
  });

  describe('zoom to resolution level', () => {
    test('deck.gl z maps onto viv resolution index', () => {
      // deck.gl counts down from 0 at full resolution; viv counts up from 0.
      expect(zoomToLevel(0, 5)).toBe(0);
      expect(zoomToLevel(-1, 5)).toBe(1);
      expect(zoomToLevel(-4, 5)).toBe(4);
    });

    test('clamps rather than reading past the pyramid', () => {
      // TileLayer is configured with minZoom -7 but the pyramid has 5 levels, so
      // out-of-range z arrives routinely and must not index undefined.
      expect(zoomToLevel(-7, 5)).toBe(4);
      expect(zoomToLevel(1, 5)).toBe(0);
      expect(zoomToLevel(-100, 1)).toBe(0);
    });
  });

  describe('intensity window', () => {
    test('defaults to the full dtype range, not a stretch', () => {
      // The viewer applies its own intensity slider afterwards; stretching here as well
      // double-applies and saturates the image.
      expect(defaultWindow(undefined, 'Uint16')).toEqual([0, 65535]);
      expect(defaultWindow({ label: 'DAPI' }, 'Uint16')).toEqual([0, 65535]);
      expect(defaultWindow(undefined, 'Uint8')).toEqual([0, 255]);
    });

    test('honours an omero window when the store provides one', () => {
      expect(
        defaultWindow({ window: { start: 100, end: 4000 } }, 'Uint16')
      ).toEqual([100, 4000]);
    });

    test('ignores a degenerate window', () => {
      expect(defaultWindow({ window: { start: 5, end: 5 } }, 'Uint16')).toEqual(
        [0, 65535]
      );
      expect(
        defaultWindow({ window: { start: 10, end: 2 } }, 'Uint16')
      ).toEqual([0, 65535]);
    });
  });

  describe('uint16 to RGBA', () => {
    test('maps the window onto 0-255 and keeps alpha opaque', () => {
      const data = Uint16Array.from([0, 32768, 65535, 100]);
      const rgba = tileToRgba(data, 2, 2, [0, 65535]);

      expect(rgba.length).toBe(2 * 2 * 4);
      expect(rgba[0]).toBe(0);
      expect(rgba[4]).toBe(128);
      expect(rgba[8]).toBe(255);
      // Grey, so the channel colour applied downstream is not tinted twice.
      expect(rgba[8]).toBe(rgba[9]);
      expect(rgba[9]).toBe(rgba[10]);
      // Alpha opaque everywhere.
      expect([rgba[3], rgba[7], rgba[11], rgba[15]]).toEqual([
        255, 255, 255, 255,
      ]);
    });

    test('clamps values outside the window instead of wrapping', () => {
      const data = Uint16Array.from([0, 5000]);
      const rgba = tileToRgba(data, 2, 1, [1000, 2000]);
      expect(rgba[0]).toBe(0);
      expect(rgba[4]).toBe(255);
    });

    test('a zero-width window does not divide by zero', () => {
      const data = Uint16Array.from([7]);
      const rgba = tileToRgba(data, 1, 1, [7, 7]);
      expect(Number.isFinite(rgba[0])).toBe(true);
    });
  });
});

describe('metadata the manifest no longer carries', () => {
  let SpatialDataImageSource;

  beforeAll(() => {
    const fs = require('fs');
    const path = require('path');
    const source = fs
      .readFileSync(
        path.join(__dirname, '../spatialdata/image_source.js'),
        'utf8'
      )
      .replace(/^import \{[^}]*\} from '[^']+';$/gm, '')
      .replace(/^export const /gm, 'const ')
      .replace(/^export class /gm, 'class ');
    const code = `${source}\nmodule.exports = { SpatialDataImageSource };`;
    const module = { exports: {} };
    new Function('module', 'exports', code)(module, module.exports);
    ({ SpatialDataImageSource } = module.exports);
  });

  // A store read natively has no WebP pyramid, so the manifest carries no image_info,
  // image_dimensions or max_pyramid_zoom. Everything they held is in the OME-Zarr, and
  // getting this wrong leaves the viewer with no channels and no extent -- a black square
  // with cell centroids scattered across the wrong area.
  const fakeSource = (channels) => ({
    data: [
      {
        shape: [channels.length, 13770, 34155],
        labels: ['c', 'y', 'x'],
        tileSize: 4096,
        dtype: 'Uint16',
      },
      {},
      {},
      {},
      {},
    ],
    metadata: { omero: { channels } },
  });

  test('dimensions come from the base level, by axis name', () => {
    const src = new SpatialDataImageSource(fakeSource([{ label: 'DAPI' }]));
    // Taken by axis label, not position: shape is c,y,x so width is the last entry.
    expect(src.dimensions).toEqual({ width: 34155, height: 13770 });
    expect(src.tileSize).toBe(4096);
    expect(src.maxPyramidZoom).toBe(4);
  });

  test('channels carry a name, label, index and a distinct colour', () => {
    const src = new SpatialDataImageSource(
      fakeSource([
        { label: 'DAPI' },
        { label: 'ATP1A1/CD45/E-Cadherin' },
        { label: '18S' },
      ])
    );
    const channels = src.channels();
    expect(channels.map((c) => c.index)).toEqual([0, 1, 2]);
    // Slashes would otherwise create nested directories and break relative paths.
    expect(channels.map((c) => c.name)).toEqual([
      'dapi',
      'atp1a1_cd45_e_cadherin',
      '18s',
    ]);
    expect(channels.map((c) => c.button_name)).toEqual([
      'DAPI',
      'ATP1A1/CD45/E-Cadherin',
      '18S',
    ]);
    // omero gives labels but no colours, so channels must not all come out white.
    expect(channels.map((c) => c.color)).toEqual([
      [0, 0, 255],
      [0, 255, 0],
      [255, 0, 0],
    ]);
  });

  test('an omero colour wins over the default', () => {
    const src = new SpatialDataImageSource(
      fakeSource([{ label: 'DAPI', color: '00FF88' }])
    );
    expect(src.channels()[0].color).toEqual([0, 255, 136]);
  });

  test('a channel with no label still gets a usable name', () => {
    const src = new SpatialDataImageSource(fakeSource([{}, {}]));
    expect(src.channels().map((c) => c.name)).toEqual([
      'channel_0',
      'channel_1',
    ]);
  });
});

describe('discovering the image element', () => {
  let SpatialDataStore;

  beforeAll(() => {
    const fs = require('fs');
    const path = require('path');
    const source = fs
      .readFileSync(
        path.join(__dirname, '../spatialdata/spatialdata_store.js'),
        'utf8'
      )
      .replace(
        /^import \* as (\w+) from '[^']+';$/gm,
        // Only imageElements() is under test and it uses plain fetch, so zarrita just
        // has to be constructible.
        'const $1 = { FetchStore: function () {}, root: () => ({ resolve: () => ({}) }) };'
      )
      .replace(/^export const /gm, 'const ')
      .replace(/^export class /gm, 'class ');
    const code = `${source}\nmodule.exports = { SpatialDataStore };`;
    const module = { exports: {} };
    new Function('module', 'exports', code)(module, module.exports);
    ({ SpatialDataStore } = module.exports);
  });

  const withRootJson = (body) => {
    global.fetch = jest.fn(async () => ({
      ok: body !== null,
      json: async () => body,
    }));
    return new SpatialDataStore('http://host/s.zarr');
  };

  // Removing the WebP writer also removed `image_element` from the manifest, leaving the
  // reader with nothing to open -- a black square with no channels. SpatialData's
  // consolidated metadata lists every node, so the store can be asked instead.
  test('finds elements from consolidated metadata', async () => {
    const store = withRootJson({
      consolidated_metadata: {
        metadata: {
          images: {},
          'images/morphology_focus': {},
          'images/morphology_focus/s0': {},
          'images/morphology_focus/s1': {},
          'images/he_stain': {},
          points: {},
          'points/transcripts': {},
        },
      },
    });
    // Pyramid levels below the element must not be mistaken for elements.
    expect(await store.imageElements()).toEqual([
      'he_stain',
      'morphology_focus',
    ]);
  });

  test('a store with no images yields nothing rather than guessing', async () => {
    const store = withRootJson({
      consolidated_metadata: {
        metadata: { points: {}, 'points/transcripts': {} },
      },
    });
    expect(await store.imageElements()).toEqual([]);
  });

  test('no consolidated metadata is not an error', async () => {
    expect(await withRootJson({ zarr_format: 3 }).imageElements()).toEqual([]);
  });

  test('a failed fetch is not an error', async () => {
    expect(await withRootJson(null).imageElements()).toEqual([]);
  });
});
