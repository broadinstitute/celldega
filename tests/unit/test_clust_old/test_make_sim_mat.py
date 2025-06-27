from copy import deepcopy
from pathlib import Path
import sys
from unittest.mock import Mock, patch

import numpy as np
import pytest


# Add the source directory to the path for imports
sys.path.insert(0, str(Path(__file__).parents[3] / "src"))

from celldega.clust_old.clustering.make_sim_mat import adjust_filter_sim, dm_to_sim, main


class TestFixtures:
    """Shared test fixtures and utilities."""

    @staticmethod
    def create_mock_network():
        """Create a standard mock network for testing."""
        mock_net = Mock()
        mock_net.dat = {
            "nodes": {"row": ["r1", "r2", "r3"], "col": ["c1", "c2", "c3"]},
            "node_info": {"row": {}, "col": {}},
            "mat": np.array([[1, 2, 3], [4, 5, 6], [7, 8, 9]]),
        }
        mock_net.viz = {"views": []}
        return mock_net

    @staticmethod
    def create_sample_distance_matrices():
        """Create sample distance matrices for testing."""
        return {
            "row": np.array([0.1, 0.2, 0.3]),  # condensed 3x3
            "col": np.array([0.4, 0.5, 0.6]),  # condensed 3x3
        }


class TestMainFunction:
    """Test main function with core functionality and edge cases."""

    def setup_method(self):
        """Setup common test fixtures."""
        self.mock_net = TestFixtures.create_mock_network()
        self.inst_dm = TestFixtures.create_sample_distance_matrices()

    @patch("celldega.clust_old.clustering.calc_clust.cluster_row_and_col")
    def test_main_functionality_and_network_setup(self, mock_cluster):
        """Test basic functionality, multiple axes, and network object setup."""
        # Test basic functionality
        result = main(self.mock_net, self.inst_dm, ["row"], 0.0)
        assert "row" in result
        mock_cluster.assert_called_once()

        # Test multiple axes
        mock_cluster.reset_mock()
        result = main(self.mock_net, self.inst_dm, ["row", "col"], 0.1)
        assert "row" in result and "col" in result
        assert len(result) == 2
        assert mock_cluster.call_count == 2

        # Test network object setup (result should be different object but same data)
        result = main(self.mock_net, self.inst_dm, ["row"], 0.1)
        assert result["row"] is not self.mock_net
        assert result["row"].dat["nodes"]["row"] == self.mock_net.dat["nodes"]["row"]

    def test_main_edge_cases(self):
        """Test edge cases: empty list, missing keys, custom parameters."""
        # Empty which_sim list
        result = main(self.mock_net, self.inst_dm, [], 0.0)
        assert result == {}

        # Missing distance matrix key
        with pytest.raises(KeyError):
            main(self.mock_net, self.inst_dm, ["missing_key"], 0.0)

        # Custom sim_mat_views parameter (unused but should not cause errors)
        with patch("celldega.clust_old.clustering.calc_clust.cluster_row_and_col") as mock_cluster:
            result = main(self.mock_net, self.inst_dm, ["row"], 0.0, ["custom_view"])
            assert "row" in result
            mock_cluster.assert_called_once()


class TestDistanceToSimilarity:
    """Test dm_to_sim function with various matrix types and filtering."""

    def test_basic_conversion_and_formats(self):
        """Test basic distance to similarity conversion and different matrix formats."""
        # Basic square matrix conversion
        dist_matrix = np.array([[0, 0.2, 0.4], [0.2, 0, 0.6], [0.4, 0.6, 0]])
        result = dm_to_sim(dist_matrix, make_squareform=False)
        expected = 1 - dist_matrix
        np.testing.assert_array_equal(result, expected)

        # Condensed matrix conversion
        condensed_dm = np.array([0.1, 0.2, 0.3])  # 3x3 condensed form
        result = dm_to_sim(condensed_dm, make_squareform=True)
        assert result.shape == (3, 3)
        assert np.all(result >= 0)  # Similarities should be positive if distances < 1

    def test_similarity_filtering(self):
        """Test similarity filtering with various thresholds and edge cases."""
        dist_matrix = np.array([[0, 0.1, 0.9], [0.1, 0, 0.8], [0.9, 0.8, 0]])

        # Test filtering with threshold
        result = dm_to_sim(dist_matrix, filter_sim=0.5)
        expected = 1 - dist_matrix
        expected[np.abs(expected) < 0.5] = 0
        np.testing.assert_array_almost_equal(result, expected)

        # Test no filtering when filter_sim=0
        result = dm_to_sim(dist_matrix, filter_sim=0)
        expected = 1 - dist_matrix
        np.testing.assert_array_equal(result, expected)

        # Test filtering correctly zeros small values
        dist_matrix = np.array([[0, 0.6, 0.4], [0.6, 0, 0.3], [0.4, 0.3, 0]])
        result = dm_to_sim(dist_matrix, filter_sim=0.5)
        assert result[0, 1] == 0  # 0.4 < 0.5, should be zeroed
        assert result[1, 0] == 0  # symmetric
        assert result[0, 2] != 0  # 0.6 >= 0.5, should remain

    def test_special_matrices(self):
        """Test handling of special matrices: empty, single element, extreme values."""
        # Empty matrix
        empty_matrix = np.array([])
        result = dm_to_sim(empty_matrix)
        assert result.size == 0

        # Single element matrix
        single_matrix = np.array([[0]])
        result = dm_to_sim(single_matrix)
        np.testing.assert_array_equal(result, np.array([[1]]))

        # Non-square matrix (should handle gracefully)
        non_square = np.array([[1, 2, 3], [4, 5, 6]])
        result = dm_to_sim(non_square)
        assert result.shape == (2, 3)

        # Negative distances (become similarities > 1)
        dist_matrix = np.array([[0, -0.1, 0.5], [-0.1, 0, 0.3], [0.5, 0.3, 0]])
        result = dm_to_sim(dist_matrix)
        assert result[0, 1] > 1  # Negative distance becomes similarity > 1


