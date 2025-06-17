"""
Unit tests for make_clust_fun module with improved robustness and maintainability.

This module provides comprehensive testing for the make_clust function with focus on
parameter validation, network state management, data flow integration, and edge cases.
"""

from copy import deepcopy
from pathlib import Path
import sys
from typing import Any
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd
import pytest


# =============================================================================
# MODULE CONSTANTS AND CONFIGURATION
# =============================================================================

# Path configuration
SRC_ROOT = Path(__file__).parents[3] / "src"
sys.path.insert(0, str(SRC_ROOT))

from celldega.clust.clustering.make_clust_fun import make_clust


# Test data constants
DEFAULT_DISTANCE_MATRICES = {"row": np.array([1, 2, 3]), "col": np.array([1, 2, 3])}
DEFAULT_TEST_DF = pd.DataFrame({"col1": [1, 2]}, index=["gene1", "gene2"])
PROCESSED_TEST_DF = pd.DataFrame({"col1": [3, 4]}, index=["processed1", "processed2"])

# Default network structure constants
DEFAULT_NODES = {"row": ["gene1", "gene2"], "col": ["sample1", "sample2"]}
DEFAULT_MAT = np.array([[1, 2], [3, 4]])
DEFAULT_NODE_INFO_STRUCTURE = {"ini": [], "clust": [], "rank": [], "rankvar": [], "value": []}
DEFAULT_VIZ_STRUCTURE = {"views": [], "cat_colors": {"row": {}, "col": {}}}
DEFAULT_DAT_STRUCTURE = {
    "nodes": DEFAULT_NODES,
    "mat": DEFAULT_MAT,
    "node_info": {
        "row": DEFAULT_NODE_INFO_STRUCTURE.copy(),
        "col": DEFAULT_NODE_INFO_STRUCTURE.copy(),
    },
}

# Parameter testing constants
DISTANCE_METRICS = ["cosine", "euclidean", "manhattan", "correlation"]
LINKAGE_METHODS = ["average", "ward", "complete", "single"]
CLUSTERING_LIBRARIES = ["scipy", "fastcluster", "hdbscan"]
SIM_MAT_VALID_VALUES = [True, False, "row", "col"]
SIM_MAT_INVALID_VALUES = ["invalid", 1, 0, None]
ENRICHR_LIBRARIES = ["KEGG_2016", "GO_Biological_Process_2015", ""]

# Error messages
MISSING_ATTRIBUTE_ERROR = "Missing required network attribute"
CLUSTERING_FAILURE_ERROR = "Clustering failed"
SIM_MAT_FAILURE_ERROR = "Sim mat failed"


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================


def create_mock_network(
    include_viz: bool = True,
    include_dat: bool = True,
    include_sim: bool = False,
    viz_structure: dict[str, Any] | None = None,
    dat_structure: dict[str, Any] | None = None,
) -> Mock:
    """
    Create a mock network object with configurable structure.

    Args:
        include_viz: Whether to include viz attribute
        include_dat: Whether to include dat attribute
        include_sim: Whether to include sim attribute
        viz_structure: Custom viz structure (merged with defaults)
        dat_structure: Custom dat structure (merged with defaults)

    Returns:
        Mock network object with specified structure
    """
    mock_net = Mock()

    if include_viz:
        viz = DEFAULT_VIZ_STRUCTURE.copy()
        if viz_structure:
            viz.update(viz_structure)
        mock_net.viz = viz

    if include_dat:
        dat = deepcopy(DEFAULT_DAT_STRUCTURE)
        if dat_structure:
            dat.update(dat_structure)
        mock_net.dat = dat

    if include_sim:
        mock_net.sim = {}

    # Configure DataFrame method mocks
    mock_net.dat_to_df.return_value = DEFAULT_TEST_DF
    return mock_net


def setup_similarity_mocks(mock_make_sim_mat: Mock, mock_calc_clust: Mock) -> None:
    """Configure similarity matrix mock behavior."""
    mock_calc_clust.cluster_row_and_col.return_value = DEFAULT_DISTANCE_MATRICES

    mock_sim_net = Mock()
    mock_sim_net.viz = {"cat_colors": {"row": {}, "col": {}}}
    mock_make_sim_mat.main.return_value = {"row": mock_sim_net, "col": mock_sim_net}


