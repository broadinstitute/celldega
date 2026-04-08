import { BitmapLayer, Deck, LineLayer, ScatterplotLayer, TileLayer } from 'deck.gl';

const Observable = (initialValue) => {
  let value = initialValue;
  const subscribers = new Set();
  return {
    get: () => value,
    set: (newValue) => {
      if (value === newValue) return;
      value = newValue;
      subscribers.forEach((fn) => fn(value));
    },
    subscribe: (fn, options = { immediate: true }) => {
      subscribers.add(fn);
      if (options.immediate) fn(value);
      return () => subscribers.delete(fn);
    },
  };
};

const createStore = () => ({
  stations: Observable([]),
  edge_index: Observable({}),
  click_info: Observable({}),
  selected_rows: Observable([]),
  selected_cols: Observable([]),
  width: Observable(560),
  height: Observable(800),
  debug: Observable(false),
  focus: Observable(''),
  highlights: Observable([]),
  edges: Observable([]),
  deck_check: Observable({ inputs: true, computed: true, layers: true }),
  deck_ready: Observable(false),
  palette_rgb: Observable([]),
});

const log = (store, ...args) => {
  if (store.debug.get()) console.log('[bike-map]', ...args);
};

const sameList = (a, b) => {
  if (!Array.isArray(a) || !Array.isArray(b)) return false;
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i += 1) if (a[i] !== b[i]) return false;
  return true;
};

const setDerivedState = (store, { focus, highlights, edges }) => {
  const curFocus = store.focus.get() || '';
  const curHighlights = store.highlights.get() || [];
  const curEdges = store.edges.get() || [];

  const nextFocus = focus || '';
  const nextHighlights = highlights || [];
  const nextEdges = edges || [];

  let changed = false;
  if (curFocus !== nextFocus) {
    store.focus.set(nextFocus);
    changed = true;
  }
  if (!sameList(curHighlights, nextHighlights)) {
    store.highlights.set(nextHighlights);
    changed = true;
  }
  const curStr = JSON.stringify(curEdges);
  const nextStr = JSON.stringify(nextEdges);
  if (curStr !== nextStr) {
    store.edges.set(nextEdges);
    changed = true;
  }
  return changed;
};

function basemapLayer() {
  return new TileLayer({
    id: 'bike-basemap',
    data: 'https://a.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png',
    minZoom: 0,
    maxZoom: 19,
    tileSize: 256,
    renderSubLayers: (props) => {
      if (!props.data || !props.tile) return null;
      let west;
      let south;
      let east;
      let north;
      const bb = props.tile.boundingBox;
      if (bb && bb.length === 2) {
        [[west, south], [east, north]] = bb;
      } else if (props.tile.bbox && 'west' in props.tile.bbox) {
        ({ west, south, east, north } = props.tile.bbox);
      } else {
        return null;
      }
      return new BitmapLayer(props, {
        id: `${props.id}-bitmap`,
        data: [0],
        image: props.data,
        bounds: [west, south, east, north],
      });
    },
  });
}

/** Okabe–Ito (colorblind-safe) first, then Celldega `clust.constants._COLOR_PALETTE` — keep in sync with notebook `STATION_PALETTE_HEX`. */
const STATION_PALETTE_HEX = [
  '#E69F00', '#56B4E9', '#009E73', '#F0E442', '#0072B2', '#D55E00', '#CC79A7',
  '#393b79', '#aec7e8', '#ff7f0e', '#ffbb78', '#98df8a', '#bcbd22', '#404040',
  '#ff9896', '#c5b0d5', '#8c5648', '#1f77b4', '#5254a3', '#FFDB58', '#c49c94',
  '#e377c2', '#7f7f7f', '#2ca02c', '#9467bd', '#dbdb8d', '#17becf', '#637939',
  '#6b6ecf', '#9c9ede', '#d62728', '#8ca252', '#8c6d31', '#bd9e39', '#e7cb94',
  '#843c39', '#ad494a', '#d6616b', '#7b4173', '#a55194', '#ce6dbd', '#de9ed6',
];

function hexToRgb(hex) {
  const h = String(hex).replace('#', '');
  if (h.length !== 6) return [145, 150, 170];
  return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
}

const DEFAULT_PALETTE_RGB = STATION_PALETTE_HEX.map(hexToRgb);

