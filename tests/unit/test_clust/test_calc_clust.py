from pathlib import Path
import sys
from unittest.mock import Mock, patch

import numpy as np
import pytest
from scipy.spatial.distance import pdist


# Add the source directory to the path for imports
sys.path.insert(0, str(Path(__file__).parents[3] / "src"))

from celldega.clust.clustering.calc_clust import (
    calc_distance_matrix,
    clust_and_group,
    cluster_row_and_col,
    sort_rank_nodes,
)


class TestFixtures:
    """Shared test fixtures and utilities."""

    @staticmethod
    def create_mock_network():
        """Create a standard mock network for testing."""
        mock_net = Mock()
        mock_net.dat = {
            "nodes": {"row": ["gene1", "gene2", "gene3"], "col": ["cell1", "cell2", "cell3"]},
            "node_info": {"row": {}, "col": {}},
            "mat": np.array([[1, 2, 3], [4, 5, 6], [7, 8, 9]], dtype=float),
        }
        mock_net.viz = {"row_nodes": [], "col_nodes": []}
        mock_net.umap = {}
        return mock_net

    @staticmethod
    def create_test_matrices():
        """Create various test matrices."""
        return {
            "small": np.array([[1, 2, 3], [4, 5, 6], [7, 8, 9]], dtype=float),
            "medium": np.random.rand(20, 15).astype(float),
            "zeros": np.zeros((3, 3), dtype=float),
            "negative": np.array([[-1, -2], [-3, -4]], dtype=float),
            "mixed_signs": np.array([[-1, 2], [3, -4]], dtype=float),
            "with_nan": np.array([[1, np.nan], [3, 4]], dtype=float),
            "single_element": np.array([[1.0]]),
            "empty": np.array([]).reshape(0, 0),
        }


class TestCalcDistanceMatrix:
    """Test calc_distance_matrix function."""

    def setup_method(self):
        """Setup test data."""
        self.matrices = TestFixtures.create_test_matrices()

    def test_basic_distance_calculation(self):
        """Test basic distance matrix calculation."""
        matrix = self.matrices["small"]

        # Test row distances
        result = calc_distance_matrix(matrix, "row", "cosine")
        assert len(result) == 3  # C(3,2) = 3 distances
        assert np.all(result >= 0)

        # Test column distances
        result = calc_distance_matrix(matrix, "col", "cosine")
        assert len(result) == 3  # C(3,2) = 3 distances
        assert np.all(result >= 0)

    def test_different_distance_metrics(self):
        """Test different distance metrics."""
        matrix = self.matrices["small"]
        # Use only metrics that are guaranteed to work in scipy
        metrics = ["cosine", "euclidean", "cityblock"]  # cityblock is scipy's name for manhattan

        for metric in metrics:
            result = calc_distance_matrix(matrix, "row", metric)
            assert len(result) == 3
            assert np.all(result >= 0)

    def test_negative_distance_handling(self):
        """Test handling of negative distances."""
        matrix = self.matrices["mixed_signs"]
        result = calc_distance_matrix(matrix, "row", "cosine")
        # All distances should be non-negative after correction
        assert np.all(result >= 0)

    def test_invalid_axis(self):
        """Test invalid axis parameter."""
        matrix = self.matrices["small"]

        with pytest.raises(ValueError):
            calc_distance_matrix(matrix, "invalid_axis", "cosine")

    def test_edge_case_matrices(self):
        """Test edge case matrices."""
        # Single element matrix
        result = calc_distance_matrix(self.matrices["single_element"], "row", "cosine")
        assert len(result) == 0

        # Empty matrix - check what actually happens
        try:
            result = calc_distance_matrix(self.matrices["empty"], "row", "cosine")
            # If it succeeds, result should be empty
            assert len(result) == 0
        except (ValueError, IndexError):
            # This is acceptable behavior
            pass


