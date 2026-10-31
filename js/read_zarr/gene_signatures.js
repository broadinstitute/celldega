import * as zarrita from 'zarrita';

import { fetch_with_retry } from './anndata_zarr';

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
  const [groups, genes, matrix, metadata] = await Promise.all([
    index('obs'),
    index('var'),
    node('X'),
    read('uns/viewport_signature'),
  ]);
  const meta = JSON.parse(metadata);
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
