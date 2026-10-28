import { ViewMode } from '@deck.gl-community/editable-layers';

import { get_scatterplot_cell_data } from '../deck-gl/layers/cell_layer';
import { calc_and_update_rgn_bar_graph } from '../deck-gl/layers/edit_layer';
import { load_gene_expression } from '../global_variables/cell_exp_array';

import { fingerprint, show_space_gates } from './embedding_gates';

export const expression_axis = (
  values,
  scale,
  low = 0,
  high = 10000,
  reverse = false
) => {
  const transformed = values.map((value) =>
    scale === 'log1p' ? Math.log1p(Math.max(0, value)) : Math.max(0, value)
  );
  const max = transformed.reduce((a, b) => Math.max(a, b), 0);
  return {
    max,
    positions: transformed.map((value) =>
      max > 0
        ? low + (reverse ? 1 - value / max : value / max) * (high - low)
        : (low + high) / 2
    ),
  };
};

export const interpolate_positions = (from, to, fraction, output) => {
  for (let i = 0; i < to.length; i++) {
    output[i] = from[i] + (to[i] - from[i]) * fraction;
  }
  return output;
};

const bounds = (positions) => {
  const result = [Infinity, -Infinity, Infinity, -Infinity];
  for (let i = 0; i < positions.length; i += 2) {
    result[0] = Math.min(result[0], positions[i]);
    result[1] = Math.max(result[1], positions[i]);
    result[2] = Math.min(result[2], positions[i + 1]);
    result[3] = Math.max(result[3], positions[i + 1]);
  }
  return result.map((value, i) =>
    Number.isFinite(value) ? value : (i % 2) * 10000
  );
};

