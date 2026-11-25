"""Stacks: several widgets in one place, one shown at a time (``dega.viz.stack``)."""

import ipywidgets
import pytest


def _view():
    """A small widget with a ``view_request`` trait, like Celldega's viewers."""
    import traitlets

    widget = ipywidgets.Text()
    widget.add_traits(view_request=traitlets.Dict({}).tag(sync=True))
    return widget


def test_stack_shows_one_widget_and_links_the_rest_in_the_browser():
    from celldega.viz import stack

    tissue, cells = _view(), _view()
    spatial = stack({"Tissue": tissue, "Cells": cells}, selected="Cells")

    assert spatial.shown == "Cells"
    assert spatial.switch.labels == ["Tissue", "Cells"]
    assert spatial.children == (spatial.switch, tissue, cells)
    assert (tissue.layout.display, cells.layout.display) == ("none", "")
    # Kernel-free links: the switch drives each layout, and follows view requests.
    from ipywidgets.widgets.widget_link import DirectionalLink, Link

    links = spatial._links
    assert sum(type(link) is Link for link in links) == 2
    assert sum(type(link) is DirectionalLink for link in links) == 2
    assert spatial.switch.has_trait("request_0") and spatial.switch.has_trait("request_1")

    spatial.show("Tissue")
    assert spatial.switch.selected == 0
    assert (spatial.switch.display_0, spatial.switch.display_1) == ("", "none")
    spatial.show(cells)
    assert spatial.shown == "Cells"
    with pytest.raises(KeyError):
        spatial.show("Clusters")


def test_stack_needs_two_widgets_and_labels_lists_by_type():
    from celldega.viz import stack

    with pytest.raises(ValueError, match="two"):
        stack({"Only": ipywidgets.Text()})
    listed = stack([ipywidgets.Text(), ipywidgets.Text()])
    assert listed.switch.labels == ["Text", "Text'"]
    # A widget without view_request only gets a display link.
    assert not listed.switch.has_trait("request_0")


def test_bring_forward_and_is_hidden():
    from celldega.viz import stack
    from celldega.viz.stack import bring_forward, is_hidden

    tissue, cells = _view(), _view()
    spatial = stack({"Tissue": tissue, "Cells": cells})
    assert is_hidden(cells) and not is_hidden(tissue)
    bring_forward(cells)
    assert spatial.shown == "Cells"
    bring_forward(_view())  # not in a stack: nothing happens
    assert spatial.shown == "Cells"


def test_clerk_skips_hidden_widgets_and_brings_changed_ones_forward(monkeypatch):
    from celldega.viz import Clerk, Landscape, stack

    landscape = Landscape.__new__(Landscape)  # no data needed: only its layout is read
    ipywidgets.DOMWidget.__init__(landscape)
    clerk = Clerk()
    clerk._linked_widgets = {"landscape": landscape}
    landscape.layout.display = "none"
    views = clerk._refresh_views("q")
    assert views["hidden"] == ["landscape"]
    assert any("The Landscape is hidden" in note for note in views["notes"])
    assert not any("No Landscape" in note for note in views["notes"])

    # A view change from Clerk shows the widget it changed.
    tissue, cells = _view(), _view()
    spatial = stack({"Tissue": tissue, "Cells": cells})
    from celldega.viz.stack import bring_forward

    bring_forward(cells)
    assert spatial.shown == "Cells"
