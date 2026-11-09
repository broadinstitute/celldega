import { version as CELLDEGA_VERSION } from '../../package.json';

// A saved view is independent of Clerk and of the transport (web or notebook).
export const SNAPSHOT_SCHEMA = 'celldega.view';
export const SNAPSHOT_VERSION = 1;

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

const fingerprint = async (material) => {
  if (!globalThis.crypto?.subtle)
    throw new Error('Snapshots require Web Crypto (HTTPS or localhost)');
  const digest = await globalThis.crypto.subtle.digest(
    'SHA-256',
    new TextEncoder().encode(material)
  );
  return Array.from(new Uint8Array(digest), (b) =>
    b.toString(16).padStart(2, '0')
  ).join('');
};

export const replay_settings = (state) => {
  if (state.kind === 'clustergram') {
    const settings = {};
    if (state.marker_level)
      settings.marker_level = state.marker_level.current ?? 'all';
    if (state.display?.mode) settings.mode = state.display.mode;
    if (state.display?.size) settings.size = state.display.size;
    settings.focus_gene = state.display?.focused_row || '';
    for (const key of ['view', 'order', 'crop'])
      if (state[key] != null) settings[key] = state[key];
    return copy(settings);
  }
  const settings = { space: state.space };
  if (state.view_state?.target && state.view_state.zoom != null)
    settings.view = state.view_state;
  if (state.selected_genes?.length) settings.genes = state.selected_genes;
  else if (state.color_by === 'cluster')
    settings.clusters = state.selected_clusters || [];
  for (const key of ['layers', 'channels', 'sliders', 'image_source'])
    if (key in state) settings[key] = state[key];
  return copy(settings);
};

/** All reads happen synchronously in one JS task, before asynchronous hashing. */
export const create_snapshot_api = ({
  kind,
  get_state,
  get_replay_state,
  capture_raster,
  apply_state,
  identity,
  viewport,
  ready,
}) => ({
  snapshot: async (options = {}) => {
    for (const key of ['description', 'author']) {
      if (key in options && typeof options[key] !== 'string')
        throw new Error(`${key} must be a string`);
    }
    if (ready) await ready();
    const image = capture_raster(options);
    if (!image?.png) throw new Error('No canvas to capture');
    const observed_state = copy(get_state(options.state || {}));
    const descriptor = identity();
    const material = serialize(descriptor.data);
    const captured = {
      schema: SNAPSHOT_SCHEMA,
      version: SNAPSHOT_VERSION,
      renderer: { name: 'celldega', version: CELLDEGA_VERSION },
      kind,
      source: copy(descriptor.source || {}),
      captured_at: new Date().toISOString(),
      description: options.description || '',
      author: options.author || '',
      state: copy(
        get_replay_state ? get_replay_state() : replay_settings(observed_state)
      ),
      observed_state,
      image: copy(image),
      viewport: copy(viewport()),
      capture: {
        max_size: options.max_size ?? 1024,
        thumb_size: options.thumb_size ?? 192,
        state: copy(options.state || {}),
      },
      restoration: 'partial',
      identity: {
        algorithm: 'sha256',
        coverage: descriptor.coverage,
        unverified: copy(descriptor.unverified || []),
      },
    };
    captured.identity.digest = await fingerprint(material);
    return captured;
  },
  restore_snapshot: async (
    snapshot,
    { allow_unverified = false, allow_resize = false } = {}
  ) => {
    if (
      typeof allow_unverified !== 'boolean' ||
      typeof allow_resize !== 'boolean'
    )
      throw new Error('Restore overrides must be booleans');
    if (
      snapshot?.schema !== SNAPSHOT_SCHEMA ||
      snapshot.version !== SNAPSHOT_VERSION
    )
      throw new Error('Unsupported saved-view schema/version');
    if (snapshot.kind !== kind)
      throw new Error(`Saved view is for ${snapshot.kind}, not ${kind}`);
    if (
      !snapshot.state ||
      typeof snapshot.state !== 'object' ||
      Array.isArray(snapshot.state)
    )
      throw new Error('Saved view has no replay settings');
    snapshot = copy(snapshot);
    if (ready) await ready();
    const descriptor = identity();
    if (
      !allow_unverified &&
      (descriptor.unverified?.length || snapshot.identity?.unverified?.length)
    )
      throw new Error(
        'Dataset assets are not fully identified. Supply a content-based data_revision, or explicitly use allow_unverified'
      );
    if (!allow_resize && serialize(snapshot.viewport) !== serialize(viewport()))
      throw new Error(
        'Saved view canvas size differs; use the original size or explicitly use allow_resize'
      );
    const material = serialize(descriptor.data);
    const digest = await fingerprint(material);
    if (
      snapshot.identity?.algorithm !== 'sha256' ||
      snapshot.identity.digest !== digest
    )
      throw new Error(
        'Saved view data fingerprint does not match this dataset'
      );
    if (material !== serialize(identity().data))
      throw new Error('Dataset changed during restore validation');
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

export const landscape_identity = (state) => {
  const revision = state.model?.get?.('data_revision') || '';
  if (revision && !/^sha256:[0-9a-f]{64}$/.test(revision))
    throw new Error('data_revision must be a sha256: content digest');
  return {
    source: {
      base_url: state.global_base_url,
      zarr_url: state.model?.get?.('zarr_url'),
      data_revision: revision,
    },
    coverage: revision ? 'loaded-data-and-declared-revision' : 'loaded-data',
    unverified: revision ? [] : ['remote-images-transcripts-and-expression'],
    data: {
      revision,
      source: revision ? undefined : state.global_base_url,
      zarr_url: revision ? undefined : state.model?.get?.('zarr_url'),
      zarr_layer: state.model?.get?.('zarr_layer'),
      manifest: state.img?.landscape_parameters,
      segmentation: state.seg?.version,
      cells: state.cats.cell_names_array,
      clusters: state.cats.cell_cats,
      cluster_attr: state.cats.inst_cell_attr,
      positions:
        state.spatial.cell_scatter_data?.attributes?.getPosition?.value,
      embedding: state.spatial.cell_umap_scatter_positions,
      genes: state.genes.gene_names,
      gene_statistics: state.genes.meta_gene,
    },
  };
};
