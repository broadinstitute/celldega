import { Deck } from 'deck.gl';

export const ini_deck_sst = (root, width, height) => {
  const deck_sst = new Deck({
    parent: root,
    controller: { doubleClickZoom: false },
    width,
    height,
    // Enable raster capture (canvas.toDataURL) -- see landscape captureRaster().
    deviceProps: { type: 'webgl', preserveDrawingBuffer: true },
  });

  return deck_sst;
};
