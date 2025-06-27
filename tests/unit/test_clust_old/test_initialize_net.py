"""
Comprehensive tests for network initialization and visualization setup.

This module tests the core network initialization functions that handle:
1. Network data structure setup (nodes, matrices, metadata)
2. Visualization configuration with color schemes and display settings
3. Widget integration for interactive network displays
4. Graceful handling of incomplete or missing configuration data
5. Color preservation across reinitialization and reset operations
6. Defensive behavior with malformed input data structures
"""

from pathlib import Path
import sys
from typing import Any
from unittest.mock import MagicMock

import pytest


# =============================================================================
# MODULE CONSTANTS
# =============================================================================

# Path configuration
SRC_DIR = str(Path(__file__).parent.parent / "src")

# Default color configurations
DEFAULT_MATRIX_COLORS = {"pos": "red", "neg": "blue"}
CUSTOM_MATRIX_COLORS = {"pos": "blue", "neg": "green"}
CUSTOM_MATRIX_COLORS_ALT = {"pos": "purple", "neg": "orange"}

# Viz structure keys
VIZ_REQUIRED_KEYS = {"cat_colors", "global_cat_colors", "matrix_colors"}
VIZ_RUNTIME_KEYS = {"row_nodes", "col_nodes", "links", "mat"}

# Test data configurations
SAMPLE_CAT_COLORS = {"row": {"cat-0": {"A": "#ff0000"}}, "col": {"cat-1": {"B": "#00ff00"}}}
SAMPLE_GLOBAL_COLORS = {"category1": "#ff0000", "category2": "#00ff00"}
EMPTY_CAT_COLORS = {"row": {}, "col": {}}


# =============================================================================
# MODULE SETUP
# =============================================================================

# Add the src directory to the path to import the module
sys.path.insert(0, SRC_DIR)

from celldega.clust_old.core import initialize_net


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================


