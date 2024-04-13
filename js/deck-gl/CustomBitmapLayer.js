import { BitmapLayer } from 'deck.gl';

export class CustomBitmapLayer extends BitmapLayer {
  getShaders() {
    const shaders = super.getShaders();
    // Directly injecting shader code
    shaders.inject = {
      'fs:#decl': `uniform vec3 uColor; uniform float uOpacityScale;`,
      'fs:DECKGL_FILTER_COLOR': `
        // Convert color to grayscale and apply opacity scale
        float grayscale = ((color.r + color.g + color.b) / 3.0) * uOpacityScale;
        // Clamp grayscale to valid range
        grayscale = clamp(grayscale, 0.0, 1.0);
        // Apply custom color and scaled opacity
        color = vec4(uColor, grayscale);
      `
    };
    return shaders;
  }

  // Properly passing uniforms through updateState lifecycle hook
  updateState(params) {
    super.updateState(params);
    // Extracting custom props
    const {props, oldProps} = params;
    if (props.color !== oldProps.color || props.opacityScale !== oldProps.opacityScale) {
      // Update uniforms when props change
      this.setState({
        uniforms: {
          uColor: props.color.map(c => c / 255), // Normalize RGB to [0, 1] range
          uOpacityScale: props.opacityScale
        }
      });
    }
  }

  draw(opts) {
    // Ensuring custom uniforms are passed to the shader program
    const {uniforms} = this.state;
    super.draw({
      ...opts,
      uniforms: {
        ...opts.uniforms,
        ...uniforms, // Spread in custom uniforms
      },
    });
  }
}