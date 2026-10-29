/* global require */

describe('neighborhood-cloud parquet table parsing', () => {
  let parse_meta_slice_table;
  let parse_meta_neighborhood_table;
  let parse_shapes_table_to_features;
  let parse_gene_shapes_table_to_features;
  let parse_cells_tables;
  let parse_gene_cells_table;

  beforeAll(() => {
    const fs = require('fs');
    const path = require('path');

    const readStripped = (relPath) =>
      fs
        .readFileSync(path.join(__dirname, relPath), 'utf8')
        .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
        .replace(/^export const /gm, 'const ');

    const source = [
      readStripped('../read_parquet/table_accessors.js'),
      readStripped('../read_parquet/nbhd_cloud_tables.js'),
    ].join('\n');

    const code = `${source}\nmodule.exports = { parse_meta_slice_table, parse_meta_neighborhood_table, parse_shapes_table_to_features, parse_gene_shapes_table_to_features, parse_cells_tables, parse_gene_cells_table };`;
    const module = { exports: {} };
    new Function('module', 'exports', code)(module, module.exports);
    ({
      parse_meta_slice_table,
      parse_meta_neighborhood_table,
      parse_shapes_table_to_features,
      parse_gene_shapes_table_to_features,
      parse_cells_tables,
      parse_gene_cells_table,
    } = module.exports);
  });

  const makeTable = (columns) => ({
    numRows: (Object.values(columns)[0] || []).length,
    schema: {
      fields: Object.keys(columns).map((name) => ({ name })),
      metadata: new Map(),
    },
    getChild: (name) =>
      Object.prototype.hasOwnProperty.call(columns, name)
        ? { toArray: () => columns[name] }
        : null,
  });

  test('parse_meta_slice_table zips columns into row objects', () => {
    const table = makeTable({
      slice_id: ['s0', 's1'],
      z: [0, 100],
      centroid_x: [1.5, 2.5],
      centroid_y: [3.5, 4.5],
      centroid_z: [0, 100],
      cell_count: [10, 20],
    });

    expect(parse_meta_slice_table(table)).toEqual([
      {
        slice_id: 's0',
        z: 0,
        centroid_x: 1.5,
        centroid_y: 3.5,
        centroid_z: 0,
        cell_count: 10,
      },
      {
        slice_id: 's1',
        z: 100,
        centroid_x: 2.5,
        centroid_y: 4.5,
        centroid_z: 100,
        cell_count: 20,
      },
    ]);
  });

  test('parse_meta_neighborhood_table zips columns into row objects', () => {
    const table = makeTable({
      neighborhood_id: ['s0__0'],
      cluster_id: ['0'],
      slice_id: ['s0'],
      color: ['#ff0000'],
      area: [123.4],
      cell_count: [30],
      inv_alpha: [150],
    });

    expect(parse_meta_neighborhood_table(table)).toEqual([
      {
        neighborhood_id: 's0__0',
        cluster_id: '0',
        slice_id: 's0',
        color: '#ff0000',
        area: 123.4,
        cell_count: 30,
        inv_alpha: 150,
      },
    ]);
  });

  test('parse_shapes_table_to_features parses geometry_geojson into GeoJSON features', () => {
    const geometry = { type: 'Point', coordinates: [1, 2, 3] };
    const table = makeTable({
      neighborhood_id: ['s0__0'],
      cluster_id: ['0'],
      slice_id: ['s0'],
      color: ['#ff0000'],
      geometry_geojson: [JSON.stringify(geometry)],
    });

    expect(parse_shapes_table_to_features(table)).toEqual([
      {
        type: 'Feature',
        properties: {
          neighborhood_id: 's0__0',
          cluster_id: '0',
          slice_id: 's0',
          color: '#ff0000',
        },
        geometry,
      },
    ]);
  });

  test('parse_shapes_table_to_features carries the area column through, for draw-order tiebreaking', () => {
    const geometry = { type: 'Point', coordinates: [1, 2, 3] };
    const table = makeTable({
      neighborhood_id: ['s0__0'],
      cluster_id: ['0'],
      slice_id: ['s0'],
      color: ['#ff0000'],
      area: [42.5],
      geometry_geojson: [JSON.stringify(geometry)],
    });

    expect(parse_shapes_table_to_features(table)[0].properties.area).toBe(42.5);
  });

  test('parse_shapes_table_to_features skips rows with unparsable geometry', () => {
    const table = makeTable({
      neighborhood_id: ['a', 'b'],
      cluster_id: ['0', '1'],
      slice_id: ['s0', 's0'],
      color: ['#fff', '#000'],
      geometry_geojson: ['not json', '{"type":"Point","coordinates":[0,0]}'],
    });

    const features = parse_shapes_table_to_features(table);
    expect(features).toHaveLength(1);
    expect(features[0].properties.neighborhood_id).toBe('b');
  });

  test('parse_gene_shapes_table_to_features parses geometry_geojson into GeoJSON features', () => {
    const geometry = { type: 'Point', coordinates: [1, 2, 3] };
    const table = makeTable({
      gene: ['Matn1'],
      slice_id: ['s0'],
      mean_expression: [4.5],
      cell_count: [12],
      geometry_geojson: [JSON.stringify(geometry)],
    });

    expect(parse_gene_shapes_table_to_features(table)).toEqual([
      {
        type: 'Feature',
        properties: {
          gene: 'Matn1',
          slice_id: 's0',
          mean_expression: 4.5,
          cell_count: 12,
        },
        geometry,
      },
    ]);
  });

  test('parse_gene_shapes_table_to_features skips rows with unparsable geometry', () => {
    const table = makeTable({
      gene: ['Matn1', 'Matn1'],
      slice_id: ['s0', 's1'],
      mean_expression: [1, 2],
      cell_count: [5, 6],
      geometry_geojson: ['not json', '{"type":"Point","coordinates":[0,0]}'],
    });

    const features = parse_gene_shapes_table_to_features(table);
    expect(features).toHaveLength(1);
    expect(features[0].properties.slice_id).toBe('s1');
  });

  test('parse_cells_tables merges multiple per-slice tables into flat typed arrays', () => {
    const table1 = makeTable({
      x: [1, 2],
      y: [3, 4],
      z: [0, 0],
      cluster_id: ['0', '1'],
      slice_id: ['s0', 's0'],
    });
    const table2 = makeTable({
      x: [5],
      y: [6],
      z: [100],
      cluster_id: ['0'],
      slice_id: ['s1'],
    });

    const merged = parse_cells_tables([table1, table2]);

    expect(merged.length).toBe(3);
    expect(Array.from(merged.positions)).toEqual([1, 3, 0, 2, 4, 0, 5, 6, 100]);
    expect(merged.clusterIds).toEqual(['0', '1', '0']);
    expect(merged.sliceIds).toEqual(['s0', 's0', 's1']);
  });

  test('parse_cells_tables handles an empty list', () => {
    const merged = parse_cells_tables([]);
    expect(merged.length).toBe(0);
    expect(merged.positions.length).toBe(0);
  });

  test('parse_gene_cells_table parses a cells/by_gene/<gene>.parquet table into flat arrays', () => {
    const table = makeTable({
      cell_id: ['c0', 'c1'],
      gene: ['Matn1', 'Matn1'],
      slice_id: ['s0', 's1'],
      x: [1, 2],
      y: [3, 4],
      z: [0, 100],
      expression: [5.5, 10],
    });

    const parsed = parse_gene_cells_table(table);

    expect(parsed.length).toBe(2);
    expect(Array.from(parsed.positions)).toEqual([1, 3, 0, 2, 4, 100]);
    expect(parsed.sliceIds).toEqual(['s0', 's1']);
    expect(parsed.expressions).toEqual([5.5, 10]);
  });
});
