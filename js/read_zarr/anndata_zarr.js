import * as zarrita from 'zarrita';

/**
 * Read single-cell data for a Chromium Landscape straight from an AnnData Zarr
 * store (`adata.write_zarr(...)`), as an alternative to DegaFiles.
 *
 * Gene expression comes from a CSC matrix: `X` itself, or a layer holding a CSC
 * copy (e.g. `adata.layers["counts_csc"] = adata.layers["counts"].tocsc()`).
 * Column-compressed storage keeps each gene's values contiguous, so one gene is
 * a slice of `data`/`indices` between two `indptr` entries and a browser fetches
 * only the chunks that hold it.
 *
 * Optional `var["mean"]`, `var["max"]`, and `var["color"]` columns provide the
 * per-gene statistics DegaFiles keep in `meta_gene.parquet`. Without `mean`,
 * genes are ranked by the fraction of cells that express them (free from
 * `indptr`); without `max`, it is computed from each gene's values on load.
 *
 * Cell metadata (`cell_attr`), cluster colors (`uns[f"{cluster_attr}_colors"]`),
 * and the UMAP (`obsm["X_umap"]`) come from the store too, unless Python
 * already sent them from an in-memory AnnData.
 */

const MATRIX_ENCODINGS = ['csc_matrix', 'csr_matrix', 'array'];

// The same manifest `pre.make_chromium_from_anndata` writes. Expression is
// keyed by integer cell index (the CSC row indices are obs positions).
const CHROMIUM_PARAMETERS = {
  technology: 'Chromium',
  segmentation_approach: ['default'],
  max_pyramid_zoom: null,
  tile_size: 1,
  image_info: [],
  image_format: '.webp',
  use_int_index: true,
};

// Python's _hsv_to_hex: evenly spaced hues, saturation 0.65, value 0.9.
const hsv_to_hex = (h) => {
  const s = 0.65;
  const v = 0.9;
  const i = Math.floor(h * 6);
  const f = h * 6 - i;
  const p = v * (1 - s);
  const q = v * (1 - s * f);
  const t = v * (1 - s * (1 - f));
  const [r, g, b] = [
    [v, t, p],
    [q, v, p],
    [p, v, t],
    [p, q, v],
    [t, p, v],
    [v, p, q],
  ][i % 6];
  const hex = (x) =>
    Math.floor(x * 255)
      .toString(16)
      .padStart(2, '0');
  return `#${hex(r)}${hex(g)}${hex(b)}`;
};

export const fallback_colors = (n) =>
  Array.from({ length: n }, (_, i) => hsv_to_hex(i / n));

// zarrita returns strings as plain arrays and int64 as BigInt64Array.
const plain_values = (data) =>
  Array.isArray(data)
    ? data.map((value) => (value == null ? value : String(value)))
    : Array.from(data, (value) =>
        typeof value === 'bigint' ? Number(value) : value
      );

const FETCH_ATTEMPTS = 3;

/**
 * Fetch with retries for dropped connections and server errors (5xx), which
 * local servers and hosted stores both produce now and then. Other responses,
 * including 404s for absent nodes, return at once.
 */
export const fetch_with_retry = async (
  request,
  fetchOptions = {},
  { attempts = FETCH_ATTEMPTS, delay_ms = 200, fetch_fn = fetch } = {}
) => {
  for (let attempt = 1; ; attempt += 1) {
    try {
      // eslint-disable-next-line no-await-in-loop
      const response = await fetch_fn(new Request(request, fetchOptions));
      if (response.status < 500 || attempt >= attempts) return response;
    } catch (error) {
      if (attempt >= attempts) throw error;
    }
    // eslint-disable-next-line no-await-in-loop
    await new Promise((resolve) => setTimeout(resolve, delay_ms * attempt));
  }
};

/**
 * Build a reader around a zarrita module, so tests can pass an in-memory one.
 *
 * @param {object} zarr - The zarrita module (or a compatible stand-in).
 * @returns {function(string|URL|object, object=): Promise<object>}
 */