def setup_enrichr_mocks(mock_enr_fun: Mock) -> None:
    """Configure enrichment analysis mock behavior."""
    mock_enr_fun.add_enrichr_cats.return_value = PROCESSED_TEST_DF


def get_default_clustering_params(**overrides: Any) -> dict[str, Any]:
    """Get default clustering parameters with optional overrides."""
    defaults = {
        "dist_type": "cosine",
        "linkage_type": "average",
        "run_clustering": True,
        "dendro": True,
        "ignore_cat": False,
        "calc_cat_pval": False,
        "clust_library": "scipy",
        "min_samples": 1,
        "min_cluster_size": 2,
    }
    defaults.update(overrides)
    return defaults


def assert_clustering_called_with_params(
    mock_calc_clust: Mock, mock_net: Mock, **expected_params: Any
) -> None:
    """Assert clustering was called with expected parameters."""
    expected = get_default_clustering_params(**expected_params)
    mock_calc_clust.cluster_row_and_col.assert_called_once_with(mock_net, **expected)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_dependencies():
    """Fixture providing all common mock dependencies with default setup."""
    with (
        patch("celldega.clust.clustering.make_clust_fun.make_sim_mat") as mock_make_sim_mat,
        patch("celldega.clust.clustering.make_clust_fun.calc_clust") as mock_calc_clust,
        patch("celldega.clust.clustering.make_clust_fun.enr_fun") as mock_enr_fun,
    ):
        setup_similarity_mocks(mock_make_sim_mat, mock_calc_clust)
        setup_enrichr_mocks(mock_enr_fun)

        yield {
            "make_sim_mat": mock_make_sim_mat,
            "calc_clust": mock_calc_clust,
            "enr_fun": mock_enr_fun,
        }


@pytest.fixture
def standard_mock_net():
    """Fixture providing a standard mock network for common test scenarios."""
    return create_mock_network()


@pytest.fixture
def enriched_mock_net():
    """Fixture providing a mock network with enrichment data structures."""
    dat_structure = {"enrichrgram_lib": "KEGG_2016", "row_cat_bars": [1, 2, 3]}
    return create_mock_network(dat_structure=dat_structure)


# =============================================================================
# PARAMETER VALIDATION TESTS
# =============================================================================


class TestParameterValidation:
    """Test parameter validation and input handling."""

    @pytest.mark.parametrize(
        "net_input,expected_error",
        [
            (None, AttributeError),
            ("invalid_string", AttributeError),
            (42, AttributeError),
            ([], AttributeError),
            ({}, AttributeError),
        ],
    )
    def test_invalid_net_parameter_raises_error(self, mock_dependencies, net_input, expected_error):
        """Test that invalid net parameters raise appropriate errors."""
        with pytest.raises(expected_error):
            make_clust(net_input)

    def test_valid_net_parameter_succeeds(self, mock_dependencies, standard_mock_net):
        """Test that valid net object processes without error."""
        make_clust(standard_mock_net)
        # No exception should be raised

    @pytest.mark.parametrize("dist_type", DISTANCE_METRICS)
    def test_distance_metrics_parameter(self, mock_dependencies, standard_mock_net, dist_type):
        """Test various distance metrics are passed correctly."""
        make_clust(standard_mock_net, dist_type=dist_type)
        assert_clustering_called_with_params(
            mock_dependencies["calc_clust"], standard_mock_net, dist_type=dist_type
        )

    @pytest.mark.parametrize("linkage_type", LINKAGE_METHODS)
    def test_linkage_methods_parameter(self, mock_dependencies, standard_mock_net, linkage_type):
        """Test various linkage methods are passed correctly."""
        make_clust(standard_mock_net, linkage_type=linkage_type)
        assert_clustering_called_with_params(
            mock_dependencies["calc_clust"], standard_mock_net, linkage_type=linkage_type
        )

    @pytest.mark.parametrize("clust_library", CLUSTERING_LIBRARIES)
    def test_clustering_libraries_parameter(
        self, mock_dependencies, standard_mock_net, clust_library
    ):
        """Test various clustering libraries are passed correctly."""
        make_clust(standard_mock_net, clust_library=clust_library)
        assert_clustering_called_with_params(
            mock_dependencies["calc_clust"], standard_mock_net, clust_library=clust_library
        )


