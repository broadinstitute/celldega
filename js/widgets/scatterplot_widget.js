import {
  COORDINATE_SYSTEM,
  Deck,
  OrthographicView,
  ScatterplotLayer,
} from 'deck.gl';

import { create_obs_store } from '../obs_store/obs_store';
import { arrayBufferToArrowTable } from '../read_parquet/arrayBufferToArrowTable';
import { getTableColumnArray } from '../read_parquet/table_accessors';
import {
  cellsInPolygon,
  prepareScatterplot,
} from '../scatterplot/scatterplot_data';

const svgNamespace = 'http://www.w3.org/2000/svg';

const makeElement = (tag, style = {}, text = '') => {
  const element = document.createElement(tag);
  Object.assign(element.style, style);
  element.textContent = text;
  return element;
};

const pointColor = (value) => {
  if (Array.isArray(value)) return value.slice(0, 3);
  if (/^#[0-9a-f]{6}$/i.test(value || '')) {
    return [1, 3, 5].map((offset) =>
      parseInt(value.slice(offset, offset + 2), 16)
    );
  }
  return [55, 126, 184];
};

const formatTick = (value) => {
  if (Math.abs(value) < 1e-10) return '0';
  if (Math.abs(value) >= 10000 || Math.abs(value) < 0.001) {
    return value.toExponential(1);
  }
  return Number(value.toPrecision(3)).toString();
};

