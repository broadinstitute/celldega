/**
 * Read an AnnData table out of a SpatialData Zarr store with zarrita.
 *
 * SpatialData writes Zarr v3 with zstd-compressed arrays and `vlen-utf8` strings; zarrita
 * handles all of that without codec registration. What it does not know about is AnnData's
 * encoding conventions, which is what this module adds:
 *
 *   dataframe   group, `_index` names the index array, `column-order` lists the rest
 *   categorical group of `codes` (integer) + `categories` (values)
 *   csr_matrix  group of `data` / `indices` / `indptr`, with `shape` in the attributes
 *
 * Everything here is read-only and lazy: nothing is fetched until asked for, and each
 * array is fetched at most once.
 */

import * as zarr from 'zarrita';

const DEFAULT_TABLE = 'table';

/** AnnData encodes a missing/absent category as -1 in `codes`. */
const CATEGORY_NA = -1;

const IDENTITY = { scale: [1, 1], translation: [0, 0] };

/**
 * Reduce one NGFF coordinate transformation to the scale/translation acting on x and y.
 *
 * Only the forms SpatialData actually emits for points and shapes are handled. An `affine`
 * with rotation or shear cannot be expressed this way, so it raises rather than silently
 * dropping the rotation and putting cells in the wrong place.
 *
 * @param {object} transform
 * @param {string[]} axes - the element's axis names, e.g. ["x", "y"] or ["x", "y", "z"]
 */
export const reduceTransform = (transform, axes = ['x', 'y']) => {
  if (!transform || transform.type === 'identity') return IDENTITY;

  const xi = axes.indexOf('x');
  const yi = axes.indexOf('y');
  const pick = (values, fallback) =>
    Array.isArray(values)
      ? [values[xi] ?? fallback, values[yi] ?? fallback]
      : [fallback, fallback];

  switch (transform.type) {
    case 'scale':
      return { scale: pick(transform.scale, 1), translation: [0, 0] };

    case 'translation':
      return { scale: [1, 1], translation: pick(transform.translation, 0) };

    case 'sequence': {
      // Applied in order: p -> s1*p + t1 -> s2*(s1*p + t1) + t2
      let acc = IDENTITY;
      for (const step of transform.transformations ?? []) {
        const next = reduceTransform(step, axes);
        acc = {
          scale: [acc.scale[0] * next.scale[0], acc.scale[1] * next.scale[1]],
          translation: [
            acc.translation[0] * next.scale[0] + next.translation[0],
            acc.translation[1] * next.scale[1] + next.translation[1],
          ],
        };
      }
      return acc;
    }

    default:
      throw new Error(
        `[SpatialDataStore] coordinate transformation "${transform.type}" is not supported. ` +
          `Only identity, scale, translation and sequences of those can be reduced to a ` +
          `scale and translation.`
      );
  }
};

export class SpatialDataStore {
  /**
   * @param {string} url - URL of the .zarr store root (not the table, not the profile dir)
   * @param {object} [opts]
   * @param {string} [opts.table] - name under `tables/`, defaults to "table"
   */
  constructor(url, { table = DEFAULT_TABLE } = {}) {
    this.url = String(url).replace(/\/+$/, '');
    this.tableName = table;
    this.root = zarr.root(new zarr.FetchStore(this.url));
    this._cache = new Map();
    // Set on the first successful open; see _openNode.
    this._opener = null;
  }

  _once(key, fn) {
    if (!this._cache.has(key)) {
      // Cache the promise, not the value, so concurrent callers share one fetch.
      this._cache.set(key, fn());
    }
    return this._cache.get(key);
  }

  _tablePath(...parts) {
    return ['tables', this.tableName, ...parts].join('/');
  }

  /**
   * Open a node, remembering which Zarr version this store speaks.
   *
   * zarrita's auto-detection probes for v2 metadata first, so every node costs two 404s
   * (`.zattrs`, `.zgroup`) before the v3 `zarr.json` succeeds -- three requests instead of
   * one, and a console full of red herrings. Trying v3 first and caching the winner keeps
   * v2 stores working while making v3 stores quiet.
   */
  async _openNode(path, opts) {
    const location = this.root.resolve(path);
    if (this._opener) return this._opener(location, opts);

    try {
      const node = await zarr.open.v3(location, opts);
      this._opener = zarr.open.v3;
      return node;
    } catch {
      // Either a v2 store or a genuinely absent node; auto-detection tells them apart.
      const node = await zarr.open(location, opts);
      this._opener = zarr.open;
      return node;
    }
  }

