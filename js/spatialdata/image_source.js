/**
 * Read images straight from a SpatialData store's OME-Zarr, instead of the WebP pyramid.
 *
 * viv's loader is used rather than raw zarrita because it already handles multiscale
 * resolution, axis order, dtypes and the `omero` channel metadata -- and, contrary to an
 * earlier note in this repo, it understands the NGFF 0.5 layout SpatialData writes:
 *
 *     const ngff_v0_5_or_later = "ome" in unknownAttrs;
 *     const rootAttrs = ngff_v0_5_or_later ? unknownAttrs.ome : unknownAttrs;
 *
 * Only `@vivjs/loaders` is used, never `@vivjs/layers`: the layers peer-require deck.gl
 * ~9.3.3 while celldega is on 9.0.x, and the loader has no deck.gl dependency at all. Tiles
 * are converted to ImageBitmaps here and handed to celldega's existing TileLayer, so
 * nothing about the rendering path changes.
 *
 * The cost is real and worth stating: for Xenium pancreas the canonical uint16 pyramid is
 * 2.9 GB against 25 MB for the WebP one, and a single full-resolution chunk is 16 MB --
 * more than an entire channel's WebP pyramid. Source tiles are windowed to uint8 RGBA
 * before rendering. Fresh SpatialData profiles use this native path by default; WebP
 * remains an optional derived export and the existing DegaFiles path.
 */

import { loadOmeZarr } from '@vivjs/loaders';

/** 8-bit output range. */
const MAX_U8 = 255;

/**
 * Channel colours used when `omero` gives none, which is the usual case -- SpatialData
 * populates channel *labels* from the instrument but not colours. Ordered so a typical
 * Xenium morphology stack (DAPI, membrane, RNA) comes out blue/green/red, matching what
 * the WebP path used.
 */
const DEFAULT_CHANNEL_COLORS = [
  [0, 0, 255],
  [0, 255, 0],
  [255, 0, 0],
  [255, 255, 0],
  [255, 0, 255],
  [0, 255, 255],
];

/**
 * Map deck.gl's tile z (0 at full resolution, negative as you zoom out) onto a viv
 * resolution index (0 = full resolution).
 */
export const zoomToLevel = (z, levelCount) => {
  const level = Math.round(-z);
  // `!(level > 0)` rather than `level < 0` so that -0 (from z === 0) and NaN both
  // normalise to a plain 0.
  if (!(level > 0)) return 0;
  return level > levelCount - 1 ? levelCount - 1 : level;
};

/**
 * The intensity window to stretch to 8 bits.
 *
 * Defaults to the full dtype range rather than a percentile stretch: the viewer applies its
 * own intensity slider on top, and stretching here as well double-applies and blows out the
 * image -- the same mistake the WebP writer originally made.
 */
export const defaultWindow = (channel, dtype = 'Uint16') => {
  const start = channel?.window?.start;
  const end = channel?.window?.end;
  if (Number.isFinite(start) && Number.isFinite(end) && end > start) {
    return [start, end];
  }
  return [0, dtype === 'Uint8' ? 255 : 65535];
};

/**
 * Convert one single-channel tile to greyscale RGBA.
 *
 * Left grey rather than tinted: `create_render_tile_sublayers` applies the channel colour
 * afterwards, exactly as it does for WebP tiles, so tinting here would double-apply it.
 *
 * Kept free of DOM types so it can be tested directly; the caller wraps the result in an
 * ImageData.
 */
export const tileToRgba = (data, width, height, [lo, hi]) => {
  const rgba = new Uint8ClampedArray(width * height * 4);
  const span = hi - lo || 1;
  const scale = MAX_U8 / span;

  for (let i = 0; i < data.length; i += 1) {
    let v = (data[i] - lo) * scale;
    if (v < 0) v = 0;
    else if (v > MAX_U8) v = MAX_U8;
    const o = i * 4;
    rgba[o] = v;
    rgba[o + 1] = v;
    rgba[o + 2] = v;
    rgba[o + 3] = MAX_U8;
  }

  return rgba;
};

const hexToRgbTriple = (hex) => {
  if (typeof hex !== 'string') return null;
  const clean = hex.replace('#', '');
  if (clean.length !== 6) return null;
  return [
    parseInt(clean.slice(0, 2), 16),
    parseInt(clean.slice(2, 4), 16),
    parseInt(clean.slice(4, 6), 16),
  ];
};

export class SpatialDataImageSource {
  constructor(source) {
    this.source = source;
    this.levels = source.data;
    this.base = source.data[0];
  }

  /**
   * @param {string} storeUrl - URL of the .zarr root
   * @param {string} element - image element name, e.g. "morphology_focus"
   */
  static async open(storeUrl, element) {
    const url = `${String(storeUrl).replace(/\/+$/, '')}/images/${element}`;
    const source = await loadOmeZarr(url, { type: 'multiscales' });
    return new SpatialDataImageSource(source);
  }

  /** Full-resolution pixel dimensions, matching what the manifest calls image_dimensions. */
  get dimensions() {
    const { shape, labels } = this.base;
    const width = shape[labels.indexOf('x')];
    const height = shape[labels.indexOf('y')];
    return { width, height };
  }

  /** deck.gl tile size, taken from the chunking rather than assumed. */
  get tileSize() {
    return this.base.tileSize;
  }

  /** Deepest usable zoom, in the same sign convention as the WebP pyramid manifest. */
  get maxPyramidZoom() {
    return this.levels.length - 1;
  }

  /**
   * Channel descriptors in the shape `image_info` uses, so the existing UI can consume them
   * without knowing where they came from. Names come from `omero`, which SpatialData
   * populates from the Xenium channel names -- exactly what the profile writes by hand.
   */
  channels() {
    const omero = this.source.metadata?.omero;
    const { labels } = this.base;
    const count = this.base.shape[labels.indexOf('c')] ?? 1;

    return Array.from({ length: count }, (_, i) => {
      const channel = omero?.channels?.[i];
      const label = channel?.label ?? `channel_${i}`;
      return {
        name: label
          .toLowerCase()
          .replace(/[^a-z0-9]+/g, '_')
          .replace(/^_|_$/g, ''),
        button_name: label,
        color:
          hexToRgbTriple(channel?.color) ??
          DEFAULT_CHANNEL_COLORS[i % DEFAULT_CHANNEL_COLORS.length],
        index: i,
        window: defaultWindow(channel, this.base.dtype),
      };
    });
  }

  /**
   * A `getTileData` for deck.gl's TileLayer, matching the signature the WebP path uses.
   *
   * Returns an ImageBitmap, which BitmapLayer accepts directly, so the sublayer renderer
   * needs no changes.
   */
  makeGetTileData(channelIndex, window) {
    const { levels } = this;
    const intensity = window ?? this.channels()[channelIndex].window;

    return async ({ index, signal }) => {
      const { x, y, z } = index;
      const level = zoomToLevel(z, levels.length);

      const tile = await levels[level].getTile({
        x,
        y,
        selection: { c: channelIndex },
        signal,
      });
      if (!tile) return null;

      const rgba = tileToRgba(tile.data, tile.width, tile.height, intensity);
      return createImageBitmap(new ImageData(rgba, tile.width, tile.height));
    };
  }
}