def create_complete_viz(
    matrix_colors: dict[str, str] | None = None,
    cat_colors: dict[str, dict[str, Any]] | None = None,
    global_colors: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Create a complete viz structure with optional custom values."""
    return {
        "row_nodes": ["node1", "node2"],
        "col_nodes": ["col1", "col2"],
        "links": ["link1"],
        "mat": [[1, 2], [3, 4]],
        "cat_colors": cat_colors or SAMPLE_CAT_COLORS.copy(),
        "global_cat_colors": global_colors or SAMPLE_GLOBAL_COLORS.copy(),
        "matrix_colors": matrix_colors or CUSTOM_MATRIX_COLORS.copy(),
    }


def verify_viz_structure(viz: dict[str, Any], allow_runtime_keys: bool = True) -> None:
    """Verify that viz has the expected structure."""
    assert isinstance(viz, dict)

    # Check required keys
    for key in VIZ_REQUIRED_KEYS:
        assert key in viz

    # Check runtime keys if allowed
    if allow_runtime_keys:
        for key in VIZ_RUNTIME_KEYS:
            assert key in viz


def verify_default_viz_state(network: "MockNetwork") -> None:
    """Verify network has default viz state after initialization."""
    assert hasattr(network, "viz")
    verify_viz_structure(network.viz)
    assert network.viz["cat_colors"] == EMPTY_CAT_COLORS
    assert network.viz["global_cat_colors"] == {}
    assert network.viz["matrix_colors"] == DEFAULT_MATRIX_COLORS


class MockNetwork:
    """Mock Network class for testing initialization functions."""

    def __init__(self, **kwargs: Any) -> None:
        # Initialize only the attributes provided
        for key, value in kwargs.items():
            setattr(self, key, value)


# =============================================================================
# SHARED FIXTURES
# =============================================================================


@pytest.fixture
def clean_network() -> MockNetwork:
    """Create a clean mock network object."""
    return MockNetwork()


@pytest.fixture
def network_with_meta_cat() -> MockNetwork:
    """Network with existing meta_cat attribute."""
    return MockNetwork(meta_cat=True)


@pytest.fixture
def network_with_persistent_colors() -> MockNetwork:
    """Network with persistent_cat_colors and complete viz structure."""
    viz = create_complete_viz()
    return MockNetwork(persistent_cat_colors=True, viz=viz)


@pytest.fixture
def network_with_complete_viz() -> MockNetwork:
    """Network with complete viz structure."""
    viz = create_complete_viz()
    return MockNetwork(viz=viz)


@pytest.fixture
def mock_widget() -> MagicMock:
    """Create a mock widget for testing."""
    return MagicMock()


# =============================================================================
# MAIN FUNCTION TESTS
# =============================================================================


class TestMainFunction:
    """Test cases for the main() initialization function."""

    def test_basic_initialization(self, clean_network: MockNetwork) -> None:
        """Test main() with clean network - covers basic initialization path."""
        # Execute
        initialize_net.main(clean_network)

        # Verify basic structure
        assert hasattr(clean_network, "meta_cat")
        assert clean_network.meta_cat is False
        assert hasattr(clean_network, "dat")
        assert hasattr(clean_network, "is_downsampled")
        assert clean_network.is_downsampled is False

        # Verify dat structure
        assert "nodes" in clean_network.dat
        assert "row" in clean_network.dat["nodes"]
        assert "col" in clean_network.dat["nodes"]
        assert "node_info" in clean_network.dat

        # Verify node_info structure for both row and col
        for node_type in ["row", "col"]:
            node_info = clean_network.dat["node_info"][node_type]
            expected_keys = {"ini", "clust", "rank", "info", "cat", "value"}
            assert set(node_info.keys()) == expected_keys

        # Verify viz with default matrix colors
        verify_default_viz_state(clean_network)

    def test_preserves_existing_meta_cat(self, network_with_meta_cat: MockNetwork) -> None:
        """Test main() preserves existing meta_cat - covers meta_cat preservation path."""
        # Execute
        initialize_net.main(network_with_meta_cat)

        # Verify meta_cat is preserved
        assert network_with_meta_cat.meta_cat is True

    def test_with_widget_parameter(
        self, clean_network: MockNetwork, mock_widget: MagicMock
    ) -> None:
        """Test main() with widget parameter - covers widget assignment path."""
        # Execute
        initialize_net.main(clean_network, widget=mock_widget)

        # Verify widget is stored
        assert hasattr(clean_network, "widget_class")
        assert clean_network.widget_class is mock_widget

    def test_with_persistent_colors_success(
        self, network_with_persistent_colors: MockNetwork
    ) -> None:
        """Test main() success path with persistent colors - covers color preservation."""
        original_cat_colors = network_with_persistent_colors.viz["cat_colors"].copy()
        original_matrix_colors = network_with_persistent_colors.viz["matrix_colors"].copy()

        # Execute
        initialize_net.main(network_with_persistent_colors)

        # Verify colors are preserved when viz is complete
        assert network_with_persistent_colors.viz["cat_colors"] == original_cat_colors
        assert network_with_persistent_colors.viz["matrix_colors"] == original_matrix_colors

    @pytest.mark.parametrize(
        "network_attrs",
        [
            {"persistent_cat_colors": True},  # No viz
            {"persistent_cat_colors": True, "meta_cat": True},  # No viz with meta_cat
            {"persistent_cat_colors": True, "viz": {}},  # Empty viz
            {"persistent_cat_colors": True, "viz": {"other_key": "value"}},  # Partial viz
        ],
    )
    def test_defensive_behavior_with_missing_viz(self, network_attrs: dict[str, Any]) -> None:
        """Test FIXED BEHAVIOR: main() gracefully handles various missing viz scenarios."""
        network = MockNetwork(**network_attrs)

        # Should NOT raise any exceptions
        initialize_net.main(network)

        # Should have proper viz structure
        verify_default_viz_state(network)


# =============================================================================
# VIZ FUNCTION TESTS
# =============================================================================


class TestVizFunction:
    """Test cases for the viz() function."""

    def test_graceful_fallback_no_viz_attribute(self) -> None:
        """Test FIXED BEHAVIOR: viz() gracefully handles missing viz attribute."""
        network = MockNetwork()

        # Should NOT raise AttributeError anymore
        initialize_net.viz(network)

        # Verify graceful initialization occurred
        verify_default_viz_state(network)

    def test_graceful_fallback_missing_color_keys(self) -> None:
        """Test FIXED BEHAVIOR: viz() gracefully handles viz with missing keys."""
        network = MockNetwork(viz={"matrix_colors": CUSTOM_MATRIX_COLORS_ALT.copy()})

        # Should NOT raise KeyError anymore
        initialize_net.viz(network)

        # Verify graceful fallback with preserved matrix colors
        assert network.viz["cat_colors"] == EMPTY_CAT_COLORS
        assert network.viz["global_cat_colors"] == {}
        assert network.viz["matrix_colors"] == CUSTOM_MATRIX_COLORS_ALT

    def test_preserves_colors_when_reset_false(
        self, network_with_complete_viz: MockNetwork
    ) -> None:
        """Test viz() with reset_cat_colors=False preserves all colors."""
        original_cat_colors = network_with_complete_viz.viz["cat_colors"].copy()
        original_global_colors = network_with_complete_viz.viz["global_cat_colors"].copy()
        original_matrix_colors = network_with_complete_viz.viz["matrix_colors"].copy()

        # Execute
        initialize_net.viz(network_with_complete_viz, reset_cat_colors=False)

        # Verify all colors are preserved
        assert network_with_complete_viz.viz["cat_colors"] == original_cat_colors
        assert network_with_complete_viz.viz["global_cat_colors"] == original_global_colors
        assert network_with_complete_viz.viz["matrix_colors"] == original_matrix_colors

        # Verify structure is reset
        assert network_with_complete_viz.viz["row_nodes"] == []

    def test_resets_cat_colors_when_reset_true(
        self, network_with_complete_viz: MockNetwork
    ) -> None:
        """Test viz() with reset_cat_colors=True resets cat/global colors but preserves matrix colors."""
        original_matrix_colors = network_with_complete_viz.viz["matrix_colors"].copy()

        # Execute
        initialize_net.viz(network_with_complete_viz, reset_cat_colors=True)

        # Verify cat/global colors are reset
        assert network_with_complete_viz.viz["cat_colors"] == EMPTY_CAT_COLORS
        assert network_with_complete_viz.viz["global_cat_colors"] == {}

        # Verify matrix colors are preserved
        assert network_with_complete_viz.viz["matrix_colors"] == original_matrix_colors

    def test_matrix_colors_defaults_when_missing(self) -> None:
        """Test viz() uses default matrix colors when none exist in original viz."""
        network = MockNetwork(
            viz={
                "cat_colors": EMPTY_CAT_COLORS.copy(),
                "global_cat_colors": {},
                # No matrix_colors key
            }
        )

        # Execute
        initialize_net.viz(network, reset_cat_colors=False)

        # Should use defaults
        assert network.viz["matrix_colors"] == DEFAULT_MATRIX_COLORS

    @pytest.mark.parametrize(
        "viz_input",
        [
            None,  # viz is None
            "not_a_dict",  # viz is not a dict
            {},  # Empty viz
            {"random_key": "value"},  # Missing required keys
        ],
    )
    def test_handles_malformed_viz_gracefully(self, viz_input: Any) -> None:
        """Test viz() handles various malformed viz scenarios gracefully."""
        network = MockNetwork() if viz_input is None else MockNetwork(viz=viz_input)

        # Should NOT raise any exceptions
        initialize_net.viz(network, reset_cat_colors=False)

        # Should have proper viz structure
        verify_viz_structure(network.viz)
        assert "cat_colors" in network.viz
        assert "global_cat_colors" in network.viz
        assert "matrix_colors" in network.viz

    @pytest.mark.parametrize("reset_value", [True, False])
    def test_matrix_colors_preserved_regardless_of_reset(self, reset_value: bool) -> None:
        """Test matrix colors are preserved regardless of reset_cat_colors value."""
        network = MockNetwork(
            viz={
                "cat_colors": EMPTY_CAT_COLORS.copy(),
                "global_cat_colors": {},
                "matrix_colors": CUSTOM_MATRIX_COLORS_ALT.copy(),
            }
        )

        # Execute
        initialize_net.viz(network, reset_cat_colors=reset_value)

        # Matrix colors should always be preserved
        assert network.viz["matrix_colors"] == CUSTOM_MATRIX_COLORS_ALT


# =============================================================================
# INTEGRATION AND WORKFLOW TESTS
# =============================================================================


class TestIntegrationScenarios:
    """Integration tests for realistic usage patterns."""

    def test_typical_initialization_sequence(self) -> None:
        """Test normal sequence: main() followed by viz()."""
        network = MockNetwork()

        # Step 1: Initialize with main
        initialize_net.main(network)

        # Verify main worked
        assert hasattr(network, "viz")
        assert network.viz["matrix_colors"] == DEFAULT_MATRIX_COLORS

        # Step 2: Call viz
        initialize_net.viz(network, reset_cat_colors=False)

        # Verify viz preserved colors
        assert network.viz["matrix_colors"] == DEFAULT_MATRIX_COLORS
        assert network.viz["row_nodes"] == []

    def test_persistent_colors_full_sequence(
        self, network_with_persistent_colors: MockNetwork
    ) -> None:
        """Test sequence with persistent colors: main() then viz()."""
        original_cat_colors = network_with_persistent_colors.viz["cat_colors"].copy()
        original_matrix_colors = network_with_persistent_colors.viz["matrix_colors"].copy()

        # Step 1: Main with persistent colors
        initialize_net.main(network_with_persistent_colors)

        # Step 2: Viz should preserve colors
        initialize_net.viz(network_with_persistent_colors, reset_cat_colors=False)

        # Verify colors preserved through both calls
        assert network_with_persistent_colors.viz["cat_colors"] == original_cat_colors
        assert network_with_persistent_colors.viz["matrix_colors"] == original_matrix_colors

    def test_error_recovery_pattern_now_works(self) -> None:
        """Test FIXED BEHAVIOR: Previously problematic scenarios now work gracefully."""
        # Start with previously problematic network
        network = MockNetwork(persistent_cat_colors=True)

        # This used to fail, but now works gracefully
        initialize_net.main(network)
        assert hasattr(network, "dat")
        assert hasattr(network, "viz")

        # Should be able to call viz() as well
        initialize_net.viz(network)
        assert network.viz["row_nodes"] == []

    def test_repeated_calls_stability(self) -> None:
        """Test calling main() and viz() multiple times."""
        network = MockNetwork()

        # Multiple main() calls
        for _ in range(3):
            initialize_net.main(network)
            assert hasattr(network, "dat")
            assert hasattr(network, "viz")

        # Multiple viz() calls
        for i in range(3):
            initialize_net.viz(network, reset_cat_colors=(i % 2 == 0))
            assert network.viz["row_nodes"] == []


# =============================================================================
# PARAMETRIZED COMBINATION TESTS
# =============================================================================


class TestParametrizedScenarios:
    """Parametrized tests to reduce redundancy while ensuring coverage."""

    @pytest.mark.parametrize(
        "has_meta_cat,has_widget,expected_meta_cat,expected_widget",
        [
            (False, False, False, False),
            (True, False, True, False),
            (False, True, False, True),
            (True, True, True, True),
        ],
    )
    def test_main_parameter_combinations(
        self,
        has_meta_cat: bool,
        has_widget: bool,
        expected_meta_cat: bool,
        expected_widget: bool,
        mock_widget: MagicMock,
    ) -> None:
        """Test various parameter combinations for main() function."""
        network = MockNetwork()
        if has_meta_cat:
            network.meta_cat = True

        widget = mock_widget if has_widget else None

        # Execute
        initialize_net.main(network, widget=widget)

        # Verify results
        assert network.meta_cat == expected_meta_cat
        if expected_widget:
            assert hasattr(network, "widget_class")
            assert network.widget_class is mock_widget
        else:
            assert not hasattr(network, "widget_class")

    @pytest.mark.parametrize(
        "reset_colors,has_custom_matrix_colors,expected_colors",
        [
            (False, True, CUSTOM_MATRIX_COLORS_ALT),
            (True, True, CUSTOM_MATRIX_COLORS_ALT),
            (False, False, DEFAULT_MATRIX_COLORS),
            (True, False, DEFAULT_MATRIX_COLORS),
        ],
    )
    def test_viz_matrix_colors_combinations(
        self,
        reset_colors: bool,
        has_custom_matrix_colors: bool,
        expected_colors: dict[str, str],
    ) -> None:
        """Test matrix colors behavior in various combinations."""
        viz = {"cat_colors": EMPTY_CAT_COLORS.copy(), "global_cat_colors": {}}

        if has_custom_matrix_colors:
            viz["matrix_colors"] = CUSTOM_MATRIX_COLORS_ALT.copy()

        network = MockNetwork(viz=viz)

        # Execute
        initialize_net.viz(network, reset_cat_colors=reset_colors)

        # Matrix colors should always match expected (preserved or default)
        assert network.viz["matrix_colors"] == expected_colors


# =============================================================================
# BUG FIX VERIFICATION TESTS
# =============================================================================


class TestBugFixVerification:
    """Verify that the original bugs have been fixed."""

    def test_bug_fix_main_handles_missing_viz(self) -> None:
        """Verify Bug 1 is FIXED: main() no longer crashes with persistent_cat_colors=True but no viz."""
        network = MockNetwork(persistent_cat_colors=True)

        # This used to raise AttributeError, now should work gracefully
        initialize_net.main(network)

        # Verify it worked properly
        verify_default_viz_state(network)

    def test_bug_fix_viz_handles_missing_viz(self) -> None:
        """Verify Bug 2 is FIXED: viz() no longer crashes when no viz attribute exists."""
        network = MockNetwork()

        # This used to raise AttributeError, now should work gracefully
        initialize_net.viz(network)

        # Verify it worked properly
        verify_default_viz_state(network)

    def test_bug_fix_viz_handles_missing_keys(self) -> None:
        """Verify Bug 3 is FIXED: viz() no longer crashes when viz exists but missing required keys."""
        network = MockNetwork(viz={"some_other_key": "value"})

        # This used to raise KeyError, now should work gracefully
        initialize_net.viz(network)

        # Verify it worked properly
        assert network.viz["cat_colors"] == EMPTY_CAT_COLORS
        assert network.viz["global_cat_colors"] == {}

    def test_comprehensive_defensive_behavior(self) -> None:
        """Test that all previously problematic scenarios now work gracefully."""
        # All scenarios that used to crash
        problematic_scenarios = [
            # Bug 1 scenarios
            MockNetwork(persistent_cat_colors=True),  # No viz
            MockNetwork(persistent_cat_colors=True, meta_cat=True),  # No viz
            MockNetwork(persistent_cat_colors=True, viz={}),  # Empty viz
            # Bug 2 scenarios (for viz function)
            MockNetwork(),  # No viz at all
            MockNetwork(meta_cat=True),  # No viz
            # Bug 3 scenarios
            MockNetwork(viz={"random_key": "value"}),  # Partial viz
            MockNetwork(viz={"matrix_colors": DEFAULT_MATRIX_COLORS.copy()}),  # Missing cat colors
        ]

        for network in problematic_scenarios:
            # Test main() - should NOT raise any exceptions
            initialize_net.main(network)

            # Test viz() - should NOT raise any exceptions
            initialize_net.viz(network)

            # Verify proper structure exists
            verify_viz_structure(network.viz)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
