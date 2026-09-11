import { options } from '../../global_variables/fetch_options';
import { fetch_all_tables_new } from '../../read_parquet/fetch_all_tables';
import { createEmptyTrxCompact } from '../../utils/compact_data';

/**
 * Column names used by DegaFiles. A SpatialData store declares its own in the manifest
 * (display_xy / feature_code); anything that does not declare them keeps these.
 */
const DEFAULT_POSITION_COLUMN = 'geometry';
const DEFAULT_FEATURE_COLUMN = 'name';

/**
 * Resolve the transcript column names for the dataset currently loaded.
 * @param {Object} viz_state - Visualization state
 * @returns {{position: string, feature: string}}
 */
const trx_columns = (viz_state) => ({
  position: viz_state?.trx_position_column || DEFAULT_POSITION_COLUMN,
  positions: viz_state?.trx_position_columns || null,
  feature: viz_state?.trx_feature_column || DEFAULT_FEATURE_COLUMN,
});

/**
 * Fetch transcript tiles from row group reader
 * @param {Array} tiles_in_view - Array of tiles with tileX and tileY
 * @param {Object} viz_state - Visualization state containing row_group_readers
 * @returns {Promise<arrow.Table|null>} - Combined Arrow table for requested tiles
 */
async function grab_trx_tiles_row_groups(tiles_in_view, viz_state) {
  const reader = viz_state.row_group_readers?.trx;
  if (!reader) {
    // console.error('[grab_trx_tiles] Row group reader not initialized');
    return null;
  }

  // Convert tile format from {tileX, tileY} to {tile_x, tile_y}
  const tilesForReader = tiles_in_view.map((tile) => ({
    tile_x: tile.tileX,
    tile_y: tile.tileY,
  }));

  return reader.readTiles(tilesForReader, { returnTablesArray: true });
}

const numericBuffer = (vector) => {
  const chunk = vector?.data?.[0];
  if (!chunk?.values) return null;
  const start = chunk.offset || 0;
  return chunk.values.subarray(start, start + chunk.length);
};

const normalizeGeneId = (value) => {
  if (typeof value === 'bigint') return Number(value);
  const numericValue = Number(value);
  return Number.isFinite(numericValue) ? numericValue : -1;
};

const geneIdFor = (value, viz_state) => {
  if (viz_state.trx_feature_encoding === 'dictionary') {
    return viz_state.genes.g_nameMapping?.[String(value)] ?? -1;
  }
  if (viz_state.vector_name_integer) return normalizeGeneId(value);
  return viz_state.genes.g_nameMapping?.[value] ?? -1;
};

const materializeSeparatedTranscriptBuffers = (tables, viz_state) => {
  const { positions: positionColumns, feature: featureColumn } =
    trx_columns(viz_state);
  const [xColumn, yColumn] = positionColumns || [];
  const tableArray = (Array.isArray(tables) ? tables : [tables]).filter(
    Boolean
  );

  const batches = tableArray.flatMap((table) => table.batches || []);
  const totalRows = batches.reduce((sum, batch) => sum + batch.numRows, 0);
  const geneIds = new Int32Array(totalRows);
  const chunks = [];
  const coordinateChunks = [];
  let rowOffset = 0;

  for (const batch of batches) {
    const x = numericBuffer(batch.getChild(xColumn));
    const y = numericBuffer(batch.getChild(yColumn));
    const features = batch.getChild(featureColumn);
    if (!x || !y || x.length !== batch.numRows || y.length !== batch.numRows) {
      continue;
    }

    for (let i = 0; i < batch.numRows; i += 1) {
      geneIds[rowOffset + i] = geneIdFor(features?.get(i), viz_state);
    }

    chunks.push({
      length: batch.numRows,
      rowOffset,
      attributes: {
        getX: { value: x, size: 1 },
        getY: { value: y, size: 1 },
      },
    });
    coordinateChunks.push({ x, y, rowOffset, length: batch.numRows });
    rowOffset += batch.numRows;
  }

  return {
    geneIds: rowOffset === totalRows ? geneIds : geneIds.slice(0, rowOffset),
    scatterData: chunks,
    coordinateChunks,
  };
};