export const make_anndata_zarr_source = (zarr) => {
  const open_store = (url, fetchOptions) => {
    // Drop trailing slashes with a scan rather than a regex, which backtracks
    // quadratically on long runs of '/'.
    let href = String(url);
    let end = href.length;
    while (end > 0 && href[end - 1] === '/') end -= 1;
    href = href.slice(0, end);
    const store = new zarr.FetchStore(href, {
      fetch: (request) => fetch_with_retry(request, fetchOptions),
    });
    // With consolidated metadata (zarr.consolidate_metadata), one request
    // covers every node; without it, each node is fetched as it is opened.
    return zarr.withMaybeConsolidatedMetadata(store, { format: ['v3', 'v2'] });
  };

  return async (
    url_or_store,
    {
      layer = '',
      cell_attr = [],
      cluster_attr = 'leiden',
      fetchOptions = {},
    } = {}
  ) => {
    const label = typeof url_or_store === 'string' ? url_or_store : 'store';
    // Anything with a `get` method is already a zarrita store; otherwise a URL.
    const store =
      typeof url_or_store?.get === 'function'
        ? url_or_store
        : await open_store(url_or_store, fetchOptions);
    const root = zarr.root(store);

    // zarrita's auto-detection probes v2 before v3; pin whichever opens first.
    let opener = null;
    const node = async (path) => {
      const location = root.resolve(path);
      if (opener) return opener(location);
      try {
        const opened = await zarr.open.v3(location);
        opener = zarr.open.v3;
        return opened;
      } catch {
        const opened = await zarr.open.v2(location);
        opener = zarr.open.v2;
        return opened;
      }
    };
    const maybe_node = (path) => node(path).catch(() => null);
    const encoding = (opened) => opened?.attrs?.['encoding-type'];

    const read = async (opened, selection) => {
      // zarrita cannot read zero-size arrays.
      if (opened.shape.includes(0)) return { data: [], shape: opened.shape };
      return selection ? zarr.get(opened, selection) : zarr.get(opened);
    };
    const read_values = async (path) =>
      plain_values((await read(await node(path))).data);

    // A dataframe column: categorical, or a plain (string or numeric) array.
    const read_column = async (axis, name) => {
      const path = `${axis}/${name}`;
      const column = await node(path);
      if (encoding(column) === 'categorical') {
        const [categories, codes] = await Promise.all([
          read_values(`${path}/categories`),
          read_values(`${path}/codes`),
        ]);
        return {
          categories,
          values: codes.map((code) => (code < 0 ? 'nan' : categories[code])),
        };
      }
      if (!column.shape) {
        throw new Error(
          `[anndata_zarr_source] ${path} is a ${encoding(column)} group, which Landscape cannot read`
        );
      }
      return { values: plain_values((await read(column)).data) };
    };

    const read_dataframe = async (axis) => {
      const group = await node(axis);
      return {
        index: await read_values(`${axis}/${group.attrs._index ?? '_index'}`),
        columns: group.attrs['column-order'] ?? [],
      };
    };

    // The CSC matrix to read genes from: `layer` if given, else X if it is
    // CSC, else the store's only CSC layer.
    const find_matrix = async () => {
      if (layer) {
        const path = layer === 'X' ? 'X' : `layers/${layer}`;
        const matrix = await maybe_node(path);
        if (!matrix) {
          throw new Error(`[anndata_zarr_source] ${label} has no ${path}`);
        }
        return { path, matrix };
      }
      const X = await maybe_node('X');
      if (encoding(X) === 'csc_matrix') return { path: 'X', matrix: X };
      const listed =
        typeof store.contents === 'function'
          ? store
              .contents()
              .map((entry) => entry.path.replace(/^\//, ''))
              .filter((path) => /^layers\/[^/]+$/.test(path))
          : [];
      const layers = await Promise.all(
        listed.map(async (path) => ({ path, matrix: await node(path) }))
      );
      const csc = layers.filter(
        ({ matrix }) => encoding(matrix) === 'csc_matrix'
      );
      if (csc.length === 1) return csc[0];
      const hint =
        csc.length > 1
          ? `several CSC layers (${csc.map(({ path }) => path.slice(7)).join(', ')}); pass zarr_layer to choose one`
          : typeof store.contents === 'function'
            ? 'no CSC layer; save one, e.g. adata.layers["counts_csc"] = adata.layers["counts"].tocsc()'
            : 'pass zarr_layer to name the layer holding a CSC copy of the counts, or consolidate the store metadata (zarr.consolidate_metadata) so Celldega can find it';
      throw new Error(
        `[anndata_zarr_source] X in ${label} is ${encoding(X) ?? 'missing'}, not CSC, and the store has ${hint}`
      );
    };

    const [obs, vars, { path: matrix_path, matrix }] = await Promise.all([
      read_dataframe('obs'),
      read_dataframe('var'),
      find_matrix(),
    ]);
    if (encoding(matrix) !== 'csc_matrix') {
      const kind = MATRIX_ENCODINGS.includes(encoding(matrix))
        ? encoding(matrix)
        : 'not a sparse matrix';
      throw new Error(
        `[anndata_zarr_source] ${matrix_path} in ${label} is ${kind}; Landscape needs a CSC copy, e.g. adata.layers["counts_csc"] = adata.layers["counts"].tocsc()`
      );
    }

    const cell_names = obs.index;
    const gene_names = vars.index;
    const n_cells = cell_names.length;
    const [n_obs, n_vars] = (matrix.attrs.shape ?? []).map(Number);
    if (n_obs !== n_cells || n_vars !== gene_names.length) {
      throw new Error(
        `[anndata_zarr_source] ${matrix_path} is ${n_obs} x ${n_vars}, but obs and var have ${n_cells} and ${gene_names.length} entries`
      );
    }

    const var_column = (name) =>
      vars.columns.includes(name)
        ? read_column('var', name).then(({ values }) => values)
        : null;
    const [indptr, data, indices, gene_mean, gene_max, gene_colors] =
      await Promise.all([
        read_values(`${matrix_path}/indptr`),
        node(`${matrix_path}/data`),
        node(`${matrix_path}/indices`),
        var_column('mean'),
        var_column('max'),
        var_column('color'),
      ]);
    const gene_index = new Map(gene_names.map((name, i) => [name, i]));

    const readGeneExpression = async (gene) => {
      const g = gene_index.get(gene);
      const start = indptr[g];
      const stop = indptr[g + 1];
      if (g === undefined || !(stop > start)) {
        return { cell_names: new Int32Array(), cell_exp: new Float64Array() };
      }
      const selection = [zarr.slice(start, stop)];
      const [rows, values] = await Promise.all([
        read(indices, selection),
        read(data, selection),
      ]);
      return {
        // Integer obs positions, matching the manifest's use_int_index.
        cell_names: Int32Array.from(rows.data, Number),
        cell_exp: Float64Array.from(values.data, Number),
      };
    };

    // Cell metadata in the shape `objects_from_parquet` returns:
    // { result: { cell: [values...] }, attr: [names...] }.
    const wanted = [...new Set([...cell_attr, cluster_attr])];
    if (obs.columns.includes('color')) wanted.push('color');
    const attrs = wanted.filter((name) => obs.columns.includes(name));
    const columns = await Promise.all(
      attrs.map((name) => read_column('obs', name))
    );
    const by_cell = (rows) =>
      Object.fromEntries(cell_names.map((name, i) => [name, rows(i)]));
    const meta_cell = attrs.length
      ? {
          result: by_cell((i) => columns.map(({ values }) => values[i])),
          attr: attrs,
        }
      : { result: {}, attr: [] };

    // Clusters in Python's order (value_counts().sort_index()): category order
    // for a categorical, sorted values otherwise.
    let meta_cluster = { result: {}, attr: [] };
    const cluster = columns[attrs.indexOf(cluster_attr)];
    if (cluster) {
      const names =
        cluster.categories ?? [...new Set(cluster.values.map(String))].sort();
      const counts = new Map(names.map((name) => [name, 0]));
      cluster.values.forEach((value) => {
        const key = String(value);
        if (counts.has(key)) counts.set(key, counts.get(key) + 1);
      });
      const color_node = await maybe_node(`uns/${cluster_attr}_colors`);
      const stored = color_node?.shape
        ? plain_values((await read(color_node)).data)
        : [];
      const colors =
        stored.length >= names.length ? stored : fallback_colors(names.length);
      meta_cluster = {
        result: Object.fromEntries(
          names.map((name, i) => [name, [colors[i], counts.get(name)]])
        ),
        attr: ['color', 'count'],
      };
    }

    let umap = null;
    const umap_node = await maybe_node('obsm/X_umap');
    if (umap_node?.shape?.length === 2) {
      const { data: coords, shape, stride } = await read(umap_node);
      const [row_stride, col_stride] = stride ?? [shape[1], 1];
      umap = by_cell((i) => [
        Number(coords[i * row_stride]),
        Number(coords[i * row_stride + col_stride]),
      ]);
    }

    return {
      matrix_path,
      cell_names,
      gene_names,
      // Without var["mean"], rank genes by the fraction of cells expressing them.
      gene_mean:
        gene_mean ??
        gene_names.map(
          (_, g) => (indptr[g + 1] - indptr[g]) / Math.max(n_cells, 1)
        ),
      gene_max,
      gene_colors: gene_colors ?? fallback_colors(gene_names.length),
      meta_cell,
      meta_cluster,
      umap,
      landscape_parameters: { ...CHROMIUM_PARAMETERS },
      cbg_reader: { readGeneExpression },
    };
  };
};

/**
 * Open an AnnData Zarr store for a Chromium Landscape.
 *
 * @param {string|URL} url - URL of the `.zarr` store.
 * @param {{layer?: string, cell_attr?: string[], cluster_attr?: string,
 *   fetchOptions?: object}} [options]
 * @returns {Promise<object>} Cells, genes, metadata, and a gene reader.
 */
export const anndata_zarr_source = make_anndata_zarr_source(zarrita);
