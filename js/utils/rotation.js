import { Matrix4 } from '@math.gl/core';

const EPSILON = 1e-6;

export const build_rotation_state = (angleDegrees = 0, center = [0, 0]) => {
  const angleRadians = (angleDegrees * Math.PI) / 180;
  const hasRotation = Math.abs(angleRadians) > EPSILON;
  const sin = Math.sin(angleRadians);
  const cos = Math.cos(angleRadians);

  const rotationState = {
    angleDegrees,
    angleRadians,
    hasRotation,
    sin,
    cos,
    center,
    modelMatrix: null,
  };

  if (hasRotation) {
    const matrix = new Matrix4()
      .translate([center[0], center[1], 0])
      .rotateZ(angleRadians)
      .translate([-center[0], -center[1], 0]);
    rotationState.modelMatrix = Array.from(matrix);
  }

  return rotationState;
};

export const getModelMatrixProps = (rotationState) => {
  if (rotationState?.hasRotation && rotationState.modelMatrix) {
    return { modelMatrix: rotationState.modelMatrix };
  }
  return {};
};

export const rotate_point = (x, y, rotationState) => {
  if (!rotationState?.hasRotation) {
    return [x, y];
  }
  const { center, sin, cos } = rotationState;
  const dx = x - center[0];
  const dy = y - center[1];
  return [cos * dx - sin * dy + center[0], sin * dx + cos * dy + center[1]];
};

export const rotate_point_inverse = (x, y, rotationState) => {
  if (!rotationState?.hasRotation) {
    return [x, y];
  }
  const { center, sin, cos } = rotationState;
  const dx = x - center[0];
  const dy = y - center[1];
  return [cos * dx + sin * dy + center[0], -sin * dx + cos * dy + center[1]];
};
