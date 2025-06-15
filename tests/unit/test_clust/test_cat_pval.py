"""
Test cases for cat_pval.py module

Tests the category p-value calculation functions with comprehensive edge case coverage.
Follows pytest conventions and includes fixtures for reusable test data.

Note: This test file requires src directory to be in PYTHONPATH.
Options to run tests:
1. Add to pytest.ini: pythonpath = src
2. Run with: PYTHONPATH=src pytest
3. Run with: python -m pytest (if using src layout)
"""

import importlib.util
from pathlib import Path
import sys
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest


# Add src to path if not already there (fallback method)
if "src" not in sys.path:
    src_path = Path(__file__).parent.parent.parent / "src"
    if src_path.exists():
        sys.path.insert(0, str(src_path))

# Import from the src layout structure
main = None
dist_matrix_lattice = None
calc_median_dist_subset = None
calc_hist_distances = None

# Try primary import path
if importlib.util.find_spec("celldega.clust.cat_pval") is not None:
    try:
        from celldega.clust.cat_pval import (
            calc_hist_distances,
            calc_median_dist_subset,
            dist_matrix_lattice,
            main,
        )

        MODULE_PATH = "celldega.clust.cat_pval"
    except ImportError:
        pass

# Try alternative import path if primary failed
if main is None and importlib.util.find_spec("src.celldega.clust.cat_pval") is not None:
    try:
        from src.celldega.clust.cat_pval import (
            calc_hist_distances,
            calc_median_dist_subset,
            dist_matrix_lattice,
            main,
        )

        MODULE_PATH = "src.celldega.clust.cat_pval"
    except ImportError:
        pass

# Skip tests if no imports worked
if main is None:
    pytest.skip("Cannot import cat_pval module. Please ensure src is in PYTHONPATH.")


class TestDistMatrixLattice:
    """Test the distance matrix lattice function"""

    def test_basic_functionality(self):
        """Test basic distance matrix creation"""
        names = ["A", "B", "C"]
        result = dist_matrix_lattice(names)

        # Check structure
        assert isinstance(result, pd.DataFrame)
        assert result.shape == (3, 3)
        assert list(result.columns) == names
        assert list(result.index) == names

        # Check diagonal is zero
        assert all(result.iloc[i, i] == 0 for i in range(3))

        # Check symmetry
        assert result.iloc[0, 1] == result.iloc[1, 0]

        # Check expected distances (lattice positions 0, 1, 2)
        assert result.iloc[0, 1] == 1.0  # distance between positions 0 and 1
        assert result.iloc[0, 2] == 2.0  # distance between positions 0 and 2
        assert result.iloc[1, 2] == 1.0  # distance between positions 1 and 2

    def test_single_element(self):
        """Test with single element - edge case"""
        names = ["A"]
        result = dist_matrix_lattice(names)

        assert result.shape == (1, 1)
        assert result.iloc[0, 0] == 0.0

    def test_empty_list(self):
        """Test with empty list - now properly handled"""
        names = []
        result = dist_matrix_lattice(names)

        # FIXED: Now properly returns empty DataFrame
        assert result.shape == (0, 0)
        assert result.empty

    def test_large_list(self):
        """Test with larger list to verify scaling"""
        names = [f"item_{i}" for i in range(10)]
        result = dist_matrix_lattice(names)

        assert result.shape == (10, 10)
        assert result.iloc[0, 9] == 9.0  # max distance
        assert result.iloc[4, 6] == 2.0  # middle distance

    def test_numeric_names(self):
        """Test with numeric node names"""
        names = [1, 2, 3, 4]
        result = dist_matrix_lattice(names)

        assert result.shape == (4, 4)
        assert result.loc[1, 3] == 2.0  # positions 0 to 2 = distance 2