  async _openGroup(path) {
    return this._openNode(path, { kind: 'group' });
  }

  async _openArray(path) {
    return this._openNode(path, { kind: 'array' });
  }

  /** Read a whole array as a flat typed array (or string array). */
  async _readArray(path) {
    const arr = await this._openArray(path);
    const chunk = await zarr.get(arr);
    return chunk.data;
  }

  // ---------------------------------------------------------------- var / obs

  /**
   * Decode one column of an AnnData dataframe group, following the `encoding-type`
   * attribute. Categoricals come back as the decoded string values, not codes.
   */
  async _readDataFrameColumn(groupPath, column) {
    // `column-order` already lists what exists, so an absent column is answered without a
    // request. Without this, an optional column like var["color"] costs a 404 every load.
    const group = await this._openGroup(groupPath);
    const known = group.attrs?.['column-order'];
    const indexName = group.attrs?._index ?? '_index';
    if (
      Array.isArray(known) &&
      !known.includes(column) &&
      column !== indexName
    ) {
      return null;
    }

    const path = `${groupPath}/${column}`;
    let node;
    try {
      node = await this._openNode(path);
    } catch {
      return null;
    }

    const encoding = node.attrs?.['encoding-type'];

    if (encoding === 'categorical') {
      const [codes, categories] = await Promise.all([
        this._readArray(`${path}/codes`),
        this._readArray(`${path}/categories`),
      ]);
      const out = new Array(codes.length);
      for (let i = 0; i < codes.length; i += 1) {
        const code = Number(codes[i]);
        out[i] = code === CATEGORY_NA ? null : categories[code];
      }
      return out;
    }

    if (node.kind === 'group') {
      // Nullable integer/boolean are stored as `values` + `mask`.
      const [values, mask] = await Promise.all([
        this._readArray(`${path}/values`),
        this._readArray(`${path}/mask`).catch(() => null),
      ]);
      if (!mask) return values;
      const out = new Array(values.length);
      for (let i = 0; i < values.length; i += 1) {
        out[i] = mask[i] ? null : values[i];
      }
      return out;
    }

    return this._readArray(path);
  }

  /**
   * Read a categorical while retaining its stored category order.
   *
   * Decoded cell values alone are insufficient for Scanpy palettes: colors in
   * `uns["<column>_colors"]` align with the categorical's categories, including
   * unused categories, rather than sorted observed values.
   */
  async _readCategoricalDataFrameColumn(groupPath, column) {
    const path = `${groupPath}/${column}`;
    let node;
    try {
      node = await this._openNode(path);
    } catch {
      return null;
    }
    if (node.attrs?.['encoding-type'] !== 'categorical') return null;

    const [codes, rawCategories] = await Promise.all([
      this._readArray(`${path}/codes`),
      this._readArray(`${path}/categories`),
    ]);
    const categories = Array.from(rawCategories, (v) => String(v));
    const values = new Array(codes.length);
    for (let i = 0; i < codes.length; i += 1) {
      const code = Number(codes[i]);
      values[i] = code === CATEGORY_NA ? null : categories[code];
    }
    return { values, categories, codes };
  }

  /** Names of the columns in an AnnData dataframe group, index excluded. */
  async _dataFrameColumns(groupPath) {
    const group = await this._openGroup(groupPath);
    const order = group.attrs?.['column-order'];
    return Array.isArray(order) ? order : [];
  }

  /** Values of an AnnData dataframe's index. */
  async _dataFrameIndex(groupPath) {
    const group = await this._openGroup(groupPath);
    const indexName = group.attrs?._index ?? '_index';
    const values = await this._readArray(`${groupPath}/${indexName}`);
    return Array.from(values, (v) => String(v));
  }

