const element = (tag, styles = {}, text = '') => {
  const node = document.createElement(tag);
  Object.assign(node.style, styles);
  node.textContent = text;
  return node;
};

/** Count the local cell population using the same Cartesian view as Deck. */
export const visible_category_counts = (points, viewState, size) => {
  const scale = 2 ** viewState.zoom;
  const halfWidth = size.width / (2 * scale);
  const halfHeight = size.height / (2 * scale);
  const [cx, cy] = viewState.target;
  const counts = new Map();
  let total = 0;
  for (const point of points) {
    if (
      Math.abs(point.position[0] - cx) > halfWidth ||
      Math.abs(point.position[1] - cy) > halfHeight
    )
      continue;
    total += 1;
    const label = String(point.label ?? 'N.A.');
    counts.set(label, (counts.get(label) || 0) + 1);
  }
  return { counts, total };
};

/** Compact CELL bars, matching the population bars in Landscape controls. */
export const create_scatter_category_panel = ({ onSelect }) => {
  const container = element('div', {
    width: '190px',
    minWidth: '150px',
    fontSize: '10px',
  });
  const summary = element('div', { margin: '2px 0', color: '#47515b' });
  const bars = element('div', {
    height: '49px',
    overflowY: 'auto',
    border: '1px solid #d3d3d3',
  });
  const legend = element('div', { display: 'none', marginTop: '4px' });
  const gradient = element('div', {
    height: '8px',
    border: '1px solid #d3d3d3',
  });
  const range = element('div', {
    display: 'flex',
    justifyContent: 'space-between',
    marginTop: '2px',
  });
  const minLabel = element('span');
  const maxLabel = element('span');
  range.append(minLabel, maxLabel);
  legend.append(gradient, range);
  container.append(summary, bars, legend);
  const onClick = (event) => {
    const button = event.target.closest('button[data-category]');
    if (button && !button.disabled && bars.contains(button))
      onSelect(button.dataset.category, event.shiftKey);
  };
  bars.addEventListener('click', onClick);

  const update = ({
    points,
    viewState,
    size,
    meta,
    selectedCategories,
    loading,
  }) => {
    const { counts, total } = visible_category_counts(points, viewState, size);
    const colorType =
      meta.color_type || (meta.color_by ? 'categorical' : 'uniform');
    const numeric = colorType === 'numeric';
    summary.textContent = `${total.toLocaleString()} cells in view`;
    bars.style.display = colorType === 'categorical' ? 'block' : 'none';
    legend.style.display = numeric ? 'block' : 'none';
    if (numeric) {
      const stops = (
        meta.color_scale || ['#440154', '#21918c', '#fde725']
      ).filter((color) => /^#[0-9a-f]{6}$/i.test(color));
      gradient.style.background = `linear-gradient(to right, ${stops.join(', ')})`;
      minLabel.textContent =
        meta.color_min == null
          ? 'No finite values'
          : String(Number(meta.color_min.toPrecision(4)));
      maxLabel.textContent =
        meta.color_max == null
          ? ''
          : String(Number(meta.color_max.toPrecision(4)));
      return;
    }
    if (colorType !== 'categorical') return;
    const categories = meta.color_categories || [
      ...new Map(
        points.map((point) => [
          point.label,
          { name: point.label, color: point.color },
        ])
      ).values(),
    ];
    const selected = new Set(selectedCategories);
    const maxCount = Math.max(1, ...counts.values());
    bars.replaceChildren(
      ...categories.map(({ name, color }) => {
        const count = counts.get(String(name)) || 0;
        const active = selected.has(String(name));
        const button = element('button', {
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          position: 'relative',
          height: '17px',
          width: '100%',
          padding: '1px 3px',
          border: '0',
          background: 'transparent',
          cursor: 'pointer',
          fontFamily: 'inherit',
          fontSize: '10px',
          textAlign: 'left',
          color: selected.size && !active ? 'gray' : 'black',
          fontWeight: active ? '700' : '400',
        });
        button.type = 'button';
        button.dataset.category = String(name);
        button.setAttribute('aria-pressed', String(active));
        button.disabled = loading;
        button.title = `${name}: ${count} cells in view. Shift-click to select multiple groups.`;
        const bar = element('span', {
          position: 'absolute',
          left: '0',
          top: '0',
          height: '100%',
          width: `${(100 * count) / maxCount}%`,
          background: /^#[0-9a-f]{6}$/i.test(color || '') ? color : 'steelblue',
          opacity: active ? '0.5' : '0.25',
          pointerEvents: 'none',
        });
        const label = element(
          'span',
          {
            position: 'relative',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          },
          String(name)
        );
        const countLabel = element(
          'span',
          { position: 'relative', marginLeft: '5px' },
          count.toLocaleString()
        );
        button.append(bar, label, countLabel);
        return button;
      })
    );
  };
  return {
    element: container,
    update,
    finalize: () => bars.removeEventListener('click', onClick),
  };
};
