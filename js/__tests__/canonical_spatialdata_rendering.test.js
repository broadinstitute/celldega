/* global require */

const loadSource = (relativePath, prelude, exports) => {
  const fs = require('fs');
  const path = require('path');
  const source = fs
    .readFileSync(path.join(__dirname, relativePath), 'utf8')
    .replace(/^import[\s\S]*?;$/gm, '')
    .replace(/^export /gm, '');
  const module = { exports: {} };
  new Function(
    'module',
    'exports',
    `${prelude}\n${source}\nmodule.exports = { ${exports.join(', ')} };`
  )(module, module.exports);
  return module.exports;
};

describe('canonical transcript buffers', () => {
  let materializeTranscriptBuffers;

  beforeAll(() => {
    ({ materializeTranscriptBuffers } = loadSource(
      '../vector_tile/transcripts/grab_trx_tiles_in_view.js',
      'const options = {}; const fetch_all_tables_new = () => {}; const createEmptyTrxCompact = () => ({});',
      ['materializeTranscriptBuffers']
    ));
  });

  const vector = (values) => ({
    data: [{ values, offset: 0, length: values.length }],
    get: (index) => values[index],
  });

  test('passes separate x/y Arrow buffers through without copying', () => {
    const x = Float32Array.from([1, 2, 3]);
    const y = Float32Array.from([10, 20, 30]);
    const feature = ['A', 'B', 'missing'];
    const columns = {
      x: vector(x),
      y: vector(y),
      feature_name: vector(feature),
    };
    const batch = {
      numRows: 3,
      getChild: (name) => columns[name],
    };
    const vizState = {
      trx_position_encoding: 'separate_columns',
      trx_position_columns: ['x', 'y'],
      trx_feature_column: 'feature_name',
      trx_feature_encoding: 'dictionary',
      vector_name_integer: true,
      genes: { g_nameMapping: { A: 4, B: 7 } },
    };

    const out = materializeTranscriptBuffers([{ batches: [batch] }], vizState);

    expect(out.scatterData).toHaveLength(1);
    expect(out.scatterData[0].attributes.getX.value.buffer).toBe(x.buffer);
    expect(out.scatterData[0].attributes.getY.value.buffer).toBe(y.buffer);
    expect(Array.from(out.geneIds)).toEqual([4, 7, -1]);
    expect(out.coordinateChunks[0].x.buffer).toBe(x.buffer);
  });

  test('keeps row offsets stable across record batches', () => {
    const makeBatch = (x, y, names) => {
      const columns = {
        x: vector(Float32Array.from(x)),
        y: vector(Float32Array.from(y)),
        feature_name: vector(names),
      };
      return { numRows: x.length, getChild: (name) => columns[name] };
    };
    const vizState = {
      trx_position_encoding: 'separate_columns',
      trx_position_columns: ['x', 'y'],
      trx_feature_column: 'feature_name',
      trx_feature_encoding: 'dictionary',
      genes: { g_nameMapping: { A: 0, B: 1 } },
    };

    const out = materializeTranscriptBuffers(
      [
        {
          batches: [
            makeBatch([1, 2], [3, 4], ['A', 'B']),
            makeBatch([5], [6], ['B']),
          ],
        },
      ],
      vizState
    );

    expect(out.scatterData.map((chunk) => chunk.rowOffset)).toEqual([0, 2]);
    expect(Array.from(out.geneIds)).toEqual([0, 1, 1]);
  });

  test('preserves the interleaved DegaFiles transcript path', () => {
    const positions = Float32Array.from([1, 10, 2, 20]);
    const geometryChild = { data: [{ values: positions }] };
    const columns = {
      geometry: { getChildAt: () => geometryChild },
      name: { toArray: () => Int32Array.from([3, 8]) },
    };
    const table = {
      numRows: 2,
      getChild: (name) => columns[name],
    };
    const vizState = {
      vector_name_integer: true,
      genes: { g_nameMapping: {} },
    };

    const out = materializeTranscriptBuffers([table], vizState);

    expect(out.scatterData.length).toBe(2);
    expect(out.scatterData.attributes.getPosition.size).toBe(2);
    expect(Array.from(out.scatterData.attributes.getPosition.value)).toEqual([
      1, 10, 2, 20,
    ]);
    expect(Array.from(out.geneIds)).toEqual([3, 8]);
    expect(out.coordinateChunks).toBeNull();
  });
});

describe('separate-coordinate shader', () => {
  let displayTransformUniform;
  let SeparatedScatterplotLayer;

  beforeAll(() => {
    class ScatterplotLayer {
      static defaultProps = {};
      getShaders() {
        return {
          vs: 'in vec3 instancePositions;\nin vec3 instancePositions64Low;\nvoid main(void) {\n geometry.worldPosition = instancePositions;\n}',
        };
      }
    }
    class CompositeLayer {}
    ({ displayTransformUniform, SeparatedScatterplotLayer } = loadSource(
      '../deck-gl/layers/separated_scatterplot_layer.js',
      `${ScatterplotLayer.toString()}\n${CompositeLayer.toString()}`,
      ['displayTransformUniform', 'SeparatedScatterplotLayer']
    ));
  });

  test('converts the SpatialData affine matrix for a GLSL mat3', () => {
    expect(
      displayTransformUniform({
        affine_matrix: [
          [2, 3, 4],
          [5, 6, 7],
        ],
      })
    ).toEqual([2, 5, 0, 3, 6, 0, 4, 7, 1]);
  });

  test('shader builds positions from two scalar attributes', () => {
    const shader = new SeparatedScatterplotLayer().getShaders().vs;
    expect(shader).toContain('in float instanceX;');
    expect(shader).toContain('in float instanceY;');
    expect(shader).toContain('displayTransform * vec3(instanceX, instanceY');
    expect(shader).toContain(
      'vec3 instancePositions = vec3(transformedPosition.xy, 0.0);'
    );
    expect(shader).not.toContain('in vec3 instancePositions;');
  });
});

describe('canonical polygon display transform', () => {
  let extractPolygonPaths;

  beforeAll(() => {
    ({ extractPolygonPaths } = loadSource(
      '../vector_tile/polygons/extractPolygonPaths.js',
      '',
      ['extractPolygonPaths']
    ));
  });

  test('pairs separated coordinates and maps microns to display pixels', () => {
    const paths = extractPolygonPaths(
      {
        length: 1,
        startIndices: Int32Array.from([0, 3]),
        attributes: {
          getPolygonX: { value: Float64Array.from([1, 2, 1]) },
          getPolygonY: { value: Float64Array.from([3, 3, 4]) },
        },
      },
      {
        affine_matrix: [
          [2, 0, 10],
          [0, 3, 20],
        ],
      }
    );

    expect(paths).toEqual([
      [
        [12, 29],
        [14, 29],
        [12, 32],
      ],
    ]);
  });
});
