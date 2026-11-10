import { version as CELLDEGA_VERSION } from '../../package.json';

import { model_source } from './source';

// A saved view is independent of Clerk and of the transport (web or notebook).
export const SNAPSHOT_SCHEMA = 'celldega.view';
// 2: name-based data identity and canvas size in CSS pixels (1 hashed all loaded data).
export const SNAPSHOT_VERSION = 2;

export const wait_for_canvas = (deck, disposed) =>
  new Promise((resolve, reject) => {
    const deadline = Date.now() + 10000;
    const check = () => {
      if (disposed()) return reject(new Error('Visualization was disposed'));
      const canvas = deck.getCanvas?.();
      if (
        canvas?.width &&
        canvas?.height &&
        deck.isInitialized &&
        deck.getViewports().length
      )
        return resolve();
      if (Date.now() >= deadline)
        return reject(new Error('Visualization canvas did not become ready'));
      setTimeout(check, 16);
    };
    check();
  });

/** A timeout is an error acknowledgement; it does not promise rollback/cancellation. */
export const wait_for_operation = (operation, timeout_ms = 30000) => {
  if (!Number.isFinite(timeout_ms) || timeout_ms <= 0)
    return Promise.reject(new Error('timeout_ms must be positive and finite'));
  let timer;
  return Promise.race([
    Promise.resolve().then(operation),
    new Promise((_, reject) => {
      timer = setTimeout(
        () => reject(new Error('Visualization operation timed out')),
        timeout_ms
      );
    }),
  ]).finally(() => clearTimeout(timer));
};

const canonical = (value) => {
  if (ArrayBuffer.isView(value)) return Array.from(value, canonical);
  if (Array.isArray(value)) return value.map(canonical);
  if (value && typeof value === 'object')
    return Object.fromEntries(
      Object.keys(value)
        .sort()
        .filter((key) => value[key] !== undefined)
        .map((key) => [key, canonical(value[key])])
    );
  return value;
};
const serialize = (value) => JSON.stringify(canonical(value));
const copy = (value) => JSON.parse(serialize(value));

/**
 * A fast 53-bit hash of a list of names (cyrb53). It tells datasets apart; it is
 * not a cryptographic proof of content (declare a `data_revision` for that).
 * @param {Iterable<unknown>} names
 * @returns {string} 14 hex digits.
 */
export const hash_names = (names) => {
  let h1 = 0xdeadbeef;
  let h2 = 0x41c6ce57;
  for (const name of names) {
    const text = String(name);
    for (let i = 0; i < text.length; i += 1) {
      const code = text.charCodeAt(i);
      h1 = Math.imul(h1 ^ code, 2654435761);
      h2 = Math.imul(h2 ^ code, 1597334677);
    }
    // A separator, so ['ab', 'c'] and ['a', 'bc'] differ.
    h1 = Math.imul(h1 ^ 0x1f, 2654435761);
    h2 = Math.imul(h2 ^ 0x1f, 1597334677);
  }
  h1 =
    Math.imul(h1 ^ (h1 >>> 16), 2246822507) ^
    Math.imul(h2 ^ (h2 >>> 13), 3266489909);
  h2 =
    Math.imul(h2 ^ (h2 >>> 16), 2246822507) ^
    Math.imul(h1 ^ (h1 >>> 13), 3266489909);
  return (4294967296 * (2097151 & h2) + (h1 >>> 0))
    .toString(16)
    .padStart(14, '0');
};

// Loaded name arrays are replaced, not edited, when data changes, so a signature
// is computed once per array (and again only if its length changes).
const signatures = new WeakMap();

/**
 * How many names there are and a hash of them, in order.
 * @param {ArrayLike<unknown>|null|undefined} names
 * @returns {{count: number, hash: string}}
 */
