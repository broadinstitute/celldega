/**
 * A Clustergram with several matrices about the same objects, for example
 * clusters by genes (gene expression) and clusters by clusters (neighborhood
 * enrichment): Python's `Clustergram(matrix={name: Matrix})`, or a web page's
 * `clustergram(el, {matrices: [...]})`.
 *
 * One matrix is drawn at a time with `matrix_viz`. Switching (the MAT dropdown,
 * the `active_matrix` trait, `apply_state({matrix})`, a saved view of another
 * matrix, or a gene link for a gene only another matrix has) finalizes it and
 * draws the other, entirely in the browser, so it works without a kernel too.
 * Each matrix keeps its own view (zoom, order, marker level, mode) between
 * visits.
 *
 * Manual categories (e.g. cell types of clusters) are kept in the first
 * matrix's rows and columns (the model's `manual_cat`, which Python reads).
 * Another matrix shows them on each axis with the same entity (e.g. clusters on
 * both axes of an enrichment matrix), and labels made there go back to them.
 */

import { handleValidationWarning } from '../temp_utils/errorHandler';

import { matrix_viz } from './matrix_viz';
import {
  consume_initial_snapshot,
  identity_differences,
  names_signature,
} from './snapshot';
import { listen_for_view_requests } from './view_requests';

/** Model values that belong to each matrix, swapped in when it is shown. */
export const PER_MATRIX_KEYS = [
  'rank_dim',
  'viz_mode',
  'dot_size_encoded',
  'row_entity',
  'col_entity',
];

const MANUAL_KEYS = new Set([
  'manual_cat',
  'manual_cat_config',
  'manual_row_cat',
  'manual_col_cat',
]);

const DEFAULT_ROW_ENTITY = { entity: 'gene', attr: 'name' };
const DEFAULT_COL_ENTITY = { entity: 'cell', attr: 'leiden' };

const parse_json = (value, fallback = {}) => {
  if (value && typeof value === 'object') return value;
  try {
    const parsed = JSON.parse(value || 'null');
    return parsed && typeof parsed === 'object' ? parsed : fallback;
  } catch {
    return fallback;
  }
};

const clone = (value) => JSON.parse(JSON.stringify(value ?? {}));

// Each view gets its own copy: matrix_viz decorates the network it draws.
const copy_network = (network) =>
  typeof structuredClone === 'function'
    ? structuredClone(network)
    : JSON.parse(JSON.stringify(network));

/** `entity:attr` of an axis entity (a JSON string or an object). */
export const entity_key = (entity) => {
  const parsed = parse_json(entity, null);
  if (!parsed) return String(entity ?? '');
  return `${parsed.entity ?? ''}:${parsed.attr ?? ''}`;
};

/**
 * For each axis of a matrix, the first matrix's axis with the same entity
 * (`'row'`, `'col'` or null): where its manual categories are kept.
 */
export const axis_map_for = (entry, primary) => {
  const primary_keys = {
    row: entity_key(primary.row_entity),
    col: entity_key(primary.col_entity),
  };
  // Columns first: they are the clusters of a typical expression matrix.
  const find = (key) => {
    if (key === primary_keys.col) return 'col';
    if (key === primary_keys.row) return 'row';
    return null;
  };
  return {
    row: find(entity_key(entry.row_entity)),
    col: find(entity_key(entry.col_entity)),
  };
};

/** A label value, or null for none. */
const label_value = (value) =>
  value == null || value === '' || value === 'N.A.' ? null : String(value);

/** `{attribute: {values, colors}}` keeping only the given names' values. */
const restrict = (axis_payload, names) =>
  Object.fromEntries(
    Object.entries(axis_payload || {}).map(([attribute, spec]) => [
      attribute,
      {
        values: Object.fromEntries(
          Object.entries(spec?.values || {}).filter(([name]) =>
            names.has(String(name))
          )
        ),
        colors: { ...(spec?.colors || {}) },
      },
    ])
  );

/**
 * Label changes between two exports of one axis (`{attribute: {values}}`), as
 * `[attribute, name, value-or-null]`, for names on that axis.
 */
