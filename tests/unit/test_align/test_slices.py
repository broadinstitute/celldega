from anndata import AnnData
import numpy as np
import pandas as pd
import pytest

from celldega.align._slices import _ordered_slices, _resolve_slice_order


def test_resolve_slice_order_sorts_numeric_strings_numerically():
    # Lexicographic sort would put "10" between "1" and "2" -- with 11+
    # slices, string ids like "0".."10" must still resolve in numeric order.
    column = pd.Series([str(i) for i in [3, 10, 1, 0, 2]])

    assert _resolve_slice_order(column) == ["0", "1", "2", "3", "10"]


def test_resolve_slice_order_falls_back_to_lexicographic_for_non_numeric():
    column = pd.Series(["sample_b", "sample_a", "sample_c"])

    assert _resolve_slice_order(column) == ["sample_a", "sample_b", "sample_c"]


def test_resolve_slice_order_respects_ordered_categorical():
    column = pd.Series(pd.Categorical(["10", "0", "2"], categories=["2", "0", "10"], ordered=True))

    assert _resolve_slice_order(column) == ["2", "0", "10"]


def test_ordered_slices_from_combined_anndata_orders_batch_numerically():
    n_per_slice = 2
    batch = [str(i) for i in range(11)]
    obs = pd.DataFrame({"batch": np.repeat(batch, n_per_slice)})
    adata = AnnData(
        X=np.zeros((len(obs), 1)),
        obs=obs,
        var=pd.DataFrame(index=["g0"]),
    )

    slice_ids, slices, slice_attr = _ordered_slices(adata, "batch", copy=False)

    assert slice_ids == [str(i) for i in range(11)]
    assert slice_attr == "batch"
    assert [s.n_obs for s in slices] == [n_per_slice] * 11


def test_ordered_slices_missing_slice_attr_raises():
    adata = AnnData(X=np.zeros((2, 1)), obs=pd.DataFrame(index=["c0", "c1"]))

    with pytest.raises(ValueError, match="slice_attr"):
        _ordered_slices(adata, None)
