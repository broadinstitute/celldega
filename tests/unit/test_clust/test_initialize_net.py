"""
Comprehensive tests for initialize_net.py module (UPDATED FOR FIXED CODE).

Tests verify the corrected behavior after bug fixes:
1. main() now handles missing viz gracefully (no more AttributeError)
2. viz() now handles missing viz gracefully (no more AttributeError)
3. Both functions use defensive programming with proper fallbacks
4. Matrix colors preservation logic works correctly
"""

from pathlib import Path
import sys
from unittest.mock import MagicMock

import pytest


# Add the src directory to the path to import the module
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from celldega.clust.core import initialize_net


class MockNetwork:
    """Mock Network class for testing initialization functions."""

    def __init__(self, **kwargs):
        # Initialize only the attributes provided
        for key, value in kwargs.items():
            setattr(self, key, value)


# Module-level fixtures for cross-class usage
@pytest.fixture
def clean_network():
    """Create a clean mock network object."""
    return MockNetwork()


@pytest.fixture
def network_with_meta_cat():
    """Network with existing meta_cat attribute."""
    return MockNetwork(meta_cat=True)


@pytest.fixture
def network_with_persistent_colors_and_complete_viz():
    """Network with persistent_cat_colors and complete viz structure."""
    viz = {
        "cat_colors": {"row": {"cat-0": {}}, "col": {"cat-1": {}}},
        "global_cat_colors": {"category1": "#ff0000"},
        "matrix_colors": {"pos": "blue", "neg": "green"},
    }
    return MockNetwork(persistent_cat_colors=True, viz=viz)


@pytest.fixture
def network_with_complete_viz():
    """Network with complete viz structure."""
    viz = {
        "row_nodes": ["node1", "node2"],
        "col_nodes": ["col1", "col2"],
        "links": ["link1"],
        "mat": [[1, 2], [3, 4]],
        "cat_colors": {"row": {"cat-0": {"A": "#ff0000"}}, "col": {"cat-1": {"B": "#00ff00"}}},
        "global_cat_colors": {"category1": "#ff0000", "category2": "#00ff00"},
        "matrix_colors": {"pos": "blue", "neg": "green"},
    }
    return MockNetwork(viz=viz)


