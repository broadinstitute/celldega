import { CompositeLayer, ScatterplotLayer } from 'deck.gl';

/**
 * ScatterplotLayer variant whose x and y instance attributes stay in separate Arrow
 * buffers. SpatialData stores canonical point coordinates this way; combining them in
 * the vertex shader avoids allocating and filling an interleaved CPU array for every
 * viewport update.
 */
export class SeparatedScatterplotLayer extends ScatterplotLayer {
  static layerName = 'SeparatedScatterplotLayer';

  static defaultProps = {
    ...ScatterplotLayer.defaultProps,
    getX: { type: 'accessor', value: 0 },
    getY: { type: 'accessor', value: 0 },
    displayTransform: {
      type: 'array',
      value: [1, 0, 0, 0, 1, 0, 0, 0, 1],
      compare: true,
    },
  };

  getShaders() {
    const shaders = super.getShaders();
    const declarations =
      'in vec3 instancePositions;\nin vec3 instancePositions64Low;';
    const replacement =
      'in float instanceX;\nin float instanceY;\nuniform mat3 displayTransform;';
    const main = 'void main(void) {';
    const position = `${main}\n  vec3 transformedPosition = displayTransform * vec3(instanceX, instanceY, 1.0);\n  vec3 instancePositions = vec3(transformedPosition.xy, 0.0);\n  vec3 instancePositions64Low = vec3(0.0);`;

    return {
      ...shaders,
      vs: shaders.vs.replace(declarations, replacement).replace(main, position),
    };
  }

  initializeState() {
    super.initializeState();
    const attributeManager = this.getAttributeManager();
    attributeManager.remove(['instancePositions']);
    attributeManager.addInstanced({
      instanceX: {
        size: 1,
        type: 'float32',
        accessor: 'getX',
      },
      instanceY: {
        size: 1,
        type: 'float32',
        accessor: 'getY',
      },
    });
  }

  draw(args) {
    this.state.model?.setUniforms({
      displayTransform: this.props.displayTransform,
    });
    super.draw(args);
  }
}

/** Convert a two-row affine manifest matrix to GLSL's column-major mat3. */
export const displayTransformUniform = (manifestTransform) => {
  const matrix = manifestTransform?.affine_matrix;
  if (!Array.isArray(matrix) || matrix.length < 2) {
    return [1, 0, 0, 0, 1, 0, 0, 0, 1];
  }
  const [a = 1, b = 0, c = 0] = matrix[0] || [];
  const [d = 0, e = 1, f = 0] = matrix[1] || [];
  return [a, d, 0, b, e, 0, c, f, 1];
};

/**
 * Render one binary sublayer per Arrow record batch. Each sublayer points directly at
 * the x and y buffers returned by parquet-wasm, so changing visible tiles does not zip
 * or concatenate coordinates on the CPU.
 */
export class SeparatedTranscriptLayer extends CompositeLayer {
  static layerName = 'SeparatedTranscriptLayer';

  static defaultProps = {
    ...ScatterplotLayer.defaultProps,
    displayTransform: SeparatedScatterplotLayer.defaultProps.displayTransform,
  };

  renderLayers() {
    const chunks = Array.isArray(this.props.data) ? this.props.data : [];
    return chunks.map((chunk, index) => {
      const { rowOffset = 0 } = chunk;
      const wrapAccessor = (accessor) =>
        typeof accessor === 'function'
          ? (object, info) =>
              accessor(object, { ...info, index: info.index + rowOffset })
          : accessor;
      const { onClick } = this.props;

      return new SeparatedScatterplotLayer(
        this.getSubLayerProps({
          id: `batch-${index}`,
          data: chunk,
          pickable: this.props.pickable,
          visible: this.props.visible,
          getRadius: wrapAccessor(this.props.getRadius),
          getFillColor: wrapAccessor(this.props.getFillColor),
          getLineColor: wrapAccessor(this.props.getLineColor),
          getLineWidth: wrapAccessor(this.props.getLineWidth),
          radiusUnits: this.props.radiusUnits,
          radiusScale: this.props.radiusScale,
          radiusMinPixels: this.props.radiusMinPixels,
          radiusMaxPixels: this.props.radiusMaxPixels,
          stroked: this.props.stroked,
          filled: this.props.filled,
          billboard: this.props.billboard,
          antialiasing: this.props.antialiasing,
          displayTransform: this.props.displayTransform,
          onClick:
            typeof onClick === 'function'
              ? (info, event) =>
                  onClick({ ...info, index: info.index + rowOffset }, event)
              : undefined,
        })
      );
    });
  }
}