export const label_changes = (before, after, names) => {
  const changes = [];
  const attributes = new Set([
    ...Object.keys(before || {}),
    ...Object.keys(after || {}),
  ]);
  attributes.forEach((attribute) => {
    const old_values = before?.[attribute]?.values || {};
    const new_values = after?.[attribute]?.values || {};
    new Set([...Object.keys(old_values), ...Object.keys(new_values)]).forEach(
      (name) => {
        if (!names.has(String(name))) return;
        const old_value = label_value(old_values[name]);
        const new_value = label_value(new_values[name]);
        if (old_value !== new_value)
          changes.push([attribute, String(name), new_value]);
      }
    );
  });
  return changes;
};

/**
 * Apply label changes to one axis of `manual_cat` (in place).
 * @returns {boolean} Whether anything changed.
 */
export const apply_label_changes = (manual, axis, changes, colors = {}) => {
  let changed = false;
  changes.forEach(([attribute, name, value]) => {
    manual[axis] = manual[axis] || {};
    const spec = (manual[axis][attribute] = manual[axis][attribute] || {
      values: {},
      colors: {},
    });
    spec.values = spec.values || {};
    spec.colors = spec.colors || {};
    const current = label_value(spec.values[name]);
    if (current === value) return;
    changed = true;
    if (value === null) delete spec.values[name];
    else {
      spec.values[name] = value;
      if (colors[value] && !spec.colors[value])
        spec.colors[value] = colors[value];
    }
  });
  return changed;
};

/**
 * Render a Clustergram with several matrices.
 *
 * @param {object} model - The widget model (or an options model)
 * @param {HTMLElement} el - Container element
 * @param {Array<{name: string, description?: string, viz_mode?: string,
 *   row_entity?: string, col_entity?: string, load: () => Promise<object>}>}
 *   entries - One per matrix, in dropdown order; `load` returns its network.
 * @param {number|string} width
 * @param {number|string} height
 * @param {object} [callbacks] - `row_label_callback`, `col_label_callback`,
 *   `col_dendro_callback`, as for matrix_viz.
 * @returns {Promise<object>} The Clustergram: the single-matrix API (get_state,
 *   apply_state, snapshot, restore_snapshot, ...) for the matrix on screen, with
 *   `apply_state`/`restore_snapshot` switching first when needed, plus
 *   `matrix_names`, `active_matrix()` and `switch_matrix(name)`.
 */
