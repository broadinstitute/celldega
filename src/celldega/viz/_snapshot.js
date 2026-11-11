// Static postcard renderer: no visualization bundle, network requests or data loaders.
export default {
  render({ model, el }) {
    const card = document.createElement('figure');
    card.className = 'celldega-snapshot';
    const style = document.createElement('style');
    style.textContent = `
      .celldega-snapshot { margin:12px 0; max-width:760px; background:#fff;
        color:#334155; border:1px solid #d9dfe5; border-radius:6px; overflow:hidden;
        box-shadow:0 2px 7px #2434440c; font:13px/1.5 system-ui,sans-serif; }
      .celldega-snapshot > img { display:block; width:100%; height:auto; }
      .celldega-snapshot figcaption { padding:12px 16px; border-top:1px solid #edf0f3; }
      .celldega-snapshot h3 { margin:0; font-size:15px; color:#253547; }
      .celldega-snapshot .memo { white-space:pre-wrap; margin:4px 0 10px; }
      .celldega-snapshot .actions { display:flex; gap:18px; flex-wrap:wrap; align-items:baseline; }
      .celldega-snapshot button { border:0; background:none; padding:0;
        font:inherit; cursor:pointer; color:#2c7fb8; text-decoration:underline; }
      .celldega-snapshot button:disabled { cursor:wait; opacity:.6; }
      .celldega-snapshot summary { cursor:pointer; color:#64748b; }
      .celldega-snapshot pre { white-space:pre-wrap; overflow-wrap:anywhere;
        max-height:260px; overflow:auto; padding:8px; background:#f6f8fa; font-size:11px; }
      .celldega-snapshot .status { font-size:12px; color:#64748b; margin-top:6px; }
    `;
    const img = document.createElement('img');
    const caption = document.createElement('figcaption');
    const title = document.createElement('h3');
    const memo = document.createElement('div');
    memo.className = 'memo';
    const actions = document.createElement('div');
    actions.className = 'actions';
    const restore = document.createElement('button');
    restore.type = 'button';
    restore.textContent = 'Show this view';
    const details = document.createElement('details');
    const summary = document.createElement('summary');
    summary.textContent = 'Snapshot metadata';
    const metadata = document.createElement('pre');
    details.append(summary, metadata);
    const status = document.createElement('div');
    status.className = 'status';
    status.setAttribute('role', 'status');
    actions.append(restore);
    caption.append(title, memo, actions, details, status);
    card.append(img, caption);
    el.append(style, card);

    let pending = false;
    let timer;
    const update = () => {
      const src = `data:image/png;base64,${model.get('image')}`;
      if (img.getAttribute('src') !== src) img.src = src;
      img.alt = model.get('name') || 'Snapshot';
      title.textContent = model.get('name');
      memo.textContent = model.get('description');
      restore.hidden = !model.get('can_restore');
      restore.title = `Open in the linked ${model.get('target_label')}`;
      restore.disabled = Boolean(model.get('busy'));
      status.textContent = model.get('status');
      metadata.textContent = JSON.stringify(model.get('metadata'), null, 2);
      pending = false;
      clearTimeout(timer);
    };
    const navigate = () => {
      if (pending || model.get('busy')) return;
      pending = true;
      restore.disabled = true;
      status.textContent = 'Opening this view…';
      model.send({ event: 'restore' });
      // An exported notebook may have no kernel to answer the click.
      timer = setTimeout(() => {
        pending = false;
        restore.disabled = false;
        status.textContent =
          'Connect a live kernel and display the linked viewer to open this view.';
      }, 40000);
    };
    restore.addEventListener('click', navigate);
    const traits = [
      'image',
      'name',
      'description',
      'metadata',
      'can_restore',
      'target_label',
      'status',
      'busy',
    ];
    traits.forEach((name) => model.on(`change:${name}`, update));
    update();
    return () => {
      clearTimeout(timer);
      traits.forEach((name) => model.off(`change:${name}`, update));
      restore.removeEventListener('click', navigate);
      card.remove();
      style.remove();
    };
  },
};