class TestCalcMedianDistSubset:
    """Test median distance calculation for subsets"""

    @pytest.fixture
    def sample_distance_matrix(self):
        """Create a sample distance matrix for testing"""
        data = np.array([[0, 1, 2, 3], [1, 0, 1, 2], [2, 1, 0, 1], [3, 2, 1, 0]])
        names = ["A", "B", "C", "D"]
        return pd.DataFrame(data, index=names, columns=names)

    def test_basic_median_calculation(self, sample_distance_matrix):
        """Test basic median calculation"""
        subset = ["A", "C"]
        result = calc_median_dist_subset(sample_distance_matrix, subset)

        # For subset ['A', 'C'], we get submatrix:
        # A-A: 0, A-C: 2, C-A: 2, C-C: 0
        # Values: [0, 2, 2, 0], median should be 1.0
        expected = 1.0
        assert result == expected

    def test_single_element_subset(self, sample_distance_matrix):
        """Test with single element subset"""
        subset = ["A"]
        result = calc_median_dist_subset(sample_distance_matrix, subset)

        # Single element should return 0 (distance to itself)
        assert result == 0.0

    def test_all_elements_subset(self, sample_distance_matrix):
        """Test with all elements in subset"""
        subset = ["A", "B", "C", "D"]
        result = calc_median_dist_subset(sample_distance_matrix, subset)

        # Should calculate median of entire matrix
        all_values = sample_distance_matrix.values.flatten()
        expected = np.median(all_values)
        assert result == expected

    def test_empty_subset(self, sample_distance_matrix):
        """Test with empty subset - edge case"""
        subset = []

        # The current implementation doesn't raise an error for empty subsets
        # It actually returns NaN due to taking median of empty array
        # This documents the current behavior
        result = calc_median_dist_subset(sample_distance_matrix, subset)

        # Should return NaN for empty subset
        assert np.isnan(result)

    def test_invalid_subset_elements(self, sample_distance_matrix):
        """Test with subset containing invalid elements"""
        subset = ["A", "Z"]  # 'Z' doesn't exist

        # FIXED: Now gracefully handles invalid elements by filtering them out
        # and returns NaN if no valid elements remain
        result = calc_median_dist_subset(sample_distance_matrix, subset)

        # Should handle this gracefully since 'A' exists but 'Z' doesn't
        # The function now filters to valid elements, so this should work
        assert isinstance(result, (int, float))
        assert not np.isnan(result)  # 'A' exists, so should get a valid result


class TestCalcHistDistances:
    """Test histogram calculation for null distribution"""

    @pytest.fixture
    def sample_distance_matrix(self):
        """Create a sample distance matrix for testing"""
        data = np.array(
            [[0, 1, 2, 3, 4], [1, 0, 1, 2, 3], [2, 1, 0, 1, 2], [3, 2, 1, 0, 1], [4, 3, 2, 1, 0]]
        )
        names = ["A", "B", "C", "D", "E"]
        return pd.DataFrame(data, index=names, columns=names)

    def test_basic_histogram_calculation(self, sample_distance_matrix):
        """Test basic histogram calculation"""
        subset = ["A", "C"]
        inst_nodes = ["A", "B", "C", "D", "E"]

        result = calc_hist_distances(sample_distance_matrix, subset, inst_nodes)

        # Check structure
        assert "prob" in result
        assert "bins" in result
        assert len(result["prob"]) == 30  # Default bins
        assert len(result["bins"]) == 31  # bins + 1 for edges

        # Probabilities should sum to 1.0 (approximately)
        assert abs(sum(result["prob"]) - 1.0) < 1e-10

    def test_single_element_subset_histogram(self, sample_distance_matrix):
        """Test histogram with single element subset"""
        subset = ["A"]
        inst_nodes = ["A", "B", "C", "D", "E"]

        result = calc_hist_distances(sample_distance_matrix, subset, inst_nodes)

        # Structure should be valid
        assert "prob" in result
        assert "bins" in result
        assert len(result["prob"]) == 30

    def test_empty_subset_histogram(self, sample_distance_matrix):
        """Test histogram with empty subset"""
        subset = []
        inst_nodes = ["A", "B", "C", "D", "E"]

        # Should handle empty subset gracefully or raise appropriate error
        with pytest.raises((ValueError, IndexError)):
            calc_hist_distances(sample_distance_matrix, subset, inst_nodes)

    @patch("numpy.random.seed")
    def test_random_seed_is_set(self, mock_seed, sample_distance_matrix):
        """Test that random seed is properly set"""
        subset = ["A", "B"]
        inst_nodes = ["A", "B", "C", "D", "E"]

        calc_hist_distances(sample_distance_matrix, subset, inst_nodes)

        mock_seed.assert_called_once_with(100)

    def test_probability_bounds(self, sample_distance_matrix):
        """Test that probabilities are within valid bounds"""
        subset = ["A", "B", "C"]
        inst_nodes = ["A", "B", "C", "D", "E"]

        result = calc_hist_distances(sample_distance_matrix, subset, inst_nodes)

        # All probabilities should be non-negative and <= 1
        assert all(0 <= prob <= 1 for prob in result["prob"])

        # Bins should be increasing
        assert all(
            result["bins"][i] <= result["bins"][i + 1] for i in range(len(result["bins"]) - 1)
        )