class TestMainFunction:
    """Test cases for the main() initialization function."""

    def test_main_basic_initialization(self, clean_network):
        """Test main() with clean network - covers basic initialization path."""
        # Execute
        initialize_net.main(clean_network)

        # Verify basic structure
        assert hasattr(clean_network, "meta_cat")
        assert clean_network.meta_cat is False
        assert hasattr(clean_network, "dat")
        assert hasattr(clean_network, "viz")
        assert hasattr(clean_network, "is_downsampled")
        assert clean_network.is_downsampled is False

        # Verify dat structure
        assert "nodes" in clean_network.dat
        assert "row" in clean_network.dat["nodes"]
        assert "col" in clean_network.dat["nodes"]

        # Verify viz with default matrix colors
        assert clean_network.viz["matrix_colors"] == {"pos": "red", "neg": "blue"}

    def test_main_preserves_existing_meta_cat(self, network_with_meta_cat):
        """Test main() preserves existing meta_cat - covers meta_cat preservation path."""
        # Execute
        initialize_net.main(network_with_meta_cat)

        # Verify meta_cat is preserved
        assert network_with_meta_cat.meta_cat is True

    def test_main_with_widget_parameter(self, clean_network):
        """Test main() with widget parameter - covers widget assignment path."""
        mock_widget = MagicMock()

        # Execute
        initialize_net.main(clean_network, widget=mock_widget)

        # Verify widget is stored
        assert hasattr(clean_network, "widget_class")
        assert clean_network.widget_class is mock_widget

    def test_main_graceful_fallback_persistent_colors_no_viz(self):
        """Test FIXED BEHAVIOR: main() gracefully handles persistent_cat_colors=True but no viz."""
        network = MockNetwork(persistent_cat_colors=True)

        # Should NOT raise AttributeError anymore - should gracefully fallback
        initialize_net.main(network)

        # Verify graceful fallback occurred
        assert hasattr(network, "viz")
        assert network.viz["cat_colors"] == {"row": {}, "col": {}}
        assert network.viz["global_cat_colors"] == {}
        assert network.viz["matrix_colors"] == {"pos": "red", "neg": "blue"}

    def test_main_graceful_fallback_persistent_colors_empty_viz(self):
        """Test FIXED BEHAVIOR: main() gracefully handles viz with missing keys."""
        network = MockNetwork(persistent_cat_colors=True, viz={})

        # Should NOT raise KeyError anymore - should gracefully fallback
        initialize_net.main(network)

        # Verify graceful fallback occurred
        assert hasattr(network, "viz")
        assert network.viz["cat_colors"] == {"row": {}, "col": {}}
        assert network.viz["global_cat_colors"] == {}

    def test_main_with_persistent_colors_success(
        self, network_with_persistent_colors_and_complete_viz
    ):
        """Test main() success path with persistent colors - covers color preservation."""
        original_cat_colors = network_with_persistent_colors_and_complete_viz.viz["cat_colors"]
        original_matrix_colors = network_with_persistent_colors_and_complete_viz.viz[
            "matrix_colors"
        ]

        # Execute
        initialize_net.main(network_with_persistent_colors_and_complete_viz)

        # Verify colors are preserved when viz is complete
        assert (
            network_with_persistent_colors_and_complete_viz.viz["cat_colors"] == original_cat_colors
        )
        assert (
            network_with_persistent_colors_and_complete_viz.viz["matrix_colors"]
            == original_matrix_colors
        )

    def test_main_defensive_behavior_multiple_contexts(self):
        """Test defensive behavior works in multiple contexts."""
        contexts = [
            MockNetwork(persistent_cat_colors=True),  # No viz
            MockNetwork(persistent_cat_colors=True, meta_cat=True),  # No viz
            MockNetwork(persistent_cat_colors=True, viz={}),  # Empty viz
            MockNetwork(persistent_cat_colors=True, viz={"other_key": "value"}),  # Partial viz
        ]

        for network in contexts:
            # Should NOT raise any exceptions
            initialize_net.main(network)

            # Should have proper viz structure
            assert hasattr(network, "viz")
            assert isinstance(network.viz, dict)
            assert "cat_colors" in network.viz
            assert "global_cat_colors" in network.viz
            assert "matrix_colors" in network.viz


