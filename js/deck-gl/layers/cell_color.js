export const CELL_COLOR_SIZE = 4;

// In UMAP views, cells outside a selection stay as a faint backdrop so the
// selected cells keep the context of the whole embedding. Mid-gray reads on
// both the black canvas and a white page.
export const DIMMED_CELL_COLOR = [128, 128, 128, 16];

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

/**
 * @param {object} cats
 * @param {Set<string>} [highlighted_cells]
 * @param {object} [options]
 * @param {boolean} [options.cluster_colors] - Cluster colors even with genes
 *   selected (intermediate zoom with transcripts forced, see trx_handle.js).
 * @param {boolean} [options.dim_unselected] - Draw cells outside the selected
 *   clusters or highlighted cells in DIMMED_CELL_COLOR instead of hiding them.
 */
export const getCellColorContext = (
  cats,
  highlighted_cells = new Set(),
  { cluster_colors = false, dim_unselected = false } = {}
) => {
  const highlightedCells = highlighted_cells ?? new Set();
  const selectedCats = Array.isArray(cats.selected_cats)
    ? cats.selected_cats
    : [];
  const colorDict = cats.color_dict_cluster || {};
  const isGeneMode = !is_cluster_color_mode(cats);
  // With genes selected, selected_cats holds the genes; only its cluster
  // categories filter cells.
  const clusterFilter = isGeneMode
    ? selectedCats.filter((cat) =>
        Object.prototype.hasOwnProperty.call(colorDict, String(cat))
      )
    : selectedCats;
  const isClusterMode = !isGeneMode || cluster_colors;

  return {
    cats,
    cellNames: cats.cell_names_array || [],
    highlightedCells,
    hasHighlights: highlightedCells.size > 0,
    clusterFilter,
    colorDict,
    isClusterMode,
    hasClusterFilter: !isClusterMode && clusterFilter.length > 0,
    dimUnselected: dim_unselected,
  };
};

export const getVizCellColorContext = (viz_state) => {
  const isUmap = Boolean(viz_state.obs_store?.umap_state?.get());
  return getCellColorContext(viz_state.cats, viz_state.highlighted_cells, {
    cluster_colors: Boolean(viz_state.trx_force_shown) && !isUmap,
    dim_unselected: isUmap,
  });
};

const hasClusterColor = (context, index) =>
  Array.isArray(context.colorDict[String(context.cats.cell_cats?.[index])]);

// True when highlighted cells or selected clusters leave this cell out.
const isOutsideSelection = (context, index) => {
  const {
    cats,
    cellNames,
    highlightedCells,
    hasHighlights,
    clusterFilter,
    isClusterMode,
    hasClusterFilter,
  } = context;

  if (hasHighlights) {
    return !highlightedCells.has(cellNames[index]);
  }

  const isFiltering = isClusterMode
    ? clusterFilter.length > 0
    : hasClusterFilter;
  return isFiltering && !isSelectedCat(clusterFilter, cats.cell_cats?.[index]);
};

// Dimmed cells are the ones a selection leaves out; cells without a cluster
// color are not part of the cluster coloring, so they stay hidden.
const isDimmedCell = (context, index) =>
  context.dimUnselected &&
  isOutsideSelection(context, index) &&
  (!context.isClusterMode || hasClusterColor(context, index));

export const isCellVisible = (context, index) => {
  if (isOutsideSelection(context, index)) {
    return isDimmedCell(context, index);
  }

  if (context.hasHighlights) {
    return true;
  }

  if (context.isClusterMode) {
    return hasClusterColor(context, index);
  }

  return toByte(context.cats.cell_exp_array?.[index]) > 0;
};

export const writeCellColor = (context, index, colors, offset) => {
  const { cats, colorDict, hasHighlights, isClusterMode } = context;

  if (isOutsideSelection(context, index)) {
    if (isDimmedCell(context, index)) {
      setColor(colors, offset, ...DIMMED_CELL_COLOR);
    } else {
      setColor(colors, offset, 0, 0, 0, 0);
    }
    return;
  }

  if (hasHighlights) {
    setColor(colors, offset, 0, 0, 255, 255);
    return;
  }

  if (isClusterMode) {
    const instColor = colorDict[String(cats.cell_cats?.[index])];
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