export const initialize_expression_scatter = (
  viz_state,
  layers_obj,
  refresh,
  deck_ist
) => {
  const { model, obs_store: obs, cats, spatial } = viz_state;
  const container = viz_state.containers.view_modes;
  const umap = spatial.cell_umap_scatter_positions;
  const has_xy = Boolean(
    container && umap && viz_state.genes.gene_names.length
  );
  viz_state.expression_scatter_enabled = has_xy;
  const disposers = [];
  let disposed = false;
  let request = 0;
  let animation = null;
  let position_version = 0;
  let genes = [...(model?.get('xy_genes') ?? [])];
  let scale = model?.get('xy_scale') || 'log1p';
  let displayed = new Float32Array(
    layers_obj.cell_layer.props.data.attributes.getPosition.value
  );
  const dataset = fingerprint(cats.cell_names_array);
  const umap_space = umap
    ? { kind: 'umap', dataset, embedding: fingerprint(umap) }
    : null;
  const physical_space = {
    kind: 'spatial',
    dataset,
    coordinates: 'image_pixels',
    geometry: fingerprint(
      spatial.cell_scatter_data?.attributes.getPosition.value || []
    ),
    axes: { x: 'x', y: 'y' },
  };
  const [x0, x1, y0, y1] = bounds(umap || []);
  const known_genes = new Set(viz_state.genes.gene_names);
  viz_state.embedding_gates = model?.get('gates') || {
    type: 'FeatureCollection',
    features: [],
  };

  const publish = (name, value) => {
    if (
      !model?.set ||
      JSON.stringify(model.get(name)) === JSON.stringify(value)
    )
      return;
    model.set(name, value);
    model.save_changes();
  };
  const listen = (name, callback) => {
    model?.on?.(`change:${name}`, callback);
    disposers.push(() => model?.off?.(`change:${name}`, callback));
  };
  const subscribe = (observable, callback) => {
    disposers.push(observable.subscribe(callback, { immediate: false }));
  };
  const show_gates = (space) => {
    show_space_gates(viz_state, layers_obj, space);
    if (layers_obj.edit_layer) {
      viz_state.edit.mode = 'view';
      layers_obj.edit_layer = layers_obj.edit_layer.clone({ mode: ViewMode });
      calc_and_update_rgn_bar_graph(viz_state, deck_ist, layers_obj);
    }
    publish('view_space', space || { kind: 'spatial' });
  };
  listen('gates', () => {
    if (viz_state.publishing_gates) return;
    viz_state.embedding_gates = model.get('gates');
    show_gates(viz_state.neighborhood_space);
    refresh();
  });
  const publish_selection = (ids) => {
    viz_state.publishing_selection = true;
    publish('selected_cells', ids.map(String));
    viz_state.publishing_selection = false;
  };
  subscribe(obs.selected_cells, publish_selection);
  subscribe(obs.selected_cats, () => {
    if (cats.cat !== 'cluster') return;
    const selected = new Set(cats.selected_cats);
    publish_selection(
      selected.size
        ? cats.cell_names_array.filter((_, i) =>
            selected.has(cats.cell_cats[i])
          )
        : []
    );
  });

  if (!has_xy) {
    const update_space = () => {
      const view = obs.landscape_view.get();
      show_gates(view === 'umap' ? umap_space : physical_space);
      publish('landscape_state', view);
      refresh();
    };
    subscribe(obs.landscape_view, update_space);
    listen('landscape_state', () => {
      const view = model.get('landscape_state');
      if (
        ['spatial', 'umap'].includes(view) &&
        obs.landscape_view.get() !== view
      )
        obs.landscape_view.set(view);
    });
    update_space();
    return () => disposers.forEach((dispose) => dispose?.());
  }
  // Styled like the UMAP button (make_button), so the view modes line up.
  const button = (text, title, width, click) => {
    const element = document.createElement('div');
    element.className = 'button';
    element.textContent = text;
    element.title = title;
    Object.assign(element.style, {
      width: `${width}px`,
      textAlign: 'left',
      cursor: 'pointer',
      fontSize: '12px',
      fontWeight: 'bold',
      color: 'gray',
      marginTop: '5px',
      marginLeft: '5px',
      userSelect: 'none',
      fontFamily:
        '-apple-system, BlinkMacSystemFont, "San Francisco", "Helvetica Neue", Helvetica, Arial, sans-serif',
    });
    element.addEventListener('click', click);
    container.appendChild(element);
    return element;
  };
  const xy_button = button(
    'XY',
    'Plot expression of two genes',
    20,
    on_xy_click
  );
  const lin_button = button('LIN', 'Linear gene expression', 25, () =>
    publish('xy_scale', 'linear')
  );
  const log_button = button('LOG', 'log(1 + gene expression)', 30, () =>
    publish('xy_scale', 'log1p')
  );
  viz_state.buttons.buttons.xy = xy_button;
  const update_scale_controls = () => {
    const xy = obs.landscape_view.get() === 'xy';
    xy_button.style.color = xy ? 'blue' : 'gray';
    [lin_button, log_button].forEach((element) => {
      element.style.display = xy ? '' : 'none';
    });
    lin_button.style.color = scale === 'linear' ? 'blue' : 'gray';
    log_button.style.color = scale === 'log1p' ? 'blue' : 'gray';
  };
  const inputs = document.createElement('div');
  Object.assign(inputs.style, { display: 'none', fontSize: '11px' });
  viz_state.containers.image.appendChild(inputs);
  // Both axis inputs autocomplete from one list of the dataset's genes.
  const gene_list = document.createElement('datalist');
  gene_list.id = `xy_genes_${dataset}_${Math.random().toString(36).slice(2)}`;
  viz_state.genes.gene_names.forEach((gene) => {
    const option = document.createElement('option');
    option.value = gene;
    gene_list.appendChild(option);
  });
  inputs.appendChild(gene_list);
  const axis_inputs = ['X', 'Y'].map((axis, i) => {
    const label = document.createElement('label');
    label.textContent = `${axis}: `;
    const input = document.createElement('input');
    input.setAttribute('aria-label', `${axis} gene`);
    input.setAttribute('list', gene_list.id);
    input.placeholder = `${axis} gene`;
    input.style.cssText = 'width:65px;font-size:11px;box-sizing:border-box';
    input.value = genes[i] || '';
    const update_axes = (event) => {
      const pair = axis_inputs.map((element) => element.value.trim());
      if (
        pair.some((gene) => gene && !known_genes.has(gene)) ||
        (!pair[0] && pair[1])
      ) {
        if (event.type === 'change') {
          input.setCustomValidity('Enter known genes, starting with X.');
          input.reportValidity();
        }
        return;
      }
      input.setCustomValidity('');
      publish('xy_genes', pair.filter(Boolean));
    };
    input.addEventListener('input', update_axes);
    input.addEventListener('change', update_axes);
    label.appendChild(input);
    inputs.appendChild(label);
    inputs.appendChild(document.createElement('br'));
    return input;
  });
  const caption = document.createElement('div');
  caption.style.cssText =
    'font:11px system-ui;color:#555;max-width:135px;white-space:normal';
  inputs.appendChild(caption);

  // Animate the small single-cell buffers directly. This also survives color
  // and dendrogram updates, which can replace the deck.gl layer mid-transition.
  const animate = (target) => {
    cancelAnimationFrame(animation);
    const from = displayed.slice();
    layers_obj.cell_layer = layers_obj.cell_layer.clone({
      id: `cell-layer-expression-${++position_version}`,
      transitions: false,
    });
    const started = performance.now();
    const was_visible = obs.viz_edit_layer.get();
    const frame = (now) => {
      if (disposed) return;
      const t = Math.min(1, (now - started) / 800);
      const eased = t * t * (3 - 2 * t);
      // deck.gl detects external binary-buffer updates by array identity.
      // A fresh buffer makes each animation frame reach the GPU.
      const output = new Float32Array(target.length);
      spatial.embedding_animation_positions = interpolate_positions(
        from,
        target,
        eased,
        output
      );
      displayed = output;
      layers_obj.cell_layer = layers_obj.cell_layer.clone({
        data: get_scatterplot_cell_data(viz_state),
        transitions: false,
        radiusUnits: 'pixels',
        radiusMinPixels: 0,
        modelMatrix: null,
      });
      if (layers_obj.edit_layer) {
        layers_obj.edit_layer = layers_obj.edit_layer.clone({
          visible: t === 1 && was_visible,
        });
      }
      refresh();
      if (t < 1) animation = requestAnimationFrame(frame);
      else {
        spatial.embedding_animation_positions = null;
      }
    };
    animation = requestAnimationFrame(frame);
  };

  const raw_expression = async (gene) => {
    const values = new Float64Array(cats.cell_names_array.length);
    if (!gene) return values;
    const { cell_names, cell_exp } = await load_gene_expression(
      (cats.expression_cache ??= new Map()),
      viz_state.global_base_url,
      viz_state.seg.version,
      gene,
      viz_state.aws,
      viz_state.row_group_readers?.cbg
    );
    cell_names.forEach((name, i) => {
      const index = viz_state.vector_name_integer
        ? Number(name)
        : cats.cell_name_to_index_map.get(String(name));
      if (Number.isInteger(index) && index >= 0 && index < values.length) {
        values[index] = Number(cell_exp[i]) || 0;
      }
    });
    return values;
  };

  const update_xy = async () => {
    const token = ++request;
    const pair = [...genes];
    const axis_scale = scale;
    caption.textContent = 'Loading expression…';
    try {
      const raw = await Promise.all([
        raw_expression(pair[0]),
        raw_expression(pair[1]),
      ]);
      if (disposed || token !== request || obs.landscape_view.get() !== 'xy')
        return;
      const x = expression_axis(raw[0], axis_scale, x0, x1);
      const y = expression_axis(raw[1], axis_scale, y0, y1, true);
      const positions = new Float32Array(raw[0].length * 2);
      for (let i = 0; i < raw[0].length; i++) {
        positions[i * 2] = x.positions[i];
        positions[i * 2 + 1] = y.positions[i];
      }
      spatial.cell_xy_scatter_positions = positions;
      show_gates({
        kind: 'xy',
        dataset,
        genes: pair,
        scale: axis_scale,
        expression: fingerprint([...raw[0], ...raw[1]]),
        axes: {
          x: { min: 0, max: x.max, bounds: [x0, x1] },
          y: { min: 0, max: y.max, bounds: [y0, y1], reversed: true },
        },
        units: 'raw counts',
      });
      caption.textContent = `${pair.length ? `X → ${pair[0]} · Y ↑ ${pair[1] || '—'}` : 'Choose X and Y genes'} · ${axis_scale === 'linear' ? 'counts' : 'log(1 + counts)'}`;
      animate(positions);
    } catch (error) {
      if (token === request)
        caption.textContent = `Expression unavailable: ${error.message}`;
    }
  };

  // XY is entered only from its button. Selected genes (up to two) become the
  // axes; otherwise the previous axes are kept.
  function on_xy_click() {
    const selected = (obs.selected_genes.get() || []).filter((gene) =>
      known_genes.has(gene)
    );
    if (selected.length) {
      genes = selected.slice(0, 2);
      axis_inputs.forEach((input, i) => {
        input.value = genes[i] || '';
      });
      publish('xy_genes', genes);
    }
    // Already in XY, new axes replot through the xy_genes listener.
    if (obs.landscape_view.get() !== 'xy') obs.landscape_view.set('xy');
  }

  const update_view = () => {
    const view = obs.landscape_view.get();
    update_scale_controls();
    inputs.style.display = view === 'xy' ? '' : 'none';
    publish('landscape_state', view);
    if (view === 'xy') update_xy();
    else {
      request += 1;
      show_gates(view === 'umap' ? umap_space : physical_space);
      if (view === 'umap') animate(umap);
      else {
        cancelAnimationFrame(animation);
        spatial.embedding_animation_positions = null;
        displayed = new Float32Array(
          spatial.cell_scatter_data.attributes.getPosition.value
        );
      }
    }
  };
  subscribe(obs.landscape_view, update_view);
  listen('landscape_state', () => {
    const view = model.get('landscape_state');
    if (
      ['xy', 'umap', 'spatial'].includes(view) &&
      obs.landscape_view.get() !== view
    )
      obs.landscape_view.set(view);
  });
  listen('xy_genes', () => {
    genes = [...(model.get('xy_genes') || [])];
    axis_inputs.forEach((input, i) => {
      input.value = genes[i] || '';
    });
    if (obs.landscape_view.get() === 'xy') update_xy();
  });
  listen('xy_scale', () => {
    scale = model.get('xy_scale') || 'log1p';
    update_scale_controls();
    if (obs.landscape_view.get() === 'xy') update_xy();
  });

  // Initialize gates without moving an already rendered UMAP on page load.
  update_scale_controls();
  show_gates(
    obs.landscape_view.get() === 'spatial' ? physical_space : umap_space
  );
  if (obs.landscape_view.get() === 'xy') update_view();
  return () => {
    disposed = true;
    request += 1;
    cancelAnimationFrame(animation);
    spatial.embedding_animation_positions = null;
    disposers.forEach((dispose) => dispose?.());
    xy_button.remove();
    lin_button.remove();
    log_button.remove();
    if (viz_state.buttons.buttons.xy === xy_button) {
      delete viz_state.buttons.buttons.xy;
    }
    inputs.remove();
  };
};