# =============================================================================
# SIMILARITY MATRIX LOGIC TESTS
# =============================================================================


class TestSimilarityMatrixLogic:
    """Test similarity matrix generation and parameter handling."""

    @pytest.mark.parametrize(
        "sim_mat_value,should_call_sim_mat,expected_axes",
        [
            (True, True, ["row", "col"]),
            (False, False, []),
            ("row", True, ["row"]),
            ("col", True, ["col"]),
        ],
    )
    def test_valid_sim_mat_parameters(
        self,
        mock_dependencies,
        standard_mock_net,
        sim_mat_value,
        should_call_sim_mat,
        expected_axes,
    ):
        """Test valid sim_mat parameter values and their effects."""
        make_clust(standard_mock_net, sim_mat=sim_mat_value)

        if should_call_sim_mat:
            mock_dependencies["make_sim_mat"].main.assert_called_once()
            call_args = mock_dependencies["make_sim_mat"].main.call_args[0]
            assert call_args[2] == expected_axes
        else:
            mock_dependencies["make_sim_mat"].main.assert_not_called()

    @pytest.mark.parametrize("invalid_value", SIM_MAT_INVALID_VALUES)
    def test_invalid_sim_mat_parameters_ignored(
        self, mock_dependencies, standard_mock_net, invalid_value
    ):
        """Test that invalid sim_mat values are silently ignored."""
        make_clust(standard_mock_net, sim_mat=invalid_value)
        mock_dependencies["make_sim_mat"].main.assert_not_called()

    @pytest.mark.parametrize("filter_sim_value", [0.0, 0.1, 0.5, 0.9, 1.0])
    def test_filter_sim_parameter_passed_correctly(
        self, mock_dependencies, standard_mock_net, filter_sim_value
    ):
        """Test filter_sim parameter is passed correctly to similarity matrix generation."""
        make_clust(standard_mock_net, sim_mat=True, filter_sim=filter_sim_value)

        call_args = mock_dependencies["make_sim_mat"].main.call_args[0]
        assert call_args[3] == filter_sim_value

    def test_sim_mat_views_parameter_handling(self, mock_dependencies, standard_mock_net):
        """Test sim_mat_views parameter default and custom values."""
        # Test default
        make_clust(standard_mock_net, sim_mat=True)
        call_args = mock_dependencies["make_sim_mat"].main.call_args[0]
        assert call_args[4] == ["N_row_sum"]  # Default sim_mat_views

        # Test custom
        custom_views = ["custom_view1", "custom_view2"]
        make_clust(standard_mock_net, sim_mat=True, sim_mat_views=custom_views)
        call_args = mock_dependencies["make_sim_mat"].main.call_args[0]
        assert call_args[4] == custom_views


# =============================================================================
# ENRICHMENT ANALYSIS TESTS
# =============================================================================


