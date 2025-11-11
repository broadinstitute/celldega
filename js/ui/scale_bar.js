import { SolidPolygonLayer, TextLayer } from 'deck.gl';

import { get_layers_list } from '../deck-gl/utils/layers_ist';
import { hexToRgb } from '../utils/hexToRgb';

const BLUE_HEX = '#1e5bff';
const NICE_STEP_FACTORS = [1, 2, 5];
const NICE_EXPONENT_RANGE = { min: -3, max: 6 };
const TARGET_PIXEL_WIDTH = 80;
const MIN_PIXEL_WIDTH = 40;
const MAX_PIXEL_WIDTH = 160;
const BAR_THICKNESS_PX = 3;
const HORIZONTAL_MARGIN_PX = 24;
const VERTICAL_MARGIN_PX = 28;
const TEXT_GAP_PX = 6;
const TEXT_OFFSET_X_PX = 4;
const TEXT_SIZE_PX = 10;

const FONT_FAMILY =
  "-apple-system, BlinkMacSystemFont, 'San Francisco', 'Helvetica Neue', Helvetica, Arial, sans-serif";

const BLUE_RGBA = [...hexToRgb(BLUE_HEX), 255];

const DEFAULT_PIXEL_TO_MICRON_BY_TECH = {
  Chromium: 0.2125,
  Xenium: 0.1625,
  'Xenium Prime': 0.1625,
  'Visium HD': 0.5,
  'Visium HD FFPE': 0.5,
  'Visium HD Fresh Frozen': 0.5,
  'Visium-HD': 0.5,
  'Visium HD (CytAssist)': 0.5,
  Visium: 1,
  'Visium CytAssist': 1,
  MERFISH: 0.1,
  MERSCOPE: 0.1,
  'point-cloud': 1,
};

const formatLabel = (microns) => {
  if (microns >= 1000) {
    const millimeters = microns / 1000;
    const formatted = Number.isInteger(millimeters)
      ? millimeters.toString()
      : millimeters.toFixed(1);
    return `${formatted} mm`;
  }

  if (microns >= 1) {
    const formatted = Number.isInteger(microns)
      ? microns.toString()
      : microns.toFixed(1);
    return `${formatted} µm`;
  }

  const nanometers = microns * 1000;
  const formatted = Number.isInteger(nanometers)
    ? nanometers.toString()
    : nanometers.toFixed(1);
  return `${formatted} nm`;
};

const resolvePixelToMicron = (landscapeParameters = {}, override = null) => {
  if (typeof override === 'number' && Number.isFinite(override) && override > 0) {
    return override;
  }

  const { pixel_to_micron, technology } = landscapeParameters;

  if (typeof pixel_to_micron === 'number' && pixel_to_micron > 0) {
    return pixel_to_micron;
  }

  if (
    typeof pixel_to_micron === 'object' &&
    pixel_to_micron !== null &&
    typeof pixel_to_micron.value === 'number' &&
    pixel_to_micron.value > 0
  ) {
    return pixel_to_micron.value;
  }

  if (technology) {
    return DEFAULT_PIXEL_TO_MICRON_BY_TECH[technology] ?? 1;
  }

  return 1;
};

const chooseScaleMicrons = (micronsPerPixel) => {
  if (!micronsPerPixel || !Number.isFinite(micronsPerPixel) || micronsPerPixel <= 0) {
    return null;
  }

  const candidates = [];
  for (let exponent = NICE_EXPONENT_RANGE.min; exponent <= NICE_EXPONENT_RANGE.max; exponent += 1) {
    const base = 10 ** exponent;
    NICE_STEP_FACTORS.forEach((factor) => {
      candidates.push(factor * base);
    });
  }

  let chosenMicrons = null;
  let chosenPixels = null;
  let bestScore = Infinity;

  candidates.forEach((microns) => {
    const pixels = microns / micronsPerPixel;
    if (!Number.isFinite(pixels) || pixels <= 0) {
      return;
    }

    if (pixels < MIN_PIXEL_WIDTH || pixels > MAX_PIXEL_WIDTH) {
      return;
    }

    const score = Math.abs(pixels - TARGET_PIXEL_WIDTH);
    if (score < bestScore) {
      chosenMicrons = microns;
      chosenPixels = pixels;
      bestScore = score;
    }
  });

  if (!chosenMicrons) {
    candidates.forEach((microns) => {
      const pixels = microns / micronsPerPixel;
      if (!Number.isFinite(pixels) || pixels <= 0) {
        return;
      }

      const score = Math.abs(pixels - TARGET_PIXEL_WIDTH);
      if (score < bestScore) {
        chosenMicrons = microns;
        chosenPixels = pixels;
        bestScore = score;
      }
    });
  }

  if (!chosenMicrons || !Number.isFinite(chosenPixels) || chosenPixels <= 0) {
    return null;
  }

  const limitedPixels = Math.max(Math.min(chosenPixels, MAX_PIXEL_WIDTH), MIN_PIXEL_WIDTH);

  return {
    microns: chosenMicrons,
    pixels: limitedPixels,
  };
};

const applyLayerUpdates = (viz_state, barLayer, textLayer, deck_ist) => {
  viz_state.scale_bar.layers = {
    bar: barLayer,
    text: textLayer,
  };

  if (viz_state.layers_obj) {
    viz_state.layers_obj.scale_bar_bar_layer = barLayer;
    viz_state.layers_obj.scale_bar_text_layer = textLayer;
  }

  if (deck_ist) {
    if (typeof viz_state.scale_bar?.commit === 'function') {
      viz_state.scale_bar.commit(deck_ist);
    } else if (viz_state.layers_obj) {
      const layers_list = get_layers_list(viz_state.layers_obj, viz_state.close_up);
      deck_ist.setProps({ layers: layers_list });
    }
  }
};

