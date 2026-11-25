"""What Clerk reads about a Clustergram's matrices.

A Clustergram can hold several matrices about the same objects
(``Clustergram(matrix={"Gene expression": ..., "Neighborhood enrichment": ...})``)
and shows one at a time. The browser reports the one on screen
(``Clustergram.request_state``); the others are summarized here, in Python, from
their :class:`~celldega.clust.Matrix` objects, in the same shape as the browser's
snapshot so :func:`celldega.clerk.llm.format_clustergram_state` renders both:
names in dendrogram order, the dendrogram groups at the default cut, and a capped
table of values (and dot sizes). Small matrices, such as clusters by clusters, are
sent whole.

The marker and gene lookups Clerk asks for also work here, from the Matrix, when
the matrix that has them is not on screen.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


#: The browser's default dendrogram cut: half the height of the tree.
DEFAULT_CUT = 0.5
#: Caps on what is listed, as in the browser's snapshot.
MAX_GROUPS = 25
MAX_GROUP_MEMBERS = 40
#: Value-table caps for a matrix not on screen (a clusters x clusters matrix of up
#: to 40 clusters is sent whole).
MAX_ROWS = 40
MAX_COLS = 40


def _axis_names(matrix: Any, axis: str) -> list[str]:
    """An axis's names in data order (the order of the linkage's leaves)."""
    data = matrix.data
    return [str(name) for name in (data.index if axis == "row" else data.columns)]


def clustered_names(matrix: Any, axis: str) -> list[str]:
    """An axis's names in dendrogram (clustered) order."""
    nodes = (getattr(matrix, "viz", None) or {}).get(f"{axis}_nodes") or []
    if nodes and all(isinstance(node, dict) and "clust" in node for node in nodes):
        return [str(node["name"]) for node in sorted(nodes, key=lambda node: node["clust"])]
    return _axis_names(matrix, axis)


def dendrogram_groups(matrix: Any, axis: str, cut: float = DEFAULT_CUT) -> dict | None:
    """The groups of an axis's dendrogram cut at ``cut`` of its height, in display
    order, named 1, 2, ... (``None`` without a dendrogram)."""
    from scipy.cluster.hierarchy import fcluster

    linkage = (getattr(matrix, "viz", None) or {}).get("linkage", {}).get(axis)
    linkage = np.asarray(linkage if linkage is not None else [], dtype=float)
    if linkage.ndim != 2 or len(linkage) == 0:
        return None
    # As in the browser: merges below (top height + 0.01) * cut.
    threshold = (float(linkage[-1, 2]) + 0.01) * cut
    labels = fcluster(linkage, t=np.nextafter(threshold, 0), criterion="distance")
    names = _axis_names(matrix, axis)
    if len(labels) != len(names):
        return None
    position = {name: index for index, name in enumerate(clustered_names(matrix, axis))}
    members: dict[int, list[str]] = {}
    for name, label in zip(names, labels, strict=True):
        members.setdefault(int(label), []).append(name)
    groups = sorted(members.values(), key=lambda group: min(position.get(n, 0) for n in group))
    for group in groups:
        group.sort(key=lambda n: position.get(n, 0))
    return {
        "cut_percent": round(cut * 100, 1),
        "n_groups": len(groups),
        "truncated": len(groups) > MAX_GROUPS,
        "groups": [
            {"name": str(index + 1), "size": len(group), "members": group[:MAX_GROUP_MEMBERS]}
            for index, group in enumerate(groups[:MAX_GROUPS])
        ],
    }


def _number(value: Any) -> float | None:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return None if not np.isfinite(value) else round(value, 4)


def _labels(names: list[str], labels: dict[str, dict[str, str]] | None) -> list[dict]:
    """Attributes (e.g. cell types of clusters) for ``names``, as the browser lists them."""
    return [
        {"name": attribute, "type": "categorical", "values": [values.get(n) for n in names]}
        for attribute, values in (labels or {}).items()
        if any(n in values for n in names)
    ]