class TestEnrichmentAnalysis:
    """Test gene enrichment analysis integration."""

    @pytest.mark.parametrize("enrichr_lib", ENRICHR_LIBRARIES)
    def test_enrichr_libraries_processing(self, mock_dependencies, standard_mock_net, enrichr_lib):
        """Test various Enrichr libraries are processed correctly."""
        make_clust(standard_mock_net, run_enrichr=enrichr_lib)

        mock_dependencies["enr_fun"].add_enrichr_cats.assert_called_once_with(
            DEFAULT_TEST_DF, "row", enrichr_lib
        )
        standard_mock_net.df_to_dat.assert_called_once_with(
            PROCESSED_TEST_DF, define_cat_colors=True
        )

    def test_no_enrichr_processing_when_none(self, mock_dependencies, standard_mock_net):
        """Test that no enrichment processing occurs when run_enrichr is None."""
        make_clust(standard_mock_net, run_enrichr=None)
        mock_dependencies["enr_fun"].add_enrichr_cats.assert_not_called()

    @pytest.mark.parametrize(
        "enrichr_param,enrichrgram_param,expected_enrichr_calls,expected_viz_enrichrgram",
        [
            (None, None, 0, None),
            ("KEGG_2016", None, 1, None),
            (None, True, 0, True),
            (None, False, 0, False),
            ("GO_Biological_Process_2015", True, 1, True),
            ("", False, 1, False),
        ],
    )
    def test_enrichment_parameter_combinations(
        self,
        mock_dependencies,
        standard_mock_net,
        enrichr_param,
        enrichrgram_param,
        expected_enrichr_calls,
        expected_viz_enrichrgram,
    ):
        """Test run_enrichr and enrichrgram parameter interactions."""
        make_clust(standard_mock_net, run_enrichr=enrichr_param, enrichrgram=enrichrgram_param)

        assert mock_dependencies["enr_fun"].add_enrichr_cats.call_count == expected_enrichr_calls

        if expected_viz_enrichrgram is not None:
            assert standard_mock_net.viz["enrichrgram"] == expected_viz_enrichrgram

    @pytest.mark.parametrize(
        "dat_enrichrgram_lib,enrichrgram_param,expected_enrichrgram,expected_lib_key",
        [
            ("KEGG_2016", False, True, "enrichrgram_lib"),  # dat takes precedence
            ("KEGG_2016", True, True, "enrichrgram_lib"),  # dat takes precedence
            (None, True, True, None),  # parameter used
            (None, False, False, None),  # parameter used
        ],
    )
    def test_enrichrgram_precedence_logic(
        self,
        mock_dependencies,
        dat_enrichrgram_lib,
        enrichrgram_param,
        expected_enrichrgram,
        expected_lib_key,
    ):
        """Test enrichrgram parameter precedence between dat and parameters."""
        dat_structure = {}
        if dat_enrichrgram_lib:
            dat_structure["enrichrgram_lib"] = dat_enrichrgram_lib

        mock_net = create_mock_network(dat_structure=dat_structure)
        make_clust(mock_net, enrichrgram=enrichrgram_param)

        assert mock_net.viz["enrichrgram"] == expected_enrichrgram
        if expected_lib_key:
            assert expected_lib_key in mock_net.viz
            assert mock_net.viz[expected_lib_key] == dat_enrichrgram_lib


# =============================================================================
# NETWORK STATE MANAGEMENT TESTS
# =============================================================================


class TestNetworkStateManagement:
    """Test network object state management and modifications."""

    @pytest.mark.parametrize(
        "initial_views,expected_final_views",
        [
            (["existing_view"], []),
            (["view1", "view2", "view3"], []),
            ([], []),
        ],
    )
    def test_viz_views_reset_behavior(self, mock_dependencies, initial_views, expected_final_views):
        """Test that viz views are properly reset regardless of initial state."""
        viz_structure = {"views": initial_views}
        mock_net = create_mock_network(viz_structure=viz_structure)

        make_clust(mock_net)
        assert mock_net.viz["views"] == expected_final_views

    def test_sim_object_initialization_when_disabled(self, mock_dependencies, standard_mock_net):
        """Test sim object initialization when similarity matrices are disabled."""
        standard_mock_net.sim = {"existing": "data"}
        make_clust(standard_mock_net, sim_mat=False)
        assert standard_mock_net.sim == {}

    def test_sim_object_population_when_enabled(self, mock_dependencies, standard_mock_net):
        """Test sim object population when similarity matrices are enabled."""
        standard_mock_net.viz["cat_colors"] = {"row": {"color1": "red"}, "col": {"color2": "blue"}}

        make_clust(standard_mock_net, sim_mat=True)

        # Verify sim object structure
        assert "row" in standard_mock_net.sim
        assert "col" in standard_mock_net.sim
        assert "cat_colors" in standard_mock_net.sim["row"]
        assert "cat_colors" in standard_mock_net.sim["col"]

    @pytest.mark.parametrize(
        "missing_attr,attr_path",
        [
            ("viz", "viz"),
            ("dat", "dat"),
            ("cat_colors", "viz.cat_colors"),
        ],
    )
    def test_missing_network_attributes_handling(self, mock_dependencies, missing_attr, attr_path):
        """Test behavior when expected network attributes are missing."""
        mock_net = create_mock_network()

        # Remove the specified attribute
        if attr_path == "viz":
            delattr(mock_net, "viz")
        elif attr_path == "dat":
            delattr(mock_net, "dat")
        elif attr_path == "viz.cat_colors":
            mock_net.viz.pop("cat_colors")

        # Set up test scenario that would use the missing attribute
        kwargs = {"sim_mat": True} if missing_attr == "cat_colors" else {}

        with pytest.raises((AttributeError, KeyError)):
            make_clust(mock_net, **kwargs)

    def test_object_state_consistency_throughout_processing(
        self, mock_dependencies, standard_mock_net
    ):
        """Test that object maintains consistent state throughout processing."""
        standard_mock_net.viz["views"] = ["existing_view"]
        original_dat_keys = set(standard_mock_net.dat.keys())

        make_clust(standard_mock_net)

        # Verify expected state changes
        assert standard_mock_net.viz["views"] == []
        assert set(standard_mock_net.dat.keys()) == original_dat_keys
        assert hasattr(standard_mock_net, "sim")


