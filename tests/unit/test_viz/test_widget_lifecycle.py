import pytest

from celldega.viz._widget_lifecycle import CelldegaWidget, _widget_registry
from celldega.viz.cloud import CellCloud, NeighborhoodCloud
from celldega.viz.landmark_widget import Landmark
from celldega.viz.widget import Clustergram, Composition, Enrich, Landscape, Yearbook


class _TestWidget(CelldegaWidget):
    _registry_namespace = "test-widget-lifecycle"


def teardown_function():
    for widget in list(_widget_registry.values()):
        if isinstance(widget, _TestWidget):
            widget.close()


def test_same_registry_key_closes_and_replaces_previous_widget():
    first = _TestWidget(name="shared")
    first_model_id = first.model_id

    second = _TestWidget(registry_key="shared")

    assert first.comm is None
    assert second.comm is not None
    assert _widget_registry[("test-widget-lifecycle", "shared")] is second
    assert first_model_id != second.model_id


def test_distinct_keys_allow_widgets_to_coexist():
    first = _TestWidget(name="first")
    second = _TestWidget(name="second")

    assert first.comm is not None
    assert second.comm is not None
    assert _widget_registry[("test-widget-lifecycle", "first")] is first
    assert _widget_registry[("test-widget-lifecycle", "second")] is second


def test_close_unregisters_only_the_current_widget():
    widget = _TestWidget(name="shared")
    widget.close()

    assert ("test-widget-lifecycle", "shared") not in _widget_registry


def test_name_and_registry_key_must_agree():
    with pytest.raises(ValueError, match="must match"):
        _TestWidget(name="one", registry_key="two")


@pytest.mark.parametrize(
    "widget_type",
    [
        Landscape,
        CellCloud,
        NeighborhoodCloud,
        Yearbook,
        Clustergram,
        Composition,
        Enrich,
        Landmark,
    ],
)
def test_all_public_widgets_share_lifecycle_base(widget_type):
    assert issubclass(widget_type, CelldegaWidget)


def test_enrich_accepts_registry_key_without_conflicting_with_default_name():
    first = Enrich(registry_key="enrich-lifecycle-test")
    second = Enrich(registry_key="enrich-lifecycle-test")

    assert first.comm is None
    assert second.comm is not None
    second.close()
