import * as zarrita from 'zarrita';

import { arrayBufferToArrowTable } from '../read_parquet/arrayBufferToArrowTable';

import { fetch_with_retry } from './anndata_zarr';

const GENE_COLUMNS = ['gene', '__index_level_0__', 'index'];

/**
 * Gene signatures from an Arrow table with genes as rows and one column of
 * means per cell type: what `Landscape(adata_sig=...)` sends, and the layout of
 * DegaFiles' df_sig.parquet. `groupby` and `units` come from the schema's
 * `viewport_signature` metadata, else from `defaults`.
 */
export const gene_signatures_from_table = (table, defaults = {}) => {
  const fields = table.schema.fields.map((field) => field.name);
  const gene_field = GENE_COLUMNS.find((name) => fields.includes(name));
  const stored = table.schema.metadata?.get?.('viewport_signature');
  const meta = { ...defaults, ...(stored ? JSON.parse(stored) : {}) };
  const genes = gene_field
    ? Array.from(table.getChild(gene_field).toArray(), String)
    : [];
  const groups = fields.filter((name) => name !== gene_field);
  if (
    !meta.groupby ||
    !meta.units ||
    !genes.length ||
    !groups.length ||
    new Set(genes).size !== genes.length
  ) {
    throw new Error(
      'Gene signatures need a gene column, unique genes, cell-type columns, and groupby/units metadata.'
    );
  }
  const means = new Map(
    groups.map((group) => {
      const values = Float32Array.from(table.getChild(group).toArray(), Number);
      if (values.some((value) => !Number.isFinite(value) || value < 0)) {
        throw new Error(
          'Gene signatures must contain finite, nonnegative means before z-scoring.'
        );
      }
      return [group, values];
    })
  );
  return { ...meta, genes, means };
};

/** Gene signatures from parquet bytes (a DataView, typed array, or ArrayBuffer). */
export const gene_signatures_from_parquet = async (bytes, defaults) =>
  gene_signatures_from_table(
    await arrayBufferToArrowTable(
      ArrayBuffer.isView(bytes)
        ? bytes.buffer.slice(
            bytes.byteOffset,
            bytes.byteOffset + bytes.byteLength
          )
        : bytes
    ),
    defaults
  );

// Small, dense AnnData: observations are cell types, variables are genes, and
// X holds means before gene-wise z-scoring. Never read the cell-level matrix.
export const make_gene_signatures_source = (zarr) => async (url_or_store) => {
  const store =
    typeof url_or_store?.get === 'function'
      ? url_or_store
      : await zarr.withMaybeConsolidatedMetadata(
          new zarr.FetchStore(String(url_or_store).replace(/\/$/, ''), {
            fetch: (request) => fetch_with_retry(request),
          }),
          { format: ['v3', 'v2'] }
        );
  const root = zarr.root(store);
  let opener;
  const node = async (path) => {
    if (!opener) {
      try {
        await zarr.open.v3(root);
        opener = zarr.open.v3;
      } catch {
        await zarr.open.v2(root);
        opener = zarr.open.v2;
      }
    }
    return opener(root.resolve(path));
  };
  const read = async (path) => zarr.get(await node(path));
  const index = async (axis) => {
    const group = await node(axis);
    return Array.from(
      (await read(`${axis}/${group.attrs._index || '_index'}`)).data,
      String
    );
  };
  // Establish the format before opening arrays concurrently.
  await node('');
  const meta = JSON.parse(await read('uns/viewport_signature'));
  // The estimate reads `meta.layer`, else the mean counts in layers/counts when
  // present (a log1p layer is for z-scored views), else X.
  const matrix_path = meta.layer
    ? `layers/${meta.layer}`
    : await node('layers/counts').then(
        () => 'layers/counts',
        () => 'X'
      );
  const [groups, genes, matrix] = await Promise.all([
    index('obs'),
    index('var'),
    node(matrix_path),
  ]);
  const layer = matrix_path.replace(/^layers\//, '');
  meta.units = meta.layers?.[layer] ?? meta.units;
  if (
    !meta.groupby ||
    !meta.units ||
    matrix.shape?.length !== 2 ||
    matrix.shape[0] !== groups.length ||
    matrix.shape[1] !== genes.length ||
    !groups.length ||
    !genes.length ||
    new Set(groups).size !== groups.length ||
    new Set(genes).size !== genes.length
  ) {
    throw new Error(
      'Gene signatures need unique cell types and genes, dense X, and groupby/units metadata.'
    );
  }
  const { data, stride = [genes.length, 1] } = await zarr.get(matrix);
  const means = new Map(
    groups.map((group, i) => {
      const values = new Float32Array(genes.length);
      for (let j = 0; j < genes.length; j++) {
        const value = Number(data[i * stride[0] + j * stride[1]]);
        if (!Number.isFinite(value) || value < 0) {
          throw new Error(
            'Gene signatures must contain finite, nonnegative means before z-scoring.'
          );
        }
        values[j] = value;
      }
      return [group, values];
    })
  );
  return { ...meta, genes, means };
};

const cache = new Map();
export const gene_signatures_source = (url) => {
  if (!cache.has(url)) {
    const promise = make_gene_signatures_source(zarrita)(url);
    cache.set(url, promise);
    promise.catch(() => cache.delete(url));
    if (cache.size > 4) cache.delete(cache.keys().next().value);
  }
  return cache.get(url);
};
