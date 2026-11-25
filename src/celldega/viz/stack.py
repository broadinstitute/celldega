"""Stacks: several visualizations in one place, one shown at a time.

``stack({"Tissue": landscape, "Cells": yearbook})`` puts a small switch above the
widgets and shows one of them; the others stay rendered (hidden), so switching
back is instant and keeps their view. A widget comes forward on its own when a
saved view is opened in it (a Snapshot card, a pin, or a Clerk link), and Clerk
brings forward the widget it changes. Everything runs in the browser, so it works
without a kernel too.

Typical stacks, by slot: spatial (Landscape | Yearbook), data (a Clustergram with
several matrices does this itself), and information (Clerk | Enrich).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any
import weakref

from ipywidgets import VBox, jsdlink, jslink
import traitlets

from ._widget_lifecycle import CelldegaWidget
from .widget import _WIDGET_ESM


#: Every live stack, so Clerk can bring forward the widget it changes.
_STACKS: weakref.WeakSet = weakref.WeakSet()


class StackSwitch(CelldegaWidget):
    """The switch of a :func:`stack`: one button per widget, the shown one in blue.

    Its ``display_<i>`` traits are linked in the browser to each widget's
    ``layout.display``, and its ``request_<i>`` traits follow each widget's
    ``view_request``, so a saved view opened in a widget shows it.
    """

    _esm = _WIDGET_ESM

    component = traitlets.Unicode("StackSwitch").tag(sync=True)
    labels = traitlets.List(traitlets.Unicode(), default_value=[]).tag(sync=True)
    selected = traitlets.Int(0).tag(sync=True)

    def __init__(self, labels: Sequence[str], selected: int, requests: Sequence[bool], **kwargs):
        extra: dict[str, traitlets.TraitType] = {}
        for index in range(len(labels)):
            shown = "" if index == selected else "none"
            extra[f"display_{index}"] = traitlets.Unicode(shown).tag(sync=True)
            if requests[index]:
                extra[f"request_{index}"] = traitlets.Dict({}).tag(sync=True)
        self.add_traits(**extra)
        super().__init__(labels=list(labels), selected=selected, **kwargs)

    @traitlets.observe("selected")
    def _show_selected(self, change) -> None:
        for index in range(len(self.labels)):
            name = f"display_{index}"
            if self.has_trait(name):
                setattr(self, name, "" if index == change["new"] else "none")


class ViewStack(VBox):
    """Widgets in one place, one shown at a time (see :func:`stack`)."""

    def __init__(self, views: dict[str, Any], switch: StackSwitch, links: list):
        super().__init__([switch, *views.values()])
        self.views = views
        self.switch = switch
        self._links = links

    @property
    def shown(self) -> str:
        """The label of the widget shown."""
        return list(self.views)[self.switch.selected]

    def show(self, view: str | Any) -> None:
        """Show a widget, by its label or the widget itself."""
        labels = list(self.views)
        if isinstance(view, str):
            if view not in self.views:
                raise KeyError(f"no view {view!r} in this stack; choose one of {labels}")
            index = labels.index(view)
        else:
            index = next((i for i, w in enumerate(self.views.values()) if w is view), None)
            if index is None:
                raise KeyError("that widget is not in this stack")
        self.switch.selected = index


def stack(
    views: Mapping[str, Any] | Sequence[Any],
    *,
    selected: str | int | None = None,
) -> ViewStack:
    """Put several widgets in one place with a small switch; one is shown at a time.

    The hidden widgets stay rendered, so switching back is instant and keeps their
    view. A widget comes forward when a saved view is opened in it (a Snapshot
    card, a pin, a Clerk link), and when Clerk changes it.

    Args:
        views: ``{label: widget}``, in switch order; or a list of widgets, labeled
            by their type (e.g. "Landscape").
        selected: The label (or index) of the widget shown first; the first by default.

    Returns:
        ViewStack: Display it; ``.show(label)`` switches, ``.views`` and
        ``.switch`` hold the parts.

    Example::

        spatial = dega.viz.stack({"Tissue": landscape, "Cells": yearbook})
        info = dega.viz.stack({"Clerk": clerk, "Enrichr": enrich})
        widgets.HBox([spatial, cgm, info])
    """
    if isinstance(views, Mapping):
        items = {str(label): widget for label, widget in views.items()}
    else:
        items = {}
        for widget in views:
            label = type(widget).__name__
            while label in items:
                label += "'"
            items[label] = widget
    if len(items) < 2:
        raise ValueError("a stack needs at least two widgets")
    labels = list(items)
    if selected is None:
        index = 0
    elif isinstance(selected, int):
        index = selected
    elif selected in items:
        index = labels.index(selected)
    else:
        raise KeyError(f"no view {selected!r} in this stack; choose one of {labels}")
    if not 0 <= index < len(labels):
        raise IndexError("selected is out of range")

    widgets = list(items.values())
    requests = [hasattr(w, "has_trait") and w.has_trait("view_request") for w in widgets]
    switch = StackSwitch(labels, index, requests)
    links = []
    for i, widget in enumerate(widgets):
        widget.layout.display = "" if i == index else "none"
        links.append(jslink((switch, f"display_{i}"), (widget.layout, "display")))
        if requests[i]:
            links.append(jsdlink((widget, "view_request"), (switch, f"request_{i}")))
    result = ViewStack(items, switch, links)
    _STACKS.add(result)
    return result


def bring_forward(widget: Any) -> None:
    """Show ``widget`` in every stack that holds it (a no-op otherwise)."""
    for each in list(_STACKS):
        if any(view is widget for view in each.views.values()):
            each.show(widget)


def is_hidden(widget: Any) -> bool:
    """Whether a stack is showing another widget in this one's place."""
    layout = getattr(widget, "layout", None)
    return getattr(layout, "display", None) == "none"