export const multi_matrix_viz = async (
  model,
  el,
  entries,
  width,
  height,
  callbacks = {}
) => {
  if (!entries?.length) throw new Error('No matrices to show');
  const names = entries.map((entry) => String(entry.name));
  const descriptions = {};
  const networks = new Map(); // name -> loaded network (cloned for each view)
  const axis_names = new Map(); // name -> {rows, cols}
  const saved_views = new Map(); // name -> replay state
  const per_matrix = new Map(); // name -> {key: value}
  const message_listeners = new Set();
  const primary = entries[0];
  let current = null; // {index, entry, api, map, names, baseline}
  let switching = Promise.resolve();
  let target = null;
  let finalized = false;

  entries.forEach((entry) => {
    if (entry.description) descriptions[entry.name] = entry.description;
  });

  const initial_name = names.includes(model.get('active_matrix'))
    ? model.get('active_matrix')
    : names[0];
  // The model's values were set for the matrix shown first.
  per_matrix.set(
    initial_name,
    Object.fromEntries(
      PER_MATRIX_KEYS.filter(
        (key) => key !== 'row_entity' && key !== 'col_entity'
      ).map((key) => [key, model.get(key)])
    )
  );
  const initial_rank_dim = model.get('rank_dim');

  const load_network = async (entry) => {
    if (!networks.has(entry.name)) {
      networks.set(
        entry.name,
        Promise.resolve(entry.load()).then((network) => {
          if (network?.description && !descriptions[entry.name])
            descriptions[entry.name] = network.description;
          axis_names.set(entry.name, {
            rows: (network.row_nodes || []).map((node) => String(node.name)),
            cols: (network.col_nodes || []).map((node) => String(node.name)),
          });
          return network;
        })
      );
    }
    try {
      return await networks.get(entry.name);
    } catch (error) {
      networks.delete(entry.name);
      throw error;
    }
  };

  const entity_of = (entry, network, axis) =>
    entry[`${axis}_entity`] ||
    JSON.stringify(
      network[`${axis}_entity`] ||
        (axis === 'row' ? DEFAULT_ROW_ENTITY : DEFAULT_COL_ENTITY)
    );

  // ---------------------------------------------------------------------------
  // Manual categories: kept in the first matrix's frame (model.manual_cat).
  // ---------------------------------------------------------------------------
  const view_names = (view, axis) =>
    new Set(
      (axis === 'row' ? view.names.rows : view.names.cols) ||
        axis_names.get(view.entry.name)?.[axis === 'row' ? 'rows' : 'cols'] ||
        []
    );

  const composed = (view, key) => {
    const { map } = view;
    if (key === 'manual_cat') {
      const manual = parse_json(model.get('manual_cat'));
      return JSON.stringify({
        row: map.row ? clone(manual[map.row]) : {},
        col: map.col ? clone(manual[map.col]) : {},
      });
    }
    if (key === 'manual_cat_config') {
      const config = parse_json(model.get('manual_cat_config'));
      return JSON.stringify({
        row: map.row ? (config[map.row] ?? null) : null,
        col: map.col ? (config[map.col] ?? null) : null,
      });
    }
    const axis = key === 'manual_row_cat' ? 'row' : 'col';
    return map[axis] ? model.get(`manual_${map[axis]}_cat`) : '';
  };

  const write_manual = (manual) => {
    const json = JSON.stringify(manual);
    if (json === model.get('manual_cat')) return;
    model.set('manual_cat', json);
    model.save_changes?.();
  };

  // Labels made in another matrix go back to the first matrix's axis.
  const merge_back = (view, json) => {
    const exported = parse_json(json);
    const manual = parse_json(model.get('manual_cat'));
    let changed = false;
    ['row', 'col'].forEach((axis) => {
      const target_axis = view.map[axis];
      if (!target_axis) return;
      const axis_set = view_names(view, axis);
      const before =
        view.baseline[axis] ?? restrict(manual[target_axis], axis_set);
      const after = exported[axis] || {};
      const colors = Object.assign(
        {},
        ...Object.values(after).map((spec) => spec?.colors || {})
      );
      const changes = label_changes(before, after, axis_set);
      view.baseline[axis] = clone(after);
      if (apply_label_changes(manual, target_axis, changes, colors))
        changed = true;
    });
    if (changed) write_manual(manual);
  };

  // Labels changed elsewhere (Python, Clerk, the other axis) reach the matrix shown.
  const sync_down = (view) => {
    const manual = parse_json(model.get('manual_cat'));
    ['row', 'col'].forEach((axis) => {
      const source_axis = view.map[axis];
      if (!source_axis) return;
      const axis_set = view_names(view, axis);
      const wanted = restrict(manual[source_axis], axis_set);
      const changes = label_changes(
        view.baseline[axis] || {},
        wanted,
        axis_set
      );
      const by_attribute = new Map();
      changes.forEach(([attribute, name, value]) => {
        if (!by_attribute.has(attribute)) by_attribute.set(attribute, {});
        by_attribute.get(attribute)[name] = value ?? '';
      });
      by_attribute.forEach((values, attribute) => {
        try {
          view.api?.set_categories?.({
            axis,
            attribute,
            values,
            colors: wanted[attribute]?.colors || {},
          });
        } catch (error) {
          handleValidationWarning('Could not show labels in this matrix', {
            data: { error: String(error?.message || error) },
          });
        }
      });
    });
  };

  // The model as one matrix's view sees it.
  const make_view_model = (view) => ({
    id: model.id,
    get: (key) => {
      if (key === 'active_matrix') return view.entry.name;
      if (view.index !== 0 && MANUAL_KEYS.has(key)) return composed(view, key);
      return model.get(key);
    },
    set: (key, value, ...rest) => {
      if (key === 'row_names') view.names.rows = (value || []).map(String);
      if (key === 'col_names') view.names.cols = (value || []).map(String);
      if (view.index !== 0 && MANUAL_KEYS.has(key)) {
        if (key === 'manual_cat') merge_back(view, value);
        return;
      }
      model.set(key, value, ...rest);
    },
    on: (event, listener, ...rest) => {
      if (event === 'msg:custom') message_listeners.add(listener);
      else model.on(event, listener, ...rest);
    },
    off: (event, listener, ...rest) => {
      if (event === 'msg:custom') {
        if (listener) message_listeners.delete(listener);
        else message_listeners.clear();
      } else model.off?.(event, listener, ...rest);
    },
    send: (...args) => model.send?.(...args),
    save_changes: () => model.save_changes?.(),
  });

  // ---------------------------------------------------------------------------
  // Showing a matrix
  // ---------------------------------------------------------------------------
  const unmount = () => {
    if (!current) return;
    const view = current;
    current = null;
    try {
      const state = view.api.get_replay_state();
      // Labels follow the objects, not the view: never restore old ones.
      delete state.annotations;
      saved_views.set(view.entry.name, state);
    } catch {
      saved_views.delete(view.entry.name);
    }
    per_matrix.set(
      view.entry.name,
      Object.fromEntries(PER_MATRIX_KEYS.map((key) => [key, model.get(key)]))
    );
    view.api.finalize();
  };

  // The first matrix's entities, known once it has loaded (or given).
  let primary_network = null;
  const network_for_primary = () => primary_network || {};

  const mount = async (index) => {
    const entry = entries[index];
    const network = await load_network(entry);
    if (finalized) return;
    // Unset values (null) fall back to this matrix's defaults.
    const stored = Object.fromEntries(
      Object.entries(per_matrix.get(entry.name) || {}).filter(
        ([, value]) => value != null
      )
    );
    const values = {
      rank_dim: initial_rank_dim,
      viz_mode: entry.viz_mode || (network.size_mat ? 'dotplot' : 'heatmap'),
      dot_size_encoded: true,
      ...stored,
      row_entity: entity_of(entry, network, 'row'),
      col_entity: entity_of(entry, network, 'col'),
    };
    PER_MATRIX_KEYS.forEach((key) => {
      if (values[key] !== undefined) model.set(key, values[key]);
    });
    // Where this matrix came from (a web page's Matrix Zarr URL), for saved views.
    if ('url' in entry) model.set('url', entry.url || '');
    if (model.get('active_matrix') !== entry.name)
      model.set('active_matrix', entry.name);
    model.save_changes?.();

    const view = {
      index,
      entry: {
        ...entry,
        row_entity: values.row_entity,
        col_entity: values.col_entity,
      },
      api: null,
      names: {},
      baseline: {},
      map:
        index === 0
          ? { row: 'row', col: 'col' }
          : axis_map_for(
              { row_entity: values.row_entity, col_entity: values.col_entity },
              {
                row_entity: entity_of(primary, network_for_primary(), 'row'),
                col_entity: entity_of(primary, network_for_primary(), 'col'),
              }
            ),
    };
    const view_model = make_view_model(view);
    current = view;
    view.api = await matrix_viz(
      view_model,
      el,
      copy_network(network),
      width,
      height,
      callbacks.row_label_callback ?? null,
      callbacks.col_label_callback ?? null,
      callbacks.col_dendro_callback ?? null,
      {
        matrix_menu: {
          names,
          active: entry.name,
          descriptions: { ...descriptions },
          // Through the model, so Python and linked widgets follow too.
          on_change: (name) => {
            model.set('active_matrix', name);
            model.save_changes?.();
          },
        },
        view_requests: false,
        initial_snapshot: false,
      }
    );
    if (finalized) {
      view.api.finalize();
      return;
    }
    const remembered = saved_views.get(entry.name);
    if (remembered) {
      try {
        view.api.apply_state(remembered);
      } catch (error) {
        handleValidationWarning('Could not restore the matrix view', {
          data: { error: String(error?.message || error) },
        });
      }
    }
  };

  /**
   * Show the matrix called `name` (a no-op when it is shown).
   * @returns {Promise<void>} Resolves once it is drawn.
   */
  const switch_matrix = (name) => {
    const index = names.indexOf(String(name));
    if (index < 0)
      return Promise.reject(
        new Error(`Unknown matrix "${name}"; choose one of ${names.join(', ')}`)
      );
    target = names[index];
    switching = switching
      .catch(() => {})
      .then(async () => {
        if (finalized || current?.index === index) return;
        // Hold the height while one matrix replaces the other.
        const held = el.style.minHeight;
        if (current) el.style.minHeight = `${el.offsetHeight}px`;
        try {
          unmount();
          await mount(index);
        } finally {
          el.style.minHeight = held;
        }
      });
    return switching;
  };

  // ---------------------------------------------------------------------------
  // Which matrix a request is about
  // ---------------------------------------------------------------------------
  const current_has_row = (name) =>
    (current?.names.rows || axis_names.get(current?.entry.name)?.rows || [])
      .map(String)
      .includes(String(name));

  const load_all = () =>
    Promise.all(entries.map((entry) => load_network(entry).catch(() => null)));

  const matrix_with_row = async (name) => {
    await load_all();
    const found = entries.find((entry) =>
      (axis_names.get(entry.name)?.rows || []).includes(String(name))
    );
    return found ? found.name : null;
  };

  /** The matrix `changes` should apply to: theirs, or one with their focus gene. */
  const target_for_changes = async (changes) => {
    if (changes.matrix) {
      if (!names.includes(String(changes.matrix)))
        throw new Error(
          `Unknown matrix "${changes.matrix}"; choose one of ${names.join(', ')}`
        );
      return String(changes.matrix);
    }
    if (changes.focus_gene && !current_has_row(changes.focus_gene))
      return matrix_with_row(changes.focus_gene);
    return null;
  };

  /** The matrix a saved view was taken of: recorded, else matched by its names. */
  const target_for_snapshot = async (snapshot) => {
    const recorded = snapshot?.source?.active_matrix;
    if (recorded && names.includes(recorded)) return recorded;
    const identity = snapshot?.identity;
    if (!identity?.rows && !identity?.cols) return null;
    await load_all();
    const found = entries.find((entry) => {
      const axes = axis_names.get(entry.name);
      return (
        axes &&
        !identity_differences(identity, {
          rows: names_signature(axes.rows),
          cols: names_signature(axes.cols),
        }).length
      );
    });
    return found ? found.name : null;
  };

  // Label edits sent with apply_state are in the first matrix's frame (as
  // Python's manual_cat is); for another matrix they edit model.manual_cat,
  // which then reaches the view (sync_down).
  const translate_label_changes = (changes) => {
    if (!current || current.index === 0) return changes;
    const out = { ...changes };
    if (out.categories) {
      const request = out.categories;
      delete out.categories;
      const axis = request.axis || 'col';
      const config = parse_json(model.get('manual_cat_config'));
      const attribute =
        request.attribute ||
        config?.[axis]?.attribute ||
        model.get(`manual_${axis}_cat`);
      if (attribute) {
        const manual = parse_json(model.get('manual_cat'));
        const existing = manual[axis]?.[attribute] || {};
        const values = request.replace ? {} : { ...(existing.values || {}) };
        Object.entries(request.values || {}).forEach(([name, value]) => {
          if (label_value(value) === null) delete values[name];
          else values[name] = String(value);
        });
        manual[axis] = {
          [attribute]: {
            values,
            colors: { ...(existing.colors || {}), ...(request.colors || {}) },
          },
        };
        write_manual(manual);
      }
    }
    if (out.annotations) {
      const { annotations } = out;
      delete out.annotations;
      const manual = parse_json(model.get('manual_cat'));
      ['row', 'col'].forEach((axis) => {
        if (!(axis in annotations)) return;
        const spec = annotations[axis];
        manual[axis] = spec?.attribute
          ? {
              [spec.attribute]: {
                values: { ...(spec.values || {}) },
                colors: { ...(spec.colors || {}) },
              },
            }
          : {};
      });
      write_manual(manual);
    }
    return out;
  };

  /** apply_state for whichever matrix the changes are about. */
  const apply_state = async (changes = {}) => {
    const to = await target_for_changes(changes || {});
    if (to) await switch_matrix(to);
    else await switching;
    const rest = { ...(changes || {}) };
    delete rest.matrix;
    const done = current?.api.apply_state(translate_label_changes(rest)) || [];
    return to ? [`matrix -> ${to}`, ...done] : done;
  };

  const restore_snapshot = async (snapshot, options = {}) => {
    const to = await target_for_snapshot(snapshot);
    if (to) await switch_matrix(to);
    else await switching;
    return current.api.restore_snapshot(snapshot, options);
  };

  // ---------------------------------------------------------------------------
  // Model events and messages
  // ---------------------------------------------------------------------------
  const on_active_matrix = () => {
    const name = model.get('active_matrix');
    if (name && names.includes(name) && name !== target)
      void switch_matrix(name);
  };

  const on_manual_cat = () => {
    if (current && current.index !== 0) sync_down(current);
  };

  // Python's messages go to the matrix shown, after switching when they are about
  // another one; replies keep their ids.
  const on_message = async (msg, ...rest) => {
    await switching.catch(() => {});
    let message = msg;
    try {
      if (msg?.event === 'apply_state') {
        const changes = msg.changes || {};
        const to = await target_for_changes(changes);
        if (to) await switch_matrix(to);
        const forwarded = { ...changes };
        delete forwarded.matrix;
        message = { ...msg, changes: translate_label_changes(forwarded) };
      } else if (msg?.event === 'restore_snapshot') {
        const to = await target_for_snapshot(msg.snapshot);
        if (to) await switch_matrix(to);
      } else if (
        msg?.event === 'set_categories' &&
        current &&
        current.index !== 0
      ) {
        // Python updates manual_cat itself; the view follows (sync_down).
        model.send?.({ event: 'categories_set', id: msg.id, applied: 0 });
        return;
      }
    } catch (error) {
      const reply = {
        apply_state: 'apply_error',
        restore_snapshot: 'apply_error',
      }[msg?.event];
      if (reply)
        model.send?.({
          event: reply,
          id: msg.id,
          error: String(error?.message || error),
        });
      return;
    }
    [...message_listeners].forEach((listener) => listener(message, ...rest));
  };

  model.on('change:active_matrix', on_active_matrix);
  model.on('change:manual_cat', on_manual_cat);
  model.on('msg:custom', on_message);

  // Snapshot cards and Clerk's links: one listener for every matrix, so a request
  // for another matrix switches first.
  const stop_view_requests = listen_for_view_requests(
    model,
    (snapshot) => restore_snapshot(snapshot, { allow_resize: true }),
    { apply: (changes) => apply_state(changes) }
  );

  primary_network = await load_network(primary);
  target = initial_name;
  await switch_matrix(initial_name);

  const call =
    (method) =>
    (...args) =>
      current?.api?.[method]?.(...args);
  const multi = {
    /** The names of the matrices, in dropdown order. */
    matrix_names: [...names],
    /** The name of the matrix shown. */
    active_matrix: () => current?.entry.name ?? target,
    switch_matrix,
    get obs_store() {
      return current?.api?.obs_store;
    },
    get_state: call('get_state'),
    get_replay_state: () => ({
      ...(current?.api?.get_replay_state() || {}),
      matrix: current?.entry.name,
    }),
    apply_state,
    set_categories: call('set_categories'),
    capture_raster: call('capture_raster'),
    snapshot: (...args) => current.api.snapshot(...args),
    restore_snapshot,
    finalize: () => {
      if (finalized) return;
      finalized = true;
      model.off?.('change:active_matrix', on_active_matrix);
      model.off?.('change:manual_cat', on_manual_cat);
      model.off?.('msg:custom', on_message);
      stop_view_requests();
      unmount();
      message_listeners.clear();
    },
  };

  void consume_initial_snapshot(model, multi, el);
  return multi;
};