export const names_signature = (names) => {
  if (!names || typeof names !== 'object' || !Number.isFinite(names.length))
    return { count: 0, hash: '' };
  const cached = signatures.get(names);
  if (cached?.count === names.length) return { ...cached };
  const signature = { count: names.length, hash: hash_names(names) };
  signatures.set(names, signature);
  return { ...signature };
};

const IDENTITY_LABELS = {
  revision: 'data revision',
  cells: 'cells',
  genes: 'genes',
  clusters: 'cluster labels',
  rows: 'rows',
  cols: 'columns',
};

/**
 * The parts of a saved view's data identity that differ from the loaded data.
 * Parts the saved view doesn't record are not compared; a declared revision is
 * compared only when both sides declare one.
 * @returns {string[]} Readable names of the differing parts.
 */
export const identity_differences = (saved = {}, current = {}) =>
  Object.keys(saved)
    .filter((key) =>
      key === 'revision'
        ? Boolean(saved.revision && current.revision) &&
          saved.revision !== current.revision
        : key in current && serialize(saved[key]) !== serialize(current[key])
    )
    .map((key) => IDENTITY_LABELS[key] || key);

const canvas_size = (value) => ({
  width: Math.round(Number(value?.width) || 0),
  height: Math.round(Number(value?.height) || 0),
});

/**
 * Saved views for a visualization: `snapshot()` and `restore_snapshot()`.
 *
 * @param {object} api
 * @param {'landscape'|'clustergram'} api.kind
 * @param {(options: object) => object} api.get_state - Bounded observations.
 * @param {() => object} api.get_replay_state - Complete supported settings.
 * @param {(options: object) => object|null} api.capture_raster
 * @param {(state: object) => Promise<string[]>|string[]} api.apply_state - Applies a
 *   saved view's replay settings.
 * @param {() => object} api.identity - What the loaded data is (see
 *   `landscape_identity`): small, comparable, cheap to compute.
 * @param {() => object} [api.source] - Where the data came from (URLs, name).
 * @param {() => {width: number, height: number}} api.viewport - Canvas size in
 *   CSS pixels (what the camera framing depends on).
 * @param {() => Promise<void>} [api.ready]
 */
export const create_snapshot_api = ({
  kind,
  get_state,
  get_replay_state,
  capture_raster,
  apply_state,
  identity,
  source,
  viewport,
  ready,
}) => ({
  /** Image, observations, replay settings and identity, all read in one JS task. */
  snapshot: async (options = {}) => {
    for (const key of ['description', 'author']) {
      if (key in options && typeof options[key] !== 'string')
        throw new Error(`${key} must be a string`);
    }
    if (ready) await ready();
    const image = capture_raster(options);
    if (!image?.png) throw new Error('No canvas to capture');
    return {
      schema: SNAPSHOT_SCHEMA,
      version: SNAPSHOT_VERSION,
      renderer: { name: 'celldega', version: CELLDEGA_VERSION },
      kind,
      source: copy(source ? source() : {}),
      captured_at: new Date().toISOString(),
      description: options.description || '',
      author: options.author || '',
      state: copy(get_replay_state()),
      observed_state: copy(get_state(options.state || {})),
      image: copy(image),
      viewport: canvas_size(viewport()),
      capture: {
        max_size: options.max_size ?? 1024,
        thumb_size: options.thumb_size ?? 192,
        state: copy(options.state || {}),
      },
      restoration: 'partial',
      identity: copy(identity()),
    };
  },
  restore_snapshot: async (snapshot, { allow_resize = false } = {}) => {
    if (typeof allow_resize !== 'boolean')
      throw new Error('allow_resize must be a boolean');
    if (
      snapshot?.schema !== SNAPSHOT_SCHEMA ||
      snapshot.version !== SNAPSHOT_VERSION
    )
      throw new Error(
        `Unsupported saved-view schema/version (${snapshot?.schema} v${snapshot?.version}); this Celldega reads ${SNAPSHOT_SCHEMA} v${SNAPSHOT_VERSION}`
      );
    if (snapshot.kind !== kind)
      throw new Error(`Saved view is for ${snapshot.kind}, not ${kind}`);
    if (
      !snapshot.state ||
      typeof snapshot.state !== 'object' ||
      Array.isArray(snapshot.state)
    )
      throw new Error('Saved view has no replay settings');
    if (
      !snapshot.identity ||
      typeof snapshot.identity !== 'object' ||
      !Object.keys(snapshot.identity).length
    )
      throw new Error('Saved view has no data identity');
    snapshot = copy(snapshot);
    if (ready) await ready();
    if (!allow_resize) {
      const saved = canvas_size(snapshot.viewport);
      const now = canvas_size(viewport());
      if (saved.width !== now.width || saved.height !== now.height)
        throw new Error(
          `Saved view canvas size (${saved.width}x${saved.height}) differs from this one (${now.width}x${now.height}); match it, or use allow_resize`
        );
    }
    const differences = identity_differences(snapshot.identity, identity());
    if (differences.length)
      throw new Error(
        `Saved view does not match the loaded data: ${differences.join(', ')} differ`
      );
    // No mutation, including model traits, until every compatibility check passes.
    return apply_state(copy(snapshot.state));
  },
});