class TestFilterAdjustment:
    """Test adjust_filter_sim function with various scenarios."""

    def test_filter_adjustment_logic(self):
        """Test basic filter adjustment and boundary conditions."""
        # Basic filter adjustment with sufficient data
        matrix = np.array([[0.1, 0.5, 0.9], [0.3, 0.7, 0.2], [0.8, 0.4, 0.6]])
        result = adjust_filter_sim(matrix, 0.5, keep_top=3)
        flat_vals = np.abs(matrix.flatten())
        filtered_vals = flat_vals[flat_vals > 0.01]
        expected = np.sort(filtered_vals)[::-1][3]  # 3rd highest value
        assert result == expected

        # Test when keep_top exceeds available values
        matrix = np.array([[0.1, 0.2]])
        result = adjust_filter_sim(matrix, 0.5, keep_top=10)
        assert result == 0.5  # Should return original filter_sim

        # Test with all values below threshold
        matrix = np.array([[0.005, 0.008], [0.003, 0.009]])
        result = adjust_filter_sim(matrix, 0.5, keep_top=1)
        assert result == 0.5  # Should return original filter_sim

    def test_edge_cases_and_special_values(self):
        """Test edge cases: empty matrices, identical values, exact thresholds."""
        # Empty matrix
        matrix = np.array([])
        result = adjust_filter_sim(matrix, 0.5, keep_top=1)
        assert result == 0.5

        # Identical values
        matrix = np.array([[0.5, 0.5], [0.5, 0.5]])
        result = adjust_filter_sim(matrix, 0.3, keep_top=2)
        assert result == 0.5

        # Values exactly at threshold
        matrix = np.array([[0.01, 0.02], [0.005, 0.03]])
        result = adjust_filter_sim(matrix, 0.5, keep_top=1)
        assert isinstance(result, (int | float))

    def test_sorting_behavior_current_implementation(self):
        """Test current sorting behavior (documents known behavior)."""
        # Values: [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        matrix = np.array([[0.1, 0.2, 0.3, 0.4, 0.5], [0.6, 0.7, 0.8, 0.9, 1.0]])
        result = adjust_filter_sim(matrix, 0.4, keep_top=5)

        # With current implementation (fixed sorting), should return sorted[5] = 0.5
        flat_vals = np.abs(matrix.flatten())
        filtered_vals = flat_vals[flat_vals > 0.01]
        expected = np.sort(filtered_vals)[::-1][5]  # 5th highest = 0.5
        assert result == expected


