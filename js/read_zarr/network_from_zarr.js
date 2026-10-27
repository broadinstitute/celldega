import * as zarrita from 'zarrita';

/**
 * Read a clustered Matrix saved with Python's `Matrix.write_zarr` into the
 * `network` object `matrix_viz` renders (the same object `networkFromDegaFiles`
 * builds from parquet).
 *
 * The store is AnnData Zarr with the Clustergram's columns as obs and its rows
 * as var. Dendrogram orders are `obsm`/`varm["celldega_nodes"]`; linkages, views
 * packed into five arrays, and a JSON document with colors, attributes, and
 * entities are in `uns/celldega`.
 */

const FORMAT = 'celldega.matrix';
const SUPPORTED_VERSION = 1;
const NODES_KEY = 'celldega_nodes';
const VIEW_KEYS = [
  'row_indices',
  'row_clust',
  'col_clust',
  'row_linkage',
  'col_linkage',
];

// zarrita returns int64 as BigInt64Array; the viz expects plain numbers.
const numbers = (data) => Array.from(data, Number);

/** A 2-D chunk as an array of row arrays, honoring the chunk's strides. */
const rows_of = ({ data, shape, stride }) => {
  const [n_rows, n_cols] = shape;
  return Array.from({ length: n_rows }, (_, i) =>
    Array.from({ length: n_cols }, (__, j) =>
      Number(data[i * stride[0] + j * stride[1]])
    )
  );
};

/** X and layers are (columns, rows); the viz wants mat[row][col], NaN as 0. */
const transposed_rows_of = ({ data, shape, stride }) => {
  const [n_obs, n_vars] = shape;
  return Array.from({ length: n_vars }, (_, r) =>
    Array.from({ length: n_obs }, (__, c) => {
      const value = Number(data[c * stride[0] + r * stride[1]]);
      return Number.isFinite(value) ? value : 0;
    })
  );
};

/** Slice view `i` out of the five packed view arrays. */
const unpack_views = (descriptions, packed) => {
  if (!descriptions.length) return [];
  const [row_indices, row_clust, col_clust, row_linkage, col_linkage] = packed;
  const n_rows = row_clust.shape[1];
  const n_cols = col_clust.shape[1];
  let row_start = 0;
  return descriptions.map((description, i) => {
    const k = Number(description.n_rows);
    // Each earlier view contributes k - 1 rows to the concatenated linkage.
    const link_start = row_start - i;
    const view = {
      row_indices: numbers(row_indices.data.subarray(row_start, row_start + k)),
      row_clust: numbers(row_clust.data.subarray(i * n_rows, (i + 1) * n_rows)),
      col_clust: numbers(col_clust.data.subarray(i * n_cols, (i + 1) * n_cols)),
      row_linkage: rows_of({
        data: row_linkage.data.subarray(
          link_start * 4,
          (link_start + k - 1) * 4
        ),
        shape: [k - 1, 4],
        stride: [4, 1],
      }),
      col_linkage: rows_of({
        data: col_linkage.data.subarray(
          i * (n_cols - 1) * 4,
          (i + 1) * (n_cols - 1) * 4
        ),
        shape: [n_cols - 1, 4],
        stride: [4, 1],
      }),
      // view_type, level, level_unit, n_rows
      ...description,
    };
    row_start += k;
    return view;
  });
};

/**
 * Build a reader around a zarrita module, so tests can pass an in-memory one.
 *
 * @param {object} zarr - The zarrita module (or a compatible stand-in).
 * @returns {function(string|URL|object, {fetchOptions?: object}=): Promise<object>}
 */
