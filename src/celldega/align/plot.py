"""2D visualization of alignment results.

Kept separate from :mod:`celldega.align.serial_slices` so additional plot
types (e.g. a future 3D/interactive view, once serial alignment gains a Z
axis worth looking at) can be added here without growing the fitting
module — a 2D static matplotlib scatter is what's implemented for now.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from anndata import AnnData
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from celldega.align._slices import _ordered_slices


if TYPE_CHECKING:
    from celldega.align.serial_slices import SerialAlignmentTransform

__all__ = ["plot_alignment"]


def _slice_color_map(slice_ids: list[Any]) -> dict[Any, tuple]:
    cmap = plt.get_cmap("tab20" if len(slice_ids) > 10 else "tab10")
    return {slice_id: cmap(i % cmap.N) for i, slice_id in enumerate(slice_ids)}


def _scatter_landmarks(
    ax: plt.Axes,
    landmarks: pd.DataFrame,
    slice_attr: str,
    color_by: str,
    with_edges: bool,
) -> None:
    key = slice_attr if color_by == "slice" else "label"
    # A dark edge only helps the landmarks stand out when they're layered on
    # top of a cell-centroid cloud; without cells it just adds visual noise.
    edge = {"edgecolors": "black", "linewidths": 0.5} if with_edges else {}
    for value, group in landmarks.groupby(key):
        ax.scatter(group["x"], group["y"], label=str(value), s=40, alpha=0.95, zorder=3, **edge)
    ax.set_aspect("equal")
    ax.set_xlabel("x")
    ax.set_ylabel("y")


def _scatter_cells(
    ax: plt.Axes,
    transform: SerialAlignmentTransform,
    slice_by_id: dict[Any, AnnData],
    apply_transform: bool,
    color_map: dict[Any, tuple],
    max_cells_per_slice: int,
    cell_size: float,
    rng: np.random.Generator,
) -> None:
    for slice_id, adata in slice_by_id.items():
        coords = np.asarray(adata.obsm["spatial"])[:, :2]
        if max_cells_per_slice and coords.shape[0] > max_cells_per_slice:
            keep = rng.choice(coords.shape[0], size=max_cells_per_slice, replace=False)
            coords = coords[keep]
        if apply_transform:
            coords = transform.apply_to_points(slice_id, coords)
        ax.scatter(
            coords[:, 0],
            coords[:, 1],
            s=cell_size,
            alpha=0.3,
            linewidths=0,
            color=color_map[slice_id],
            zorder=1,
        )


def plot_alignment(
    transform: SerialAlignmentTransform,
    adatas: AnnData | list[AnnData] | None = None,
    slice_attr: str | None = None,
    color_by: str = "slice",
    max_cells_per_slice: int = 20000,
    cell_size: float = 1.0,
    figsize: tuple[float, float] = (12, 6),
    random_state: int = 0,
) -> tuple[plt.Figure, tuple[plt.Axes, plt.Axes]]:
    """Side-by-side 2D scatter of an alignment, before vs. after fitting.

    "Before" is each slice in its own native coordinates; "after" is every
    slice warped into the reference slice's frame by its fitted transform.

    Pass ``adatas`` (strongly recommended) to overlay each slice's actual
    cell centroids underneath the landmarks — that's what actually shows
    whether the *tissue* aligns. Landmarks alone are a poor check: an
    interpolating fit lands every landmark exactly on top of its match by
    construction, so the landmark-only "after" panel looks perfect
    regardless of how well the surrounding tissue really lines up.

    Args:
        transform: A fitted :class:`~celldega.align.serial_slices.SerialAlignmentTransform`.
        adatas: The same slices used to fit ``transform`` (a single combined
            ``AnnData`` with ``slice_attr``, or a list of per-slice
            ``AnnData``). If given, their ``obsm["spatial"]`` centroids are
            drawn faintly (colored by slice) under the landmarks, before and
            after. If ``None`` (default), only landmarks are plotted.
        slice_attr: For a single combined ``AnnData``, the ``obs`` column
            identifying each cell's slice. Defaults to ``transform``'s own
            ``slice_attr``.
        color_by: ``"slice"`` (default) or ``"label"`` — how the *landmarks*
            are colored. Cell centroids are always colored by slice (they
            have no landmark label).
        max_cells_per_slice: Randomly subsample each slice's centroids to at
            most this many before plotting (``0`` disables subsampling), to
            keep the figure light for large slices. The subsample is only
            for display — it never touches the fit.
        cell_size: Marker size for cell centroids (landmarks are drawn
            larger, on top).
        figsize: Passed to :func:`matplotlib.pyplot.subplots`.
        random_state: Seed for the subsampling RNG, so the figure is
            reproducible.

    Returns:
        ``(fig, (ax_before, ax_after))`` — call ``fig.show()`` or
        ``fig.savefig(...)`` yourself; this never calls ``plt.show()``.

    Raises:
        ValueError: If ``color_by`` isn't ``"slice"`` or ``"label"``.
    """
    if color_by not in ("slice", "label"):
        raise ValueError(f"color_by must be 'slice' or 'label', got {color_by!r}")

    slice_by_id = None
    if adatas is not None:
        resolved_attr = slice_attr or transform.slice_attr
        slice_ids, slices, _ = _ordered_slices(adatas, resolved_attr, copy=False)
        slice_by_id = dict(zip(slice_ids, slices, strict=True))

    color_map = _slice_color_map(transform.slice_ids)
    rng = np.random.default_rng(random_state)
    with_cells = slice_by_id is not None

    fig, (ax_before, ax_after) = plt.subplots(1, 2, figsize=figsize)

    if with_cells:
        _scatter_cells(
            ax_before, transform, slice_by_id, False, color_map, max_cells_per_slice, cell_size, rng
        )
    _scatter_landmarks(
        ax_before, transform.landmarks_initial, transform.slice_attr, color_by, with_cells
    )
    ax_before.set_title("Before alignment")

    if with_cells:
        rng = np.random.default_rng(random_state)  # same subsample as "before"
        _scatter_cells(
            ax_after, transform, slice_by_id, True, color_map, max_cells_per_slice, cell_size, rng
        )
    _scatter_landmarks(
        ax_after, transform.landmarks_aligned, transform.slice_attr, color_by, with_cells
    )
    ax_after.set_title(f"After alignment (reference = {transform.reference!r})")

    handles, labels = ax_after.get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        title=color_by,
        loc="center left",
        bbox_to_anchor=(1.0, 0.5),
        fontsize=8,
    )
    fig.tight_layout()
    return fig, (ax_before, ax_after)