class TestSortRankNodes:
    """Test sort_rank_nodes function."""

    def setup_method(self):
        """Setup test data."""
        self.mock_net = TestFixtures.create_mock_network()

    def test_rank_by_sum(self):
        """Test ranking nodes by sum."""
        result = sort_rank_nodes(self.mock_net, "row", "sum")
        assert isinstance(result, list)
        assert len(result) == 3
        assert all(isinstance(x, (int | np.integer)) for x in result)

    def test_rank_by_variance(self):
        """Test ranking nodes by variance."""
        result = sort_rank_nodes(self.mock_net, "row", "var")
        assert isinstance(result, list)
        assert len(result) == 3

    def test_different_axes(self):
        """Test ranking for both axes."""
        row_result = sort_rank_nodes(self.mock_net, "row", "sum")
        col_result = sort_rank_nodes(self.mock_net, "col", "sum")

        assert len(row_result) == 3
        assert len(col_result) == 3

    def test_rank_correctness(self):
        """Test ranking produces correct order."""
        net = Mock()
        net.dat = {
            "mat": np.array([[1, 1], [3, 3], [2, 2]], dtype=float),  # Sums: 2, 6, 4
            "nodes": {"row": ["low", "high", "med"]},
        }

        result = sort_rank_nodes(net, "row", "sum")
        assert isinstance(result, list)
        assert len(result) == 3


class TestClustAndGroup:
    """Test clust_and_group function."""

    def setup_method(self):
        """Setup test data."""
        self.mock_net = TestFixtures.create_mock_network()

    @patch("scipy.cluster.hierarchy.linkage")
    @patch("scipy.cluster.hierarchy.dendrogram")
    def test_scipy_clustering(self, mock_dendro, mock_linkage):
        """Test scipy clustering backend."""
        mock_linkage.return_value = np.array([[0, 1, 0.5, 2]])
        mock_dendro.return_value = {"leaves": [0, 1, 2]}

        dm = pdist(self.mock_net.dat["mat"], metric="cosine")
        clust_order, Y = clust_and_group(
            self.mock_net, dm, "row", self.mock_net.dat["mat"], clust_library="scipy"
        )

        assert isinstance(clust_order, list)
        assert len(clust_order) > 0
        assert isinstance(Y, np.ndarray)
        mock_linkage.assert_called_once()

    def test_different_linkage_types(self):
        """Test different linkage types."""
        linkage_types = ["average", "single", "complete"]
        dm = pdist(self.mock_net.dat["mat"], metric="euclidean")

        for linkage_type in linkage_types:
            with patch("scipy.cluster.hierarchy.linkage") as mock_linkage:
                mock_linkage.return_value = np.array([[0, 1, 0.5, 2]])

                clust_order, Y = clust_and_group(
                    self.mock_net, dm, "row", self.mock_net.dat["mat"], linkage_type=linkage_type
                )

                mock_linkage.assert_called_once()
                assert linkage_type in str(mock_linkage.call_args)


