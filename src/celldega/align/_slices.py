"""Shared multi-slice input resolution.

Both :func:`~celldega.align.landmarks.calc_landmarks` and
:func:`~celldega.align.serial_slices.align_serial_slices` accept the same two
input shapes for multiple datasets/slices: a list of ``AnnData`` (list order
is slice order) or one combined ``AnnData`` split by a ``slice_attr`` obs
column. This module holds that shared resolution logic so the two stay
consistent.
"""

from __future__ import annotations

from typing import Any

from anndata import AnnData
import pandas as pd


__all__ = ["_ordered_slices", "_resolve_slice_order"]


def _resolve_slice_order(column: pd.Series) -> list[Any]:
    """Slice order from a slice-tagging column: ordered-categorical order if
    it is one, else sorted unique values — numerically when every value
    looks like a number, so slice ids such as "9"/"10" don't end up sorted
    lexicographically (which would place "10" between "1" and "2")."""
    if isinstance(column.dtype, pd.CategoricalDtype) and column.dtype.ordered:
        return [c for c in column.dtype.categories if c in column.unique()]
    values = column.unique().tolist()
    try:
        return sorted(values, key=float)
    except (TypeError, ValueError):
        return sorted(values)


def _ordered_slices(
    adatas: AnnData | list[AnnData], slice_attr: str | None, copy: bool = True
) -> tuple[list[Any], list[AnnData], str]:
    """Resolve ``(slice_ids, slices, slice_attr)`` from either input shape.

    Does not enforce a minimum slice count — callers apply their own
    requirements (e.g. :func:`~celldega.align.serial_slices.align_serial_slices`
    requires at least 2).

    Args:
        adatas: A list of per-slice ``AnnData`` (list order is slice order),
            or a single ``AnnData`` combining all slices, in which case
            ``slice_attr`` is required to split it.
        slice_attr: For a single combined ``AnnData``, the ``obs`` column
            identifying each cell's slice (required in that case). For a
            list of ``AnnData``, the name to use for the resolved slice-key
            (default ``"slice"``) — purely a label, since list order already
            defines the slices.
        copy: If ``True`` (default), return copies safe to mutate. Pass
            ``False`` for read-only access (e.g. computing landmarks) to
            avoid copying potentially large ``AnnData`` objects.

    Returns:
        ``(slice_ids, slices, slice_attr)`` — ``slice_ids`` in resolved order,
        the corresponding per-slice ``AnnData`` objects, and the resolved
        ``slice_attr`` name.

    Raises:
        ValueError: If ``adatas`` is a single ``AnnData`` without
            ``slice_attr``, or ``slice_attr`` is not a column in its ``obs``.
    """
    if isinstance(adatas, AnnData):
        if slice_attr is None:
            raise ValueError(
                "slice_attr is required when 'adatas' is a single combined AnnData, "
                "so slices can be identified from an obs column"
            )
        if slice_attr not in adatas.obs.columns:
            raise ValueError(f"'{slice_attr}' is not a column in adatas.obs")

        slice_ids = _resolve_slice_order(adatas.obs[slice_attr])
        slices = [adatas[adatas.obs[slice_attr] == slice_id] for slice_id in slice_ids]
        if copy:
            slices = [s.copy() for s in slices]
        return slice_ids, slices, slice_attr

    slices = list(adatas)
    slice_ids = list(range(len(slices)))
    if copy:
        slices = [s.copy() for s in slices]
    return slice_ids, slices, slice_attr or "slice"
