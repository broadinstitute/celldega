from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from anndata import AnnData


sys.path.insert(0, str(Path(__file__).parents[3] / "src"))


@pytest.fixture
def adata() -> AnnData:
    obs = pd.DataFrame(
        {
            "cluster": ["B cell", "T cell", "B cell", "B cell", "B cell", "T cell"],
            "sample_id": ["S1", "S1", "S3", "S2", "S2", "S2"],
            "qc": [0.9, 0.2, 0.5, 0.8, 0.7, np.nan],
        },
        index=["c1", "c2", "c3", "c4", "c5", "c6"],
    )
    var = pd.DataFrame(index=["MS4A1", "CD3D"])
    X = np.array(
        [
            [0.0, 4.0],
            [1.0, 9.0],
            [2.0, 5.0],
            [3.0, 2.0],
            [10.0, 0.0],
            [8.0, 3.0],
        ]
    )
    return AnnData(X=X, obs=obs, var=var)


@pytest.fixture
def selector_cls():
    import celldega as dega

    return dega.select.Selector


def test_selector_filters_obs_attributes(adata: AnnData, selector_cls) -> None:
    selector = selector_cls(adata)

    query = (selector.attr("cluster") == "B cell") & (
        selector.attr("sample_id").isin(["S1", "S2"])
    )
    result = selector.select(query=query)

    assert result.ids == ["c1", "c4", "c5"]
    assert result.candidate_count == 3
    assert result.selected_count == 3
    assert result.query == {
        "op": "and",
        "queries": [
            {"op": "eq", "attr": {"type": "obs", "name": "cluster"}, "value": "B cell"},
            {
                "op": "isin",
                "attr": {"type": "obs", "name": "sample_id"},
                "value": ["S1", "S2"],
            },
        ],
    }


def test_selector_quantile_bin_sampler_over_gene(adata: AnnData, selector_cls) -> None:
    selector = selector_cls(adata)

    query = selector.attr("cluster") == "B cell"
    sampler = selector.samplers.quantile_bin(
        attr=selector.gene("MS4A1"),
        bin="high",
        n=2,
        seed=1,
    )
    result = selector.select(query=query, sampler=sampler)

    assert result.ids == ["c5", "c4"]
    assert result.scores == {"c5": 10.0, "c4": 3.0}
    assert result.sampler == {
        "type": "quantile_bin",
        "attr": {"type": "gene", "name": "MS4A1"},
        "bin": "high",
        "n": 2,
        "seed": 1,
        "q_low": 1 / 3,
        "q_high": 2 / 3,
    }
    assert result.provenance["sampler"]["bin_available"] == 2


def test_random_sampler_is_seeded(adata: AnnData, selector_cls) -> None:
    selector = selector_cls(adata)

    query = selector.attr("sample_id").isin(["S1", "S2"])
    result_a = selector.select(
        query=query,
        sampler=selector.samplers.random(n=3, seed=7),
    )
    result_b = selector.select(
        query=query,
        sampler=selector.samplers.random(n=3, seed=7),
    )

    assert result_a.ids == result_b.ids
    assert set(result_a.ids).issubset({"c1", "c2", "c4", "c5", "c6"})


def test_selection_pages_and_frame(adata: AnnData, selector_cls) -> None:
    selector = selector_cls(adata)

    result = selector.select(sampler="all")

    assert len(result) == 6
    assert list(result) == ["c1", "c2", "c3", "c4", "c5", "c6"]
    assert result[0] == "c1"
    assert result[:2] == ["c1", "c2"]
    assert result.names() == ["c1", "c2", "c3", "c4", "c5", "c6"]
    assert result.page(0, 2) == ["c1", "c2"]
    assert result.page(1, 2) == ["c3", "c4"]
    assert result.to_frame().to_dict("list") == {
        "id": ["c1", "c2", "c3", "c4", "c5", "c6"],
        "rank": [0, 1, 2, 3, 4, 5],
    }
    assert result.to_dataframe().equals(result.to_frame())
    assert result.to_json() == result.to_dict()
    assert result.to_json()["provenance"]["candidate_count"] == 6


def test_integer_sampler_shorthand_uses_default_seed(adata: AnnData, selector_cls) -> None:
    selector = selector_cls(adata)

    selection = selector.select(sampler=3)
    explicit_random = selector.select(sampler=selector.samplers.random(n=3, seed=0))

    assert len(selection) == 3
    assert selection.ids == explicit_random.ids
    assert selection.sampler == {"type": "random", "n": 3, "seed": 0, "replace": False}
    assert selection.provenance["sampler"]["shorthand"] == "integer"


def test_bool_is_not_treated_as_integer_sampler(adata: AnnData, selector_cls) -> None:
    selector = selector_cls(adata)

    with pytest.raises(ValueError, match="sampler must be 'all'"):
        selector.select(sampler=True)


def test_default_preview_warns_for_large_unsampled_selection(selector_cls) -> None:
    obs = pd.DataFrame(index=[f"c{i}" for i in range(1005)])
    var = pd.DataFrame(index=["MS4A1"])
    adata = AnnData(X=np.ones((1005, 1)), obs=obs, var=var)
    selector = selector_cls(adata)

    with pytest.warns(UserWarning, match="Returning a deterministic random preview"):
        selection = selector.select()

    explicit_random = selector.select(
        sampler=selector.samplers.random(n=1000, seed=0),
    )

    assert len(selection) == 1000
    assert selection.candidate_count == 1005
    assert selection.sampler == {"type": "default_random_preview", "n": 1000, "seed": 0}
    assert selection.provenance["sampler"]["type"] == "default_random_preview"
    assert selection.ids == explicit_random.ids


def test_sampler_all_returns_large_selection_without_preview_warning(selector_cls) -> None:
    obs = pd.DataFrame(index=[f"c{i}" for i in range(1005)])
    var = pd.DataFrame(index=["MS4A1"])
    adata = AnnData(X=np.ones((1005, 1)), obs=obs, var=var)
    selector = selector_cls(adata)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        selection = selector.select(sampler="all")

    assert len(caught) == 0
    assert len(selection) == 1005
    assert selection.sampler == {"type": "all"}
    assert selection.provenance["sampler"]["type"] == "all"


def test_missing_attribute_and_gene_errors_are_clear(adata: AnnData, selector_cls) -> None:
    selector = selector_cls(adata)

    with pytest.raises(KeyError, match="Attribute 'missing' not found"):
        selector.select(query=selector.attr("missing") == "x")

    with pytest.raises(KeyError, match="Gene 'MISSING' not found"):
        selector.select(query=selector.gene("MISSING") > 0)