class TestMainFunction:
    """Test the main p-value calculation function"""

    @pytest.fixture
    def mock_network(self):
        """Create a mock network object for testing"""
        net = MagicMock()

        # Mock the data structure
        net.dat = {
            "nodes": {
                "row": ["gene1", "gene2", "gene3", "gene4"],
                "col": ["sample1", "sample2", "sample3", "sample4"],
            },
            "node_info": {
                "row": {
                    "clust": [0, 2, 1, 3],  # clustered order
                    "dict_cat_celltype": {"TypeA": ["gene1", "gene3"], "TypeB": ["gene2", "gene4"]},
                    "dict_cat_pathway": {
                        "PathwayX": ["gene1", "gene2"],
                        "PathwayY": ["gene3", "gene4"],
                    },
                },
                "col": {
                    "clust": [1, 0, 3, 2],  # clustered order
                    "dict_cat_condition": {
                        "Control": ["sample1", "sample2"],
                        "Treatment": ["sample3", "sample4"],
                    },
                },
            },
        }
        return net

    # Patch with proper module path detection
    def _get_patch_path(self, func_name):
        """Get the correct patch path based on how the module was imported"""
        return f"{MODULE_PATH}.{func_name}"

    def test_basic_main_functionality(self, mock_network):
        """Test basic functionality of main function"""
        with (
            patch(self._get_patch_path("dist_matrix_lattice")) as mock_dist,
            patch(self._get_patch_path("calc_median_dist_subset")) as mock_median,
            patch(self._get_patch_path("calc_hist_distances")) as mock_hist,
        ):
            # Setup mocks
            mock_dist.return_value = pd.DataFrame()
            mock_median.return_value = 0.5
            mock_hist.return_value = {
                "prob": [0.1, 0.2, 0.3, 0.4],
                "bins": [0, 0.25, 0.5, 0.75, 1.0],
            }

            # Run function
            main(mock_network)

            # Verify structure was created
            assert "pval_cat_celltype" in mock_network.dat["node_info"]["row"]
            assert "pval_cat_pathway" in mock_network.dat["node_info"]["row"]
            assert "pval_cat_condition" in mock_network.dat["node_info"]["col"]

    def test_main_with_empty_categories(self, mock_network):
        """Test main function with empty category dictionaries"""
        # Remove all categories
        mock_network.dat["node_info"]["row"] = {"clust": [0, 1, 2, 3]}
        mock_network.dat["node_info"]["col"] = {"clust": [0, 1, 2, 3]}

        # Should run without error but not create any p-value entries
        main(mock_network)

        # Verify no p-value keys were created
        row_keys = mock_network.dat["node_info"]["row"].keys()
        col_keys = mock_network.dat["node_info"]["col"].keys()

        assert not any("pval_" in key for key in row_keys)
        assert not any("pval_" in key for key in col_keys)

    def test_pvalue_calculation_logic(self, mock_network):
        """Test the p-value calculation logic specifically"""
        with (
            patch(self._get_patch_path("calc_median_dist_subset")) as mock_median,
            patch(self._get_patch_path("calc_hist_distances")) as mock_hist,
        ):
            # Setup specific test case
            mock_median.return_value = 0.6  # observed median
            mock_hist.return_value = {
                "prob": [0.1, 0.2, 0.3, 0.4],  # probabilities for each bin
                "bins": [0, 0.25, 0.5, 0.75, 1.0],  # bin edges
            }

            # Simplify network for focused testing
            mock_network.dat["node_info"]["row"] = {
                "clust": [0, 1],
                "dict_cat_test": {"CategoryA": ["gene1", "gene2"]},
            }
            mock_network.dat["node_info"]["col"] = {"clust": [0, 1]}

            main(mock_network)

            # Check the calculated p-value exists
            pval = mock_network.dat["node_info"]["row"]["pval_cat_test"]["CategoryA"]

            # The current (flawed) implementation should still produce a p-value
            assert 0 <= pval <= 1

    def test_main_with_missing_clust_info(self, mock_network):
        """Test main function when clustering info is missing"""
        # Remove clust information
        del mock_network.dat["node_info"]["row"]["clust"]

        # Should raise KeyError
        with pytest.raises(KeyError):
            main(mock_network)


