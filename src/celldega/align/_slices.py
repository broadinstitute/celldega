"""Shared multi-slice input resolution.

Both :func:`~celldega.align.landmarks.calc_landmarks` and
:func:`~celldega.align.serial_slices.align_serial_slices` accept the same two
input shapes for multiple datasets/slices: a list of ``AnnData`` (list order
is slice order) or one combined ``AnnData`` split by a ``slice_key`` obs
column. This module holds that shared resolution logic so the two stay
consistent.
"""

from __future__ import annotations

from typing import Any

from anndata import AnnData
import pandas as pd


__all__ = ["_ordered_slices"]


def _ordered_slices(
    adatas: AnnData | list[AnnData], slice_key: str | None, copy: bool = True
) -> tuple[list[Any], list[AnnData], str]:
    """Resolve ``(slice_ids, slices, slice_key)`` from either input shape.

    Does not enforce a minimum slice count — callers apply their own
    requirements (e.g. :func:`~celldega.align.serial_slices.align_serial_slices`
    requires at least 2).

    Args:
        adatas: A list of per-slice ``AnnData`` (list order is slice order),
            or a single ``AnnData`` combining all slices, in which case
            ``slice_key`` is required to split it.
        slice_key: For a single combined ``AnnData``, the ``obs`` column
            identifying each cell's slice (required in that case). For a
            list of ``AnnData``, the name to use for the resolved slice-key
            (default ``"slice"``) — purely a label, since list order already
            defines the slices.
        copy: If ``True`` (default), return copies safe to mutate. Pass
            ``False`` for read-only access (e.g. computing landmarks) to
            avoid copying potentially large ``AnnData`` objects.

    Returns:
        ``(slice_ids, slices, slice_key)`` — ``slice_ids`` in resolved order,
        the corresponding per-slice ``AnnData`` objects, and the resolved
        ``slice_key`` name.

    Raises:
        ValueError: If ``adatas`` is a single ``AnnData`` without
            ``slice_key``, or ``slice_key`` is not a column in its ``obs``.
    """
    if isinstance(adatas, AnnData):
        if slice_key is None:
            raise ValueError(
                "slice_key is required when 'adatas' is a single combined AnnData, "
                "so slices can be identified from an obs column"
            )
        if slice_key not in adatas.obs.columns:
            raise ValueError(f"'{slice_key}' is not a column in adatas.obs")

        column = adatas.obs[slice_key]
        if isinstance(column.dtype, pd.CategoricalDtype) and column.dtype.ordered:
            slice_ids = [c for c in column.dtype.categories if c in column.unique()]
        else:
            slice_ids = sorted(column.unique().tolist())
        slices = [adatas[column == slice_id] for slice_id in slice_ids]
        if copy:
            slices = [s.copy() for s in slices]
        return slice_ids, slices, slice_key

    slices = list(adatas)
    slice_ids = list(range(len(slices)))
    if copy:
        slices = [s.copy() for s in slices]
    return slice_ids, slices, slice_key or "slice"
