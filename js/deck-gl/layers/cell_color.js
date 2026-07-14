export const CELL_COLOR_SIZE = 4;

export const is_cluster_color_mode = (cats) =>
  !cats.cat || cats.cat === 'cluster';

const isSelectedCat = (selected_cats = [], cat) => {
  const catKey = String(cat);
  return selected_cats.some((selectedCat) => String(selectedCat) === catKey);
};

export const toByte = (value) => {
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue)) {
    return 0;
  }

  return Math.max(0, Math.min(255, Math.round(numericValue)));
};

export const setColor = (colors, offset, r, g, b, a) => {
  colors[offset] = toByte(r);
  colors[offset + 1] = toByte(g);
  colors[offset + 2] = toByte(b);
  colors[offset + 3] = toByte(a);
};

export const getCellColorContext = (cats, highlighted_cells = new Set()) => {
  const highlightedCells = highlighted_cells ?? new Set();
  const selectedCats = Array.isArray(cats.selected_cats)
    ? cats.selected_cats
    : [];
  const colorDict = cats.color_dict_cluster || {};
  const isClusterMode = is_cluster_color_mode(cats);

  return {
    cats,
    cellNames: cats.cell_names_array || [],
    highlightedCells,
    hasHighlights: highlightedCells.size > 0,
    selectedCats,
    colorDict,
    isClusterMode,
    hasClusterFilter:
      !isClusterMode &&
      selectedCats.length > 0 &&
      selectedCats.some((cat) =>
        Object.prototype.hasOwnProperty.call(colorDict, String(cat))
      ),
  };
};

export const getVizCellColorContext = (viz_state) =>
  getCellColorContext(viz_state.cats, viz_state.highlighted_cells);

export const isCellVisible = (context, index) => {
  const {
    cats,
    cellNames,
    highlightedCells,
    hasHighlights,
    selectedCats,
    colorDict,
    isClusterMode,
    hasClusterFilter,
  } = context;

  if (hasHighlights) {
    return highlightedCells.has(cellNames[index]);
  }

  const instCat = cats.cell_cats?.[index];
  if (isClusterMode) {
    return (
      Array.isArray(colorDict[String(instCat)]) &&
      (selectedCats.length === 0 || isSelectedCat(selectedCats, instCat))
    );
  }

  if (hasClusterFilter && !isSelectedCat(selectedCats, instCat)) {
    return false;
  }

  return toByte(cats.cell_exp_array?.[index]) > 0;
};

export const writeCellColor = (context, index, colors, offset) => {
  const {
    cats,
    cellNames,
    highlightedCells,
    hasHighlights,
    colorDict,
    isClusterMode,
  } = context;

  if (hasHighlights) {
    if (highlightedCells.has(cellNames[index])) {
      setColor(colors, offset, 0, 0, 255, 255);
    } else {
      setColor(colors, offset, 0, 0, 0, 0);
    }
    return;
  }

  if (isClusterMode) {
    const instCat = cats.cell_cats?.[index];
    const instColor = colorDict[String(instCat)];
    if (Array.isArray(instColor)) {
      setColor(colors, offset, instColor[0], instColor[1], instColor[2], 255);
    } else {
      setColor(colors, offset, 0, 0, 0, 0);
    }
    return;
  }

  setColor(colors, offset, 255, 0, 0, cats.cell_exp_array?.[index]);
};

const getAccessorIndex = (object, accessorInfo) => {
  if (Number.isInteger(accessorInfo?.index)) {
    return accessorInfo.index;
  }

  if (Number.isInteger(object?.index)) {
    return object.index;
  }

  return Number.isInteger(object) ? object : 0;
};

// transparent to red
export const get_cell_color = (
  cats,
  highlighted_cells,
  object,
  accessorInfo
) => {
  const index = getAccessorIndex(object, accessorInfo);
  const context = getCellColorContext(cats, highlighted_cells);

  if (!isCellVisible(context, index)) {
    return [0, 0, 0, 0];
  }

  const color = [0, 0, 0, 0];
  writeCellColor(context, index, color, 0);
  return color;
};

export const update_cell_color_buffer = (viz_state) => {
  const context = getVizCellColorContext(viz_state);
  const numCells = context.cellNames.length;
  const requiredLength = numCells * CELL_COLOR_SIZE;

  if (
    !viz_state.spatial.cell_colors ||
    viz_state.spatial.cell_colors.length !== requiredLength
  ) {
    viz_state.spatial.cell_colors = new Uint8Array(requiredLength);
  }

  const colors = viz_state.spatial.cell_colors;

  for (let i = 0; i < numCells; i++) {
    const offset = i * CELL_COLOR_SIZE;
    if (isCellVisible(context, i)) {
      writeCellColor(context, i, colors, offset);
    } else {
      setColor(colors, offset, 0, 0, 0, 0);
    }
  }

  return colors;
};