/** A standalone, instance-scoped cell scatterplot with observable render state. */
export const render_scatterplot = ({ model, el }) => {
  const store = create_obs_store();
  const listeners = [];
  const subscriptions = [];
  const domListeners = [];
  let disposed = false;
  let parseRevision = 0;
  let animationTimer = null;
  let deck = null;
  let rasterPending = false;
  let resizeObserver = null;

  const getState = () => store.scatterplot_state.get();
  const setState = (patch) => {
    if (!disposed) store.scatterplot_state.set({ ...getState(), ...patch });
  };
  const on = (element, event, handler) => {
    element.addEventListener(event, handler);
    domListeners.push(() => element.removeEventListener(event, handler));
  };
  const watch = (name, handler) => {
    model.on(`change:${name}`, handler);
    listeners.push([`change:${name}`, handler]);
  };

  const root = makeElement('div', {
    display: 'flex',
    flexDirection: 'column',
    minWidth: '260px',
    fontFamily:
      '-apple-system, BlinkMacSystemFont, "San Francisco", "Helvetica Neue", Helvetica, Arial, sans-serif',
    fontSize: '11px',
    color: '#47515b',
    background: '#fff',
    border: '1px solid #d3d3d3',
    boxSizing: 'border-box',
  });
  root.className = 'celldega-scatterplot';
  const toolbar = makeElement('div', {
    display: 'flex',
    flexWrap: 'wrap',
    gap: '6px',
    alignItems: 'end',
    padding: '5px',
    borderBottom: '1px solid #d3d3d3',
  });
  const frame = makeElement('div', {
    flex: '1 1 auto',
    minHeight: '160px',
    position: 'relative',
    overflow: 'hidden',
  });
  const plot = makeElement('div', {
    position: 'absolute',
    left: '64px',
    right: '22px',
    top: '14px',
    bottom: '52px',
  });
  const canvas = makeElement('canvas', { position: 'absolute', inset: '0' });
  canvas.setAttribute(
    'aria-label',
    'Cell scatterplot. Use Gate to select a rectangle of cells.'
  );
  const axes = document.createElementNS(svgNamespace, 'svg');
  Object.assign(axes.style, {
    position: 'absolute',
    inset: '0',
    width: '100%',
    height: '100%',
    pointerEvents: 'none',
  });
  axes.setAttribute('aria-hidden', 'true');
  const gateOverlay = makeElement('div', {
    position: 'absolute',
    inset: '0',
    display: 'none',
    cursor: 'crosshair',
    touchAction: 'none',
  });
  gateOverlay.setAttribute('aria-label', 'Drag a rectangle to select cells');
  const gateRect = makeElement('div', {
    position: 'absolute',
    display: 'none',
    border: '1px solid #2f74ff',
    background: '#2f74ff20',
    pointerEvents: 'none',
    boxSizing: 'border-box',
  });
  gateOverlay.appendChild(gateRect);
  const tooltip = makeElement('div', {
    position: 'absolute',
    display: 'none',
    pointerEvents: 'none',
    zIndex: '2',
    padding: '7px 9px',
    background: '#172b3fee',
    color: '#fff',
    borderRadius: '4px',
    whiteSpace: 'pre-line',
    maxWidth: '240px',
  });
  const footer = makeElement('div', {
    padding: '4px 5px',
    borderTop: '1px solid #d3d3d3',
    minHeight: '18px',
  });
  footer.setAttribute('role', 'status');
  plot.append(canvas, gateOverlay);
  frame.append(plot, axes, tooltip);
  root.append(toolbar, frame, footer);
  el.appendChild(root);

  const makeControl = (label, tag = 'select') => {
    const holder = makeElement('label', {
      display: 'flex',
      flexDirection: 'column',
      gap: '3px',
    });
    holder.appendChild(
      makeElement('span', { fontSize: '10px', fontWeight: '600' }, label)
    );
    const control = makeElement(tag, {
      height: '24px',
      border: '1px solid #d3d3d3',
      borderRadius: '0',
      padding: '1px 2px',
      fontSize: '11px',
      fontFamily: 'inherit',
      boxSizing: 'border-box',
      background: '#fff',
      color: '#243746',
      maxWidth: '150px',
    });
    control.setAttribute('aria-label', label);
    holder.appendChild(control);
    toolbar.appendChild(holder);
    return control;
  };
  const controls = {
    view: makeControl('View'),
    x: makeControl('X gene', 'input'),
    x_scale: makeControl('X scale'),
    y: makeControl('Y gene', 'input'),
    y_scale: makeControl('Y scale'),
    color_by: makeControl('Color'),
    layer: makeControl('Expression'),
  };
  const geneList = makeElement('datalist');
  geneList.id = `celldega-genes-${globalThis.crypto?.randomUUID?.() || Math.random().toString(36).slice(2)}`;
  root.appendChild(geneList);
  [controls.x, controls.y].forEach((input) => {
    input.setAttribute('list', geneList.id);
    input.setAttribute('autocomplete', 'off');
    input.style.width = '120px';
  });
  const setOptions = (select, entries) => {
    select.replaceChildren(
      ...entries.map(([value, label]) => {
        const option = makeElement('option', {}, label);
        option.value = value;
        return option;
      })
    );
  };
  [controls.x_scale, controls.y_scale].forEach((control) => {
    setOptions(control, [
      ['linear', 'Linear'],
      ['log1p', 'Log(1 + x)'],
    ]);
  });
  const gateButton = makeElement('button', {}, 'GATE');
  const clearButton = makeElement('button', {}, 'CLEAR');
  const resetButton = makeElement('button', {}, 'RESET');
  [gateButton, clearButton, resetButton].forEach((button) => {
    Object.assign(button.style, {
      height: '24px',
      border: 'none',
      padding: '1px 2px',
      background: 'none',
      color: 'blue',
      fontSize: '11px',
      fontWeight: '700',
      fontFamily: 'inherit',
      userSelect: 'none',
      cursor: 'pointer',
    });
    button.type = 'button';
    toolbar.appendChild(button);
  });
  gateButton.title =
    'Drag a rectangle to select cells; hold Shift to add cells';
  clearButton.title = 'Clear cell selection';

  store.scatterplot_state.set({
    rows: [],
    prepared: prepareScatterplot([]),
    meta: {},
    settings: {},
    size: { width: 500, height: 400 },
    viewState: { target: [0, 0, 0], zoom: 7 },
    gateMode: false,
    drag: null,
    loading: false,
    error: '',
    animating: false,
  });
  store.selected_cells.set(model.get('selected_cells') || []);

  function fitView() {
    const { size } = getState();
    setState({
      viewState: {
        target: [0, 0, 0],
        zoom: Math.log2(Math.max(1, Math.min(size.width, size.height)) / 2.2),
      },
    });
  }

  function selectCells(ids, additive = false) {
    const selected = [
      ...new Set(additive ? [...store.selected_cells.get(), ...ids] : ids),
    ];
    store.selected_cells.set(selected);
    model.set('selected_cells', selected);
    model.set('click_info', {
      type: 'cells_selection',
      value: { cell_ids: selected },
    });
    model.save_changes();
  }

  function drawAxes() {
    const state = getState();
    const { width, height } = state.size;
    const { zoom, target } = state.viewState;
    const scale = Math.pow(2, zoom);
    const project = ([x, y]) => [
      64 + width / 2 + (x - target[0]) * scale,
      14 + height / 2 - (y - target[1]) * scale,
    ];
    const bottom = 14 + height;
    const nodes = [];
    const addSvg = (tag, attrs, text = '') => {
      const node = document.createElementNS(svgNamespace, tag);
      Object.entries(attrs).forEach(([key, value]) =>
        node.setAttribute(key, String(value))
      );
      node.textContent = text;
      nodes.push(node);
    };
    addSvg('path', {
      d: `M64 14V${bottom}H${64 + width}`,
      fill: 'none',
      stroke: '#cbd5df',
    });
    for (const axis of ['x', 'y']) {
      const domain = state.prepared.domains[axis];
      for (let index = 0; index <= 4; index += 1) {
        const normal = index / 2 - 1;
        const [px, py] = project(axis === 'x' ? [normal, 0] : [0, normal]);
        if (
          axis === 'x' ? px < 63 || px > 65 + width : py < 13 || py > bottom + 1
        )
          continue;
        const transformed = domain[0] + ((domain[1] - domain[0]) * index) / 4;
        const value =
          state.settings[`${axis}_scale`] === 'log1p'
            ? Math.expm1(transformed)
            : transformed;
        addSvg(
          'text',
          {
            x: axis === 'x' ? px : 57,
            y: axis === 'x' ? bottom + 18 : py + 3,
            'text-anchor': axis === 'x' ? 'middle' : 'end',
            fill: '#667085',
            'font-size': 10,
          },
          formatTick(value)
        );
      }
      const label = state.meta[`${axis}_label`] || axis.toUpperCase();
      const title =
        state.settings[`${axis}_scale`] === 'log1p'
          ? `${label} · log(1 + x)`
          : label;
      addSvg(
        'text',
        axis === 'x'
          ? {
              x: 64 + width / 2,
              y: bottom + 39,
              'text-anchor': 'middle',
              fill: '#344054',
              'font-size': 12,
            }
          : {
              transform: `translate(15 ${14 + height / 2}) rotate(-90)`,
              'text-anchor': 'middle',
              fill: '#344054',
              'font-size': 12,
            },
        title
      );
    }
    axes.replaceChildren(...nodes);
  }

  function draw() {
    if (disposed) return;
    const state = getState();
    const selected = new Set(store.selected_cells.get());
    const selectionCount = selected.size;
    gateOverlay.style.display =
      state.gateMode && !state.animating && !state.loading ? 'block' : 'none';
    gateButton.setAttribute('aria-pressed', String(state.gateMode));
    gateButton.disabled =
      state.loading || state.animating || !state.prepared.points.length;
    clearButton.disabled = !selectionCount;
    gateButton.style.color = gateButton.disabled
      ? 'gray'
      : state.gateMode
        ? 'green'
        : 'blue';
    clearButton.style.color = clearButton.disabled ? 'gray' : 'blue';
    const omittedStatus = state.prepared.omitted
      ? ` · ${state.prepared.omitted.toLocaleString()} non-finite or invalid coordinates omitted`
      : '';
    const modeStatus = state.animating
      ? ' · Animating…'
      : state.gateMode
        ? ' · Drag to gate; Shift adds cells'
        : ' · Scroll to zoom; drag to pan; Shift-click adds cells';
    footer.textContent =
      state.error ||
      state.renderError ||
      (state.loading
        ? 'Loading coordinates…'
        : `${state.prepared.points.length.toLocaleString()} cells · ${selectionCount.toLocaleString()} selected${omittedStatus}${modeStatus}`);
    if (state.drag) {
      const { start, end } = state.drag;
      Object.assign(gateRect.style, {
        display: 'block',
        left: `${Math.min(start[0], end[0])}px`,
        top: `${Math.min(start[1], end[1])}px`,
        width: `${Math.abs(start[0] - end[0])}px`,
        height: `${Math.abs(start[1] - end[1])}px`,
      });
    } else gateRect.style.display = 'none';
    drawAxes();
    if (!deck) return;
    const duration = state.animating
      ? Number(model.get('animation_duration') ?? 450)
      : 0;
    deck.setProps({
      width: state.size.width,
      height: state.size.height,
      viewState: state.viewState,
      controller: {
        dragPan: !state.gateMode,
        scrollZoom: true,
        doubleClickZoom: true,
      },
      layers: [
        new ScatterplotLayer({
          id: 'scatterplot-cells',
          data: state.prepared.points,
          coordinateSystem: COORDINATE_SYSTEM.CARTESIAN,
          pickable: !state.loading && !state.animating,
          getPosition: (point) => point.position,
          getRadius: Number(model.get('point_size') ?? 3),
          radiusUnits: 'pixels',
          radiusMinPixels: 1,
          radiusMaxPixels: 30,
          stroked: true,
          lineWidthUnits: 'pixels',
          getLineWidth: (point) => (selected.has(point.id) ? 1.5 : 0),
          getLineColor: [16, 49, 92, 255],
          getFillColor: (point) => [
            ...pointColor(point.color),
            selectionCount && !selected.has(point.id) ? 45 : 190,
          ],
          updateTriggers: {
            getFillColor: store.selected_cells.get(),
            getLineWidth: store.selected_cells.get(),
          },
          transitions: { getPosition: duration },
          parameters: { depthWriteEnabled: false },
        }),
      ],
    });
  }

  function prepareRows(animate = true) {
    const state = getState();
    const prepared = prepareScatterplot(state.rows, {
      xScale: state.settings.x_scale,
      yScale: state.settings.y_scale,
      preserveAspect: state.meta.view !== 'genes',
    });
    clearTimeout(animationTimer);
    const duration = Number(model.get('animation_duration') ?? 450);
    const animating =
      animate &&
      state.prepared.points.length > 0 &&
      prepared.points.length === state.prepared.points.length &&
      prepared.points.every(
        (point, index) => point.id === state.prepared.points[index].id
      ) &&
      duration > 0;
    setState({ prepared, animating, drag: null });
    if (animating)
      animationTimer = setTimeout(
        () => setState({ animating: false }),
        duration + 30
      );
  }

  function syncSettings() {
    const previous = getState().settings;
    const settings = Object.fromEntries(
      Object.keys(controls).map((key) => [
        key,
        model.get(key) || (key.endsWith('_scale') ? 'linear' : ''),
      ])
    );
    Object.entries(controls).forEach(([key, control]) => {
      control.value = settings[key];
    });
    [controls.x, controls.y].forEach((control) => {
      control.disabled = settings.view !== 'genes';
    });
    controls.layer.disabled = settings.view !== 'genes';
    setState({ settings });
    if (
      previous.x_scale !== settings.x_scale ||
      previous.y_scale !== settings.y_scale
    )
      prepareRows();
  }

  function syncOptions() {
    const labels = { genes: 'Gene × gene', umap: 'UMAP', spatial: 'Spatial' };
    setOptions(
      controls.view,
      (model.get('available_views') || []).map((value) => [
        value,
        labels[value] || value,
      ])
    );
    setOptions(
      geneList,
      (model.get('gene_names') || []).map((gene) => [gene, gene])
    );
    setOptions(controls.color_by, [
      ['', 'Uniform'],
      ...(model.get('obs_columns') || []).map((column) => [column, column]),
    ]);
    setOptions(controls.layer, [
      ['', 'X'],
      ...(model.get('layers') || []).map((layer) => [layer, layer]),
    ]);
    syncSettings();
  }

  function syncScaleAvailability() {
    const meta = model.get('plot_meta') || {};
    ['x', 'y'].forEach((axis) => {
      const option = controls[`${axis}_scale`].querySelector(
        'option[value="log1p"]'
      );
      option.disabled = meta[`${axis}_nonnegative`] === false;
      controls[`${axis}_scale`].title = option.disabled
        ? 'Log(1 + x) requires nonnegative values on this axis'
        : '';
    });
  }

  async function loadPoints() {
    const revision = ++parseRevision;
    const bytes = model.get('points_parquet');
    const meta = model.get('plot_meta') || {};
    setState({ loading: true, error: '', drag: null });
    try {
      let rows = [];
      if (bytes?.byteLength) {
        const buffer = ArrayBuffer.isView(bytes)
          ? bytes.buffer.slice(
              bytes.byteOffset,
              bytes.byteOffset + bytes.byteLength
            )
          : bytes;
        const table = await arrayBufferToArrowTable(buffer);
        if (disposed || revision !== parseRevision) return;
        const columns = Object.fromEntries(
          ['cell_id', 'x', 'y', 'color', 'label'].map((name) => [
            name,
            getTableColumnArray(table, name),
          ])
        );
        rows = columns.cell_id.map((cell_id, index) => ({
          cell_id: String(cell_id),
          x: columns.x[index],
          y: columns.y[index],
          color: columns.color[index],
          label: columns.label[index],
        }));
      }
      if (disposed || revision !== parseRevision) return;
      const viewChanged = meta.view !== getState().meta.view;
      setState({ rows, meta, loading: false });
      syncScaleAvailability();
      prepareRows();
      if (viewChanged) fitView();
    } catch (error) {
      if (disposed || revision !== parseRevision) return;
      setState({
        rows: [],
        prepared: prepareScatterplot([]),
        loading: false,
        error: `Unable to load scatterplot: ${error.message}`,
      });
    }
  }

  function resize() {
    if (disposed) return;
    const width = Number(model.get('width') || 0);
    root.style.width = width ? `${width}px` : '100%';
    root.style.height = `${model.get('height') || 600}px`;
    const rect = plot.getBoundingClientRect();
    setState({
      size: {
        width: Math.max(1, rect.width || (width || 600) - 86),
        height: Math.max(1, rect.height || 400),
      },
    });
    fitView();
  }

  Object.entries(controls).forEach(([key, control]) => {
    on(control, 'change', () => {
      if (
        (key === 'x' || key === 'y') &&
        !(model.get('gene_names') || []).includes(control.value)
      ) {
        control.value = model.get(key) || '';
        return;
      }
      model.set(key, control.value);
      model.save_changes();
    });
  });
  on(gateButton, 'click', () =>
    setState({ gateMode: !getState().gateMode, drag: null })
  );
  on(clearButton, 'click', () => selectCells([]));
  on(resetButton, 'click', fitView);
  const localPoint = (event) => {
    const rect = gateOverlay.getBoundingClientRect();
    return [
      Math.max(0, Math.min(getState().size.width, event.clientX - rect.left)),
      Math.max(0, Math.min(getState().size.height, event.clientY - rect.top)),
    ];
  };
  on(gateOverlay, 'pointerdown', (event) => {
    if (event.button !== 0) return;
    event.preventDefault();
    gateOverlay.setPointerCapture?.(event.pointerId);
    const start = localPoint(event);
    setState({ drag: { start, end: start, additive: event.shiftKey } });
  });
  on(gateOverlay, 'pointermove', (event) => {
    if (!getState().drag) return;
    setState({ drag: { ...getState().drag, end: localPoint(event) } });
  });
  on(gateOverlay, 'pointerup', (event) => {
    const state = getState();
    if (!state.drag) return;
    const { start, additive } = state.drag;
    const end = localPoint(event);
    const scale = Math.pow(2, state.viewState.zoom);
    const toData = ([px, py]) => [
      state.viewState.target[0] + (px - state.size.width / 2) / scale,
      state.viewState.target[1] - (py - state.size.height / 2) / scale,
    ];
    const polygon = [start, [end[0], start[1]], end, [start[0], end[1]]].map(
      toData
    );
    setState({ drag: null });
    gateOverlay.releasePointerCapture?.(event.pointerId);
    if (Math.abs(start[0] - end[0]) > 2 && Math.abs(start[1] - end[1]) > 2) {
      selectCells(cellsInPolygon(state.prepared.points, polygon), additive);
    }
  });
  on(gateOverlay, 'pointercancel', () => setState({ drag: null }));

  Object.keys(controls).forEach((key) => watch(key, syncSettings));
  ['available_views', 'gene_names', 'obs_columns', 'layers'].forEach((key) =>
    watch(key, syncOptions)
  );
  watch('points_parquet', loadPoints);
  // Metadata revisions also change when two selected genes have identical
  // coordinate bytes, so each revision must refresh labels and invalidate parses.
  watch('plot_meta', loadPoints);
  watch('selected_cells', () =>
    store.selected_cells.set(model.get('selected_cells') || [])
  );
  ['width', 'height'].forEach((key) => watch(key, resize));
  ['point_size', 'animation_duration'].forEach((key) => watch(key, draw));
  watch('raster_request', () => {
    rasterPending = true;
    deck?.redraw(true);
  });

  syncOptions();
  resize();
  try {
    deck = new Deck({
      canvas,
      width: getState().size.width,
      height: getState().size.height,
      views: new OrthographicView({ id: 'scatterplot', flipY: false }),
      viewState: getState().viewState,
      controller: true,
      onViewStateChange: ({ viewState }) => setState({ viewState }),
      onClick: (info, event) => {
        if (
          !info.object ||
          getState().gateMode ||
          getState().animating ||
          getState().loading
        )
          return;
        const id = info.object.id;
        if (event?.srcEvent?.shiftKey) {
          const current = store.selected_cells.get();
          selectCells(
            current.includes(id)
              ? current.filter((cell) => cell !== id)
              : [...current, id]
          );
        } else selectCells([id]);
      },
      onHover: ({ object, x, y }) => {
        tooltip.style.display =
          object && !getState().gateMode ? 'block' : 'none';
        if (!object) return;
        const meta = getState().meta;
        tooltip.textContent = `${object.id}${object.label ? ` · ${object.label}` : ''}\n${meta.x_label || 'X'}: ${formatTick(object.rawX)}\n${meta.y_label || 'Y'}: ${formatTick(object.rawY)}`;
        tooltip.style.left = `${Math.min(x + 76, Math.max(0, getState().size.width - 130))}px`;
        tooltip.style.top = `${y + 24}px`;
      },
      onAfterRender: () => {
        if (!rasterPending || disposed) return;
        rasterPending = false;
        try {
          model.set('raster_png', canvas.toDataURL('image/png').split(',')[1]);
          model.set('raster_view_state', {
            ...getState().viewState,
            ...getState().settings,
            ...getState().meta,
          });
          model.save_changes();
        } catch (error) {
          setState({
            error: `Unable to capture scatterplot: ${error.message}`,
          });
        }
      },
      onError: (error) =>
        setState({
          renderError: `Unable to render scatterplot: ${error.message}`,
        }),
    });
  } catch (error) {
    setState({ renderError: `Unable to initialize WebGL: ${error.message}` });
  }
  subscriptions.push(store.scatterplot_state.subscribe(draw));
  subscriptions.push(
    store.selected_cells.subscribe(draw, { immediate: false })
  );
  if (typeof ResizeObserver !== 'undefined') {
    resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(plot);
  } else on(window, 'resize', resize);
  // Start decoding after cleanup has been made available to the caller.
  loadPoints();

  return {
    finalize() {
      if (disposed) return;
      disposed = true;
      parseRevision += 1;
      clearTimeout(animationTimer);
      resizeObserver?.disconnect();
      listeners.forEach(([event, handler]) => model.off(event, handler));
      subscriptions.forEach((unsubscribe) => unsubscribe());
      domListeners.forEach((remove) => remove());
      deck?.finalize();
      deck = null;
      root.remove();
    },
  };
};