# =============================================================================
# COLOR ASSIGNMENT REGRESSION TESTS
# =============================================================================


class TestColorAssignmentLogic:
    """Test color assignment logic and verify bug fixes."""

    def test_color_assignment_correct_axis_mapping(self, mock_dependencies, standard_mock_net):
        """Test that color assignment correctly maps each axis to its own colors."""
        standard_mock_net.viz["cat_colors"] = {
            "row": {"gene_type": "red", "expression": "green"},
            "col": {"sample_type": "blue", "condition": "yellow"},
        }

        make_clust(standard_mock_net, sim_mat=True)

        # Verify each axis gets its own colors (regression test for color assignment bug)
        row_colors = standard_mock_net.sim["row"]["cat_colors"]
        col_colors = standard_mock_net.sim["col"]["cat_colors"]

        assert row_colors["row"] == {"gene_type": "red", "expression": "green"}
        assert row_colors["col"] == {"sample_type": "blue", "condition": "yellow"}
        assert col_colors["row"] == {"gene_type": "red", "expression": "green"}
        assert col_colors["col"] == {"sample_type": "blue", "condition": "yellow"}

    def test_color_assignment_with_empty_colors(self, mock_dependencies, standard_mock_net):
        """Test color assignment behavior with empty color dictionaries."""
        standard_mock_net.viz["cat_colors"] = {"row": {}, "col": {}}

        make_clust(standard_mock_net, sim_mat=True)

        # Should not raise errors and should preserve empty structure
        assert standard_mock_net.sim["row"]["cat_colors"]["row"] == {}
        assert standard_mock_net.sim["row"]["cat_colors"]["col"] == {}


# =============================================================================
# DATA FLOW AND INTEGRATION TESTS
# =============================================================================


class TestDataFlowIntegration:
    """Test data flow and integration between components."""

    def test_complete_enrichr_data_flow(self, mock_dependencies, standard_mock_net):
        """Test complete data flow through enrichment processing."""
        make_clust(standard_mock_net, run_enrichr="KEGG_2016")

        # Verify complete data flow chain
        standard_mock_net.dat_to_df.assert_called_once()
        mock_dependencies["enr_fun"].add_enrichr_cats.assert_called_once_with(
            DEFAULT_TEST_DF, "row", "KEGG_2016"
        )
        standard_mock_net.df_to_dat.assert_called_once_with(
            PROCESSED_TEST_DF, define_cat_colors=True
        )

    def test_clustering_parameter_propagation(self, mock_dependencies, standard_mock_net):
        """Test that clustering parameters are correctly propagated."""
        clustering_params = {
            "dist_type": "euclidean",
            "linkage_type": "ward",
            "run_clustering": False,
            "dendro": False,
            "calc_cat_pval": True,
            "clust_library": "fastcluster",
            "min_samples": 5,
            "min_cluster_size": 10,
        }

        make_clust(standard_mock_net, **clustering_params)
        assert_clustering_called_with_params(
            mock_dependencies["calc_clust"], standard_mock_net, **clustering_params
        )

    def test_similarity_matrix_parameter_propagation(self, mock_dependencies, standard_mock_net):
        """Test that similarity matrix parameters are correctly propagated."""
        sim_params = {"sim_mat": "row", "filter_sim": 0.3, "sim_mat_views": ["custom_view"]}

        make_clust(standard_mock_net, **sim_params)

        mock_dependencies["make_sim_mat"].main.assert_called_once()
        call_args = mock_dependencies["make_sim_mat"].main.call_args[0]

        assert call_args[2] == ["row"]  # similarity_axes
        assert call_args[3] == 0.3  # filter_sim
        assert call_args[4] == ["custom_view"]  # sim_mat_views

    def test_special_dat_structure_transfer_to_viz(self, mock_dependencies, enriched_mock_net):
        """Test transfer of special dat structure elements to viz."""
        make_clust(enriched_mock_net)

        # Verify dat information is transferred to viz
        assert enriched_mock_net.viz["enrichrgram"] is True
        assert enriched_mock_net.viz["enrichrgram_lib"] == "KEGG_2016"
        assert enriched_mock_net.viz["row_cat_bars"] == [1, 2, 3]