function resolvePaletteRgb(store) {
  const raw = store.palette_rgb.get();
  if (Array.isArray(raw) && raw.length > 0) {
    return raw.map((row) => {
      if (Array.isArray(row) && row.length >= 3) {
        return [Number(row[0]), Number(row[1]), Number(row[2])];
      }
      return [145, 150, 170];
    });
  }
  return DEFAULT_PALETTE_RGB;
}

/** cluster_id 0 = unclustered / unknown (matches Clustergram label "0"). */
const CLUSTER_UNKNOWN_RGB = [176, 180, 190];

/** Traffic view: stations with no edge to the focused hub. */
const TRAFFIC_UNCONNECTED_RGBA = [168, 172, 180, 118];

function clusterRgbFromId(clusterId, paletteRgb) {
  const id = Number(clusterId);
  if (!Number.isFinite(id) || id <= 0) return CLUSTER_UNKNOWN_RGB;
  const pal = paletteRgb.length ? paletteRgb : DEFAULT_PALETTE_RGB;
  const c = pal[(id - 1) % pal.length];
  return [c[0], c[1], c[2]];
}

function clusterFillWithAlpha(clusterId, alpha, paletteRgb) {
  const [r, g, b] = clusterRgbFromId(clusterId, paletteRgb);
  return [r, g, b, alpha];
}

function clusterFillColor(clusterId, paletteRgb) {
  return clusterFillWithAlpha(clusterId, 228, paletteRgb);
}

/** Same endpoints as LineLayer getColor: out red, in blue. */
const FLOW_OUT_RGB = [255, 70, 70];
const FLOW_IN_RGB = [70, 150, 255];

function flowBlendRgb(outW, inW) {
  const o = Math.max(0, Number(outW) || 0);
  const i = Math.max(0, Number(inW) || 0);
  const sum = o + i;
  if (sum <= 0) return [145, 150, 170];
  const t = o / sum;
  const lerp = (a, b, x) => Math.round(a + (b - a) * x);
  return [
    lerp(FLOW_IN_RGB[0], FLOW_OUT_RGB[0], t),
    lerp(FLOW_IN_RGB[1], FLOW_OUT_RGB[1], t),
    lerp(FLOW_IN_RGB[2], FLOW_OUT_RGB[2], t),
  ];
}

function flowBlendWithAlpha(outW, inW, alpha) {
  const [r, g, b] = flowBlendRgb(outW, inW);
  return [r, g, b, alpha];
}

function fitViewState(stations) {
  if (!stations.length) return { longitude: -73.98, latitude: 40.75, zoom: 10.5, pitch: 0, bearing: 0 };
  let minLat = Infinity; let maxLat = -Infinity; let minLng = Infinity; let maxLng = -Infinity;
  for (const s of stations) {
    const lat = Number(s.lat); const lng = Number(s.lng);
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) continue;
    minLat = Math.min(minLat, lat); maxLat = Math.max(maxLat, lat);
    minLng = Math.min(minLng, lng); maxLng = Math.max(maxLng, lng);
  }
  const latitude = (minLat + maxLat) / 2;
  const longitude = (minLng + maxLng) / 2;
  const span = Math.max(maxLat - minLat, maxLng - minLng, 0.02);
  const zoom = Math.min(14, Math.max(9, 12 - Math.log2(span * 80)));
  return { latitude, longitude, zoom, pitch: 0, bearing: 0 };
}

