export const createEmptyTrxCompact = () => ({
  geneIds: new Int32Array(),
  positions: new Float64Array(),
  size: 2,
});

/** Visit transcript coordinates in display space for either profile encoding. */
export const forEachTrxCoordinate = (compact, visit) => {
  if (Array.isArray(compact?.coordinateChunks)) {
    const matrix = compact.displayTransform?.affine_matrix;
    const [a = 1, b = 0, c = 0] = matrix?.[0] || [];
    const [d = 0, e = 1, f = 0] = matrix?.[1] || [];
    for (const chunk of compact.coordinateChunks) {
      for (let i = 0; i < chunk.length; i += 1) {
        const x = chunk.x[i];
        const y = chunk.y[i];
        visit(a * x + b * y + c, d * x + e * y + f, chunk.rowOffset + i);
      }
    }
    return;
  }

  const stride = compact?.size || 2;
  for (let i = 0; i < (compact?.geneIds?.length || 0); i += 1) {
    visit(compact.positions[i * stride], compact.positions[i * stride + 1], i);
  }
};

export const createEmptyCellCompact = () => ({
  categoryIds: new Int32Array(),
  categoryNames: [],
  positions: new Float64Array(),
  size: 2,
});

export const makeVisibleTileKey = (tiles) =>
  tiles.map(({ tileX, tileY }) => `${tileX}:${tileY}`).join('|');

export const areBarDataEqual = (left = [], right = []) => {
  if (left === right) {
    return true;
  }

  if (!Array.isArray(left) || !Array.isArray(right)) {
    return false;
  }

  if (left.length !== right.length) {
    return false;
  }

  for (let i = 0; i < left.length; i++) {
    if (
      left[i]?.name !== right[i]?.name ||
      left[i]?.value !== right[i]?.value
    ) {
      return false;
    }
  }

  return true;
};

export const buildCellCompactData = (
  cellNames,
  positions,
  size,
  dictCellCats
) => {
  if (!Array.isArray(cellNames) || cellNames.length === 0) {
    return createEmptyCellCompact();
  }

  const safeSize = size || 2;
  const safePositions =
    positions && positions.length >= cellNames.length * safeSize
      ? positions
      : new Float64Array(cellNames.length * safeSize);

  const categoryIdByName = new Map();
  const categoryNames = [];
  const categoryIds = new Int32Array(cellNames.length);

  for (let i = 0; i < cellNames.length; i++) {
    const categoryName = dictCellCats[cellNames[i]] ?? 'N.A.';
    let categoryId = categoryIdByName.get(categoryName);

    if (categoryId === undefined) {
      categoryId = categoryNames.length;
      categoryIdByName.set(categoryName, categoryId);
      categoryNames.push(categoryName);
    }

    categoryIds[i] = categoryId;
  }

  return {
    categoryIds,
    categoryNames,
    positions: safePositions,
    size: safeSize,
  };
};