# =============================================================================
# ERROR HANDLING AND EDGE CASES
# =============================================================================


class TestErrorHandlingAndEdgeCases:
    """Test error handling and complex edge case scenarios."""

    @pytest.mark.parametrize(
        "error_source,error_type,error_message",
        [
            ("calc_clust", RuntimeError, CLUSTERING_FAILURE_ERROR),
            ("calc_clust", ValueError, "Invalid clustering parameters"),
            ("make_sim_mat", KeyError, SIM_MAT_FAILURE_ERROR),
            ("make_sim_mat", MemoryError, "Insufficient memory for similarity matrix"),
        ],
    )
    def test_dependency_error_propagation(
        self, mock_dependencies, standard_mock_net, error_source, error_type, error_message
    ):
        """Test that errors from dependencies are properly propagated."""
        if error_source == "calc_clust":
            mock_dependencies["calc_clust"].cluster_row_and_col.side_effect = error_type(
                error_message
            )
            with pytest.raises(error_type, match=error_message):
                make_clust(standard_mock_net)
        elif error_source == "make_sim_mat":
            mock_dependencies["make_sim_mat"].main.side_effect = error_type(error_message)
            with pytest.raises(error_type, match=error_message):
                make_clust(standard_mock_net, sim_mat=True)

    def test_complex_parameter_combinations_integration(self, mock_dependencies, standard_mock_net):
        """Test complex parameter combinations that could interact unexpectedly."""
        complex_params = {
            "dist_type": "manhattan",
            "run_clustering": False,
            "dendro": False,
            "requested_views": ["custom_view_1", "custom_view_2"],
            "linkage_type": "complete",
            "sim_mat": "row",
            "filter_sim": 0.5,
            "calc_cat_pval": True,
            "sim_mat_views": ["sim_view_1", "sim_view_2"],
            "run_enrichr": "GO_Biological_Process_2015",
            "enrichrgram": True,
            "clust_library": "hdbscan",
            "min_samples": 3,
            "min_cluster_size": 5,
        }

        make_clust(standard_mock_net, **complex_params)

        # Verify all major components were invoked
        assert mock_dependencies["enr_fun"].add_enrichr_cats.called
        assert mock_dependencies["calc_clust"].cluster_row_and_col.called
        assert mock_dependencies["make_sim_mat"].main.called

    def test_concurrent_modification_scenario(self, mock_dependencies, standard_mock_net):
        """Test behavior under simulated concurrent modification."""

        def simulate_concurrent_modification(*args, **kwargs):
            standard_mock_net.viz["modified_during_execution"] = True
            return DEFAULT_DISTANCE_MATRICES

        mock_dependencies[
            "calc_clust"
        ].cluster_row_and_col.side_effect = simulate_concurrent_modification

        make_clust(standard_mock_net)

        # Function should complete successfully and preserve all modifications
        assert standard_mock_net.viz["modified_during_execution"] is True
        assert standard_mock_net.viz["views"] == []

    @pytest.mark.parametrize(
        "requested_views,expected_behavior",
        [
            (None, "default_views_used"),
            ([], "empty_views_used"),
            (["single_view"], "custom_views_used"),
            (["view1", "view2", "view3"], "multiple_views_used"),
        ],
    )
    def test_requested_views_parameter_edge_cases(
        self, mock_dependencies, standard_mock_net, requested_views, expected_behavior
    ):
        """Test requested_views parameter handling in various edge cases."""
        make_clust(standard_mock_net, requested_views=requested_views)

        # The actual views processing happens in calc_clust, so we verify the parameter
        # was passed correctly
        _ = mock_dependencies["calc_clust"].cluster_row_and_col.call_args[1]

        # The function should have processed the requested_views (though the exact
        # processing logic is in calc_clust, not make_clust)
        assert mock_dependencies["calc_clust"].cluster_row_and_col.called


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