  /** Gene names, in `var` order — this is the order `feature_code` indexes into. */
  async geneNames() {
    return this._once('geneNames', () =>
      this._dataFrameIndex(this._tablePath('var'))
    );
  }

  /** Cell names, in `obs` order — this is the order `X` rows and `obsm` rows follow. */
  async cellNames() {
    return this._once('cellNames', () =>
      this._dataFrameIndex(this._tablePath('obs'))
    );
  }

  async varColumns() {
    return this._dataFrameColumns(this._tablePath('var'));
  }

  async obsColumns() {
    return this._dataFrameColumns(this._tablePath('obs'));
  }

  /** One `var` column, or null when absent. */
  async varColumn(name) {
    return this._once(`var:${name}`, () =>
      this._readDataFrameColumn(this._tablePath('var'), name)
    );
  }

  /** One `obs` column, or null when absent. */
  async obsColumn(name) {
    return this._once(`obs:${name}`, () =>
      this._readDataFrameColumn(this._tablePath('obs'), name)
    );
  }

  /** A categorical obs column with values and categories in stored order. */
  async obsCategorical(name) {
    return this._once(`obs-categorical:${name}`, () =>
      this._readCategoricalDataFrameColumn(this._tablePath('obs'), name)
    );
  }

  // ------------------------------------------------------------- discovery

  /**
   * Names of the store's image elements.
   *
   * SpatialData writes consolidated metadata at the root, which lists every node, so a
   * client can discover what a store holds without being told. That is what lets the
   * manifest stay silent about images: the store already knows.
   *
   * Returns an empty list when there is no consolidated metadata, rather than guessing.
   *
   * @returns {Promise<string[]>} element names, sorted
   */
  async imageElements() {
    return this._once('imageElements', async () => {
      let root;
      try {
        const response = await fetch(`${this.url}/zarr.json`);
        if (!response.ok) return [];
        root = await response.json();
      } catch {
        return [];
      }

      const nodes = root?.consolidated_metadata?.metadata;
      if (!nodes) return [];

      // Keep `images/<name>`, drop the pyramid levels below it.
      const names = new Set();
      for (const key of Object.keys(nodes)) {
        const parts = key.split('/');
        if (parts.length === 2 && parts[0] === 'images') names.add(parts[1]);
      }
      return [...names].sort();
    });
  }

  // ------------------------------------------------------- coordinate systems

  /**
   * The affine mapping from an element's own axes into a target coordinate system,
   * reduced to the scale and translation acting on x and y.
   *
   * SpatialData records this on each element as NGFF `coordinateTransformations`, which is
   * why the profile's `micron_to_image_transform.csv` is redundant: for Xenium the shapes
   * carry `scale: [4.705882, 4.705882]` (µm -> px) and the image is identity, so "global"
   * *is* display pixel space.
   *
   * @param {string} path - e.g. "shapes/cell_boundaries"
   * @param {string} [target] - output coordinate system name
   * @returns {Promise<{scale: [number, number], translation: [number, number]}>}
   */
  async elementTransform(path, target = 'global') {
    return this._once(`xf:${path}:${target}`, async () => {
      const node = await this._openGroup(path);
      const axes = node.attrs?.axes ?? ['x', 'y'];
      const list = node.attrs?.coordinateTransformations ?? [];
      const chosen = list.find((t) => t?.output?.name === target) ?? list[0];
      return reduceTransform(chosen, axes);
    });
  }

  // -------------------------------------------------------------------- uns

  /**
   * An array under `uns`, or null when absent.
   *
   * Used for `uns["<column>_colors"]`, the scanpy convention for the palette of an `obs`
   * categorical. Absence is expected and not an error.
   */
  async unsArray(name) {
    return this._once(`uns:${name}`, async () => {
      try {
        const values = await this._readArray(this._tablePath('uns', name));
        return Array.from(values, (v) => String(v));
      } catch {
        return null;
      }
    });
  }

  // ------------------------------------------------------------------- obsm

  /**
   * A 2D `obsm` array, flattened row-major.
   * @returns {Promise<{values: ArrayLike<number>, shape: number[]}>}
   */
  async obsm(name) {
    return this._once(`obsm:${name}`, async () => {
      const arr = await this._openArray(this._tablePath('obsm', name));
      const chunk = await zarr.get(arr);
      return { values: chunk.data, shape: arr.shape };
    });
  }