class TestIntegrationAndErrorHandling:
    """Integration tests and error handling."""

    def test_complete_pipeline_integration(self):
        """Test complete pipeline from main through dm_to_sim to adjust_filter_sim."""
        mock_net = TestFixtures.create_mock_network()
        # Adjust for smaller network (2x2)
        mock_net.dat["nodes"]["row"] = ["r1", "r2"]
        inst_dm = {"row": np.array([0.3])}  # Single distance for 2x2 matrix

        with patch("celldega.clust_old.clustering.calc_clust.cluster_row_and_col") as mock_cluster:
            result = main(mock_net, inst_dm, ["row"], 0.1)
            assert "row" in result
            assert mock_cluster.called
            assert result["row"] is not mock_net

    def test_filtering_integration_and_performance(self):
        """Test integration between dm_to_sim and adjust_filter_sim, plus performance."""
        # Integration test: filtering should trigger adjust_filter_sim
        dist_matrix = np.array([[0, 0.1, 0.8], [0.1, 0, 0.9], [0.8, 0.9, 0]])
        result = dm_to_sim(dist_matrix, filter_sim=0.3)
        assert np.any(result == 0)  # Some values should be filtered to 0
        assert np.any(result != 0)  # Some values should remain non-zero

        # Performance test with larger matrices
        size = 50
        large_matrix = np.random.rand(size, size) * 0.1
        np.fill_diagonal(large_matrix, 0)
        result = dm_to_sim(large_matrix, filter_sim=0.1)
        assert result.shape == (size, size)
        assert np.all(np.diag(result) == 1)

    def test_error_handling_and_invalid_inputs(self):
        """Test error handling for various invalid inputs."""
        # Invalid input types for dm_to_sim
        with pytest.raises((TypeError, AttributeError)):
            dm_to_sim("not_an_array")

        # Invalid input types for adjust_filter_sim
        with pytest.raises((TypeError, ValueError)):
            adjust_filter_sim("not_a_matrix", 0.5)

        # NaN and infinity handling (should handle gracefully or raise appropriate errors)
        matrix_with_nan = np.array([[0.1, np.nan], [np.inf, 0.2]])
        try:
            result = dm_to_sim(matrix_with_nan)
            # If it succeeds, result should contain NaN/inf appropriately
            assert np.isnan(result[0, 1]) or np.isinf(result[0, 1])
        except (ValueError, TypeError):
            # Acceptable if function doesn't handle NaN/inf
            pass

    def test_network_state_preservation(self):
        """Test that original network state is preserved during operations."""
        mock_net = TestFixtures.create_mock_network()
        original_dat = deepcopy(mock_net.dat)
        inst_dm = TestFixtures.create_sample_distance_matrices()

        with patch("celldega.clust_old.clustering.calc_clust.cluster_row_and_col"):
            main(mock_net, inst_dm, ["row"], 0.0)
            # Original network should be unchanged
            assert mock_net.dat["nodes"]["row"] == original_dat["nodes"]["row"]
            assert np.array_equal(mock_net.dat["mat"], original_dat["mat"])


class TestDocumentedBehavior:
    """Tests that document specific behaviors and any known issues."""

    def test_unused_parameter_documentation(self):
        """Document that sim_mat_views parameter is accepted but not used."""
        mock_net = TestFixtures.create_mock_network()
        inst_dm = {"row": np.array([])}

        with patch("celldega.clust_old.clustering.calc_clust.cluster_row_and_col"):
            # Parameter is accepted but has no effect on output
            result1 = main(mock_net, inst_dm, [], 0.0, None)
            result2 = main(mock_net, inst_dm, [], 0.0, ["custom_view"])
            assert result1 == result2  # Parameter has no effect

    def test_matrix_format_handling(self):
        """Test handling of different matrix formats and edge cases."""
        # Test with extreme values
        extreme_matrix = np.array([[1e-10, 1e10], [1e10, 1e-10]])
        try:
            result = dm_to_sim(extreme_matrix, filter_sim=0.5)
            assert isinstance(result, np.ndarray)
        except (OverflowError, ValueError):
            # Acceptable if system can't handle extreme values
            pass

        # Test mismatched dimensions (non-square)
        non_square = np.array([[1, 2, 3], [4, 5, 6]])
        result = dm_to_sim(non_square)
        assert result.shape == (2, 3)  # Should handle gracefully


# Parametrized tests for common patterns
class TestParametrizedCases:
    """Parametrized tests for common test patterns."""

    @pytest.mark.parametrize(
        "filter_value,expected_zeros",
        [
            (0.0, False),  # No filtering
            (0.5, True),  # Some filtering
            (1.0, True),  # Heavy filtering
        ],
    )
    def test_filtering_thresholds(self, filter_value, expected_zeros):
        """Test various filtering thresholds."""
        dist_matrix = np.array([[0, 0.3, 0.7], [0.3, 0, 0.8], [0.7, 0.8, 0]])
        result = dm_to_sim(dist_matrix, filter_sim=filter_value)

        if expected_zeros:
            assert np.any(result == 0)  # Some values should be filtered
        else:
            assert not np.any(result == 0)  # No values should be filtered

    @pytest.mark.parametrize(
        "axes",
        [
            ["row"],
            ["col"],
            ["row", "col"],
        ],
    )
    def test_main_with_different_axes(self, axes):
        """Test main function with different axis combinations."""
        mock_net = TestFixtures.create_mock_network()
        inst_dm = TestFixtures.create_sample_distance_matrices()

        with patch("celldega.clust_old.clustering.calc_clust.cluster_row_and_col"):
            result = main(mock_net, inst_dm, axes, 0.0)
            for axis in axes:
                assert axis in result

    @pytest.mark.parametrize("matrix_size", [1, 3, 10])
    def test_matrix_sizes(self, matrix_size):
        """Test with different matrix sizes."""
        # Create distance matrix of specified size
        dist_matrix = np.random.rand(matrix_size, matrix_size) * 0.5
        np.fill_diagonal(dist_matrix, 0)

        result = dm_to_sim(dist_matrix)
        assert result.shape == (matrix_size, matrix_size)
        assert np.all(np.diag(result) == 1)  # Diagonal should be 1 (distance 0 -> similarity 1)
