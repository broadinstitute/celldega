import celldega from '../../docs/assets/js/celldega.js';

const status = document.querySelector('#status');
const controls = [...document.querySelectorAll('button, input')];
const network = await (await fetch('./network.json')).json();
const options = { width: 560, height: 450 };
const render = (id, data = network) =>
  celldega.clustergram(document.getElementById(id), {
    ...options,
    network: structuredClone(data),
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

async function fresh(data = network) {
  restored?.finalize();
  restored = await render('restored', data);
  return restored;
}

async function restore() {
  saved ||= await source.snapshot();
  const viz = await fresh();
  await viz.restore_snapshot(saved);
  await settled();
  show(`Restored ${saved.kind} view. Data identity: ${saved.identity.digest}`);
  return viz;
}

async function check() {
  source.finalize();
  source = await render('source');
  source.apply_state({
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
  await document.fonts.ready;
  await settled();
  // JSON encode/decode is also the export/reopen boundary used by an application.
  saved = JSON.parse(JSON.stringify(await source.snapshot()));
  await restore();
  const again = await restored.snapshot();
  const result = {
    fresh_instance_state:
      JSON.stringify(saved.state) === JSON.stringify(again.state),
    fresh_instance_pixels: saved.image.png === again.image.png,
    data_change_rejected: false,
    future_schema_rejected: false,
  };
  try {
    await restored.restore_snapshot({ ...saved, version: 999 });
  } catch (error) {
    result.future_schema_rejected = error.message.includes('schema/version');
  }
  const changed = structuredClone(network);
  changed.mat[0][0] += 0.5; // Same names/dimensions, different scientific value.
  await fresh(changed);
  const before = JSON.stringify((await restored.snapshot()).state);
  try {
    await restored.restore_snapshot(saved);
  } catch (error) {
    result.data_change_rejected =
      error.message.includes('fingerprint') &&
      before === JSON.stringify((await restored.snapshot()).state);
  }
  await restore();
  if (!Object.values(result).every(Boolean))
    throw new Error(JSON.stringify(result));
  show(`All checks passed.\n${JSON.stringify(result, null, 2)}`);
  return result;
}

document.querySelector('#save').onclick = () =>
  busy(async () => {
    saved = await source.snapshot();
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(saved, null, 2)], { type: 'application/json' })
    );
    const link = document.createElement('a');
    link.href = url;
    link.download = 'celldega-view.json';
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
    saved = JSON.parse(await file.text());
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