function render({ model, el }) {
  const store = createStore();
  const root = document.createElement('div');
  root.style.background = '#e2e4e8';
  root.style.borderRadius = '4px';
  root.style.overflow = 'hidden';
  el.appendChild(root);

  let deck = null;
  let raf = 0;
  let renderVersion = 0;
  let lastSig = "";
  let lastActionKey = null;
  let lastActionSeq = -1;
  /** Increments when linked Clustergram traits change (jslink / static HTML); drives label+mat toggle. */
  let linkInteractionSeq = 0;
  let linkSnap = { ci: '', rows: '', cols: '' };

  const getLinkedWeights = () => {
    const focus = store.focus.get();
    const idx = store.edge_index.get() || {};
    const out = new Map();
    const inn = new Map();
    if (!focus || !idx[focus]) return { out, inn };
    for (const e of idx[focus].out || []) out.set(e.name, Number(e.w) || 0);
    for (const e of idx[focus].in || []) inn.set(e.name, Number(e.w) || 0);
    return { out, inn };
  };

  const computeStateFromInputs = () => {
    const info = store.click_info.get() || {};
    const t = String(info.type || '').replace('-', '_');
    const v = info.value || {};
    const idx = store.edge_index.get() || {};
    const seq = linkInteractionSeq;
    const sig = JSON.stringify({
      t,
      v,
      rows: store.selected_rows.get() || [],
      cols: store.selected_cols.get() || [],
    });
    if (sig === lastSig) {
      log(store, 'compute skip (same signature)', t);
      return;
    }
    lastSig = sig;
    log(store, 'compute start', t, 'rows', (store.selected_rows.get()||[]).length, 'cols', (store.selected_cols.get()||[]).length);

    const setState = (focus, highlights, edges) =>
      setDerivedState(store, { focus, highlights, edges });

    const stationFrom = (raw) => {
      const txt = String(raw || '').trim();
      if (idx[txt]) return txt;
      if (txt.includes('|')) {
        const rhs = txt.split('|', 2)[1].trim();
        if (idx[rhs]) return rhs;
      }
      return txt;
    };

    if (t === 'row_label' || t === 'col_label') {
      const name = stationFrom(v.name);
      const actionKey = `${t}:${name}`;
      if (actionKey === lastActionKey && seq !== lastActionSeq) {
        setState('', [], []);
        lastActionKey = null;
        lastActionSeq = seq;
        log(store, 'label toggle off', t, name);
        return;
      }
      const bucket = idx[name] || { out: [], in: [] };
      const edges = [
        ...(bucket.out || []).map((e) => ({
          source_name: name,
          target_name: e.name,
          direction: 'out',
          opacity: e.opacity,
          weight: e.w,
          geom_share: e.geom_share,
          trips: e.trips,
          source: e.source,
          target: e.target,
        })),
        ...(bucket.in || []).map((e) => ({
          source_name: e.name,
          target_name: name,
          direction: 'in',
          opacity: e.opacity,
          weight: e.w,
          geom_share: e.geom_share,
          trips: e.trips,
          source: e.source,
          target: e.target,
        })),
      ];
      setState(name, name ? [name] : [], edges);
      lastActionKey = actionKey;
      lastActionSeq = seq;
      log(store, 'label', t, name, 'edges', edges.length);
      return;
    }

    if (t === 'mat_value') {
      const row = stationFrom((v.row || {}).name);
      const col = stationFrom((v.col || {}).name);
      const actionKey = `mat:${col}->${row}`;
      if (actionKey === lastActionKey && seq !== lastActionSeq) {
        setState('', [], []);
        lastActionKey = null;
        lastActionSeq = seq;
        log(store, 'mat toggle off', col, row);
        return;
      }
      const p = Number(v.value || 0);
      const src = idx[col]?.coord;
      const dst = idx[row]?.coord;
      const outEdge = (idx[col]?.out || []).find((e) => e.name === row);
      const g = outEdge != null ? Number(outEdge.geom_share) : NaN;
      const geom = Number.isFinite(g) && g > 0 ? g : Math.sqrt(Math.max(0, p));
      const edge = src && dst
        ? [{
          source_name: col,
          target_name: row,
          direction: 'direct',
          opacity: Math.max(0.2, Math.min(0.98, p * 3)),
          weight: p,
          geom_share: geom,
          trips: outEdge?.trips,
          source: src,
          target: dst,
        }]
        : [];
      setState('', [col, row].filter(Boolean), edge);
      lastActionKey = actionKey;
      lastActionSeq = seq;
      log(store, 'mat', col, '->', row, p);
      return;
    }

    if (t === 'row_dendro' || t === 'col_dendro') {
      const fromClick = (v.selected_names || []).map(stationFrom).filter((n) => idx[n]);
      const rows = (store.selected_rows.get() || []).map(stationFrom).filter((n) => idx[n]);
      const cols = (store.selected_cols.get() || []).map(stationFrom).filter((n) => idx[n]);

      if (v.is_unselecting || (Array.isArray(v.selected_names) && v.selected_names.length === 0 && rows.length === 0 && cols.length === 0)) {
        setState('', [], []);
        lastActionKey = null;
        lastActionSeq = seq;
        log(store, 'dendro clear', t);
        return;
      }

      // Prefer axis traitlets (they represent full live dendrogram selection);
      // click_info.selected_names can be a smaller interim payload.
      const names = t === 'col_dendro'
        ? (cols.length ? cols : (fromClick.length ? fromClick : rows))
        : (rows.length ? rows : (fromClick.length ? fromClick : cols));

      // No actionKey "toggle off" vs linkInteractionSeq here: dendrogram updates can
      // re-send the same selection across frames; toggling off would flicker.
      const actionKey = `${t}:${names.slice().sort().join('|')}`;
      setState('', names, []);
      lastActionKey = actionKey;
      lastActionSeq = seq;
      log(store, 'dendro', t, 'names', names.length, 'rows', rows.length, 'cols', cols.length);
      return;
    }

    if (t === 'cat_value') {
      const axis = v.axis;
      const attrIndex = v.attr_index;
      const catVal = v.value;
      const rawNames = Array.isArray(v.node_names) ? v.node_names : [];
      const names = [...new Set(rawNames.map(stationFrom).filter((n) => idx[n]))];
      const actionKey = `cat:${axis}:${attrIndex}:${String(catVal)}`;
      if (actionKey === lastActionKey && seq !== lastActionSeq) {
        setState('', [], []);
        lastActionKey = null;
        lastActionSeq = seq;
        log(store, 'cat toggle off', axis, catVal);
        return;
      }
      setState('', names, []);
      lastActionKey = actionKey;
      lastActionSeq = seq;
      log(store, 'cat', axis, 'value', catVal, 'stations', names.length);
      return;
    }
  };

  const buildLayers = () => {
    const stations = store.stations.get() || [];
    const focus = store.focus.get();
    const highlightArr = store.highlights.get() || [];
    const highlights = new Set(highlightArr);
    const edges = store.edges.get() || [];
    const stationNameSet = new Set(stations.map((d) => d.name));
    const overlap = highlightArr.filter((n) => stationNameSet.has(n));
    log(store, 'buildLayers', {
      focus,
      highlightCount: highlightArr.length,
      overlap: overlap.length,
      sample: overlap.slice(0, 5),
      stations: stations.length,
      edges: edges.length,
      version: renderVersion,
    });
    const hasSel = Boolean(focus) || highlights.size > 0;
    const { out, inn } = getLinkedWeights();
    const highlightKey = Array.from(highlights).sort().join('|');
    const outKey = Array.from(out.entries())
      .map(([k, v]) => `${k}:${v}`)
      .sort()
      .join('|');
    const inKey = Array.from(inn.entries())
      .map(([k, v]) => `${k}:${v}`)
      .sort()
      .join('|');
    const styleKey = `${focus}__${highlightKey}__${outKey}__${inKey}__${hasSel}`;

    let peakLinkWeight = 0;
    for (const v of out.values()) peakLinkWeight = Math.max(peakLinkWeight, v);
    for (const v of inn.values()) peakLinkWeight = Math.max(peakLinkWeight, v);

    let hubSumOut = 0;
    let hubSumIn = 0;
    for (const v of out.values()) hubSumOut += Number(v) || 0;
    for (const v of inn.values()) hubSumIn += Number(v) || 0;

    const linkedRadius = (n) => {
      const wo = out.has(n) ? Math.min(1, Math.max(0, out.get(n) || 0)) : 0;
      const wi = inn.has(n) ? Math.min(1, Math.max(0, inn.get(n) || 0)) : 0;
      const w = Math.max(wo, wi);
      return 100 + 125 * Math.sqrt(w);
    };

    const focusHubRadius = () =>
      178 + 48 * Math.sqrt(Math.min(1, peakLinkWeight));

    const palRgb = resolvePaletteRgb(store);

    // Force a new data container each render so style-only updates always propagate
    const pointData = stations.map((d) => d);

    const points = new ScatterplotLayer({
      id: 'bike-stations',
      data: pointData,
      pickable: true,
      radiusUnits: 'meters',
      radiusMinPixels: 3,
      radiusMaxPixels: 56,
      getPosition: (d) => [Number(d.lng), Number(d.lat)],
      getRadius: (d) => {
        const n = d.name;
        if (focus && n === focus) return focusHubRadius();
        if (focus && (out.has(n) || inn.has(n))) return linkedRadius(n);
        if (highlights.has(n)) return 90;
        return hasSel ? 70 : 90;
      },
      getFillColor: (d) => {
        const n = d.name;
        // Focus / traffic: hub + neighbors use red↔blue blend from out vs in weight (lines still encode direction/width).
        if (focus) {
          if (n === focus) {
            return flowBlendWithAlpha(hubSumOut, hubSumIn, 248);
          }
          if (out.has(n) || inn.has(n)) {
            const wo = out.has(n) ? Math.max(0, out.get(n) || 0) : 0;
            const wi = inn.has(n) ? Math.max(0, inn.get(n) || 0) : 0;
            const w = Math.max(wo, wi);
            const a = Math.round(148 + 102 * Math.sqrt(Math.min(1, w)));
            return flowBlendWithAlpha(wo, wi, a);
          }
          return TRAFFIC_UNCONNECTED_RGBA;
        }
        // Dendrogram / matrix highlights (no focus): keep dendrogram cluster colors
        if (highlights.size > 0) {
          const c = clusterFillColor(d.cluster_id, palRgb);
          if (highlights.has(n)) return [c[0], c[1], c[2], 242];
          return [c[0], c[1], c[2], 36];
        }
        return clusterFillColor(d.cluster_id, palRgb);
      },
      updateTriggers: {
        getRadius: [styleKey, renderVersion],
        getFillColor: [styleKey, renderVersion],
      },
      onClick: (info) => {
        if (!info.object) return;
        const n = info.object.name;
        if (store.focus.get() === n) {
          setDerivedState(store, { focus: '', highlights: [], edges: [] });
          lastActionKey = null;
          scheduleRender();
          log(store, 'map toggle off', n);
          return;
        }
        const idx = store.edge_index.get() || {};
        const bucket = idx[n] || { out: [], in: [] };
        const e = [
          ...(bucket.out || []).map((x) => ({
            source_name: n,
            target_name: x.name,
            direction: 'out',
            opacity: x.opacity,
            weight: x.w,
            geom_share: x.geom_share,
            trips: x.trips,
            source: x.source,
            target: x.target,
          })),
          ...(bucket.in || []).map((x) => ({
            source_name: x.name,
            target_name: n,
            direction: 'in',
            opacity: x.opacity,
            weight: x.w,
            geom_share: x.geom_share,
            trips: x.trips,
            source: x.source,
            target: x.target,
          })),
        ];
        setDerivedState(store, { focus: n, highlights: [n], edges: e });
        lastActionKey = null;
        scheduleRender();
        log(store, 'map click', n, 'edges', e.length);
      },
    });

    // geom_share in [0,1]; scale like matrix emphasis (stronger than before, pixel units).
    const lineWidthFor = (d) => {
      if (d.direction === 'direct') {
        const g = Number(d.geom_share);
        const x = Number.isFinite(g) ? Math.min(1, Math.max(0, g)) : 0;
        return 4 + 14 * x;
      }
      const g = Number(d.geom_share);
      if (Number.isFinite(g) && g > 0) {
        const x = Math.min(1, g);
        return 4 + 22 * x ** 0.92;
      }
      return 2.5;
    };

    const lines = new LineLayer({
      id: 'bike-flow-lines',
      data: edges,
      widthUnits: 'pixels',
      getSourcePosition: (d) => d.source,
      getTargetPosition: (d) => d.target,
      getWidth: lineWidthFor,
      updateTriggers: {
        getWidth: [styleKey, renderVersion],
      },
      getColor: (d) => {
        const a = Math.round(Math.max(0, Math.min(1, Number(d.opacity) || 0)) * 255);
        if (d.direction === 'in') return [70, 150, 255, a];
        if (d.direction === 'out') return [255, 70, 70, a];
        return [255, 240, 120, a];
      },
    });

    return [basemapLayer(), lines, points];
  };

  let pendingProps = null;

  const prepareDeckProps = () => {
    const stations = store.stations.get() || [];
    const w = Number(store.width.get() || 560);
    const h = Number(store.height.get() || 800);
    root.style.width = `${w}px`;
    root.style.height = `${h}px`;


    const props = {
      parent: root,
      width: w,
      height: h,
      controller: true,
      layers: buildLayers(),
      getTooltip: ({ object, layer }) => {
        if (!object || layer.id !== 'bike-stations') return null;
        const sid = object.station_id != null ? String(object.station_id) : '';
        const nm = object.name != null ? String(object.name) : '';
        const html = sid
          ? `<div style="font:12px system-ui,sans-serif;"><b>id</b> ${sid}<br/><b>name</b> ${nm}</div>`
          : `<div style="font:12px system-ui,sans-serif;">${nm}</div>`;
        return {
          html,
          style: {
            backgroundColor: 'rgba(255,255,255,0.94)',
            color: '#1a1d24',
            padding: '6px 10px',
            borderRadius: '4px',
            boxShadow: '0 1px 4px rgba(0,0,0,0.18)',
          },
        };
      },
    };

    if (!deck) {
      deck = new Deck({ ...props, initialViewState: fitViewState(stations) });
      log(store, 'deck init', 'stations', stations.length);
      pendingProps = null;
      return;
    }

    pendingProps = props;
  };

  const applyDeckProps = () => {
    if (deck && pendingProps) {
      deck.setProps(pendingProps);
      if (typeof deck.redraw === 'function') deck.redraw(true);
      log(store, 'deck setProps', {
        layers: pendingProps.layers.length,
        highlights: (store.highlights.get() || []).length,
        edges: (store.edges.get() || []).length,
        version: renderVersion,
      });
      pendingProps = null;
    }
  };

  store.deck_check.subscribe(
    (check) => {
      const ready = Object.values(check).every((v) => v === true);
      if (store.deck_ready.get() !== ready) store.deck_ready.set(ready);
    },
    { immediate: true }
  );

  store.deck_ready.subscribe(
    (ready) => {
      if (!ready) return;
      log(store, 'deck_ready -> apply');
      applyDeckProps();
    },
    { immediate: false }
  );

  const scheduleRender = () => {
    if (raf) return;
    raf = requestAnimationFrame(() => {
      raf = 0;
      renderVersion += 1;
      log(store, 'flush start', { version: renderVersion });
      store.deck_check.set({ inputs: false, computed: false, layers: false });

      // 1) inputs considered synced for this frame
      store.deck_check.set({ ...store.deck_check.get(), inputs: true });

      // 2) derive interaction state
      computeStateFromInputs();
      store.deck_check.set({ ...store.deck_check.get(), computed: true });

      // 3) prepare deck props (or init deck)
      prepareDeckProps();
      store.deck_check.set({ ...store.deck_check.get(), layers: true });

      log(store, 'flush end', store.deck_check.get());
    });
  };

  // subscriptions: any change schedules one render pass
  [
    store.stations,
    store.edge_index,
    store.click_info,
    store.selected_rows,
    store.selected_cols,
    store.width,
    store.height,
    store.palette_rgb,
  ].forEach((obs) => obs.subscribe(() => scheduleRender(), { immediate: false }));

  const syncFromModel = () => {
    const ci = JSON.stringify(model.get('click_info') || {});
    const rows = JSON.stringify(model.get('selected_rows') || []);
    const cols = JSON.stringify(model.get('selected_cols') || []);
    if (ci !== linkSnap.ci || rows !== linkSnap.rows || cols !== linkSnap.cols) {
      linkSnap = { ci, rows, cols };
      linkInteractionSeq += 1;
    }
    log(store, 'syncFromModel start');
    store.stations.set(model.get('stations') || []);
    store.palette_rgb.set(model.get('palette_rgb') || []);
    store.edge_index.set(model.get('edge_index') || {});
    store.click_info.set(model.get('click_info') || {});
    store.selected_rows.set(model.get('selected_rows') || []);
    store.selected_cols.set(model.get('selected_cols') || []);
    store.width.set(model.get('width') || 560);
    store.height.set(model.get('height') || 800);
    store.debug.set(Boolean(model.get('debug')));
    log(store, 'syncFromModel done', {
      linkSeq: linkInteractionSeq,
      rows: (store.selected_rows.get() || []).length,
      cols: (store.selected_cols.get() || []).length,
      clickType: (store.click_info.get() || {}).type || null,
    });
    scheduleRender();
  };

  [
    'stations',
    'edge_index',
    'click_info',
    'selected_rows',
    'selected_cols',
    'width',
    'height',
    'debug',
    'palette_rgb',
  ].forEach((name) => model.on(`change:${name}`, syncFromModel));

  syncFromModel();

  return () => {
    if (raf) cancelAnimationFrame(raf);
    if (deck) deck.finalize();
  };
}

export default { render };
