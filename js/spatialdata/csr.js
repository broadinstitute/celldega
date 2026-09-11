/**
 * Gene-major reads out of a cell-major (CSR) expression matrix.
 *
 * Transposing to CSC up front would cost a second copy of the matrix in memory -- 266 MB
 * for Xenium Prime skin. It is not needed: CSR column indices are sorted within each row,
 * so one gene can be pulled with a binary search per cell. For skin that is
 * 112,551 x log2(296) ~= 0.9 M comparisons rather than a 33 M-element transpose.
 */

/**
 * Binary search for `target` in `indices[lo, hi)`, which must be ascending.
 * @returns {number} index into `indices`, or -1
 */
const searchRow = (indices, lo, hi, target) => {
  let low = lo;
  let high = hi - 1;
  while (low <= high) {
    const mid = (low + high) >>> 1;
    const value = indices[mid];
    if (value === target) return mid;
    if (value < target) low = mid + 1;
    else high = mid - 1;
  }
  return -1;
};

/**
 * Expression of a single gene across every cell, including the zeros.
 *
 * @param {{data, indices, indptr, shape}} csr
 * @param {number} geneIndex - column index, i.e. position in `var`
 * @returns {Float32Array} one value per cell, in `obs` order
 */
export const geneColumn = (csr, geneIndex) => {
  const { data, indices, indptr, shape } = csr;
  const nCells = shape[0];
  const out = new Float32Array(nCells);

  for (let cell = 0; cell < nCells; cell += 1) {
    const start = indptr[cell];
    const end = indptr[cell + 1];
    if (end > start) {
      const hit = searchRow(indices, start, end, geneIndex);
      if (hit !== -1) out[cell] = data[hit];
    }
  }

  return out;
};

/**
 * The non-zero entries of one gene's column.
 *
 * The CBG Parquet stores only non-zeros, and the viewer's expression path expects the same,
 * so this avoids materialising a dense array per gene.
 *
 * @param {{data, indices, indptr, shape}} csr
 * @param {number} geneIndex
 * @returns {{cellIds: Uint32Array, values: Float32Array}} cellIds are positions in `obs`
 */
export const geneColumnSparse = (csr, geneIndex) => {
  const { data, indices, indptr, shape } = csr;
  const nCells = shape[0];

  // Two passes to size the output exactly; counting is far cheaper than growing an array.
  let count = 0;
  for (let cell = 0; cell < nCells; cell += 1) {
    const start = indptr[cell];
    const end = indptr[cell + 1];
    if (end > start && searchRow(indices, start, end, geneIndex) !== -1)
      count += 1;
  }

  const cellIds = new Uint32Array(count);
  const values = new Float32Array(count);
  let out = 0;
  for (let cell = 0; cell < nCells; cell += 1) {
    const start = indptr[cell];
    const end = indptr[cell + 1];
    if (end > start) {
      const hit = searchRow(indices, start, end, geneIndex);
      if (hit !== -1) {
        cellIds[out] = cell;
        values[out] = data[hit];
        out += 1;
      }
    }
  }

  return { cellIds, values };
};

/**
 * Per-gene summary statistics, matching the columns of DegaFiles' `meta_gene.parquet`.
 *
 * One pass over the non-zeros. Zeros are included in `mean` and `std` (they are real
 * measurements, not missing data), so `std` is the population standard deviation over all
 * cells. `nonZero` is the *fraction* of cells with a non-zero value, which is what
 * `celldega.pre` writes in the `non-zero` column.
 *
 * @param {{data, indices, indptr, shape}} csr
 * @returns {{mean: Float64Array, std: Float64Array, max: Float64Array, nonZero: Float64Array}}
 */
export const geneStats = (csr) => {
  const { data, indices, indptr, shape } = csr;
  const [nCells, nGenes] = shape;

  const sum = new Float64Array(nGenes);
  const sumSq = new Float64Array(nGenes);
  const max = new Float64Array(nGenes);
  const count = new Float64Array(nGenes);

  const nnz = indptr[nCells];
  for (let k = 0; k < nnz; k += 1) {
    const gene = indices[k];
    const value = data[k];
    sum[gene] += value;
    sumSq[gene] += value * value;
    if (value > max[gene]) max[gene] = value;
    count[gene] += 1;
  }

  const mean = new Float64Array(nGenes);
  const std = new Float64Array(nGenes);
  const nonZero = new Float64Array(nGenes);

  for (let g = 0; g < nGenes; g += 1) {
    const m = sum[g] / nCells;
    mean[g] = m;
    // Var[x] = E[x^2] - E[x]^2, with the zeros contributing to the denominator only.
    const variance = Math.max(0, sumSq[g] / nCells - m * m);
    std[g] = Math.sqrt(variance);
    nonZero[g] = count[g] / nCells;
  }

  return { mean, std, max, nonZero };
};
