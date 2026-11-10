import celldega from '../../docs/assets/js/celldega.js';

const status = document.querySelector('#status');
const controls = [...document.querySelectorAll('button, input')];
const network = await (await fetch('./network.json')).json();
const options = { width: 560, height: 450 };
const render = (id, data = network, data_revision = '') =>
  celldega.clustergram(document.getElementById(id), {
    ...options,
    network: structuredClone(data),
    data_revision,
  });
let source = await render('source');
let restored;
let saved;

// The demo waits for the existing reorder/camera animations to settle before
// comparing pixels. snapshot() itself reads image + state in a single JS task.
const settled = () => new Promise((resolve) => setTimeout(resolve, 1600));
const show = (message) => {
  status.textContent = message;
};
const busy = async (work) => {
  controls.forEach((control) => {
    control.disabled = true;
  });
  try {
    return await work();
  } catch (error) {
    show(`Failed: ${error.message}`);
    throw error;
  } finally {
    controls.forEach((control) => {
      control.disabled = false;
    });
  }
};

async function fresh(data = network, data_revision = '') {
  restored?.finalize();
  restored = await render('restored', data, data_revision);
  return restored;
}

async function restore() {
  saved ||= await source.snapshot();
  const viz = await fresh();
  await viz.restore_snapshot(saved);
  await settled();
  const { rows, cols } = saved.identity;
  show(
    `Restored ${saved.kind} view of ${rows.count} rows x ${cols.count} columns (names ${rows.hash} / ${cols.hash}).`
  );
  return viz;
}

async function check() {
  source.finalize();
  source = await render('source');
  source.apply_state({
    dendrogram: { row: 35, col: 65 },
    annotations: {
      row: {
        attribute: 'review',
        values: { [network.row_nodes[3].name]: 'marker' },
        colors: { marker: '#dd3344' },
      },
      col: {
        attribute: 'cell_type',
        values: { C3: 'population' },
        colors: { population: '#3377cc' },
      },
    },
    selection: {
      rows: [network.row_nodes[3].name],
      cols: ['C3'],
      genes: [network.row_nodes[3].name],
      highlighted_genes: [network.row_nodes[3].name.toLowerCase()],
      dendrogram: null,
    },
    order: {
      row: network.row_nodes.map((node) => node.name).reverse(),
      col: 'rank',
    },
    crop: {
      row: network.row_nodes.slice(2, 16).map((node) => node.name),
      col: ['C1', 'C3', 'C5', 'C7'],
    },
    view: { target: [230, 220], zoom: [0.25, 0.5] },
  });
  const group = source.get_state().cols.groups.groups[0];
  source.apply_state({
    selection: { dendrogram: { axis: 'col', members: group.members } },
  });
  await document.fonts.ready;
  await settled();
  // JSON encode/decode is also the export/reopen boundary used by an application.
  saved = JSON.parse(JSON.stringify(await source.snapshot()));
  source.apply_state({
    dendrogram: { row: 80, col: 20 },
    annotations: { row: null, col: null },
    selection: {
      rows: [],
      cols: [],
      genes: [],
      highlighted_genes: [],
      dendrogram: null,
    },
    crop: { row: null, col: null },
    order: { row: 'clust', col: 'clust' },
    view: { target: [0, 0], zoom: [1, 1] },
  });
  await settled();
  await source.restore_snapshot(saved);
  await settled();
  const restoredSource = await source.snapshot();
  await restore();
  const again = await restored.snapshot();
  const result = {
    changed_view_state:
      JSON.stringify(saved.state) === JSON.stringify(restoredSource.state),
    changed_view_pixels: saved.image.png === restoredSource.image.png,
    fresh_instance_state:
      JSON.stringify(saved.state) === JSON.stringify(again.state),
    fresh_instance_pixels: saved.image.png === again.image.png,
    data_change_rejected: false,
    revision_change_rejected: false,
    future_schema_rejected: false,
  };
  try {
    await restored.restore_snapshot({ ...saved, version: 999 });
  } catch (error) {
    result.future_schema_rejected = error.message.includes('schema/version');
  }
  const changed = structuredClone(network);
  // Same dimensions, a different row: the saved view is for other data.
  changed.row_nodes[0].name = `${changed.row_nodes[0].name}-other`;
  await fresh(changed);
  const before = JSON.stringify((await restored.snapshot()).state);
  try {
    await restored.restore_snapshot(saved);
  } catch (error) {
    result.data_change_rejected =
      error.message.includes('rows differ') &&
      before === JSON.stringify((await restored.snapshot()).state);
  }
  // The same matrix declared as two releases: a constructor's data_revision is
  // recorded in the saved view and compared on restore.
  const release_1 = await (await fresh(network, 'release-1')).snapshot();
  await fresh(network, 'release-2');
  try {
    await restored.restore_snapshot(release_1);
  } catch (error) {
    result.revision_change_rejected =
      release_1.identity.revision === 'release-1' &&
      error.message.includes('data revision differ');
  }
  await restore();
  const png = celldega.snapshot_png(saved);
  const record = await celldega.read_png(png);
  result.png_metadata = JSON.stringify(record.widgets[0].snapshot.state) === JSON.stringify(saved.state)
    && !('image' in record.widgets[0].snapshot);
  restored.finalize();
  restored = await celldega.from_png(document.getElementById('restored'), png, {
    network: structuredClone(network),
  });
  await settled();
  const pngRestored = await restored.snapshot();
  result.png_fresh_instance_state = JSON.stringify(pngRestored.state) === JSON.stringify(saved.state);
  result.png_fresh_instance_pixels = pngRestored.image.png === saved.image.png;
  if (!Object.values(result).every(Boolean))
    throw new Error(JSON.stringify(result));
  show(`All checks passed.\n${JSON.stringify(result, null, 2)}`);
  return result;
}

document.querySelector('#save').onclick = () =>
  busy(async () => {
    saved = await source.snapshot();
    const url = URL.createObjectURL(celldega.snapshot_png(saved));
    const link = document.createElement('a');
    link.href = url;
    link.download = 'celldega-view.png';
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    show(
      'Saved image, observations, replay settings and data identity together.'
    );
  });
document.querySelector('#open').onchange = (event) =>
  busy(async () => {
    const file = event.target.files[0];
    if (!file) return;
    saved = file.name.toLowerCase().endsWith('.png')
      ? (await celldega.read_png(file)).widgets[0].snapshot
      : JSON.parse(await file.text());
    await restore();
  });
document.querySelector('#restore').onclick = () => busy(restore);
document.querySelector('#check').onclick = () => busy(check);
controls.forEach((control) => {
  control.disabled = false;
});
show('Ready. Explore the left view, or run the reproducibility checks.');
// Automation hook: no notebook, kernel or model service is required.
window.celldegaSnapshotExample = {
  check: () => busy(check),
  restore: () => busy(restore),
};
