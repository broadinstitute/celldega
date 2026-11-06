"""Shared lifecycle and replacement semantics for Celldega widgets."""

from contextlib import suppress
from weakref import WeakValueDictionary

import anywidget


_widget_registry: WeakValueDictionary[tuple[object, str], "CelldegaWidget"] = WeakValueDictionary()


class CelldegaWidget(anywidget.AnyWidget):
    """AnyWidget base with explicit, key-based replacement and cleanup.

    Passing ``name=`` (or the more explicit ``registry_key=``) makes a widget
    replace the previous live widget in the same registry namespace. Omitting a
    key allows any number of widgets of that type to coexist.
    """

    _registry_namespace: object | None = None

    def __init__(self, *args, name=None, registry_key=None, **kwargs):
        if name is not None and registry_key is not None and str(name) != str(registry_key):
            raise ValueError("name and registry_key must match when both are provided")

        key = registry_key if registry_key is not None else name
        self._registry_key = None if key is None else str(key)
        namespace = self._registry_namespace or type(self)
        self._registry_id = None if self._registry_key is None else (namespace, self._registry_key)
        self._owns_layout = "layout" not in kwargs

        if self._registry_id is not None:
            old_widget = _widget_registry.get(self._registry_id)
            if old_widget is not None and old_widget is not self:
                with suppress(Exception):
                    old_widget.close()

        super().__init__(*args, **kwargs)

        if self._registry_id is not None:
            _widget_registry[self._registry_id] = self

    def close(self):  # pragma: no cover - front-end cleanup depends on JS
        """Finalize the front end, unregister this instance, and close its comm."""
        trait_values = getattr(self, "_trait_values", {}) or {}
        comm = trait_values.get("comm")
        layout = trait_values.get("layout") if getattr(self, "_owns_layout", False) else None

        if comm is not None:
            with suppress(Exception):
                self.send({"event": "finalize"})

        registry_id = getattr(self, "_registry_id", None)
        if registry_id is not None and _widget_registry.get(registry_id) is self:
            with suppress(KeyError):
                del _widget_registry[registry_id]

        with suppress(Exception):
            super().close()
        if layout is not None:
            with suppress(Exception):
                layout.close()
