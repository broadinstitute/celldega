/**
 * Pixel size in microns for different technologies
 */
export const PIXEL_SIZE_MICRONS = {
  Xenium: 0.2125,
  MERSCOPE: 0.108,
};

/**
 * Create a dynamic scale bar for spatial visualizations
 * @param {number} micronsPerPixel - The base resolution of the image in microns per pixel
 * @param {string} tech - The technology name (e.g., 'Xenium', 'MERSCOPE', 'Visium-HD')
 * @returns {Object} Object with container element, update function, and setVisible function
 */
export const create_scale_bar = (micronsPerPixel, tech) => {
  const techKey = tech || '';
  const blackLabelTechs = ['Visium-HD'];
  const whiteLabelTechs = ['Xenium', 'MERSCOPE'];

  const labelColor = blackLabelTechs.includes(techKey)
    ? 'black'
    : whiteLabelTechs.includes(techKey)
      ? 'white'
      : 'white';

  const rev_labelColor = labelColor === 'white' ? 'black' : 'white';

  const container = document.createElement('div');
  container.style.position = 'absolute';
  container.style.bottom = '10px';
  container.style.left = '10px';
  container.style.backgroundColor = 'transparent';
  container.style.color = labelColor;
  container.style.padding = '6px 8px';
  container.style.fontSize = '12px';
  container.style.lineHeight = '1.2';
  container.style.display = 'flex';
  container.style.flexDirection = 'column';
  container.style.alignItems = 'flex-start';
  container.style.pointerEvents = 'none';
  container.style.zIndex = '10';
  container.style.opacity = '0.5';

  const label = document.createElement('div');
  label.textContent = '1 µm';

  const bar = document.createElement('div');
  bar.style.height = '2px';
  bar.style.backgroundColor = labelColor;
  bar.style.outline = `1px solid ${rev_labelColor}`;
  bar.style.marginTop = '4px';
  bar.style.width = '80px';

  if (labelColor === 'white') {
    container.style.textShadow = '0 0 3px black';
  }

  container.appendChild(label);
  container.appendChild(bar);

  const formatLabel = (microns) => {
    if (microns >= 1000) {
      const millimeters = microns / 1000;
      if (millimeters >= 10) {
        return `${Math.round(millimeters)} mm`;
      }
      if (millimeters >= 1) {
        return `${Number(millimeters.toFixed(1))} mm`;
      }
    }

    if (microns >= 100) {
      return `${Math.round(microns)} µm`;
    }
    if (microns >= 10) {
      return `${Number(microns.toFixed(1))} µm`;
    }
    return `${Number(microns.toPrecision(2))} µm`;
  };

  const setVisible = (visible) => {
    container.style.display = visible ? 'flex' : 'none';
  };

  const update = ({ zoom }) => {
    const zoomFactor = Math.pow(2, zoom || 0);
    const micronsPerScreenPixel = micronsPerPixel / zoomFactor;
    const targetPixelWidth = 100;
    const rawMicrons = micronsPerScreenPixel * targetPixelWidth;
    const cappedMicrons = Math.min(rawMicrons, 1000);

    const magnitude = Math.pow(10, Math.floor(Math.log10(cappedMicrons)));
    const normalized = cappedMicrons / magnitude;

    let niceNormalized = 1;
    if (normalized > 5) {
      niceNormalized = 10;
    } else if (normalized > 2) {
      niceNormalized = 5;
    } else if (normalized > 1) {
      niceNormalized = 2;
    }

    const barMicrons = niceNormalized * magnitude;
    const barPixelWidth = barMicrons / micronsPerScreenPixel;

    label.textContent = formatLabel(barMicrons);
    bar.style.width = `${barPixelWidth}px`;
  };

  return { container, update, setVisible };
};
