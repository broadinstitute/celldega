import { PointCloudLayer } from 'deck.gl';

// A translucent point must not write depth: otherwise a near cell drawn early
// rejects farther cells instead of blending with them, and gene coloring changes
// when the camera moves to the other side. CellCloud expression uses one red
// hue with per-cell alpha, so its blending is independent of point order.
// Keep normal depth writes for opaque colors and the picking pass, which must
// still find the nearest cell rather than whichever input row was drawn last.
export const CellCloudLayer = class extends PointCloudLayer {
  static layerName = 'CellCloudLayer';
  static defaultProps = { cellCloudTransparent: false };

  draw(options) {
    const picking = Boolean(options.moduleParameters?.picking?.isActive);
    const useDepth = picking || !this.props.cellCloudTransparent;
    // Apply this per draw pass, without changing the model's render-pipeline
    // parameters (or its attribute/shader state) during a draw.
    this.context.device.withParametersWebGL(
      { depthTest: useDepth, depthMask: useDepth },
      () => super.draw(options)
    );
  }
};
