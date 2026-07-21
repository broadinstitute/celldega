"""2D visualization of alignment results.

Kept separate from :mod:`celldega.align.serial_slices` so additional plot
types (e.g. a future 3D/interactive view, once serial alignment gains a Z
axis worth looking at) can be added here without growing the fitting
module — a 2D static matplotlib scatter is what's implemented for now.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
import pandas as pd


if TYPE_CHECKING:
    from celldega.align.serial_slices import SerialAlignmentTransform

__all__ = ["plot_alignment"]


def _scatter_landmarks(
    ax: plt.Axes, landmarks: pd.DataFrame, slice_attr: str, color_by: str
) -> None:
    key = slice_attr if color_by == "slice" else "label"
    for value, group in landmarks.groupby(key):
        ax.scatter(group["x"], group["y"], label=str(value), s=24, alpha=0.85)
    ax.set_aspect("equal")
    ax.set_xlabel("x")
    ax.set_ylabel("y")


def plot_alignment(
    transform: SerialAlignmentTransform,
    color_by: str = "slice",
    figsize: tuple[float, float] = (10, 5),
) -> tuple[plt.Figure, tuple[plt.Axes, plt.Axes]]:
    """Side-by-side 2D scatter of landmarks before vs. after fitting.

    "Before" is ``transform.landmarks_initial`` (each slice's own native
    coordinates — corresponding landmarks generally don't overlap yet);
    "after" is ``transform.landmarks_aligned`` (every slice's landmarks
    warped into the reference slice's frame via its fitted transform). A
    good fit shows same-label points from different slices landing on top
    of each other in the right-hand panel; a poor one shows visible spread.

    Args:
        transform: A fitted :class:`~celldega.align.serial_slices.SerialAlignmentTransform`.
        color_by: ``"slice"`` (default — one color per slice, so a slice
            whose landmarks still stand out after alignment is easy to
            spot) or ``"label"`` (one color per landmark — see which
            specific landmark has the most residual spread).
        figsize: Passed to :func:`matplotlib.pyplot.subplots`.

    Returns:
        ``(fig, (ax_before, ax_after))`` — call ``fig.show()`` or
        ``fig.savefig(...)`` yourself; this never calls ``plt.show()``.

    Raises:
        ValueError: If `color_by` isn't `"slice"` or `"label"`.
    """
    if color_by not in ("slice", "label"):
        raise ValueError(f"color_by must be 'slice' or 'label', got {color_by!r}")

    fig, (ax_before, ax_after) = plt.subplots(1, 2, figsize=figsize)
    _scatter_landmarks(ax_before, transform.landmarks_initial, transform.slice_attr, color_by)
    ax_before.set_title("Before alignment")

    _scatter_landmarks(ax_after, transform.landmarks_aligned, transform.slice_attr, color_by)
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