export const materializeTranscriptBuffers = (tables, viz_state) => {
  if (
    viz_state?.trx_position_encoding === 'separate_columns' &&
    Array.isArray(viz_state?.trx_position_columns)
  ) {
    return materializeSeparatedTranscriptBuffers(tables, viz_state);
  }

  const { position: positionColumn, feature: featureColumn } =
    trx_columns(viz_state);
  const tableArray = (Array.isArray(tables) ? tables : [tables]).filter(
    Boolean
  );

  if (tableArray.length === 0) {
    return {
      geneIds: new Int32Array(),
      scatterData: {
        length: 0,
        attributes: {
          getPosition: { value: new Float32Array(), size: 2 },
        },
      },
    };
  }

  let totalRows = 0;
  let totalCoordinates = 0;

  for (const table of tableArray) {
    totalRows += table.numRows;

    const geometryColumn = table.getChild(positionColumn)?.getChildAt(0);
    const chunks = geometryColumn?.data || [];
    for (const chunk of chunks) {
      totalCoordinates += chunk.values.length;
    }
  }

  if (totalRows === 0 || totalCoordinates === 0) {
    return {
      geneIds: new Int32Array(),
      scatterData: {
        length: 0,
        attributes: {
          getPosition: { value: new Float32Array(), size: 2 },
        },
      },
    };
  }

  const positions = new Float64Array(totalCoordinates);
  const geneIds = new Int32Array(totalRows);
  let coordinateOffset = 0;
  let rowOffset = 0;

  for (const table of tableArray) {
    const geometryColumn = table.getChild(positionColumn)?.getChildAt(0);
    const chunks = geometryColumn?.data || [];

    for (const chunk of chunks) {
      // chunk.values is the flat, already-interleaved Arrow child buffer
      // ([x0,y0,x1,y1,...]); current SpatialData display_xy is float32.
      // This copies into Float64 storage but does not zip separate x/y columns.
      positions.set(chunk.values, coordinateOffset);
      coordinateOffset += chunk.values.length;
    }

    const nameColumn = table.getChild(featureColumn);
    const nameValues = nameColumn ? nameColumn.toArray() : [];

    for (let i = 0; i < nameValues.length; i++) {
      geneIds[rowOffset + i] = geneIdFor(nameValues[i], viz_state);
    }

    rowOffset += table.numRows;
  }

  return {
    geneIds,
    scatterData: {
      length: totalRows,
      attributes: {
        getPosition: {
          value: positions,
          size: totalCoordinates / totalRows,
        },
      },
    },
    coordinateChunks: null,
  };
};

export const grab_trx_tiles_in_view = async (
  base_url,
  tiles_in_view,
  viz_state
) => {
  let trx_tables;

  // Check if using row group mode
  if (viz_state.use_row_groups && viz_state.row_group_readers?.trx) {
    trx_tables = await grab_trx_tiles_row_groups(tiles_in_view, viz_state);
  } else {
    // Traditional mode: fetch individual tile files
    const tile_trx_urls = tiles_in_view.map((tile) => {
      return `${base_url}/transcript_tiles/transcripts_tile_${tile.tileX}_${tile.tileY}.parquet`;
    });

    const tile_trx_tables_ini = await fetch_all_tables_new(
      viz_state.cache.trx,
      tile_trx_urls,
      options,
      viz_state.aws
    );

    trx_tables = tile_trx_tables_ini.filter((table) => table !== null);
  }

  // Handle case where no transcript tiles were loaded
  if (!trx_tables || (Array.isArray(trx_tables) && trx_tables.length === 0)) {
    viz_state.genes.trx_gene_ids = new Int32Array();
    viz_state.combo_data.trx = [];
    viz_state.combo_data.trx_compact = createEmptyTrxCompact();
    return {
      length: 0,
      attributes: {
        getPosition: { value: new Float32Array(), size: 2 },
      },
    };
  }

  const {
    geneIds,
    scatterData: trx_scatter_data,
    coordinateChunks,
  } = materializeTranscriptBuffers(trx_tables, viz_state);

  viz_state.genes.trx_gene_ids = geneIds;
  viz_state.combo_data.trx_compact = coordinateChunks
    ? {
        geneIds,
        positions: new Float64Array(),
        size: 2,
        coordinateChunks,
        displayTransform: viz_state.trx_display_transform,
      }
    : {
        geneIds,
        positions: trx_scatter_data.attributes.getPosition.value,
        size: trx_scatter_data.attributes.getPosition.size || 2,
      };
  // Backward-compatible field retained for any external consumers.
  viz_state.combo_data.trx = [];

  return trx_scatter_data;
};