def matrix_state(
    matrix: Any,
    name: str = "",
    *,
    max_rows: int = MAX_ROWS,
    max_cols: int = MAX_COLS,
    extra_rows: list[str] | tuple = (),
    labels: dict[str, dict[str, str]] | None = None,
) -> dict:
    """A snapshot-shaped summary of a Matrix not on screen.

    A matrix with up to ``max_rows`` rows is listed whole, with its dendrogram
    groups. A bigger one (e.g. thousands of genes) lists only ``extra_rows``: its
    values for the rows asked about, plus its column groups.

    Args:
        matrix: A clustered :class:`~celldega.clust.Matrix`.
        name: Its name in the Clustergram.
        max_rows: Rows listed (in dendrogram order) and in the value table.
        max_cols: Columns listed and in the value table.
        extra_rows: Row names to add (e.g. ones named in the question).
        labels: ``{attribute: {name: label}}`` to annotate rows and columns with,
            e.g. ``{"cell_type": {"4": "Podocyte"}}``; applied to whichever axis
            has those names.

    Returns:
        dict: ``matrix``, ``description``, ``rows``/``cols`` (names, total, order,
        groups, attributes), ``values`` (values and dot sizes) and ``display``.
    """
    data = getattr(matrix, "data", None)
    if data is None or getattr(data, "empty", True):
        return {}
    rows = clustered_names(matrix, "row")
    cols = clustered_names(matrix, "col")
    known = set(rows)
    whole = len(rows) <= max_rows
    shown_rows = rows if whole else []
    added = [str(n) for n in dict.fromkeys(extra_rows) if str(n) in known]
    added = [n for n in added if n not in shown_rows]
    shown_rows = shown_rows + added
    shown_cols = cols[:max_cols]

    frame = data.copy()
    frame.index = frame.index.astype(str)
    frame.columns = frame.columns.astype(str)
    values = frame.reindex(index=shown_rows, columns=shown_cols)
    block: dict[str, Any] = {"values": [[_number(v) for v in row] for row in values.to_numpy()]}
    size = getattr(matrix, "size_matrix", None)
    if isinstance(size, pd.DataFrame) and not size.empty:
        size = size.copy()
        size.index = size.index.astype(str)
        size.columns = size.columns.astype(str)
        sizes = size.reindex(index=shown_rows, columns=shown_cols)
        block["sizes"] = [[_number(v) for v in row] for row in sizes.to_numpy()]

    def axis_state(names, shown, axis):
        listed_whole = len(names) <= (max_rows if axis == "row" else max_cols)
        return {
            # A big matrix lists only the rows asked about.
            "selection_mode": "ranked" if listed_whole else "names",
            "names": shown,
            "added": added if axis == "row" and listed_whole else [],
            "total": len(names) if listed_whole else len(shown),
            "truncated": False,
            "count": len(names),
            "order": {"label": "clustered"},
            "attributes": _labels(shown, labels),
            # Groups of a few hundred names would swamp the summary.
            "groups": dendrogram_groups(matrix, axis) if listed_whole else None,
        }

    return {
        "kind": "clustergram",
        "matrix": name,
        "description": str(getattr(matrix, "description", "") or ""),
        "rows": axis_state(rows, shown_rows, "row"),
        "cols": axis_state(cols, shown_cols, "col"),
        "values": block,
        "display": {"mode": "dotplot" if "sizes" in block else "heatmap"},
    }


def has_markers(matrix: Any) -> bool:
    """Whether a Matrix carries ranked markers (``rank_genes_groups``)."""
    ranks = getattr(matrix, "_marker_ranks", None)
    return ranks is not None and not ranks.empty


def cluster_markers(matrix: Any, clusters: list[str] | None, n: int = 10) -> list[dict]:
    """Each cluster's top ``n`` ranked markers with their value and dot size, as the
    browser's ``cluster_markers`` reports them (``clusters``: all when None)."""
    data = matrix.data.copy()
    data.index = data.index.astype(str)
    data.columns = data.columns.astype(str)
    size = getattr(matrix, "size_matrix", None)
    if isinstance(size, pd.DataFrame):
        size = size.copy()
        size.index = size.index.astype(str)
        size.columns = size.columns.astype(str)
    groups = matrix._marker_groups() if has_markers(matrix) else {}
    wanted = [str(c) for c in clusters] if clusters is not None else list(groups)
    out = []
    for cluster in wanted:
        genes = groups.get(cluster) or []
        if not genes:
            out.append({"cluster": cluster, "found": False, "genes": []})
            continue
        entries = []
        for gene in genes[: max(1, int(n))]:
            entry: dict[str, Any] = {"name": gene, "value": None, "size": None}
            if cluster in data.columns:
                entry["value"] = _number(data.at[gene, cluster])
                if (
                    isinstance(size, pd.DataFrame)
                    and cluster in size.columns
                    and gene in size.index
                ):
                    entry["size"] = _number(size.at[gene, cluster])
            entries.append(entry)
        out.append({"cluster": cluster, "found": True, "genes": entries})
    return out
