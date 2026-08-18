export const vs = `#version 300 es
#define SHADER_NAME scatterplot-layer-vertex-shader

// customize the vertex shader to allow for x and y scaling and zooming

in vec3 positions;
in vec3 instancePositions;
in vec3 instancePositions64Low;
in vec3 instancePickingColors;
in vec4 instanceFillColors;
in float instanceRadius;

uniform float opacity;
uniform float tile_height;
uniform float tile_width;

out vec4 vFillColor;
out vec2 unitPosition;

void main(void) {

  // instanceRadius (from getRadius) is a per-cell size scale in [0, 1] that
  // shrinks the square around its center for the "dotplot" encoding.
  // It defaults to 1.0 (full tile) so the classic heatmap is unchanged.
  vec3 scaled_positions = vec3(tile_width * positions.x * instanceRadius, tile_height * positions.y * instanceRadius, positions.z);

  vec3 positionCommon = project_position(instancePositions + scaled_positions , instancePositions64Low);

  gl_Position = project_common_position_to_clipspace(vec4(positionCommon, 1.0));

  gl_PointSize = 100.0;

  geometry.pickingColor = instancePickingColors;

  vFillColor = vec4(instanceFillColors.rgb, instanceFillColors.a * opacity);
  DECKGL_FILTER_COLOR(vFillColor, geometry);

}

`;

export const fs = `#version 300 es
#define SHADER_NAME scatterplot-layer-fragment-shader

// Customize the fragment shader to create square-shaped points

precision highp float;
in vec4 vFillColor;
in vec2 unitPosition;
out vec4 fragColor;

void main(void) {
    geometry.uv = unitPosition;
    fragColor = vFillColor;
    DECKGL_FILTER_COLOR(fragColor, geometry);
}`;
