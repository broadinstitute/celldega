export const hexToRgb = (hex) => {
  hex = hex.replace(/^#/, '');
  if (hex.length === 3) hex = hex.replace(/./g, '$&$&');
  return hex.length === 6
    ? [0, 2, 4].map((i) => parseInt(hex.substr(i, 2), 16))
    : [0, 0, 0];
};