export const attachScaleBar = (viz_state, options = {}) => {
  const normalizedOptions =
    options && typeof options === 'object' ? options : {};

  const barLayer = new SolidPolygonLayer({
    id: 'scale-bar-layer',
    data: [],
    pickable: false,
    visible: false,
    getPolygon: (d) => d.polygon,
    getFillColor: BLUE_RGBA,
    parameters: {
      depthTest: false,
    },
  });

  const textLayer = new TextLayer({
    id: 'scale-bar-text-layer',
    data: [],
    pickable: false,
    visible: false,
    getPosition: (d) => d.position,
    getText: (d) => d.text,
    getSize: (d) => d.size,
    sizeUnits: 'pixels',
    getColor: () => BLUE_RGBA,
    getTextAnchor: () => 'start',
    getAlignmentBaseline: () => 'bottom',
    fontFamily: FONT_FAMILY,
    outlineWidth: 0,
    parameters: {
      depthTest: false,
    },
  });

  viz_state.scale_bar = {
    layers: {
      bar: barLayer,
      text: textLayer,
    },
    visible: false,
    last_view_state: null,
    pixel_to_micron_override:
      typeof normalizedOptions.pixelToMicron === 'number' &&
      Number.isFinite(normalizedOptions.pixelToMicron) &&
      normalizedOptions.pixelToMicron > 0
        ? normalizedOptions.pixelToMicron
        : null,
  };

  return viz_state.scale_bar.layers;
};

export const hideScaleBar = (viz_state, deck_ist) => {
  if (!viz_state?.scale_bar?.layers) {
    return false;
  }

  if (viz_state.scale_bar.visible === false) {
    return false;
  }

  const barLayer = viz_state.scale_bar.layers.bar.clone({ visible: false });
  const textLayer = viz_state.scale_bar.layers.text.clone({ visible: false });

  viz_state.scale_bar.visible = false;

  applyLayerUpdates(viz_state, barLayer, textLayer, deck_ist);
  return true;
};

const computeBounds = (viewState, fallbackBounds) => {
  if (fallbackBounds) {
    return fallbackBounds;
  }

  if (!viewState || typeof viewState.zoom !== 'number') {
    return null;
  }

  const { target = [0, 0], width, height, zoom } = viewState;
  if (
    typeof width !== 'number' ||
    typeof height !== 'number' ||
    !Array.isArray(target) ||
    target.length < 2
  ) {
    return null;
  }

  const zoomFactor = 2 ** zoom;
  const halfWidthZoomed = width / (2 * zoomFactor);
  const halfHeightZoomed = height / (2 * zoomFactor);
  const [targetX, targetY] = target;

  return {
    min_x: targetX - halfWidthZoomed,
    max_x: targetX + halfWidthZoomed,
    min_y: targetY - halfHeightZoomed,
    max_y: targetY + halfHeightZoomed,
  };
};

export const refreshScaleBar = (viz_state, deck_ist, viewStateOverride = null) => {
  if (!viz_state?.scale_bar?.layers) {
    return false;
  }

  if (viewStateOverride) {
    viz_state.scale_bar.last_view_state = viewStateOverride;
  }

  const activeViewState = viz_state.scale_bar.last_view_state;
  if (!activeViewState || typeof activeViewState.zoom !== 'number') {
    return false;
  }

  const landscapeParameters = viz_state.img?.landscape_parameters;
  if (landscapeParameters?.technology === 'point-cloud') {
    return hideScaleBar(viz_state, deck_ist);
  }

  const pixelToMicron = resolvePixelToMicron(
    landscapeParameters,
    viz_state.scale_bar.pixel_to_micron_override
  );
  if (!pixelToMicron) {
    return hideScaleBar(viz_state, deck_ist);
  }

  const { zoom } = activeViewState;
  const zoomFactor = 2 ** zoom;
  if (!Number.isFinite(zoomFactor) || zoomFactor <= 0) {
    return hideScaleBar(viz_state, deck_ist);
  }

  const bounds = computeBounds(activeViewState, viz_state.bounds);
  if (!bounds) {
    return hideScaleBar(viz_state, deck_ist);
  }

  const micronsPerPixel = pixelToMicron / zoomFactor;
  const selection = chooseScaleMicrons(micronsPerPixel);

  if (!selection) {
    return hideScaleBar(viz_state, deck_ist);
  }

  const { microns, pixels } = selection;

  const baseX = bounds.min_x + HORIZONTAL_MARGIN_PX / zoomFactor;
  const baseY =
    bounds.max_y - VERTICAL_MARGIN_PX / zoomFactor - BAR_THICKNESS_PX / zoomFactor;

  const lengthWorld = pixels / zoomFactor;
  const thicknessWorld = BAR_THICKNESS_PX / zoomFactor;

  const barData = [
    {
      polygon: [
        [baseX, baseY],
        [baseX + lengthWorld, baseY],
        [baseX + lengthWorld, baseY + thicknessWorld],
        [baseX, baseY + thicknessWorld],
      ],
    },
  ];

  const textX = baseX + TEXT_OFFSET_X_PX / zoomFactor;
  const textY = baseY - TEXT_GAP_PX / zoomFactor;
  const textData = [
    {
      position: [textX, textY],
      text: formatLabel(microns),
      size: TEXT_SIZE_PX,
    },
  ];

  const barLayer = viz_state.scale_bar.layers.bar.clone({
    data: barData,
    visible: true,
  });

  const textLayer = viz_state.scale_bar.layers.text.clone({
    data: textData,
    visible: true,
  });

  viz_state.scale_bar.visible = true;

  applyLayerUpdates(viz_state, barLayer, textLayer, deck_ist);
  return true;
};