class TestVizFunction:
    """Test cases for the viz() function."""

    def test_viz_graceful_fallback_no_viz_attribute(self):
        """Test FIXED BEHAVIOR: viz() gracefully handles missing viz attribute."""
        network = MockNetwork()

        # Should NOT raise AttributeError anymore
        initialize_net.viz(network)

        # Verify graceful initialization occurred
        assert hasattr(network, "viz")
        assert network.viz["cat_colors"] == {"row": {}, "col": {}}
        assert network.viz["global_cat_colors"] == {}
        assert network.viz["matrix_colors"] == {"pos": "red", "neg": "blue"}

    def test_viz_graceful_fallback_missing_color_keys(self):
        """Test FIXED BEHAVIOR: viz() gracefully handles viz with missing keys."""
        network = MockNetwork(viz={"matrix_colors": {"pos": "purple", "neg": "orange"}})

        # Should NOT raise KeyError anymore
        initialize_net.viz(network)

        # Verify graceful fallback with preserved matrix colors
        assert network.viz["cat_colors"] == {"row": {}, "col": {}}
        assert network.viz["global_cat_colors"] == {}
        assert network.viz["matrix_colors"] == {"pos": "purple", "neg": "orange"}

    def test_viz_preserves_colors_when_reset_false(self, network_with_complete_viz):
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

    def test_viz_resets_cat_colors_when_reset_true(self, network_with_complete_viz):
        """Test viz() with reset_cat_colors=True resets cat/global colors but preserves matrix colors."""
        original_matrix_colors = network_with_complete_viz.viz["matrix_colors"].copy()

        # Execute
        initialize_net.viz(network_with_complete_viz, reset_cat_colors=True)

        # Verify cat/global colors are reset
        assert network_with_complete_viz.viz["cat_colors"] == {"row": {}, "col": {}}
        assert network_with_complete_viz.viz["global_cat_colors"] == {}

        # Verify matrix colors are preserved
        assert network_with_complete_viz.viz["matrix_colors"] == original_matrix_colors
        assert network_with_complete_viz.viz["matrix_colors"] == {"pos": "blue", "neg": "green"}

    def test_viz_matrix_colors_defaults_when_missing(self):
        """Test viz() uses default matrix colors when none exist in original viz."""
        network = MockNetwork(
            viz={
                "cat_colors": {"row": {}, "col": {}},
                "global_cat_colors": {},
                # No matrix_colors key
            }
        )

        # Execute
        initialize_net.viz(network, reset_cat_colors=False)

        # Should use defaults
        assert network.viz["matrix_colors"] == {"pos": "red", "neg": "blue"}

    def test_viz_handles_malformed_viz_gracefully(self):
        """Test viz() handles various malformed viz scenarios gracefully."""
        malformed_scenarios = [
            MockNetwork(),  # No viz attribute
            MockNetwork(viz=None),  # viz is None
            MockNetwork(viz="not_a_dict"),  # viz is not a dict
            MockNetwork(viz={}),  # Empty viz
            MockNetwork(viz={"random_key": "value"}),  # Missing required keys
        ]

        for network in malformed_scenarios:
            # Should NOT raise any exceptions
            initialize_net.viz(network, reset_cat_colors=False)

            # Should have proper viz structure
            assert hasattr(network, "viz")
            assert isinstance(network.viz, dict)
            assert "cat_colors" in network.viz
            assert "global_cat_colors" in network.viz
            assert "matrix_colors" in network.viz

    def test_viz_matrix_colors_preserved_regardless_of_reset(self):
        """Test matrix colors are preserved regardless of reset_cat_colors value."""
        custom_colors = {"pos": "purple", "neg": "orange"}

        for reset_value in [True, False]:
            network = MockNetwork(
                viz={
                    "cat_colors": {"row": {}, "col": {}},
                    "global_cat_colors": {},
                    "matrix_colors": custom_colors.copy(),
                }
            )

            # Execute
            initialize_net.viz(network, reset_cat_colors=reset_value)

            # Matrix colors should always be preserved
            assert network.viz["matrix_colors"] == custom_colors


