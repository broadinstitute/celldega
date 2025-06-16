from copy import deepcopy
from pathlib import Path
import sys
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd
import pytest


# Add the source directory to the path for imports
sys.path.insert(0, str(Path(__file__).parents[3] / "src"))

from celldega.clust.clustering.make_clust_fun import make_clust


class TestMakeClustBase:
    """Base class with common utilities and fixtures for make_clust testing."""

    # Common test data as class attributes to avoid recreation
    DEFAULT_DISTANCE_MATRICES = {"row": np.array([1, 2, 3]), "col": np.array([1, 2, 3])}
    DEFAULT_TEST_DF = pd.DataFrame({"col1": [1, 2]}, index=["gene1", "gene2"])
    PROCESSED_TEST_DF = pd.DataFrame({"col1": [3, 4]}, index=["processed1", "processed2"])

    @staticmethod
    def create_mock_net(
        include_viz=True,
        include_dat=True,
        include_sim=False,
        viz_structure=None,
        dat_structure=None,
    ):
        """Create mock network object with configurable structure."""
        mock_net = Mock()

        if include_viz:
            default_viz = {"views": [], "cat_colors": {"row": {}, "col": {}}}
            if viz_structure:
                default_viz.update(viz_structure)
            mock_net.viz = default_viz

        if include_dat:
            default_dat = {
                "nodes": {"row": ["gene1", "gene2"], "col": ["sample1", "sample2"]},
                "mat": np.array([[1, 2], [3, 4]]),
                "node_info": {
                    "row": {"ini": [], "clust": [], "rank": [], "rankvar": [], "value": []},
                    "col": {"ini": [], "clust": [], "rank": [], "rankvar": [], "value": []},
                },
            }
            if dat_structure:
                default_dat.update(dat_structure)
            mock_net.dat = default_dat

        if include_sim:
            mock_net.sim = {}

        # Mock DataFrame methods
        mock_net.dat_to_df.return_value = TestMakeClustBase.DEFAULT_TEST_DF
        return mock_net

    @staticmethod
    def setup_similarity_mocks(mock_make_sim_mat, mock_calc_clust):
        """Configure common similarity matrix mock behavior."""
        mock_calc_clust.cluster_row_and_col.return_value = (
            TestMakeClustBase.DEFAULT_DISTANCE_MATRICES
        )

        mock_sim_net = Mock()
        mock_sim_net.viz = {"cat_colors": {"row": {}, "col": {}}}
        mock_make_sim_mat.main.return_value = {"row": mock_sim_net, "col": mock_sim_net}

    @staticmethod
    def setup_enrichr_mocks(mock_enr_fun):
        """Configure common enrichment analysis mock behavior."""
        mock_enr_fun.add_enrichr_cats.return_value = TestMakeClustBase.PROCESSED_TEST_DF

    def assert_standard_mock_calls(self, mock_net, mock_calc_clust, **expected_clustering_params):
        """Assert standard clustering function calls with expected parameters."""
        default_params = {
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
        default_params.update(expected_clustering_params)

        mock_calc_clust.cluster_row_and_col.assert_called_once_with(mock_net, **default_params)


@pytest.fixture
def mock_dependencies():
    """Fixture providing all common mock dependencies."""
    with (
        patch("celldega.clust.clustering.make_clust_fun.make_sim_mat") as mock_make_sim_mat,
        patch("celldega.clust.clustering.make_clust_fun.calc_clust") as mock_calc_clust,
        patch("celldega.clust.clustering.make_clust_fun.enr_fun") as mock_enr_fun,
    ):
        # Set up default mock behaviors
        TestMakeClustBase.setup_similarity_mocks(mock_make_sim_mat, mock_calc_clust)
        TestMakeClustBase.setup_enrichr_mocks(mock_enr_fun)

        yield {
            "make_sim_mat": mock_make_sim_mat,
            "calc_clust": mock_calc_clust,
            "enr_fun": mock_enr_fun,
        }


class TestParameterValidation(TestMakeClustBase):
    """Test parameter validation and basic input handling."""

    @pytest.mark.parametrize(
        "net_input,error_type",
        [
            (None, AttributeError),
            ("invalid", AttributeError),
            (42, AttributeError),
        ],
    )
    def test_net_parameter_validation(self, mock_dependencies, net_input, error_type):
        """Test net parameter validation with various invalid inputs."""
        with pytest.raises(error_type):
            make_clust(net_input)

    def test_valid_net_parameter(self, mock_dependencies):
        """Test that valid net object works without error."""
        mock_net = self.create_mock_net()
        make_clust(mock_net)  # Should not raise

    @pytest.mark.parametrize(
        "sim_mat_value,should_call_sim_mat,expected_which_sim",
        [
            (True, True, ["row", "col"]),
            (False, False, []),
            ("row", True, ["row"]),
            ("col", True, ["col"]),
            ("invalid", False, []),
            (1, False, []),
            (0, False, []),
            (None, False, []),
        ],
    )
    def test_sim_mat_parameter_logic(
        self, mock_dependencies, sim_mat_value, should_call_sim_mat, expected_which_sim
    ):
        """Test sim_mat parameter handling logic."""
        mock_net = self.create_mock_net()
        make_clust(mock_net, sim_mat=sim_mat_value)

        if should_call_sim_mat:
            mock_dependencies["make_sim_mat"].main.assert_called_once()
            call_args = mock_dependencies["make_sim_mat"].main.call_args[0]
            assert call_args[2] == expected_which_sim
        else:
            mock_dependencies["make_sim_mat"].main.assert_not_called()

    @pytest.mark.parametrize(
        "enrichr_param,enrichrgram_param,expected_enrichr_calls,expected_viz_updates",
        [
            (None, None, 0, {}),
            ("KEGG_2016", None, 1, {}),
            (None, True, 0, {"enrichrgram": True}),
            ("GO_Biological_Process_2015", True, 1, {"enrichrgram": True}),
            ("", None, 1, {}),
        ],
    )
    def test_enrichment_parameter_combinations(
        self,
        mock_dependencies,
        enrichr_param,
        enrichrgram_param,
        expected_enrichr_calls,
        expected_viz_updates,
    ):
        """Test run_enrichr and enrichrgram parameter interactions."""
        mock_net = self.create_mock_net()
        make_clust(mock_net, run_enrichr=enrichr_param, enrichrgram=enrichrgram_param)

        assert mock_dependencies["enr_fun"].add_enrichr_cats.call_count == expected_enrichr_calls
        for key, value in expected_viz_updates.items():
            assert mock_net.viz[key] == value


class TestNetworkStateManagement(TestMakeClustBase):
    """Test network object state management and side effects."""

    @pytest.mark.parametrize(
        "initial_views,expected_final_views",
        [
            (["existing_view"], []),
            (["view1", "view2"], []),
            ([], []),
        ],
    )
    def test_viz_views_initialization(self, mock_dependencies, initial_views, expected_final_views):
        """Test that viz views are properly initialized."""
        mock_net = self.create_mock_net()
        mock_net.viz["views"] = initial_views
        make_clust(mock_net)
        assert mock_net.viz["views"] == expected_final_views

    def test_sim_object_initialization(self, mock_dependencies):
        """Test sim object initialization under different conditions."""
        mock_net = self.create_mock_net()
        mock_net.sim = {"existing": "data"}
        make_clust(mock_net, sim_mat=False)
        assert mock_net.sim == {}

    @pytest.mark.parametrize(
        "missing_attr,setup_func",
        [
            ("viz", lambda net: delattr(net, "viz")),
            ("dat", lambda net: delattr(net, "dat")),
            ("cat_colors", lambda net: net.viz.pop("cat_colors")),
        ],
    )
    def test_missing_network_structure_handling(self, mock_dependencies, missing_attr, setup_func):
        """Test behavior when expected network structure is missing."""
        mock_net = self.create_mock_net()
        setup_func(mock_net)

        # For cat_colors test, need to set up sim_mat scenario
        kwargs = {"sim_mat": True} if missing_attr == "cat_colors" else {}

        with pytest.raises((AttributeError, KeyError)):
            make_clust(mock_net, **kwargs)


class TestColorAssignmentBug(TestMakeClustBase):
    """Test the color assignment logic and verify bug fix."""

    def test_color_assignment_correct_behavior(self, mock_dependencies):
        """Test that color assignment works correctly with the bug fix."""
        mock_net = self.create_mock_net()
        mock_net.viz["cat_colors"] = {"row": {"color1": "red"}, "col": {"color2": "blue"}}

        make_clust(mock_net, sim_mat=True)

        # Verify each axis gets its own colors (bug fix verification)
        expected_row_colors = {"color1": "red"}
        expected_col_colors = {"color2": "blue"}

        assert mock_net.sim["row"]["cat_colors"]["row"] == expected_row_colors
        assert mock_net.sim["row"]["cat_colors"]["col"] == expected_col_colors


class TestDataFlowAndIntegration(TestMakeClustBase):
    """Test data flow and integration with dependencies."""

    def test_enrichr_data_flow(self, mock_dependencies):
        """Test data flow through enrichr processing."""
        mock_net = self.create_mock_net()
        mock_net.dat_to_df.return_value = self.DEFAULT_TEST_DF

        make_clust(mock_net, run_enrichr="KEGG_2016")

        # Verify complete data flow
        mock_net.dat_to_df.assert_called_once()
        mock_dependencies["enr_fun"].add_enrichr_cats.assert_called_once_with(
            self.DEFAULT_TEST_DF, "row", "KEGG_2016"
        )
        mock_net.df_to_dat.assert_called_once_with(self.PROCESSED_TEST_DF, define_cat_colors=True)

    def test_clustering_integration(self, mock_dependencies):
        """Test integration with clustering components."""
        mock_net = self.create_mock_net()

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

        make_clust(mock_net, **clustering_params)
        self.assert_standard_mock_calls(
            mock_net, mock_dependencies["calc_clust"], **clustering_params
        )

    @pytest.mark.parametrize(
        "error_source,error_type,error_message",
        [
            ("calc_clust", RuntimeError, "Clustering failed"),
            ("make_sim_mat", KeyError, "Sim mat failed"),
        ],
    )
    def test_error_propagation(self, mock_dependencies, error_source, error_type, error_message):
        """Test that errors from dependencies are properly propagated."""
        mock_net = self.create_mock_net()

        if error_source == "calc_clust":
            mock_dependencies["calc_clust"].cluster_row_and_col.side_effect = error_type(
                error_message
            )
            with pytest.raises(error_type, match=error_message):
                make_clust(mock_net)
        else:
            # Reset calc_clust and set up make_sim_mat error
            mock_dependencies["calc_clust"].cluster_row_and_col.side_effect = None
            mock_dependencies["make_sim_mat"].main.side_effect = error_type(error_message)
            with pytest.raises(error_type, match=error_message):
                make_clust(mock_net, sim_mat=True)


class TestSpecialCasesAndEdgeScenarios(TestMakeClustBase):
    """Test special cases and complex edge scenarios."""

    def test_dat_structure_special_cases(self, mock_dependencies):
        """Test handling of special dat structure cases."""
        mock_net = self.create_mock_net()
        mock_net.dat.update({"enrichrgram_lib": "KEGG_2016", "row_cat_bars": [1, 2, 3]})

        make_clust(mock_net)

        # Verify viz gets updated with dat information
        assert mock_net.viz["enrichrgram"] is True
        assert mock_net.viz["enrichrgram_lib"] == "KEGG_2016"
        assert mock_net.viz["row_cat_bars"] == [1, 2, 3]

    @pytest.mark.parametrize(
        "dat_enrichrgram_lib,enrichrgram_param,expected_enrichrgram,expected_lib",
        [
            ("KEGG_2016", False, True, "KEGG_2016"),  # dat takes precedence
            ("KEGG_2016", True, True, "KEGG_2016"),  # dat takes precedence
            (None, True, True, None),  # parameter used
            (None, False, False, None),  # parameter used
        ],
    )
    def test_enrichrgram_precedence(
        self,
        mock_dependencies,
        dat_enrichrgram_lib,
        enrichrgram_param,
        expected_enrichrgram,
        expected_lib,
    ):
        """Test enrichrgram parameter precedence logic."""
        mock_net = self.create_mock_net()
        if dat_enrichrgram_lib:
            mock_net.dat["enrichrgram_lib"] = dat_enrichrgram_lib

        make_clust(mock_net, enrichrgram=enrichrgram_param)

        assert mock_net.viz["enrichrgram"] == expected_enrichrgram
        if expected_lib:
            assert mock_net.viz["enrichrgram_lib"] == expected_lib

    def test_complex_parameter_combinations(self, mock_dependencies):
        """Test multiple parameter combinations that could interact."""
        mock_net = self.create_mock_net()

        complex_params = {
            "dist_type": "manhattan",
            "run_clustering": False,
            "dendro": False,
            "requested_views": ["custom_view"],
            "linkage_type": "complete",
            "sim_mat": "row",
            "filter_sim": 0.5,
            "calc_cat_pval": True,
            "run_enrichr": "GO_Biological_Process_2015",
            "enrichrgram": True,
            "clust_library": "hdbscan",
            "min_samples": 3,
            "min_cluster_size": 5,
        }

        make_clust(mock_net, **complex_params)

        # Verify all major components were called
        assert mock_dependencies["enr_fun"].add_enrichr_cats.called
        assert mock_dependencies["calc_clust"].cluster_row_and_col.called
        assert mock_dependencies["make_sim_mat"].main.called

    def test_object_state_consistency(self, mock_dependencies):
        """Test that objects maintain consistent state throughout processing."""
        mock_net = self.create_mock_net()
        mock_net.viz["views"] = ["existing_view"]
        original_dat = deepcopy(mock_net.dat)

        make_clust(mock_net)

        # Verify expected state changes
        assert mock_net.viz["views"] == []  # Views cleared
        assert "nodes" in mock_net.dat and "mat" in mock_net.dat  # Core data preserved
        assert hasattr(mock_net, "sim") and mock_net.sim == {}  # Sim initialized

    def test_concurrent_modification_safety(self, mock_dependencies):
        """Test behavior under concurrent modification scenarios."""
        mock_net = self.create_mock_net()

        def modify_during_clustering(*args, **kwargs):
            mock_net.viz["modified_during_execution"] = True
            return self.DEFAULT_DISTANCE_MATRICES

        mock_dependencies["calc_clust"].cluster_row_and_col.side_effect = modify_during_clustering

        make_clust(mock_net)

        # Function should complete and preserve both modifications
        assert mock_net.viz["modified_during_execution"] is True
        assert mock_net.viz["views"] == []


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
