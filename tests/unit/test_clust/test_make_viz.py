"""Visualization JSON generation for clustergram.js."""

import numpy as np


def viz_json(net, dendro: bool = True, links: bool = False) -> None:
    """Generate visualization JSON for clustergram.js."""
    # Validate once upfront
    if not all(hasattr(net, attr) for attr in ("viz", "dat")):
        raise AttributeError("Network missing required attributes")
    if missing := {"nodes", "node_info", "mat"} - net.dat.keys():
        raise KeyError(f"Missing keys: {missing}")

    dat = net.dat  # Cache reference
    viz = net.viz  # Cache reference

    # Set linkage data
    viz["linkage"] = {axis: dat["node_info"][axis]["Y"].tolist() for axis in ("row", "col")}

    # Process nodes for both axes
    for axis in dat["nodes"]:
        node_info = dat["node_info"][axis]
        nodes = dat["nodes"][axis]
        axis_nodes = viz[f"{axis}_nodes"]

        # Pre-compute cluster lookup and category keys once per axis
        cluster_lookup = {v: i for i, v in enumerate(node_info["clust"])}
        cat_keys = [k for k in node_info if k.startswith("cat-")]

        # Process all nodes for this axis
        for i, name in enumerate(nodes):
            try:
                # Build node dict efficiently
                node = {
                    "name": name,
                    "ini": node_info["ini"][i],
                    "clust": cluster_lookup.get(node_info["clust"][i], i),
                    "rank": node_info["rank"][i],
                }

                # Add optional fields in single pass
                _add_optional_fields(node, node_info, i, cat_keys)
                axis_nodes.append(node)

            except IndexError as e:
                raise IndexError(f"Index {i} out of bounds in {axis} node_info") from e

    # Save data efficiently
    viz["mat" if not links else "links"] = (
        dat["mat"].tolist()
        if not links
        else [
            {
                "source": i,
                "target": j,
                "value": val,
                **({} if not np.isnan(val := float(dat["mat"][i, j])) else {"value_orig": "NaN"}),
            }
            for i in range(len(dat["nodes"]["row"]))
            for j in range(len(dat["nodes"]["col"]))
        ]
    )


def _add_optional_fields(node: dict, node_info: dict, i: int, cat_keys: list) -> None:
    """Add all optional fields to node in single pass."""
    # Add scalar optional fields
    for field in ("rankvar", "value", "info"):
        if (data := node_info.get(field)) and i < len(data):
            node[field] = data[i]

    # Add categories efficiently
    for cat_key in cat_keys:
        if i >= len(node_info[cat_key]):
            continue

        cat_value = node_info[cat_key][i]
        node[cat_key] = cat_value
        base_key = cat_key.replace("-", "_")

        # Add p-value and index in single check
        if (pval_data := node_info.get(f"pval_{base_key}")) and cat_value in pval_data:
            node[f"{base_key}_pval"] = pval_data[cat_value]
        if (idx_data := node_info.get(f"{base_key}_index")) and i < len(idx_data):
            node[f"{base_key}_index"] = idx_data[i]
