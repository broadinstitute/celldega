/**
 * Build the Arrow tables Celldega already consumes, from SpatialData/AnnData inputs.
 *
 * Rather than teach every call site about Zarr, this produces tables with exactly the
 * schemas the DegaFiles Parquets have, so `set_meta_gene`, `set_color_dict_gene`,
 * `set_cell_names_array`, `get_scatter_data` and `set_cell_cats` keep working untouched.
 * The only thing that changes is where the bytes came from.
 */

import * as arrow from 'apache-arrow';

const utf8Vector = (values) =>
  arrow.vectorFromArray(
    values.map((v) => (v == null ? null : String(v))),
    new arrow.Utf8()
  );

const float64Vector = (values) =>
  arrow.makeVector(
    values instanceof Float64Array ? values : Float64Array.from(values)
  );

/**
 * A List<Float64> column of fixed-width rows, built from a flat buffer.
 *
 * `get_scatter_data` reaches straight into `getChild('geometry').getChildAt(0)` and reads
 * the values buffer, so this has to be a real List column rather than a struct or a
 * fixed-size list.
 */
const listOfFloat64Vector = (flat, width) => {
  const rows = flat.length / width;
  const valueOffsets = new Int32Array(rows + 1);
  for (let i = 0; i <= rows; i += 1) valueOffsets[i] = i * width;

  const child = arrow.makeData({
    type: new arrow.Float64(),
    length: flat.length,
    data: flat instanceof Float64Array ? flat : Float64Array.from(flat),
  });

  return arrow.makeVector(
    arrow.makeData({
      type: new arrow.List(
        new arrow.Field('element', new arrow.Float64(), true)
      ),
      length: rows,
      nullCount: 0,
      valueOffsets,
      child,
    })
  );
};

const hslToHex = (h, s, l) => {
  const c = (1 - Math.abs(2 * l - 1)) * s;
  const x = c * (1 - Math.abs(((h / 60) % 2) - 1));
  const m = l - c / 2;
  const [r, g, b] =
    h < 60
      ? [c, x, 0]
      : h < 120
        ? [x, c, 0]
        : h < 180
          ? [0, c, x]
          : h < 240
            ? [0, x, c]
            : h < 300
              ? [x, 0, c]
              : [c, 0, x];
  const hex = (v) =>
    Math.round((v + m) * 255)
      .toString(16)
      .padStart(2, '0');
  return `#${hex(r)}${hex(g)}${hex(b)}`;
};

/**
 * Evenly spaced fallback colours, used when the store has no `uns["gene_colors"]`.
 *
 * Deterministic, so a gene keeps its colour between reloads. Golden-ratio hue stepping
 * keeps neighbouring genes visually distinct instead of running through a smooth ramp.
 */
export const defaultGeneColors = (n) => {
  const GOLDEN_RATIO_CONJUGATE = 0.618033988749895;
  const colors = new Array(n);
  for (let i = 0; i < n; i += 1) {
    const hue = (i * GOLDEN_RATIO_CONJUGATE) % 1;
    colors[i] = hslToHex(hue * 360, 0.65, 0.55);
  }
  return colors;
};

/**
 * `meta_gene.parquet` equivalent.
 *
 * `feature_code` must equal the row position, because the transcript layer colours points
 * by looking up `g_colorMapping_inv[feature_code]`. Gene order therefore has to stay in
 * `var` order and must not be sorted.
 */
export const buildMetaGeneTable = ({
  names,
  mean,
  std,
  max,
  nonZero,
  colors,
  isGene,
}) => {
  const n = names.length;
  const featureCode = new Uint16Array(n);
  for (let i = 0; i < n; i += 1) featureCode[i] = i;

  return new arrow.Table({
    mean: float64Vector(mean),
    std: float64Vector(std),
    max: float64Vector(max),
    'non-zero': float64Vector(nonZero),
    color: utf8Vector(colors ?? defaultGeneColors(n)),
    feature_code: arrow.makeVector(featureCode),
    is_gene: arrow.vectorFromArray(
      isGene ?? new Array(n).fill(true),
      new arrow.Bool()
    ),
    __index_level_0__: utf8Vector(names),
  });
};

/**
 * `cell_metadata.parquet` equivalent: cell name plus a 2-element geometry per row.
 *
 * @param {{names: string[], centroids: Float64Array}} input - centroids flat [x, y, x, y...]
 */
export const buildCellMetadataTable = ({ names, centroids }) =>
  new arrow.Table({
    name: utf8Vector(names),
    geometry: listOfFloat64Vector(centroids, 2),
  });

/** `cell_clusters/cluster.parquet` equivalent. */
export const buildClusterTable = ({ cellNames, clusters }) =>
  new arrow.Table({
    cluster: utf8Vector(clusters),
    __index_level_0__: utf8Vector(cellNames),
  });

/** `cell_clusters/meta_cluster.parquet` equivalent: one row per distinct cluster. */
export const buildMetaClusterTable = ({ clusters, palette }) => {
  const counts = new Map();
  for (const c of clusters) {
    const key = c == null ? 'N.A.' : String(c);
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }

  const names = [...counts.keys()];
  const fallback = defaultGeneColors(names.length);
  const colors = names.map((name, i) => palette?.[name] ?? fallback[i]);
  const countValues = new BigInt64Array(names.length);
  names.forEach((name, i) => {
    countValues[i] = BigInt(counts.get(name));
  });

  return new arrow.Table({
    color: utf8Vector(colors),
    count: arrow.makeVector(countValues),
    __index_level_0__: utf8Vector(names),
  });
};
