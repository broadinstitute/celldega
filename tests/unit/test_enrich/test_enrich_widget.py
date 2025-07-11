"""Tests for the Enrich widget traitlets."""

import pytest

try:
    from celldega.viz import Enrich
except Exception as e:  # pragma: no cover - skip if deps missing
    pytest.skip(f"celldega modules unavailable: {e}", allow_module_level=True)


def test_enrich_defaults() -> None:
    w = Enrich()
    assert w.component == "Enrich"
    assert w.gene_list == []
    assert isinstance(w.available_libs, list)
    assert "KEGG_2019_Human" in w.available_libs
    assert w.inst_lib == "KEGG_2019_Human"
    assert w.num_terms == 10


def test_enrich_traitlets_update() -> None:
    w = Enrich()
    w.gene_list = ["A", "B"]
    assert w.gene_list == ["A", "B"]
    w.inst_lib = "GO_Biological_Process_2018"
    assert w.inst_lib == "GO_Biological_Process_2018"
    w.available_libs = ["A", "B"]
    assert w.available_libs == ["A", "B"]
    w.num_terms = 5
    assert w.num_terms == 5