/** Common notebook protocol; the same methods are public on standalone instances. */
export const handle_snapshot_message = async (model, api, msg) => {
  if (msg?.event === 'capture_snapshot') {
    try {
      const snapshot = await api.snapshot(msg.options || {});
      model.send({ event: 'snapshot', id: msg.id, snapshot });
    } catch (error) {
      model.send({
        event: 'snapshot_error',
        id: msg.id,
        error: String(error.message || error),
      });
    }
  } else if (msg?.event === 'restore_snapshot') {
    try {
      const done = await api.restore_snapshot(msg.snapshot, msg.options || {});
      model.send({ event: 'applied', id: msg.id, done });
    } catch (error) {
      model.send({
        event: 'apply_error',
        id: msg.id,
        error: String(error.message || error),
      });
    }
  }
};

/**
 * What a Landscape's loaded data is: its cells, genes and per-cell cluster labels
 * (by name, in order), plus a producer-declared revision when there is one.
 */
export const landscape_identity = (state) => ({
  revision: String(state.model?.get?.('data_revision') || ''),
  cells: names_signature(state.cats?.cell_names_array),
  genes: names_signature(state.genes?.gene_names),
  clusters: {
    attribute: state.cats?.inst_cell_attr ?? null,
    ...names_signature(state.cats?.cell_cats),
  },
});

/** Where a Landscape's data came from (recorded, not compared). */
export const landscape_source = (state) => ({
  ...model_source(state.model, 'landscape'),
  base_url: state.global_base_url || '',
  zarr_url: state.model?.get?.('zarr_url') || '',
  data_revision: String(state.model?.get?.('data_revision') || ''),
});

/** Python from_png queues replay before display; consume once after render. */
export const consume_initial_snapshot = async (model, api, element) => {
  const request = model.get?.('_initial_snapshot');
  if (!request || !Object.keys(request).length) return;
  // Clear before awaiting so duplicate views cannot apply the same request twice.
  model.set('_initial_snapshot', {});
  model.save_changes?.();
  try {
    if (request.event !== 'restore_snapshot' || !api?.restore_snapshot)
      throw new Error('This visualization cannot restore the queued saved view');
    const done = await api.restore_snapshot(request.snapshot, request.options || {});
    model.send({ event: 'applied', id: request.id, done });
  } catch (error) {
    const message = String(error.message || error);
    model.send({ event: 'apply_error', id: request.id, error: message });
    if (element?.appendChild) {
      const notice = document.createElement('div');
      notice.setAttribute('role', 'alert');
      notice.textContent = `Saved view was not restored: ${message}`;
      element.appendChild(notice);
    }
  }
};