export const makeNetworkFromZarr = (zarr) => {
  const open_store = (url, fetchOptions) => {
    // Drop trailing slashes with a scan rather than /\/+$/, which backtracks
    // quadratically on long runs of '/'.
    let href = String(url);
    let end = href.length;
    while (end > 0 && href[end - 1] === '/') end -= 1;
    href = href.slice(0, end);
    const store = new zarr.FetchStore(href, {
      fetch: (request) => fetch(new Request(request, fetchOptions)),
    });
    // AnnData consolidates metadata, so one request covers every node.
    return zarr.withMaybeConsolidatedMetadata(store, { format: ['v3', 'v2'] });
  };

  return async (url_or_store, { fetchOptions = {} } = {}) => {
    // Anything with a `get` method is already a zarrita store; otherwise a URL.
    const store =
      typeof url_or_store?.get === 'function'
        ? url_or_store
        : await open_store(url_or_store, fetchOptions);
    const root = zarr.root(store);

    // zarrita's auto-detection probes v2 before v3; pin whichever opens first.
    let opener = null;
    const node = async (path, kind) => {
      const location = root.resolve(path);
      if (opener) return opener(location, { kind });
      try {
        const opened = await zarr.open.v3(location, { kind });
        opener = zarr.open.v3;
        return opened;
      } catch {
        const opened = await zarr.open.v2(location, { kind });
        opener = zarr.open.v2;
        return opened;
      }
    };
    const read = async (path) => {
      const array = await node(path, 'array');
      // zarrita cannot read zero-size arrays, e.g. the linkage of a 1-row matrix.
      if (array.shape.includes(0)) {
        return {
          data: [],
          shape: array.shape,
          stride: array.shape.map(() => 0),
        };
      }
      return zarr.get(array);
    };

    const meta = JSON.parse(await read('uns/celldega/meta_json'));
    if (meta.format !== FORMAT || Number(meta.version) > SUPPORTED_VERSION) {
      throw new Error(
        `[networkFromZarr] unsupported store: ${meta.format} v${meta.version}`
      );
    }

    const read_index = async (path) => {
      const group = await node(path, 'group');
      const index = await read(`${path}/${group.attrs._index ?? '_index'}`);
      return Array.from(index.data, String);
    };
    const read_nodes = async (axis_path, nodes_path) => {
      const [names, group] = await Promise.all([
        read_index(axis_path),
        node(nodes_path, 'group'),
      ]);
      const columns = group.attrs['column-order'] ?? [];
      const values = await Promise.all(
        columns.map((column) => read(`${nodes_path}/${column}`))
      );
      return names.map((name, i) => {
        const record = { name };
        columns.forEach((column, k) => {
          const value = values[k].data[i];
          record[column] = column.startsWith('cat-')
            ? String(value)
            : Number(value);
        });
        return record;
      });
    };

    const [X, size, row_nodes, col_nodes, row_link, col_link, packed] =
      await Promise.all([
        read('X'),
        meta.has_size_matrix ? read('layers/size') : null,
        read_nodes('var', `varm/${NODES_KEY}`),
        read_nodes('obs', `obsm/${NODES_KEY}`),
        read('uns/celldega/linkage/row'),
        read('uns/celldega/linkage/col'),
        meta.views.length
          ? Promise.all(
              VIEW_KEYS.map((key) => read(`uns/celldega/views/${key}`))
            )
          : [],
      ]);

    const network = {
      // name, *_attr_maxabs, cat_colors, matrix_colors, global_cat_colors, links
      ...meta.viz,
      row_attr: meta.row_attr,
      col_attr: meta.col_attr,
      row_cats: meta.row_cats,
      col_cats: meta.col_cats,
      row_entity: meta.row_entity,
      col_entity: meta.col_entity,
      mat: transposed_rows_of(X),
      row_nodes,
      col_nodes,
      linkage: { row: rows_of(row_link), col: rows_of(col_link) },
      // Plain arrays: ini_rank_views skips views built from typed arrays.
      views: unpack_views(meta.views, packed),
    };
    if (size) network.size_mat = transposed_rows_of(size);
    return network;
  };
};

/**
 * Read a clustered Matrix Zarr store from a URL into a Clustergram `network`.
 *
 * @param {string|URL} url - URL of the `.zarr` store.
 * @param {{fetchOptions?: object}} [options] - Options passed to every fetch.
 * @returns {Promise<object>} The network object for `matrix_viz`.
 */
export const networkFromZarr = makeNetworkFromZarr(zarrita);
