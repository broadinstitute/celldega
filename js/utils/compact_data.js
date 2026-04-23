export const createEmptyTrxCompact = () => ({
  geneIds: new Int32Array(),
  positions: new Float64Array(),
  size: 2,
});

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
    if (left[i]?.name !== right[i]?.name || left[i]?.value !== right[i]?.value) {
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