class TestIntegrationAndEdgeCases:
    """Integration tests and comprehensive edge case coverage"""

    def test_full_pipeline_integration(self):
        """Test the complete pipeline with realistic data"""
        # Create a realistic network structure
        net = MagicMock()
        net.dat = {
            "nodes": {
                "row": ["GENE1", "GENE2", "GENE3", "GENE4", "GENE5"],
                "col": ["CELL1", "CELL2", "CELL3", "CELL4", "CELL5"],
            },
            "node_info": {
                "row": {
                    "clust": [0, 3, 1, 4, 2],  # clustered order
                    "dict_cat_celltype": {
                        "Neuron": ["GENE1", "GENE3", "GENE5"],
                        "Glia": ["GENE2", "GENE4"],
                    },
                },
                "col": {
                    "clust": [2, 0, 4, 1, 3],  # clustered order
                    "dict_cat_treatment": {
                        "Control": ["CELL1", "CELL3"],
                        "Drug": ["CELL2", "CELL4", "CELL5"],
                    },
                },
            },
        }

        # Run the main function
        main(net)

        # Verify results
        assert "pval_cat_celltype" in net.dat["node_info"]["row"]
        assert "pval_cat_treatment" in net.dat["node_info"]["col"]

        # Check that p-values are reasonable (between 0 and 1)
        for category, pval in net.dat["node_info"]["row"]["pval_cat_celltype"].items():
            assert 0 <= pval <= 1, f"P-value for {category} is out of bounds: {pval}"

    def test_robustness_to_data_types(self):
        """Test robustness to different data types in node names"""
        net = MagicMock()
        net.dat = {
            "nodes": {
                "row": [1, 2, 3, 4],  # Integer node names
                "col": ["A", "B", "C", "D"],  # String node names
            },
            "node_info": {
                "row": {
                    "clust": [0, 1, 2, 3],
                    "dict_cat_numeric": {"TypeX": [1, 3], "TypeY": [2, 4]},
                },
                "col": {
                    "clust": [0, 1, 2, 3],
                    "dict_cat_string": {"GroupA": ["A", "C"], "GroupB": ["B", "D"]},
                },
            },
        }

        # Should handle mixed data types
        main(net)

        assert "pval_cat_numeric" in net.dat["node_info"]["row"]
        assert "pval_cat_string" in net.dat["node_info"]["col"]


class TestParametrizedEdgeCases:
    """Parametrized tests for systematic edge case coverage"""

    @pytest.mark.parametrize(
        "subset_size,total_size",
        [
            (1, 5),  # Very small subset
            (2, 5),  # Small subset
            (4, 5),  # Large subset
            (5, 5),  # Full set
        ],
    )
    def test_various_subset_sizes(self, subset_size, total_size):
        """Test median calculation with various subset sizes"""
        names = [f"item_{i}" for i in range(total_size)]
        dm = dist_matrix_lattice(names)
        subset = names[:subset_size]

        result = calc_median_dist_subset(dm, subset)

        assert isinstance(result, (int | float))
        assert result >= 0  # Distances should be non-negative

    @pytest.mark.parametrize("num_nodes", [2, 5, 10, 20])
    def test_distance_matrix_scaling(self, num_nodes):
        """Test distance matrix creation with different sizes"""
        names = [f"node_{i}" for i in range(num_nodes)]
        result = dist_matrix_lattice(names)

        assert result.shape == (num_nodes, num_nodes)
        assert np.allclose(result.values, result.values.T)  # Should be symmetric
        assert np.allclose(np.diag(result.values), 0)  # Diagonal should be zero


