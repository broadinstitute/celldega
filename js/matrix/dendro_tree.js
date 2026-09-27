/**
 * Full linkage tree in normalized leaf/distance coordinates. Build iteratively:
 * a highly unbalanced tree must not overflow the call stack or copy descendant
 * arrays at every merge. Leaf ids remain scipy ids; raw_index maps RANK leaves
 * back to the full matrix.
 */
export const build_dendro_tree = (linkage, leaf_map, order) => {
  const count = leaf_map.length;
  if (count < 2 || linkage.length !== count - 1) return null;

  // The matrix renders larger clust ranks first (top to bottom / left to right).
  const sorted = leaf_map
    .map((raw_index, id) => ({ raw_index, id }))
    .sort((a, b) => order[b.raw_index] - order[a.raw_index]);
  const nodes = new Array(count * 2 - 1);
  sorted.forEach(({ raw_index, id }, position) => {
    nodes[id] = {
      id,
      raw_index,
      center: (position + 0.5) / count,
      start: position / count,
      end: (position + 1) / count,
      distance: 0,
      count: 1,
    };
  });

  for (let i = 0; i < linkage.length; i++) {
    const [left_id, right_id, distance] = linkage[i];
    const left = nodes[left_id];
    const right = nodes[right_id];
    if (!left || !right || !Number.isFinite(distance) || distance < 0) {
      return null;
    }
    nodes[count + i] = {
      id: count + i,
      left: left_id,
      right: right_id,
      center: (left.center + right.center) / 2,
      start: Math.min(left.start, right.start),
      end: Math.max(left.end, right.end),
      distance,
      count: left.count + right.count,
    };
  }
  return { nodes, leaf_count: count, leaf_map };
};

/** Use the actual slider's group assignments, including zero-distance merges. */
export const get_dendro_tree_groups = (tree, matrix_nodes) => {
  const ids = new Set(
    tree.leaf_map.map((raw_index) => matrix_nodes[raw_index].group_links)
  );
  return [...ids].map((id) => tree.nodes[Number(id)]).filter(Boolean);
};

/** Rotate the column tree for rows, keeping leaves beside their existing slices. */
export const dendro_tree_point = (
  axis,
  leaf,
  distance,
  max_distance,
  width,
  height
) => {
  const fraction = Math.max(0, Math.min(1, distance / max_distance));
  return axis === 'row'
    ? [width * (1 - fraction), height * leaf]
    : [width * leaf, height * (1 - fraction)];
};
