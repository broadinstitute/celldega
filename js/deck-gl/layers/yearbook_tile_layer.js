import { OrthographicViewport } from '@deck.gl/core';
import { TileLayer } from 'deck.gl';

// TileLayer variant that requests tiles based on the union of all portraits in
// the yearbook grid. deck.gl's TileLayer only tracks one viewport when a layer
// is rendered across multiple views, so only the last viewport influences tile
// selection. By synthesizing a viewport that encloses every portrait, we make
// tile loading consistent across the grid while still sharing one TileLayer
// instance.
export class YearbookTileLayer extends TileLayer {
  _getUnionViewport() {
    const { yearbookWindows = [], yearbookZoom } = this.props;

    if (!Array.isArray(yearbookWindows) || yearbookWindows.length === 0) {
      return null;
    }

    const zoom = Number.isFinite(yearbookZoom)
      ? yearbookZoom
      : this.context.viewport?.zoom;

    if (!Number.isFinite(zoom)) return null;

    let minX = Infinity;
    let minY = Infinity;
    let maxX = -Infinity;
    let maxY = -Infinity;

    yearbookWindows.forEach((w) => {
      minX = Math.min(minX, w.minX);
      minY = Math.min(minY, w.minY);
      maxX = Math.max(maxX, w.maxX);
      maxY = Math.max(maxY, w.maxY);
    });

    if (!Number.isFinite(minX) || !Number.isFinite(minY) || !Number.isFinite(maxX) || !Number.isFinite(maxY)) {
      return null;
    }

    const centerX = (minX + maxX) / 2;
    const centerY = (minY + maxY) / 2;
    const spanX = Math.max(maxX - minX, 1);
    const spanY = Math.max(maxY - minY, 1);

    const scale = 2 ** zoom;
    const width = Math.max(Math.ceil(spanX * scale), 1);
    const height = Math.max(Math.ceil(spanY * scale), 1);

    return new OrthographicViewport({
      id: 'yearbook-union-viewport',
      target: [centerX, centerY, 0],
      zoom,
      width,
      height,
    });
  }

  _updateTileset() {
    const tileset = this.state.tileset;
    const { zRange, modelMatrix } = this.props;

    const viewport = this._getUnionViewport() || this.context.viewport;
    const frameNumber = tileset.update(viewport, { zRange, modelMatrix });
    const { isLoaded } = tileset;
    const loadingStateChanged = this.state.isLoaded !== isLoaded;
    const tilesetChanged = this.state.frameNumber !== frameNumber;

    if (isLoaded && (loadingStateChanged || tilesetChanged)) {
      this._onViewportLoad();
    }

    if (tilesetChanged) {
      this.setState({ frameNumber });
    }

    this.state.isLoaded = isLoaded;
  }
}

YearbookTileLayer.layerName = 'YearbookTileLayer';

