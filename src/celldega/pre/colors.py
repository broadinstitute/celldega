"""Categorical colour palettes for clusters and genes.

A leaf module: it imports nothing from celldega. Both ``cell_clusters`` and ``meta_cell``
need ``_create_cluster_colors``, so keeping it here rather than in either one stops those
two modules from having to import each other.
"""

import colorsys


def _hsv_to_hex(h: float) -> str:
    """Convert HSV color to hex string."""
    r, g, b = colorsys.hsv_to_rgb(h, 0.65, 0.9)
    return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"


def _create_cluster_colors(clusters):
    """
    Create color mapping for clusters.

    Parameters:
    - clusters: List of cluster names

    Returns:
    - List of colors for clusters
    """
    n = len(clusters)
    palette = [_hsv_to_hex(i / n) for i in range(n)]

    return [
        (palette[i] if "Blank" not in cluster else "#FFFFFF") for i, cluster in enumerate(clusters)
    ]
