import { options } from '../../global_variables/fetch_options';
import { fetch_all_tables_new } from '../../read_parquet/fetch_all_tables';
import { createEmptyTrxCompact } from '../../utils/compact_data';

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

const materializeTranscriptBuffers = (tables, viz_state) => {
  const tableArray = (Array.isArray(tables) ? tables : [tables]).filter(Boolean);

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

    const geometryColumn = table.getChild('geometry')?.getChildAt(0);
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
  const geneIdByName = viz_state.genes.g_nameMapping || {};

  let coordinateOffset = 0;
  let rowOffset = 0;

  const normalizeGeneId = (value) => {
    if (typeof value === 'bigint') {
      return Number(value);
    }

    const numericValue = Number(value);
    return Number.isFinite(numericValue) ? numericValue : -1;
  };

  for (const table of tableArray) {
    const geometryColumn = table.getChild('geometry')?.getChildAt(0);
    const chunks = geometryColumn?.data || [];

    for (const chunk of chunks) {
      positions.set(chunk.values, coordinateOffset);
      coordinateOffset += chunk.values.length;
    }

    const nameColumn = table.getChild('name');
    const nameValues = nameColumn ? nameColumn.toArray() : [];

    if (viz_state.vector_name_integer) {
      for (let i = 0; i < nameValues.length; i++) {
        geneIds[rowOffset + i] = normalizeGeneId(nameValues[i]);
      }
    } else {
      for (let i = 0; i < nameValues.length; i++) {
        const geneId = geneIdByName[nameValues[i]];
        geneIds[rowOffset + i] = geneId === undefined ? -1 : geneId;
      }
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
  if (
    !trx_tables ||
    (Array.isArray(trx_tables) && trx_tables.length === 0)
  ) {
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

  const { geneIds, scatterData: trx_scatter_data } = materializeTranscriptBuffers(
    trx_tables,
    viz_state
  );

  viz_state.genes.trx_gene_ids = geneIds;
  viz_state.combo_data.trx_compact = {
    geneIds,
    positions: trx_scatter_data.attributes.getPosition.value,
    size: trx_scatter_data.attributes.getPosition.size || 2,
  };
  // Backward-compatible field retained for any external consumers.
  viz_state.combo_data.trx = [];

  return trx_scatter_data;
};