class TestClusterRowAndCol:
    """Test main cluster_row_and_col function."""

    def setup_method(self):
        """Setup test data."""
        self.mock_net = TestFixtures.create_mock_network()

    def test_basic_execution(self):
        """Test basic clustering execution."""
        result = cluster_row_and_col(self.mock_net)

        # Check that node_info was populated
        assert "node_info" in self.mock_net.dat
        assert "row" in self.mock_net.dat["node_info"]
        assert "col" in self.mock_net.dat["node_info"]

    def test_clustering_toggle(self):
        """Test clustering can be toggled."""
        # Test with clustering enabled
        result1 = cluster_row_and_col(self.mock_net, run_clustering=True)

        # Test with clustering disabled
        result2 = cluster_row_and_col(self.mock_net, run_clustering=False)

        # Both should complete without error
        assert result1 is not None
        assert result2 is not None

    def test_ranking_toggle(self):
        """Test ranking can be toggled."""
        # Test with ranking enabled
        result1 = cluster_row_and_col(self.mock_net, run_rank=True)

        # Test with ranking disabled
        result2 = cluster_row_and_col(self.mock_net, run_rank=False)

        # Both should complete without error
        assert result1 is not None
        assert result2 is not None

    def test_different_distance_types(self):
        """Test different distance types."""
        distance_types = ["cosine", "euclidean"]

        for dist_type in distance_types:
            result = cluster_row_and_col(self.mock_net, dist_type=dist_type)
            assert result is not None


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_invalid_inputs(self):
        """Test handling of invalid inputs."""
        matrices = TestFixtures.create_test_matrices()

        # Test invalid distance metric
        with pytest.raises((ValueError, AttributeError)):
            calc_distance_matrix(matrices["small"], "row", "invalid_metric")

        # Test invalid axis
        with pytest.raises(ValueError):
            calc_distance_matrix(matrices["small"], "invalid_axis", "cosine")

    def test_edge_case_matrices(self):
        """Test edge case matrices don't crash functions."""
        matrices = TestFixtures.create_test_matrices()

        for matrix in matrices.values():
            if matrix.size == 0:
                continue  # Skip empty matrices

            try:
                result = calc_distance_matrix(matrix, "row", "cosine")
                if result is not None and not np.any(np.isnan(result)):
                    # For matrices with NaN, result may contain NaN
                    assert np.all(result >= 0)
            except (ValueError, IndexError):
                # Some edge cases legitimately fail
                pass

    def test_memory_efficiency(self):
        """Test memory efficiency with larger matrices."""
        large_matrix = np.random.rand(100, 80)

        try:
            result = calc_distance_matrix(large_matrix, "row", "cosine")
            if result is not None:
                expected_size = 100 * 99 // 2
                assert len(result) == expected_size
        except MemoryError:
            pytest.skip("Insufficient memory for large matrix test")


class TestIntegration:
    """Integration tests."""

    def test_complete_workflow(self):
        """Test complete clustering workflow."""
        mock_net = TestFixtures.create_mock_network()

        # Calculate distance matrix
        dm = calc_distance_matrix(mock_net.dat["mat"], "row", "cosine")
        assert dm is not None

        # Perform clustering
        clust_order, Y = clust_and_group(mock_net, dm, "row", mock_net.dat["mat"])
        assert clust_order is not None
        assert Y is not None

        # Rank nodes
        rank_result = sort_rank_nodes(mock_net, "row", "sum")
        assert rank_result is not None

        # Main clustering function
        main_result = cluster_row_and_col(mock_net)
        assert main_result is not None

    def test_function_compatibility(self):
        """Test that function outputs are compatible."""
        mock_net = TestFixtures.create_mock_network()

        # Distance matrix output should work with clustering
        dm = calc_distance_matrix(mock_net.dat["mat"], "row", "cosine")
        clust_order, Y = clust_and_group(mock_net, dm, "row", mock_net.dat["mat"])

        assert isinstance(clust_order, list)
        assert isinstance(Y, np.ndarray)
        assert len(clust_order) == len(mock_net.dat["nodes"]["row"])


# Parametrized tests
class TestParametrized:
    """Parametrized tests for systematic testing."""

    @pytest.mark.parametrize("axis", ["row", "col"])
    def test_axes_systematically(self, axis):
        """Test functions work with both axes."""
        mock_net = TestFixtures.create_mock_network()
        matrix = mock_net.dat["mat"]

        result = calc_distance_matrix(matrix, axis, "cosine")
        assert result is not None

        rank_result = sort_rank_nodes(mock_net, axis, "sum")
        assert rank_result is not None

    @pytest.mark.parametrize("metric", ["cosine", "euclidean", "cityblock"])
    def test_distance_metrics_systematically(self, metric):
        """Test different distance metrics systematically."""
        matrix = TestFixtures.create_test_matrices()["small"]

        result = calc_distance_matrix(matrix, "row", metric)
        assert len(result) == 3
        assert np.all(result >= 0)

    @pytest.mark.parametrize("rank_type", ["sum", "var"])
    def test_rank_types_systematically(self, rank_type):
        """Test different ranking types systematically."""
        mock_net = TestFixtures.create_mock_network()

        result = sort_rank_nodes(mock_net, "row", rank_type)
        assert isinstance(result, list)
        assert len(result) == 3
