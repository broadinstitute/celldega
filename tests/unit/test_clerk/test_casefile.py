"""Tests for the CaseFile durable annotation record."""

import pytest


try:
    from celldega.clerk import CaseFile
except Exception as e:  # pragma: no cover - skip if deps missing
    pytest.skip(f"celldega modules unavailable: {e}", allow_module_level=True)


def test_casefile_keys_off_entity() -> None:
    cf = CaseFile(entity_id="5", entity_attr="leiden")
    assert cf.entity_id == "5"
    assert cf.entity_attr == "leiden"
    assert cf.status == "open"
    assert cf.label == ""


def test_casefile_rulings() -> None:
    cf = CaseFile(entity_id="5")
    cf.add_message("user", "what is this?")
    cf.add_message("clerk", "CD8+ T cells")
    cf.propose("CD8+ T cell")
    assert cf.label == "CD8+ T cell"
    assert cf.status == "open"

    cf.accept()
    assert cf.status == "accepted"
    assert cf.final_label == "CD8+ T cell"
    assert cf.label == "CD8+ T cell"

    cf.edit("CD4+ T cell")
    assert cf.status == "edited"
    assert cf.label == "CD4+ T cell"
    actions = [h["action"] for h in cf.history]
    assert actions == ["propose", "accept", "edit"]


def test_casefile_roundtrip() -> None:
    cf = CaseFile(
        entity_id="5",
        gene_list=["CD3D", "CD8A"],
        context="Xenium lung",
        provenance={"view_state": {"zoom": 3}},
    )
    cf.add_message("user", "q").propose("T cell").accept()

    restored = CaseFile.from_json(cf.to_json())
    assert restored.entity_id == "5"
    assert restored.gene_list == ["CD3D", "CD8A"]
    assert restored.provenance == {"view_state": {"zoom": 3}}
    assert restored.final_label == "T cell"
    assert restored.status == "accepted"


def test_casefile_from_dict_ignores_unknown_keys() -> None:
    cf = CaseFile.from_dict({"entity_id": "9", "future_field": 123})
    assert cf.entity_id == "9"
    assert not hasattr(cf, "future_field")


def test_casefile_requires_entity_id() -> None:
    with pytest.raises(ValueError):
        CaseFile.from_dict({"gene_list": []})


def test_casefile_save_load(tmp_path) -> None:
    cf = CaseFile(entity_id="7", gene_list=["A"]).propose("Neuron").accept()
    path = tmp_path / "case7.json"
    cf.save(path)
    loaded = CaseFile.load(path)
    assert loaded.entity_id == "7"
    assert loaded.label == "Neuron"