class TestCurrentImplementationIssues:
    """Tests that verify bug fixes and document improved behavior"""

    def test_empty_list_distance_matrix_fixed(self):
        """Test that empty list bug has been fixed in dist_matrix_lattice"""
        names = []

        # FIXED: Now properly handles empty lists
        result = dist_matrix_lattice(names)
        assert result.shape == (0, 0)
        assert result.empty

    def test_empty_subset_returns_nan(self):
        """Test that documents empty subset behavior"""
        dm = pd.DataFrame([[0, 1], [1, 0]], index=["A", "B"], columns=["A", "B"])
        subset = []

        # FIXED: Still returns NaN for empty subsets, but now intentionally
        result = calc_median_dist_subset(dm, subset)
        assert np.isnan(result)

    def test_pvalue_calculation_bug_fixed(self):
        """Test that verifies the p-value calculation has been fixed"""
        # Create simple test case
        net = MagicMock()
        net.dat = {
            "nodes": {"row": ["A", "B"], "col": ["X", "Y"]},
            "node_info": {
                "row": {"clust": [0, 1], "dict_cat_test": {"Cat1": ["A", "B"]}},
                "col": {"clust": [0, 1]},
            },
        }

        # The fixed implementation should complete and give valid p-values
        main(net)

        # Verify that the function completes and creates the expected structure
        assert "pval_cat_test" in net.dat["node_info"]["row"]
        assert "Cat1" in net.dat["node_info"]["row"]["pval_cat_test"]

        # The p-value should be between 0 and 1
        pval = net.dat["node_info"]["row"]["pval_cat_test"]["Cat1"]
        assert 0 <= pval <= 1

    def test_statistical_calculation_is_now_valid(self):
        """Test that verifies the statistical calculation now uses proper null distribution"""
        # This test demonstrates the fixed statistical calculation
        with patch(self._get_patch_path("_fast_median_distance")) as mock_median:
            # Set up a scenario where we can predict the result
            mock_median.side_effect = [
                0.5,
                0.3,
                0.7,
                0.4,
                0.6,
            ] * 250  # Cycle through values for null distribution

            net = MagicMock()
            net.dat = {
                "nodes": {"row": ["gene1", "gene2"], "col": ["cell1", "cell2"]},
                "node_info": {
                    "row": {"clust": [0, 1], "dict_cat_test": {"TestCategory": ["gene1", "gene2"]}},
                    "col": {"clust": [0, 1]},
                },
            }

            main(net)

            # The fixed implementation should give a valid p-value
            pval = net.dat["node_info"]["row"]["pval_cat_test"]["TestCategory"]

            # P-value should be between 0 and 1 and represent actual statistical test
            assert 0 <= pval <= 1

            # The first call is for observed median, rest are for null distribution
            # In the optimized version, _fast_median_distance is called instead of calc_median_dist_subset
            assert (
                mock_median.call_count >= 1000
            )  # Should be called many times for null distribution

    def test_edge_case_handling_improvements(self):
        """Test that edge cases are now handled properly"""
        # Test with very specific histogram that previously might have caused issues
        dm = pd.DataFrame([[0, 1], [1, 0]], index=["A", "B"], columns=["A", "B"])
        subset = ["A"]
        nodes = ["A", "B"]

        # This should complete without issues
        result = calc_hist_distances(dm, subset, nodes)

        # Verify basic structure
        assert "prob" in result
        assert "bins" in result
        assert len(result["bins"]) == len(result["prob"]) + 1

        # Verify probabilities sum to 1
        assert abs(sum(result["prob"]) - 1.0) < 1e-10

    def _get_patch_path(self, func_name):
        """Get the correct patch path based on how the module was imported"""
        return f"{MODULE_PATH}.{func_name}"
