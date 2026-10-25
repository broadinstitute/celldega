const empty_collection = () => ({ type: 'FeatureCollection', features: [] });

// Stable across local-server port changes and HTML export. Cell identity is
// part of the space, so a saved polygon cannot silently select another sample.
export const fingerprint = (values) => {
  let hash = 2166136261;
  for (const value of values) {
    const text = `${value}\0`;
    for (let i = 0; i < text.length; i++) {
      hash = Math.imul(hash ^ text.charCodeAt(i), 16777619);
    }
  }
  return (hash >>> 0).toString(16);
};

export const space_key = (space) => JSON.stringify(space);

const in_ring = ([x, y], ring) => {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i];
    const [xj, yj] = ring[j];
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) {
      inside = !inside;
    }
  }
  return inside;
};

export const point_in_gate = (point, geometry) => {
  const polygons =
    geometry.type === 'MultiPolygon'
      ? geometry.coordinates
      : [geometry.coordinates];
  return polygons.some(
    (rings) =>
      in_ring(point, rings[0]) &&
      !rings.slice(1).some((ring) => in_ring(point, ring))
  );
};

export const gate_cell_ids = (geometry, positions, names) =>
  names.filter((_, i) =>
    point_in_gate([positions[2 * i], positions[2 * i + 1]], geometry)
  );

// Called by the existing NBHD editor. Spatial neighborhoods retain their
// original path; embedding polygons use a separate, stateful GeoJSON trait.
export const sync_embedding_gates = (viz_state) => {
  const space = viz_state.neighborhood_space || viz_state.embedding_space;
  if (!space) return false;
  const view = space.kind;
  const collection = viz_state.embedding_gates ?? empty_collection();
  const key = space_key(space);
  const current = viz_state.edit.feature_collection.features.map((feature) => {
    const positions =
      view === 'spatial'
        ? viz_state.spatial.cell_scatter_data?.attributes.getPosition.value
        : view === 'xy'
          ? viz_state.spatial.cell_xy_scatter_positions
          : viz_state.spatial.cell_umap_scatter_positions;
    const cell_ids = positions
      ? gate_cell_ids(
          feature.geometry,
          positions,
          viz_state.cats.cell_names_array
        )
      : [];
    const rings =
      feature.geometry.type === 'Polygon'
        ? feature.geometry.coordinates
        : feature.geometry.coordinates.flat();
    return {
      ...feature,
      properties: {
        ...feature.properties,
        coordinate_space: space,
        x: rings.map((ring) => ring.map((point) => point[0])),
        y: rings.map((ring) => ring.map((point) => point[1])),
        cell_ids,
        cell_count: cell_ids.length,
      },
    };
  });
  viz_state.edit.feature_collection = {
    type: 'FeatureCollection',
    features: current,
  };
  viz_state.embedding_gates = {
    type: 'FeatureCollection',
    features: [
      ...collection.features.filter(
        (feature) => space_key(feature.properties.coordinate_space) !== key
      ),
      ...current,
    ],
  };
  if (viz_state.model?.set) {
    viz_state.publishing_gates = true;
    viz_state.model.set('gates', viz_state.embedding_gates);
    viz_state.model.save_changes();
    viz_state.publishing_gates = false;
  }
  const last = current[viz_state.edit.last_feature_index ?? current.length - 1];
  if (last) viz_state.obs_store.selected_cells.set(last.properties.cell_ids);
  // Also keep the existing physical-neighborhood GeoDataFrame in sync. Its
  // Python observer applies the inverse tissue affine only to spatial polygons.
  return view !== 'spatial';
};

export const show_space_gates = (viz_state, layers_obj, space) => {
  if (!viz_state.neighborhood_space) {
    viz_state.spatial_regions = viz_state.edit.feature_collection;
  }
  viz_state.neighborhood_space = space;
  viz_state.embedding_space = space?.kind === 'spatial' ? null : space;
  const collection = space
    ? {
        type: 'FeatureCollection',
        features: (viz_state.embedding_gates?.features ?? []).filter(
          (feature) =>
            space_key(feature.properties.coordinate_space) === space_key(space)
        ),
      }
    : (viz_state.spatial_regions ?? empty_collection());
  if (
    space?.kind === 'spatial' &&
    !collection.features.length &&
    !viz_state.spatial_gates_initialized
  ) {
    collection.features = viz_state.spatial_regions?.features ?? [];
  }
  if (space?.kind === 'spatial') viz_state.spatial_gates_initialized = true;
  viz_state.edit.feature_collection = collection;
  if (layers_obj.edit_layer) {
    layers_obj.edit_layer = layers_obj.edit_layer.clone({
      data: collection,
      selectedFeatureIndexes: [],
      // Embedding coordinates have no tissue rotation.
      modelMatrix:
        space?.kind !== 'spatial'
          ? null
          : (viz_state.rotation?.modelMatrix ?? null),
      extruded: space?.kind === 'spatial',
      getElevation: space?.kind === 'spatial' ? 1000 : 0,
    });
  }
};