  /** Cell centroids as a flat [x0, y0, x1, y1, ...] Float64Array. */
  async centroids(name = 'spatial') {
    const { values, shape } = await this.obsm(name);
    const [n, dim] = shape;
    if (dim === 2) {
      return values instanceof Float64Array
        ? values
        : Float64Array.from(values);
    }
    // Keep only the first two dimensions of a 3D (or higher) embedding.
    const out = new Float64Array(n * 2);
    for (let i = 0; i < n; i += 1) {
      out[i * 2] = values[i * dim];
      out[i * 2 + 1] = values[i * dim + 1];
    }
    return out;
  }

  // ---------------------------------------------------------------------- X

  /**
   * A single gene's non-zero entries, read from the gene-major (CSC) layer.
   *
   * This is the whole point of the layer: `indptr[g]` and `indptr[g+1]` bound the gene's
   * slice, so only the chunks covering it are fetched -- roughly 6,600 non-zeros for
   * Xenium Prime skin, against 33 M for the whole matrix. Returns null when the store has
   * no CSC layer, and the caller falls back to reading X whole.
   *
   * @param {number} geneIndex - column index, i.e. position in `var`
   * @param {string} [layer]
   * @returns {Promise<{cellIds: Uint32Array, values: Float32Array} | null>}
   */
  async geneFromCscLayer(geneIndex, layer = 'X_csc') {
    const base = this._tablePath('layers', layer);

    const indptr = await this._once(`csc:indptr:${layer}`, async () => {
      const group = await this._openGroup(base).catch(() => null);
      if (!group || group.attrs?.['encoding-type'] !== 'csc_matrix')
        return null;
      return this._readArray(`${base}/indptr`);
    });
    if (!indptr) return null;

    const start = Number(indptr[geneIndex]);
    const end = Number(indptr[geneIndex + 1]);
    if (!(end > start)) {
      return { cellIds: new Uint32Array(0), values: new Float32Array(0) };
    }

    const [dataArr, indicesArr] = await Promise.all([
      this._openArray(`${base}/data`),
      this._openArray(`${base}/indices`),
    ]);
    const [values, cells] = await Promise.all([
      zarr.get(dataArr, [zarr.slice(start, end)]),
      zarr.get(indicesArr, [zarr.slice(start, end)]),
    ]);

    return {
      cellIds: Uint32Array.from(cells.data),
      values: Float32Array.from(values.data),
    };
  }

  /** Per-gene statistics precomputed into `var`, or null when absent. */
  async geneStatistics() {
    return this._once('geneStats', async () => {
      const columns = await this.varColumns();
      const needed = ['mean', 'std', 'max', 'non_zero'];
      if (!needed.every((c) => columns.includes(c))) return null;

      const [mean, std, max, nonZero] = await Promise.all(
        needed.map((c) => this.varColumn(c))
      );
      return { mean, std, max, nonZero };
    });
  }

  /**
   * The expression matrix as CSR (rows = cells, columns = genes).
   *
   * SpatialData/AnnData store `X` cell-major, so reading it whole is the only way to get
   * gene-major access. It is smaller than it sounds -- 4.5 MB for Xenium pancreas and
   * 54.8 MB for Xenium Prime skin on disk -- and once loaded every gene is free.
   *
   * @returns {Promise<{data, indices, indptr, shape: number[]}>}
   */
  async csr() {
    return this._once('X', async () => {
      const group = await this._openGroup(this._tablePath('X'));
      const encoding = group.attrs?.['encoding-type'];
      if (encoding !== 'csr_matrix') {
        throw new Error(
          `[SpatialDataStore] expected X to be csr_matrix, found "${encoding}". ` +
            `Dense and CSC matrices are not supported yet.`
        );
      }
      const [data, indices, indptr] = await Promise.all([
        this._readArray(this._tablePath('X', 'data')),
        this._readArray(this._tablePath('X', 'indices')),
        this._readArray(this._tablePath('X', 'indptr')),
      ]);
      return { data, indices, indptr, shape: group.attrs.shape };
    });
  }
}
