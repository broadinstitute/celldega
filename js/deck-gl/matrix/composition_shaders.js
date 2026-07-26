// Composition (stacked-bar) body shaders.
//
// Same square-fill approach as the heatmap body, but the per-instance size is a
// world-space half-extent [halfWidth, halfHeight] (from `getSize`) instead of a
// uniform tile size scaled by a single radius. This lets each segment have a
// full-column width and an independent, value-driven height.

export const comp_vs = `#version 300 es
#define SHADER_NAME composition-layer-vertex-shader

in vec3 positions;
in vec3 instancePositions;
in vec3 instancePositions64Low;
in vec3 instancePickingColors;
in vec4 instanceFillColors;
in vec2 instanceSize;

uniform float opacity;

out vec4 vFillColor;
out vec2 unitPosition;

void main(void) {

  // instanceSize = [halfWidth, halfHeight] in world units for this segment.
  vec3 scaled_positions = vec3(instanceSize.x * positions.x, instanceSize.y * positions.y, positions.z);

  vec3 positionCommon = project_position(instancePositions + scaled_positions , instancePositions64Low);

  gl_Position = project_common_position_to_clipspace(vec4(positionCommon, 1.0));

  gl_PointSize = 100.0;

  geometry.pickingColor = instancePickingColors;

  vFillColor = vec4(instanceFillColors.rgb, instanceFillColors.a * opacity);
  DECKGL_FILTER_COLOR(vFillColor, geometry);

}

`;

export const comp_fs = `#version 300 es
#define SHADER_NAME composition-layer-fragment-shader

precision highp float;
in vec4 vFillColor;
in vec2 unitPosition;
out vec4 fragColor;

void main(void) {
    geometry.uv = unitPosition;
    fragColor = vFillColor;
    DECKGL_FILTER_COLOR(fragColor, geometry);
}`;
