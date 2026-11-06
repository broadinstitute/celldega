"""Checked portraits are separate from Yearbook's displayed cell candidates."""

import anndata as ad
import numpy as np
import pytest
import traitlets

from celldega.viz import Yearbook


@pytest.fixture
def yearbook():
    widget = Yearbook(
        base_url="https://example.org/data",
        cells=["a", "b", "c", "d", "e", "f"],
        rows=1,
        cols=2,
    )
    yield widget
    widget.close()


def test_checked_portraits_default_empty_and_sync_independently(yearbook):
    assert yearbook.selected_cells == []
    assert yearbook.get_state()["selected_cells"] == []
    assert yearbook.traits()["selected_cells"].metadata["sync"]
    another = Yearbook(base_url="https://example.org/data")
    try:
        yearbook.selected_cells = ["b"]
        assert another.selected_cells == []
        assert yearbook.cells == ["a", "b", "c", "d", "e", "f"]
    finally:
        another.close()


def test_constructor_keeps_checked_ids_separate_from_input_selection():
    widget = Yearbook(
        base_url="https://example.org/data",
        selection={"ids": ["a", "b", "c"]},
        selected_cells=["c", "a", "off-page-id"],
    )
    try:
        assert widget.cells == ["a", "b", "c"]
        assert widget.selection["ids"] == ["a", "b", "c"]
        assert widget.selected_cells == ["c", "a", "off-page-id"]
        assert widget.get_state()["selected_cells"] == ["c", "a", "off-page-id"]
    finally:
        widget.close()


def test_checked_ids_survive_pagination_and_new_query_candidates(yearbook):
    yearbook.selected_cells = ["e", "a"]
    yearbook.go_to_page(2)
    yearbook.prev_page()
    yearbook.next_page()
    assert yearbook.current_page == 2
    assert yearbook.selected_cells == ["e", "a"]

    yearbook.front_end_query = {"cluster": {"attr": "leiden", "value": "5"}}
    yearbook.cells = ["new-a", "new-b"]
    yearbook.current_page = 0
    assert yearbook.selected_cells == ["e", "a"]


def test_programmatic_and_frontend_updates_preserve_id_order(yearbook):
    yearbook.selected_cells = ["c", "a"]
    assert yearbook.get_state()["selected_cells"] == ["c", "a"]
    yearbook.set_state({"selected_cells": ["f", "b", "细胞_1_é"]})
    assert yearbook.get_selected_cells() == ["f", "b", "细胞_1_é"]
    assert yearbook.cells == ["a", "b", "c", "d", "e", "f"]
    ids = yearbook.get_selected_cells()
    ids.append("separate-copy")
    assert yearbook.selected_cells == ["f", "b", "细胞_1_é"]


@pytest.mark.parametrize("invalid", [[1], [None], {"a": True}])
def test_checked_ids_validate_string_list_without_losing_selection(yearbook, invalid):
    yearbook.selected_cells = ["a"]
    with pytest.raises(traitlets.TraitError):
        yearbook.selected_cells = invalid
    assert yearbook.selected_cells == ["a"]


def test_get_checked_cells_returns_copied_anndata_subset(yearbook):
    adata = ad.AnnData(np.arange(6).reshape(3, 2))
    adata.obs_names = ["a", "b", "c"]
    yearbook.selected_cells = ["c", "a", "missing"]
    subset = yearbook.get_selected_cells(adata)
    assert list(subset.obs_names) == ["a", "c"]
    assert not subset.is_view
    subset.X[0, 0] = -1
    assert adata.X[0, 0] == 0
    yearbook.selected_cells = []
    assert yearbook.get_selected_cells(adata).shape == (0, 2)
