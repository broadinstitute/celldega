/* global require */

// Raster capture helpers (Landscape -> Clerk). Loaded from source like the other
// tests in this folder (no Babel transform): strip `export` and evaluate.
const load_canvas_capture = () => {
  const fs = require('fs');
  const path = require('path');
  const source = fs
    .readFileSync(path.join(__dirname, '../utils/canvas_capture.js'), 'utf8')
    .replace(/^export const /gm, 'const ');
  const module = { exports: {} };
  new Function(
    'module',
    `${source}\nmodule.exports = { downscale_canvas, canvas_to_base64_png, capture_deck };`
  )(module);
  return module.exports;
};

const { canvas_to_base64_png, capture_deck, downscale_canvas } =
  load_canvas_capture();

describe('canvas_capture', () => {
  let drawn;

  beforeEach(() => {
    drawn = [];
    // jsdom has no 2D canvas: record fills and draws, and fake the PNG encoding
    // by size.
    jest
      .spyOn(HTMLCanvasElement.prototype, 'getContext')
      .mockImplementation(() => ({
        fillStyle: '',
        fillRect(x, y, w, h) {
          drawn.push({ fill: this.fillStyle, w, h });
        },
        drawImage: (source, x, y, w, h) => drawn.push({ source, w, h }),
      }));
    jest
      .spyOn(HTMLCanvasElement.prototype, 'toDataURL')
      .mockImplementation(function toDataURL() {
        return `data:image/png;base64,${this.width}x${this.height}`;
      });
  });

  afterEach(() => jest.restoreAllMocks());

  const make_canvas = (width, height) => {
    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;
    return canvas;
  };

  test('downscale_canvas caps the longest side and keeps the aspect ratio', () => {
    const out = downscale_canvas(make_canvas(2000, 1000), 1024);
    expect([out.width, out.height]).toEqual([1024, 512]);
  });

  test('downscale_canvas never upscales', () => {
    const out = downscale_canvas(make_canvas(300, 200), 1024);
    expect([out.width, out.height]).toEqual([300, 200]);
  });

  test('canvas_to_base64_png strips the data URL prefix', () => {
    expect(canvas_to_base64_png(make_canvas(4, 2))).toBe('4x2');
  });

  test('capture_deck redraws before reading, then returns image and thumbnail', () => {
    const order = [];
    const canvas = make_canvas(1600, 800);
    const deck = {
      redraw: (reason) => order.push(`redraw:${reason}`),
      getCanvas: () => {
        order.push('getCanvas');
        return canvas;
      },
    };

    const capture = capture_deck(deck, null, {
      max_size: 800,
      thumb_size: 100,
    });

    expect(order).toEqual(['redraw:raster-capture', 'getCanvas']);
    expect(capture).toEqual({
      png: '800x400',
      thumb: '100x50',
      width: 800,
      height: 400,
    });
    // The WebGL canvas is read once; the thumbnail comes from the 2D copy.
    expect(drawn.filter((d) => d.source === canvas)).toHaveLength(1);
  });

  test('captures sit on white by default; background: null keeps transparency', () => {
    const canvas = make_canvas(400, 200);
    const deck = { getCanvas: () => canvas };
    capture_deck(deck, null, { max_size: 400 });
    // White fills the copy before the WebGL canvas is drawn over it.
    expect(drawn[0]).toEqual({ fill: 'white', w: 400, h: 200 });
    expect(drawn[1].source).toBe(canvas);

    drawn = [];
    capture_deck(deck, null, { max_size: 400, background: '#000' });
    expect(drawn[0].fill).toBe('#000');

    drawn = [];
    capture_deck(deck, null, { max_size: 400, background: null });
    expect(drawn.some((d) => 'fill' in d)).toBe(false);
  });

  test('capture_deck falls back to the root canvas and handles no canvas', () => {
    const root = document.createElement('div');
    expect(capture_deck({}, root)).toBeNull();

    root.appendChild(make_canvas(10, 10));
    expect(capture_deck({}, root)?.png).toBe('10x10');
  });
});