class TestIntegrationScenarios:
    """Integration tests for realistic usage patterns."""

    def test_typical_initialization_sequence(self):
        """Test normal sequence: main() followed by viz()."""
        network = MockNetwork()

        # Step 1: Initialize with main
        initialize_net.main(network)

        # Verify main worked
        assert hasattr(network, "viz")
        assert network.viz["matrix_colors"] == {"pos": "red", "neg": "blue"}

        # Step 2: Call viz
        initialize_net.viz(network, reset_cat_colors=False)

        # Verify viz preserved colors
        assert network.viz["matrix_colors"] == {"pos": "red", "neg": "blue"}
        assert network.viz["row_nodes"] == []

    def test_persistent_colors_full_sequence(self, network_with_persistent_colors_and_complete_viz):
        """Test sequence with persistent colors: main() then viz()."""
        original_cat_colors = network_with_persistent_colors_and_complete_viz.viz[
            "cat_colors"
        ].copy()
        original_matrix_colors = network_with_persistent_colors_and_complete_viz.viz[
            "matrix_colors"
        ].copy()

        # Step 1: Main with persistent colors
        initialize_net.main(network_with_persistent_colors_and_complete_viz)

        # Step 2: Viz should preserve colors
        initialize_net.viz(network_with_persistent_colors_and_complete_viz, reset_cat_colors=False)

        # Verify colors preserved through both calls
        assert (
            network_with_persistent_colors_and_complete_viz.viz["cat_colors"] == original_cat_colors
        )
        assert (
            network_with_persistent_colors_and_complete_viz.viz["matrix_colors"]
            == original_matrix_colors
        )

    def test_error_recovery_pattern_now_works(self):
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

    def test_repeated_calls_stability(self):
        """Test calling main() and viz() multiple times."""
        network = MockNetwork()

        # Multiple main() calls
        for i in range(3):
            initialize_net.main(network)
            assert hasattr(network, "dat")
            assert hasattr(network, "viz")

        # Multiple viz() calls
        for i in range(3):
            initialize_net.viz(network, reset_cat_colors=(i % 2 == 0))
            assert network.viz["row_nodes"] == []


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
        self, has_meta_cat, has_widget, expected_meta_cat, expected_widget
    ):
        """Test various parameter combinations for main() function."""
        network = MockNetwork()
        if has_meta_cat:
            network.meta_cat = True

        widget = MagicMock() if has_widget else None

        # Execute
        initialize_net.main(network, widget=widget)

        # Verify results
        assert network.meta_cat == expected_meta_cat
        if expected_widget:
            assert hasattr(network, "widget_class")
            assert network.widget_class is widget
        else:
            assert not hasattr(network, "widget_class")

    @pytest.mark.parametrize(
        "reset_colors,has_custom_matrix_colors",
        [
            (False, True),
            (True, True),
            (False, False),
            (True, False),
        ],
    )
    def test_viz_matrix_colors_combinations(self, reset_colors, has_custom_matrix_colors):
        """Test matrix colors behavior in various combinations."""
        viz = {"cat_colors": {"row": {}, "col": {}}, "global_cat_colors": {}}

        expected_colors = {"pos": "red", "neg": "blue"}  # Default
        if has_custom_matrix_colors:
            custom_colors = {"pos": "purple", "neg": "orange"}
            viz["matrix_colors"] = custom_colors
            expected_colors = custom_colors

        network = MockNetwork(viz=viz)

        # Execute
        initialize_net.viz(network, reset_cat_colors=reset_colors)

        # Matrix colors should always match expected (preserved or default)
        assert network.viz["matrix_colors"] == expected_colors


class TestBugFixVerification:
    """Verify that the original bugs have been fixed."""

    def test_bug_fix_1_main_handles_missing_viz(self):
        """Verify Bug 1 is FIXED: main() no longer crashes with persistent_cat_colors=True but no viz."""
        network = MockNetwork(persistent_cat_colors=True)

        # This used to raise AttributeError, now should work gracefully
        initialize_net.main(network)

        # Verify it worked properly
        assert hasattr(network, "viz")
        assert network.viz["cat_colors"] == {"row": {}, "col": {}}

    def test_bug_fix_2_viz_handles_missing_viz(self):
        """Verify Bug 2 is FIXED: viz() no longer crashes when no viz attribute exists."""
        network = MockNetwork()

        # This used to raise AttributeError, now should work gracefully
        initialize_net.viz(network)

        # Verify it worked properly
        assert hasattr(network, "viz")
        assert network.viz["matrix_colors"] == {"pos": "red", "neg": "blue"}

    def test_bug_fix_3_viz_handles_missing_keys(self):
        """Verify Bug 3 is FIXED: viz() no longer crashes when viz exists but missing required keys."""
        network = MockNetwork(viz={"some_other_key": "value"})

        # This used to raise KeyError, now should work gracefully
        initialize_net.viz(network)

        # Verify it worked properly
        assert network.viz["cat_colors"] == {"row": {}, "col": {}}
        assert network.viz["global_cat_colors"] == {}

    def test_comprehensive_defensive_behavior(self):
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
            MockNetwork(viz={"matrix_colors": {"pos": "red", "neg": "blue"}}),  # Missing cat colors
        ]

        for network in problematic_scenarios:
            # Test main() - should NOT raise any exceptions
            if hasattr(network, "persistent_cat_colors"):
                initialize_net.main(network)
            else:
                initialize_net.main(network)

            # Test viz() - should NOT raise any exceptions
            initialize_net.viz(network)

            # Verify proper structure exists
            assert hasattr(network, "viz")
            assert isinstance(network.viz, dict)
            assert all(
                key in network.viz for key in ["cat_colors", "global_cat_colors", "matrix_colors"]
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
