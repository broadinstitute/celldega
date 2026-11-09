/** Complete semantic controls, independent of bounded scientific observations. */
const axes = ['row', 'col'];
const object = (value) =>
  value && typeof value === 'object' && !Array.isArray(value);
const names = (value, label, known) => {
  if (
    !Array.isArray(value) ||
    value.some((v) => typeof v !== 'string') ||
    new Set(value).size !== value.length
  )
    throw new Error(`${label} must be a list of unique names`);
  if (known && value.some((v) => !known.has(v)))
    throw new Error(`unknown ${label} names`);
};

export const get_replay_controls = (state) => {
  const group = state.obs_store?.dendro_selection?.get?.();
  return {
    dendrogram: Object.fromEntries(
      axes.map((axis) => [
        axis,
        Number(state.dendro?.sliders?.[`${axis}_percent`] ?? 50),
      ])
    ),
    annotations: Object.fromEntries(
      axes.map((axis) => {
        const store = state.obs_store?.manual_cat?.[axis];
        return [
          axis,
          store?.attribute
            ? {
                attribute: store.attribute,
                values: Object.fromEntries(store.values),
                colors: Object.fromEntries(store.colors),
              }
            : null,
        ];
      })
    ),
    selection: {
      rows: [...(state.model?.get?.('selected_rows') || [])],
      cols: [...(state.model?.get?.('selected_cols') || [])],
      genes: [...(state.obs_store?.selected_genes?.get?.() || [])],
      highlighted_genes: [...(state.labels?.highlighted_genes || [])],
      dendrogram: group
        ? { axis: group.axis, members: [...group.selected_names] }
        : null,
    },
  };
};

export const validate_replay_controls = (state, changes) => {
  const known = Object.fromEntries(
    axes.map((axis) => [
      axis,
      new Set((state[`${axis}_nodes`] || []).map((node) => String(node.name))),
    ])
  );
  for (const key of ['dendrogram', 'annotations']) {
    if (!(key in changes)) continue;
    if (
      !object(changes[key]) ||
      Object.keys(changes[key]).some((axis) => !axes.includes(axis))
    )
      throw new Error(`${key} must contain row and/or col`);
  }
  for (const [axis, percent] of Object.entries(changes.dendrogram || {})) {
    if (
      typeof percent !== 'number' ||
      !Number.isFinite(percent) ||
      percent < 0 ||
      percent > 100
    )
      throw new Error(`dendrogram.${axis} must be a percentage from 0 to 100`);
    if (!state.state_controls?.dendrogram)
      throw new Error('Dendrogram controls are not ready');
  }
  for (const [axis, spec] of Object.entries(changes.annotations || {})) {
    if (!state.obs_store?.manual_cat?.[axis])
      throw new Error('Manual annotations are not available');
    if (spec === null) continue;
    if (
      !object(spec) ||
      Object.keys(spec).some(
        (k) => !['attribute', 'values', 'colors'].includes(k)
      ) ||
      typeof spec.attribute !== 'string' ||
      !spec.attribute ||
      !object(spec.values) ||
      !object(spec.colors)
    )
      throw new Error(
        `annotations.${axis} requires attribute, values and colors`
      );
    names(Object.keys(spec.values), `${axis} annotation`, known[axis]);
    if (Object.values(spec.values).some((v) => typeof v !== 'string' || !v))
      throw new Error('Annotation values must be nonempty strings');
    if (
      Object.values(spec.colors).some(
        (v) => typeof v !== 'string' || !/^#[0-9a-f]{6}$/i.test(v)
      )
    )
      throw new Error('Annotation colors must be six-digit hex colors');
  }
  if ('selection' in changes) {
    const spec = changes.selection;
    if (
      !object(spec) ||
      Object.keys(spec).some(
        (k) =>
          ![
            'rows',
            'cols',
            'genes',
            'highlighted_genes',
            'dendrogram',
          ].includes(k)
      )
    )
      throw new Error('Invalid Clustergram selection');
    for (const key of ['rows', 'cols', 'genes', 'highlighted_genes']) {
      if (key in spec)
        names(
          spec[key],
          key,
          key === 'rows' ? known.row : key === 'cols' ? known.col : null
        );
    }
    if (spec.dendrogram != null) {
      const group = spec.dendrogram;
      if (
        !object(group) ||
        !axes.includes(group.axis) ||
        Object.keys(group).some((k) => !['axis', 'members'].includes(k))
      )
        throw new Error('selection.dendrogram requires axis and members');
      names(group.members, 'dendrogram selection', known[group.axis]);
      if (!group.members.length)
        throw new Error('A dendrogram selection needs members');
    }
    if (!state.state_controls?.selection)
      throw new Error('Selection controls are not ready');
  }
};

export const restore_annotations = (state, annotations) => {
  for (const [axis, spec] of Object.entries(annotations)) {
    const store = state.obs_store.manual_cat[axis];
    state.manual_cat.flags[axis] = spec !== null;
    state.manual_cat.config[axis] = spec ? { attribute: spec.attribute } : null;
    // Replace both maps, including unused colors, in one notification. Saved views
    // restore the visualization's annotations; they never write to source AnnData.
    store.attribute = spec?.attribute ?? null;
    store.values = new Map(Object.entries(spec?.values || {}));
    store.colors = new Map(Object.entries(spec?.colors || {}));
    store.emit();
  }
};
