"""Selecting cells by their spatial neighbors (``Selector.neighbors``)."""

from __future__ import annotations

import json

from anndata import AnnData
import numpy as np
import pandas as pd
import pytest
from scipy import sparse


@pytest.fixture
def adata() -> AnnData:
    """Six cells in a row (c1-c2-c3-c4-c5) plus c6 alone; c3 also touches c5."""
    obs = pd.DataFrame(
        {"cluster": pd.Categorical(["EC", "Pod", "EC", "Pod", "Pod", "EC"])},
        index=[f"c{i}" for i in range(1, 7)],
    )
    adata = AnnData(
        X=np.array([[0.0], [5.0], [3.0], [6.0], [7.0], [4.0]]),
        obs=obs,
        var=pd.DataFrame(index=["NPHS2"]),
    )
    edges = [(0, 1), (1, 2), (2, 3), (3, 4), (2, 4)]
    rows, cols = zip(*[*edges, *[(b, a) for a, b in edges]], strict=True)
    # Weighted, with a self-edge: neighbors count once and never themselves.
    graph = sparse.csr_matrix((np.full(len(rows), 0.5), (rows, cols)), shape=(6, 6))
    graph = graph + sparse.eye(6, format="csr")
    adata.obsp["spatial_connectivities"] = graph
    return adata


def test_neighbors_count_and_fraction(adata):
    from celldega.select import Selector

    selector = Selector(adata)
    counts = selector.neighbors("cluster", "Pod").evaluate(selector)
    assert counts.to_dict() == {"c1": 1, "c2": 0, "c3": 3, "c4": 1, "c5": 1, "c6": 0}
    fraction = selector.neighbors("cluster", "Pod", stat="fraction").evaluate(selector)
    assert fraction["c3"] == pytest.approx(1.0)
    assert fraction["c4"] == pytest.approx(0.5)
    assert np.isnan(fraction["c6"])  # no neighbors at all


def test_neighbors_combine_with_obs_and_genes(adata):
    from celldega.select import Selector

    selector = Selector(adata)
    query = (selector.attr("cluster") == "EC") & (selector.neighbors("cluster", "Pod") >= 1)
    assert selector.select(query=query, sampler="all").names() == ["c1", "c3"]
    ranked = selector.select(
        query=selector.attr("cluster") == "EC",
        sampler=selector.samplers.rank(selector.neighbors("cluster", "Pod"), n=2, by="high"),
    )
    assert ranked.names() == ["c3", "c1"]
    query = query & (selector.gene("NPHS2") > 1)
    assert selector.select(query=query, sampler="all").names() == ["c3"]


def test_neighbors_from_json_as_clerk_writes_them(adata):
    from celldega.select import Selector, query_from_dict, sampler_from_dict

    selector = Selector(adata)
    spec = {
        "op": "and",
        "queries": [
            {"op": "eq", "attr": {"type": "obs", "name": "cluster"}, "value": "EC"},
            {
                "op": "ge",
                "attr": {"type": "neighbors", "name": "cluster", "value": "Pod"},
                "value": 2,
            },
        ],
    }
    query = query_from_dict(json.loads(json.dumps(spec)))
    assert selector.select(query=query, sampler="all").names() == ["c3"]
    # Serializes back to the same form.
    leaf = query.to_dict()["queries"][1]["attr"]
    assert leaf == {"type": "neighbors", "name": "cluster", "value": "Pod", "stat": "count"}
    sampler = sampler_from_dict(
        {"type": "rank", "attr": {"type": "neighbors", "name": "cluster", "value": "Pod"}, "n": 1}
    )
    assert selector.select(sampler=sampler).names() == ["c3"]


def test_neighbors_errors(adata):
    from celldega.select import Selector, query_from_dict

    selector = Selector(adata)
    with pytest.raises(ValueError, match="No cell has cluster == 'Podo'"):
        selector.neighbors("cluster", "Podo").evaluate(selector)
    with pytest.raises(KeyError, match="squidpy"):
        selector.neighbors("cluster", "Pod", graph="other").evaluate(selector)
    with pytest.raises(ValueError, match="stat"):
        selector.neighbors("cluster", "Pod", stat="mean")
    with pytest.raises(ValueError, match="needs a"):
        query_from_dict({"op": "gt", "attr": {"type": "neighbors", "name": "cluster"}, "value": 1})


def test_clerk_is_told_about_the_graph_not_its_values(adata):
    from celldega.clerk.llm import describe_anndata

    adata.uns["spatial_neighbors"] = {"params": {"delaunay": True, "max_edge_um": 25}}
    text = describe_anndata(adata)
    assert "spatial neighbor graph (Delaunay neighbors closer than 25 um" in text
    assert '{"type": "neighbors"' in text
    del adata.obsp["spatial_connectivities"]
    assert "neighbor graph" not in describe_anndata(adata)
