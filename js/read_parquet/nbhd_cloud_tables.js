// Parses the plain (non-row-group) Arrow tables fetched from the
// `neighborhood-cloud` DegaFile layout (`nbhd_cloud/*.parquet`) into the
// plain JS structures the rest of the neighborhood-cloud code works with.
import { getTableColumnArray } from './table_accessors';

const toNumberArray = (values) => values.map((v) => Number(v));

export const parse_meta_slice_table = (table) => {
  const sliceIds = getTableColumnArray(table, 'slice_id');
  const z = toNumberArray(getTableColumnArray(table, 'z'));
  const centroidX = toNumberArray(getTableColumnArray(table, 'centroid_x'));
  const centroidY = toNumberArray(getTableColumnArray(table, 'centroid_y'));
  const centroidZ = toNumberArray(getTableColumnArray(table, 'centroid_z'));
  const cellCount = toNumberArray(getTableColumnArray(table, 'cell_count'));

  return sliceIds.map((slice_id, i) => ({
    slice_id,
    z: z[i],
    centroid_x: centroidX[i],
    centroid_y: centroidY[i],
    centroid_z: centroidZ[i],
    cell_count: cellCount[i],
  }));
};

export const parse_meta_neighborhood_table = (table) => {
  const neighborhoodIds = getTableColumnArray(table, 'neighborhood_id');
  const clusterIds = getTableColumnArray(table, 'cluster_id');
  const sliceIds = getTableColumnArray(table, 'slice_id');
  const colors = getTableColumnArray(table, 'color');
  const areas = toNumberArray(getTableColumnArray(table, 'area'));
  const cellCounts = toNumberArray(getTableColumnArray(table, 'cell_count'));
  const invAlphas = toNumberArray(getTableColumnArray(table, 'inv_alpha'));

  return neighborhoodIds.map((neighborhood_id, i) => ({
    neighborhood_id,
    cluster_id: clusterIds[i],
    slice_id: sliceIds[i],
    color: colors[i],
    area: areas[i],
    cell_count: cellCounts[i],
    inv_alpha: invAlphas[i],
  }));
};

// Builds one GeoJSON Feature per row from a `shapes/slice_<id>.parquet` table
// (`geometry_geojson` is a JSON-encoded geometry string, not GeoParquet/WKB —
// see the Python writer for why). Rows with unparsable geometry are skipped.
export const parse_shapes_table_to_features = (table) => {
  const neighborhoodIds = getTableColumnArray(table, 'neighborhood_id');
  const clusterIds = getTableColumnArray(table, 'cluster_id');
  const sliceIds = getTableColumnArray(table, 'slice_id');
  const colors = getTableColumnArray(table, 'color');
  const areas = toNumberArray(getTableColumnArray(table, 'area'));
  const geojsonStrings = getTableColumnArray(table, 'geometry_geojson');

  const features = [];
  for (let i = 0; i < neighborhoodIds.length; i++) {
    let geometry;
    try {
      geometry = JSON.parse(geojsonStrings[i]);
    } catch {
      continue;
    }

    features.push({
      type: 'Feature',
      properties: {
        neighborhood_id: neighborhoodIds[i],
        cluster_id: clusterIds[i],
        slice_id: sliceIds[i],
        color: colors[i],
        // Drives the intra-slice draw-order tiebreak (see
        // reorder_nbhd_cloud_features_for_camera) -- smaller neighborhoods
        // drawn last (on top) so they aren't visually swallowed by a larger
        // one jittered onto a nearby Z within the same slice.
        area: areas[i],
      },
      geometry,
    });
  }

  return features;
};

// Builds one GeoJSON Feature per row from a `gene_shapes/<gene>.parquet`
// table (every slice's shape for one gene) -- same `geometry_geojson`
// convention as `parse_shapes_table_to_features`. Rows with unparsable
// geometry are skipped.
export const parse_gene_shapes_table_to_features = (table) => {
  const genes = getTableColumnArray(table, 'gene');
  const sliceIds = getTableColumnArray(table, 'slice_id');
  const meanExpressions = toNumberArray(
    getTableColumnArray(table, 'mean_expression')
  );
  const cellCounts = toNumberArray(getTableColumnArray(table, 'cell_count'));
  const geojsonStrings = getTableColumnArray(table, 'geometry_geojson');

  const features = [];
  for (let i = 0; i < genes.length; i++) {
    let geometry;
    try {
      geometry = JSON.parse(geojsonStrings[i]);
    } catch {
      continue;
    }

    features.push({
      type: 'Feature',
      properties: {
        gene: genes[i],
        slice_id: sliceIds[i],
        mean_expression: meanExpressions[i],
        cell_count: cellCounts[i],
      },
      geometry,
    });
  }

  return features;
};

// Merges per-slice `cells/by_slice/slice_<id>.parquet` tables into flat
// typed arrays ready for a PointCloudLayer's binary `data` prop.
export const parse_cells_tables = (tables) => {
  let totalLength = 0;
  const parsedTables = tables.map((table) => {
    const x = toNumberArray(getTableColumnArray(table, 'x'));
    const y = toNumberArray(getTableColumnArray(table, 'y'));
    const z = toNumberArray(getTableColumnArray(table, 'z'));
    const clusterId = getTableColumnArray(table, 'cluster_id');
    const sliceId = getTableColumnArray(table, 'slice_id');
    totalLength += x.length;
    return { x, y, z, clusterId, sliceId };
  });

  const positions = new Float32Array(totalLength * 3);
  const clusterIds = new Array(totalLength);
  const sliceIds = new Array(totalLength);

  let offset = 0;
  for (const { x, y, z, clusterId, sliceId } of parsedTables) {
    for (let i = 0; i < x.length; i++) {
      const idx = offset + i;
      positions[idx * 3] = x[i];
      positions[idx * 3 + 1] = y[i];
      positions[idx * 3 + 2] = z[i];
      clusterIds[idx] = clusterId[i];
      sliceIds[idx] = sliceId[i];
    }
    offset += x.length;
  }

  return { length: totalLength, positions, clusterIds, sliceIds };
};

// Parses one `cells/by_gene/<gene>.parquet` table (already capped/subsampled
// server-side -- see write_gene_shapes_from_cbg's max_cells) into flat typed
// arrays ready for a PointCloudLayer's binary `data` prop. Single table, not
// a list -- unlike cluster cells (loaded once per slice historically), a
// gene's cells file already covers every slice on its own.
export const parse_gene_cells_table = (table) => {
  const x = toNumberArray(getTableColumnArray(table, 'x'));
  const y = toNumberArray(getTableColumnArray(table, 'y'));
  const z = toNumberArray(getTableColumnArray(table, 'z'));
  const sliceIds = getTableColumnArray(table, 'slice_id');
  const expressions = toNumberArray(getTableColumnArray(table, 'expression'));

  const { length } = x;
  const positions = new Float32Array(length * 3);
  for (let i = 0; i < length; i++) {
    positions[i * 3] = x[i];
    positions[i * 3 + 1] = y[i];
    positions[i * 3 + 2] = z[i];
  }

  return { length, positions, sliceIds, expressions };
};
