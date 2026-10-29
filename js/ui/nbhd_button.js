import * as d3 from 'd3';

// The NBHD button is a d3 selection or, with neighborhood editing, a plain
// element, whose `style` is a CSSStyleDeclaration rather than a function.
export const set_nbhd_button_color = (viz_state, color) => {
  const button = viz_state.buttons?.buttons?.nbhd;
  if (!button) return;
  if (typeof button.style === 'function') button.style('color', color);
  else d3.select(button).style('color', color);
};
