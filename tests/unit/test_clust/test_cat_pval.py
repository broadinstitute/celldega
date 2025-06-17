# =============================================================================
# COMPREHENSIVE TEST SUITE FOR CAT_PVAL.PY MODULE
# =============================================================================
"""
Comprehensive test suite for cat_pval.py module.

Tests the category p-value calculation functions with comprehensive edge case coverage.
Follows pytest conventions and includes fixtures for reusable test data with improved
robustness, consistency, and maintainability.

Note: This test file requires src directory to be in PYTHONPATH.
Options to run tests:
1. Add to pytest.ini: pythonpath = src
2. Run with: PYTHONPATH=src pytest
3. Run with: python -m pytest (if using src layout)
"""

# =============================================================================
# IMPORTS
# =============================================================================

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
import sys
from typing import Any
from unittest.mock import MagicMock, Mock, patch

import numpy as np
import pandas as pd
import pytest


# =============================================================================
# MODULE-LEVEL CONSTANTS
# =============================================================================

# Path and module constants
SRC_PATH = Path(__file__).parents[3] / "src"
RANDOM_SEED = 100
DEFAULT_HISTOGRAM_BINS = 30
HISTOGRAM_ITERATIONS = 1000
PROBABILITY_TOLERANCE = 1e-10

# Test data constants
BASIC_NODE_NAMES = ["A", "B", "C"]
EXTENDED_NODE_NAMES = ["A", "B", "C", "D"]
LARGE_NODE_NAMES = [f"item_{i}" for i in range(10)]
NUMERIC_NODE_NAMES = [1, 2, 3, 4]
GENE_NODE_NAMES = ["gene1", "gene2", "gene3", "gene4"]
SAMPLE_NODE_NAMES = ["sample1", "sample2", "sample3", "sample4"]
CELL_NODE_NAMES = ["CELL1", "CELL2", "CELL3", "CELL4", "CELL5"]
GENE_NAMES_EXTENDED = ["GENE1", "GENE2", "GENE3", "GENE4", "GENE5"]

# Distance matrix test values
BASIC_DISTANCE_MATRIX = np.array([[0, 1, 2, 3], [1, 0, 1, 2], [2, 1, 0, 1], [3, 2, 1, 0]])

EXTENDED_DISTANCE_MATRIX = np.array(
    [[0, 1, 2, 3, 4], [1, 0, 1, 2, 3], [2, 1, 0, 1, 2], [3, 2, 1, 0, 1], [4, 3, 2, 1, 0]]
)

# Category constants
DICT_CAT_PREFIX = "dict_cat_"
PVAL_CAT_PREFIX = "pval_cat_"
CELLTYPE_CATEGORY = "celltype"
PATHWAY_CATEGORY = "pathway"
CONDITION_CATEGORY = "condition"
TREATMENT_CATEGORY = "treatment"

# Test group constants
TYPE_A_GROUP = "TypeA"
TYPE_B_GROUP = "TypeB"
PATHWAY_X_GROUP = "PathwayX"
PATHWAY_Y_GROUP = "PathwayY"
CONTROL_GROUP = "Control"
TREATMENT_GROUP = "Treatment"
DRUG_GROUP = "Drug"
NEURON_GROUP = "Neuron"
GLIA_GROUP = "Glia"

# Network structure constants
ROW_AXIS = "row"
COL_AXIS = "col"
NODES_KEY = "nodes"
NODE_INFO_KEY = "node_info"
CLUST_KEY = "clust"

# Statistical constants
ZERO_PROBABILITY = 0.0
UNIT_PROBABILITY = 1.0
MEDIAN_TEST_VALUE = 0.5

# Performance test constants
SCALING_TEST_SIZES = [2, 5, 10, 20]
MINIMAL_MATRIX_SIZE = 2

# =============================================================================
# MODULE IMPORT AND SETUP
# =============================================================================

# Import setup
sys.path.insert(0, str(SRC_PATH))

try:
    from celldega.clust.categories import cat_pval

    # Import the functions we need for testing
    calc_hist_distances = cat_pval.calc_hist_distances
    calc_median_dist_subset = cat_pval.calc_median_dist_subset
    dist_matrix_lattice = cat_pval.dist_matrix_lattice
    main = cat_pval.main

except ImportError:
    pytest.skip(
        "Cannot import cat_pval module. Please ensure src is in PYTHONPATH.",
        allow_module_level=True,
    )

# =============================================================================
# HELPER CLASSES AND UTILITIES
# =============================================================================


class TestCatPvalHelpers:
    """Helper methods and utilities for cat_pval testing."""

    @staticmethod
    def create_distance_matrix(data: np.ndarray, names: list[Any]) -> pd.DataFrame:
        """Create a standardized distance matrix for testing.

        Args:
            data: 2D numpy array with distance values
            names: List of node names for index and columns

        Returns:
            DataFrame with distance matrix structure
        """
        return pd.DataFrame(data, index=names, columns=names)

    @staticmethod
    def create_mock_network(
        row_nodes: list[str],
        col_nodes: list[str],
        row_clust: list[int],
        col_clust: list[int],
        row_categories: dict[str, dict[str, list[str]]] | None = None,
        col_categories: dict[str, dict[str, list[str]]] | None = None,
    ) -> MagicMock:
        """Create a standardized mock network object for testing.

        Args:
            row_nodes: List of row node names
            col_nodes: List of column node names
            row_clust: List of row clustering assignments
            col_clust: List of column clustering assignments
            row_categories: Optional row category dictionaries
            col_categories: Optional column category dictionaries

        Returns:
            Mock network object with specified structure
        """
        net = MagicMock()

        row_node_info = {CLUST_KEY: row_clust}
        if row_categories:
            row_node_info.update(row_categories)

        col_node_info = {CLUST_KEY: col_clust}
        if col_categories:
            col_node_info.update(col_categories)

        net.dat = {
            NODES_KEY: {ROW_AXIS: row_nodes, COL_AXIS: col_nodes},
            NODE_INFO_KEY: {ROW_AXIS: row_node_info, COL_AXIS: col_node_info},
        }
        return net

    @staticmethod
    def assert_valid_probability(value: float, name: str = "probability") -> None:
        """Assert that a value is a valid probability (0 <= p <= 1).

        Args:
            value: The probability value to validate
            name: Descriptive name for error messages
        """
        assert ZERO_PROBABILITY <= value <= UNIT_PROBABILITY, (
            f"{name} {value} is not in valid range [0, 1]"
        )

    @staticmethod
    def assert_histogram_structure(
        result: dict[str, np.ndarray], expected_bins: int = DEFAULT_HISTOGRAM_BINS
    ) -> None:
        """Assert that a histogram result has the expected structure.

        Args:
            result: Dictionary containing histogram data
            expected_bins: Expected number of histogram bins
        """
        assert "prob" in result, "Histogram result missing 'prob' key"
        assert "bins" in result, "Histogram result missing 'bins' key"
        assert len(result["prob"]) == expected_bins, f"Expected {expected_bins} probability bins"
        assert len(result["bins"]) == expected_bins + 1, f"Expected {expected_bins + 1} bin edges"

        # Verify probabilities sum to 1.0
        prob_sum = sum(result["prob"])
        assert abs(prob_sum - UNIT_PROBABILITY) < PROBABILITY_TOLERANCE, (
            f"Probabilities sum to {prob_sum}, not 1.0"
        )

        # Verify all probabilities are valid
        for i, prob in enumerate(result["prob"]):
            TestCatPvalHelpers.assert_valid_probability(prob, f"probability bin {i}")

        # Verify bins are increasing
        bins = result["bins"]
        for i in range(len(bins) - 1):
            assert bins[i] <= bins[i + 1], (
                f"Bin edges not increasing at index {i}: {bins[i]} > {bins[i + 1]}"
            )

    @staticmethod
    def create_category_dict(
        category_name: str, groups: dict[str, list[str]]
    ) -> dict[str, dict[str, list[str]]]:
        """Create a category dictionary with standardized naming.

        Args:
            category_name: Name of the category
            groups: Dictionary mapping group names to node lists

        Returns:
            Formatted category dictionary
        """
        return {f"{DICT_CAT_PREFIX}{category_name}": groups}

    @staticmethod
    @contextmanager
    def patch_cat_pval_functions() -> Generator[tuple[Mock, Mock, Mock], None, None]:
        """Context manager for patching cat_pval functions during testing."""
        with (
            patch.object(cat_pval, "dist_matrix_lattice", return_value=pd.DataFrame()) as mock_dist,
            patch.object(
                cat_pval, "calc_median_dist_subset", return_value=MEDIAN_TEST_VALUE
            ) as mock_median,
            patch.object(
                cat_pval,
                "calc_hist_distances",
                return_value={"prob": [0.1, 0.2, 0.3, 0.4], "bins": [0, 0.25, 0.5, 0.75, 1.0]},
            ) as mock_hist,
        ):
            yield mock_dist, mock_median, mock_hist

    @staticmethod
    def verify_pvalue_categories_created(
        network: MagicMock, expected_categories: dict[str, list[str]]
    ) -> None:
        """Verify that expected p-value categories were created in the network.

        Args:
            network: Mock network object to check
            expected_categories: Dictionary mapping axis to list of expected category names
        """
        for axis, categories in expected_categories.items():
            node_info = network.dat[NODE_INFO_KEY][axis]
            for category in categories:
                pval_key = f"{PVAL_CAT_PREFIX}{category}"
                assert pval_key in node_info, f"Missing p-value category: {pval_key}"

    @staticmethod
    def validate_all_pvalues_in_network(network: MagicMock) -> None:
        """Validate that all p-values in the network are within valid range.

        Args:
            network: Mock network object to validate
        """
        for axis in [ROW_AXIS, COL_AXIS]:
            node_info = network.dat[NODE_INFO_KEY][axis]
            for key, categories in node_info.items():
                if key.startswith(PVAL_CAT_PREFIX):
                    for category, pval in categories.items():
                        TestCatPvalHelpers.assert_valid_probability(pval, f"P-value for {category}")


# =============================================================================
# PYTEST FIXTURES
# =============================================================================


@pytest.fixture
def basic_distance_matrix() -> pd.DataFrame:
    """Create a basic 4x4 distance matrix for testing."""
    return TestCatPvalHelpers.create_distance_matrix(BASIC_DISTANCE_MATRIX, EXTENDED_NODE_NAMES)


@pytest.fixture
def extended_distance_matrix() -> pd.DataFrame:
    """Create an extended 5x5 distance matrix for testing."""
    return TestCatPvalHelpers.create_distance_matrix(
        EXTENDED_DISTANCE_MATRIX, ["A", "B", "C", "D", "E"]
    )


@pytest.fixture
def basic_mock_network() -> MagicMock:
    """Create a basic mock network for testing main function."""
    return TestCatPvalHelpers.create_mock_network(
        row_nodes=GENE_NODE_NAMES,
        col_nodes=SAMPLE_NODE_NAMES,
        row_clust=[0, 2, 1, 3],
        col_clust=[1, 0, 3, 2],
        row_categories={
            **TestCatPvalHelpers.create_category_dict(
                CELLTYPE_CATEGORY,
                {TYPE_A_GROUP: ["gene1", "gene3"], TYPE_B_GROUP: ["gene2", "gene4"]},
            ),
            **TestCatPvalHelpers.create_category_dict(
                PATHWAY_CATEGORY,
                {PATHWAY_X_GROUP: ["gene1", "gene2"], PATHWAY_Y_GROUP: ["gene3", "gene4"]},
            ),
        },
        col_categories=TestCatPvalHelpers.create_category_dict(
            CONDITION_CATEGORY,
            {CONTROL_GROUP: ["sample1", "sample2"], TREATMENT_GROUP: ["sample3", "sample4"]},
        ),
    )


@pytest.fixture
def minimal_mock_network() -> MagicMock:
    """Create a minimal mock network for edge case testing."""
    return TestCatPvalHelpers.create_mock_network(
        row_nodes=["gene1", "gene2"],
        col_nodes=["sample1", "sample2"],
        row_clust=[0, 1],
        col_clust=[0, 1],
    )


# =============================================================================
# TEST CLASSES - DIST_MATRIX_LATTICE FUNCTION
# =============================================================================


class TestDistMatrixLattice:
    """Test the distance matrix lattice function."""

    @pytest.mark.parametrize(
        "names,expected_shape",
        [
            (BASIC_NODE_NAMES, (3, 3)),
            (EXTENDED_NODE_NAMES, (4, 4)),
            (LARGE_NODE_NAMES, (10, 10)),
            (NUMERIC_NODE_NAMES, (4, 4)),
        ],
    )
    def test_distance_matrix_shapes(self, names: list[Any], expected_shape: tuple) -> None:
        """Test distance matrix creation with various input sizes and types."""
        result = dist_matrix_lattice(names)

        assert isinstance(result, pd.DataFrame)
        assert result.shape == expected_shape
        assert list(result.columns) == names
        assert list(result.index) == names

    def test_distance_matrix_properties(self) -> None:
        """Test mathematical properties of distance matrices."""
        result = dist_matrix_lattice(BASIC_NODE_NAMES)

        # Test diagonal is zero
        for i in range(len(BASIC_NODE_NAMES)):
            assert result.iloc[i, i] == ZERO_PROBABILITY, f"Diagonal element [{i}, {i}] should be 0"

        # Test symmetry
        for i in range(len(BASIC_NODE_NAMES)):
            for j in range(len(BASIC_NODE_NAMES)):
                assert result.iloc[i, j] == result.iloc[j, i], f"Matrix not symmetric at [{i}, {j}]"

    @pytest.mark.parametrize(
        "names,pos1,pos2,expected_distance",
        [
            (BASIC_NODE_NAMES, 0, 1, 1.0),
            (BASIC_NODE_NAMES, 0, 2, 2.0),
            (BASIC_NODE_NAMES, 1, 2, 1.0),
            (EXTENDED_NODE_NAMES, 0, 3, 3.0),
            (LARGE_NODE_NAMES, 0, 9, 9.0),
            (LARGE_NODE_NAMES, 4, 6, 2.0),
        ],
    )
    def test_specific_distances(
        self, names: list[Any], pos1: int, pos2: int, expected_distance: float
    ) -> None:
        """Test specific distance calculations."""
        result = dist_matrix_lattice(names)
        assert result.iloc[pos1, pos2] == expected_distance

    def test_edge_cases(self) -> None:
        """Test edge cases for distance matrix creation."""
        # Single element
        single_result = dist_matrix_lattice(["A"])
        assert single_result.shape == (1, 1)
        assert single_result.iloc[0, 0] == ZERO_PROBABILITY

        # Empty list
        empty_result = dist_matrix_lattice([])
        assert empty_result.shape == (0, 0)
        assert empty_result.empty


# =============================================================================
# TEST CLASSES - CALC_MEDIAN_DIST_SUBSET FUNCTION
# =============================================================================


class TestCalcMedianDistSubset:
    """Test median distance calculation for subsets."""

    @pytest.mark.parametrize(
        "subset,expected",
        [
            (["A", "C"], 1.0),  # Submatrix: [[0,2],[2,0]], median of [0,2,2,0] = 1.0
            (["A"], ZERO_PROBABILITY),  # Single element, distance to self
            (["A", "B", "C", "D"], None),  # All elements, calculate from matrix
        ],
    )
    def test_median_calculations(
        self, basic_distance_matrix: pd.DataFrame, subset: list[str], expected: float | None
    ) -> None:
        """Test median distance calculations with various subsets."""
        result = calc_median_dist_subset(basic_distance_matrix, subset)

        if expected is None:
            # For all elements, calculate expected median
            expected = np.median(basic_distance_matrix.values.flatten())

        assert result == expected

    def test_empty_subset(self, basic_distance_matrix: pd.DataFrame) -> None:
        """Test behavior with empty subset."""
        result = calc_median_dist_subset(basic_distance_matrix, [])
        assert np.isnan(result)

    def test_invalid_subset_elements(self, basic_distance_matrix: pd.DataFrame) -> None:
        """Test handling of invalid subset elements."""
        # Mix of valid and invalid elements
        result = calc_median_dist_subset(basic_distance_matrix, ["A", "Z"])
        assert isinstance(result, (int, float))
        assert not np.isnan(result)  # Should handle 'A' gracefully

    @pytest.mark.parametrize("subset_size,total_size", [(1, 5), (2, 5), (4, 5), (5, 5)])
    def test_various_subset_sizes(self, subset_size: int, total_size: int) -> None:
        """Test median calculation with systematically varied subset sizes."""
        names = [f"item_{i}" for i in range(total_size)]
        dm = dist_matrix_lattice(names)
        subset = names[:subset_size]

        result = calc_median_dist_subset(dm, subset)

        assert isinstance(result, (int, float))
        assert result >= ZERO_PROBABILITY  # Distances should be non-negative


# =============================================================================
# TEST CLASSES - CALC_HIST_DISTANCES FUNCTION
# =============================================================================


class TestCalcHistDistances:
    """Test histogram calculation for null distribution."""

    def test_basic_histogram_structure(self, extended_distance_matrix: pd.DataFrame) -> None:
        """Test basic histogram calculation structure."""
        subset = ["A", "C"]
        all_nodes = ["A", "B", "C", "D", "E"]

        result = calc_hist_distances(extended_distance_matrix, subset, all_nodes)
        TestCatPvalHelpers.assert_histogram_structure(result)

    @pytest.mark.parametrize(
        "subset",
        [
            ["A"],
            ["A", "B"],
            ["A", "B", "C"],
        ],
    )
    def test_histogram_with_various_subsets(
        self, extended_distance_matrix: pd.DataFrame, subset: list[str]
    ) -> None:
        """Test histogram calculation with different subset sizes."""
        all_nodes = ["A", "B", "C", "D", "E"]
        result = calc_hist_distances(extended_distance_matrix, subset, all_nodes)
        TestCatPvalHelpers.assert_histogram_structure(result)

    def test_empty_subset_raises_error(self, extended_distance_matrix: pd.DataFrame) -> None:
        """Test that empty subset raises appropriate error."""
        all_nodes = ["A", "B", "C", "D", "E"]

        with pytest.raises((ValueError, IndexError)):
            calc_hist_distances(extended_distance_matrix, [], all_nodes)

    @patch("numpy.random.seed")
    def test_random_seed_consistency(
        self, mock_seed: MagicMock, extended_distance_matrix: pd.DataFrame
    ) -> None:
        """Test that random seed is properly set for reproducibility."""
        subset = ["A", "B"]
        all_nodes = ["A", "B", "C", "D", "E"]

        calc_hist_distances(extended_distance_matrix, subset, all_nodes)
        mock_seed.assert_called_once_with(RANDOM_SEED)


# =============================================================================
# TEST CLASSES - MAIN FUNCTION
# =============================================================================


class TestMainFunction:
    """Test the main p-value calculation function."""

    def test_basic_main_functionality(self, basic_mock_network: MagicMock) -> None:
        """Test basic functionality of main function."""
        with TestCatPvalHelpers.patch_cat_pval_functions():
            main(basic_mock_network)

            # Verify expected p-value categories were created
            TestCatPvalHelpers.verify_pvalue_categories_created(
                basic_mock_network,
                {
                    ROW_AXIS: [CELLTYPE_CATEGORY, PATHWAY_CATEGORY],
                    COL_AXIS: [CONDITION_CATEGORY],
                },
            )

    def test_main_with_empty_categories(self, minimal_mock_network: MagicMock) -> None:
        """Test main function with no category dictionaries."""
        main(minimal_mock_network)

        # Verify no p-value keys were created
        for axis in [ROW_AXIS, COL_AXIS]:
            node_info = minimal_mock_network.dat[NODE_INFO_KEY][axis]
            pval_keys = [key for key in node_info if PVAL_CAT_PREFIX in key]
            assert len(pval_keys) == 0, f"Unexpected p-value keys found in {axis}: {pval_keys}"

    def test_main_missing_clustering_info(self, minimal_mock_network: MagicMock) -> None:
        """Test main function when clustering info is missing."""
        # Remove clustering info to trigger error
        del minimal_mock_network.dat[NODE_INFO_KEY][ROW_AXIS][CLUST_KEY]

        with pytest.raises(KeyError):
            main(minimal_mock_network)

    def test_pvalue_calculation_integration(self, basic_mock_network: MagicMock) -> None:
        """Test integration of p-value calculation."""
        main(basic_mock_network)

        # Verify p-values are within valid range
        TestCatPvalHelpers.validate_all_pvalues_in_network(basic_mock_network)


# =============================================================================
# TEST CLASSES - INTEGRATION AND EDGE CASES
# =============================================================================


class TestIntegrationAndEdgeCases:
    """Integration tests and comprehensive edge case coverage."""

    @pytest.mark.parametrize("num_nodes", SCALING_TEST_SIZES)
    def test_distance_matrix_scaling(self, num_nodes: int) -> None:
        """Test distance matrix creation with different sizes."""
        names = [f"node_{i}" for i in range(num_nodes)]
        result = dist_matrix_lattice(names)

        assert result.shape == (num_nodes, num_nodes)
        assert np.allclose(result.values, result.values.T)  # Symmetry
        assert np.allclose(np.diag(result.values), ZERO_PROBABILITY)  # Zero diagonal

    def test_full_pipeline_integration(self) -> None:
        """Test complete pipeline with realistic data."""
        net = TestCatPvalHelpers.create_mock_network(
            row_nodes=GENE_NAMES_EXTENDED,
            col_nodes=CELL_NODE_NAMES,
            row_clust=[0, 3, 1, 4, 2],
            col_clust=[2, 0, 4, 1, 3],
            row_categories=TestCatPvalHelpers.create_category_dict(
                CELLTYPE_CATEGORY,
                {NEURON_GROUP: ["GENE1", "GENE3", "GENE5"], GLIA_GROUP: ["GENE2", "GENE4"]},
            ),
            col_categories=TestCatPvalHelpers.create_category_dict(
                TREATMENT_CATEGORY,
                {
                    CONTROL_GROUP: ["CELL1", "CELL3"],
                    DRUG_GROUP: ["CELL2", "CELL4", "CELL5"],
                },
            ),
        )

        main(net)

        # Verify results structure and validity
        TestCatPvalHelpers.verify_pvalue_categories_created(
            net, {ROW_AXIS: [CELLTYPE_CATEGORY], COL_AXIS: [TREATMENT_CATEGORY]}
        )

        TestCatPvalHelpers.validate_all_pvalues_in_network(net)

    @pytest.mark.parametrize(
        "node_type",
        [
            ([1, 2, 3, 4], ["A", "B", "C", "D"]),  # Mixed integer/string
            (["x", "y", "z"], [1.0, 2.0, 3.0]),  # Mixed string/float
        ],
    )
    def test_robustness_to_data_types(self, node_type: tuple) -> None:
        """Test robustness to different data types in node names."""
        row_nodes, col_nodes = node_type

        net = TestCatPvalHelpers.create_mock_network(
            row_nodes=row_nodes,
            col_nodes=col_nodes,
            row_clust=list(range(len(row_nodes))),
            col_clust=list(range(len(col_nodes))),
            row_categories=TestCatPvalHelpers.create_category_dict(
                f"type_{type(row_nodes[0]).__name__}",
                {"Group1": row_nodes[:2], "Group2": row_nodes[2:]},
            ),
        )

        main(net)

        # Should handle mixed data types without error
        row_info = net.dat[NODE_INFO_KEY][ROW_AXIS]
        pval_keys = [k for k in row_info if k.startswith(PVAL_CAT_PREFIX)]
        assert len(pval_keys) == 1

    def test_large_category_groups(self) -> None:
        """Test handling of large category groups."""
        large_nodes = [f"node_{i}" for i in range(100)]
        net = TestCatPvalHelpers.create_mock_network(
            row_nodes=large_nodes,
            col_nodes=large_nodes[:50],
            row_clust=list(range(100)),
            col_clust=list(range(50)),
            row_categories=TestCatPvalHelpers.create_category_dict(
                "large_category",
                {"BigGroup1": large_nodes[:50], "BigGroup2": large_nodes[50:]},
            ),
        )

        # Should handle large groups without error
        main(net)

        TestCatPvalHelpers.verify_pvalue_categories_created(net, {ROW_AXIS: ["large_category"]})


# =============================================================================
# TEST CLASSES - STATISTICAL VALIDATION
# =============================================================================


class TestStatisticalValidation:
    """Tests for statistical validity and bug fixes."""

    def test_pvalue_calculation_statistical_validity(self) -> None:
        """Test that p-value calculation uses proper statistical methodology."""
        with patch.object(cat_pval, "_fast_median_distance") as mock_median:
            # Set up predictable mock values for statistical test
            mock_values = [MEDIAN_TEST_VALUE] + [0.3, 0.7, 0.4, 0.6, 0.2, 0.8, 0.1, 0.9, 0.5] * 112
            mock_median.side_effect = mock_values

            net = TestCatPvalHelpers.create_mock_network(
                row_nodes=["gene1", "gene2"],
                col_nodes=["cell1", "cell2"],
                row_clust=[0, 1],
                col_clust=[0, 1],
                row_categories=TestCatPvalHelpers.create_category_dict(
                    "test", {"TestCategory": ["gene1", "gene2"]}
                ),
            )

            main(net)

            pval = net.dat[NODE_INFO_KEY][ROW_AXIS][f"{PVAL_CAT_PREFIX}test"]["TestCategory"]
            TestCatPvalHelpers.assert_valid_probability(pval, "Calculated p-value")

            # Should be called for observed value + null distribution
            assert mock_median.call_count >= HISTOGRAM_ITERATIONS

    def test_edge_case_robustness(self) -> None:
        """Test robustness to various edge cases."""
        # Test with minimal distance matrix
        dm = pd.DataFrame(
            [[ZERO_PROBABILITY, 1], [1, ZERO_PROBABILITY]], index=["A", "B"], columns=["A", "B"]
        )
        subset = ["A"]
        nodes = ["A", "B"]

        result = calc_hist_distances(dm, subset, nodes)
        TestCatPvalHelpers.assert_histogram_structure(result)

    def test_empty_list_handling_fixed(self) -> None:
        """Verify that empty list handling has been fixed."""
        result = dist_matrix_lattice([])
        assert result.shape == (0, 0)
        assert result.empty

    def test_empty_subset_behavior_documented(self) -> None:
        """Document expected behavior for empty subsets."""
        dm = pd.DataFrame(
            [[ZERO_PROBABILITY, 1], [1, ZERO_PROBABILITY]], index=["A", "B"], columns=["A", "B"]
        )
        result = calc_median_dist_subset(dm, [])
        assert np.isnan(result)  # Expected behavior for empty subsets

    def test_symmetric_distance_matrix_validation(self) -> None:
        """Test that distance matrices maintain symmetry property."""
        for size in [3, 5, 10]:
            names = [f"node_{i}" for i in range(size)]
            dm = dist_matrix_lattice(names)

            # Check all pairwise symmetries
            for i in range(size):
                for j in range(size):
                    assert dm.iloc[i, j] == dm.iloc[j, i], (
                        f"Asymmetric distance at ({i}, {j}): {dm.iloc[i, j]} != {dm.iloc[j, i]}"
                    )

    def test_statistical_distribution_properties(self) -> None:
        """Test that statistical distributions have expected properties."""
        # Create a deterministic scenario
        dm = TestCatPvalHelpers.create_distance_matrix(
            np.array([[0, 1, 2], [1, 0, 1], [2, 1, 0]]), ["A", "B", "C"]
        )

        subset = ["A", "B"]
        all_nodes = ["A", "B", "C"]

        result = calc_hist_distances(dm, subset, all_nodes)

        # Verify statistical properties
        TestCatPvalHelpers.assert_histogram_structure(result)

        # All probabilities should be non-negative
        assert all(p >= ZERO_PROBABILITY for p in result["prob"])

        # Bin edges should span a reasonable range
        bin_range = result["bins"][-1] - result["bins"][0]
        assert bin_range > ZERO_PROBABILITY, "Histogram should have positive range"


# =============================================================================
# TEST CLASSES - PERFORMANCE TESTS
# =============================================================================


class TestPerformanceAndMemory:
    """Performance and memory efficiency tests."""

    def test_memory_efficiency_large_matrices(self) -> None:
        """Test memory efficiency with large distance matrices."""
        # Test with reasonably large matrix that shouldn't cause memory issues
        large_size = 50
        names = [f"node_{i}" for i in range(large_size)]

        # This should complete without excessive memory usage
        dm = dist_matrix_lattice(names)

        assert dm.shape == (large_size, large_size)
        assert isinstance(dm, pd.DataFrame)

    def test_performance_scaling(self) -> None:
        """Test that functions scale reasonably with input size."""
        import time

        # Test with increasing sizes
        for size in [10, 20, 30]:
            names = [f"node_{i}" for i in range(size)]

            start_time = time.time()
            dm = dist_matrix_lattice(names)
            end_time = time.time()

            # Should complete in reasonable time (adjust threshold as needed)
            assert (end_time - start_time) < 1.0, (
                f"Distance matrix creation too slow for size {size}"
            )
            assert dm.shape == (size, size)

    def test_histogram_computation_efficiency(self, extended_distance_matrix: pd.DataFrame) -> None:
        """Test that histogram computation is efficient."""
        import time

        subset = ["A", "B", "C"]
        all_nodes = ["A", "B", "C", "D", "E"]

        start_time = time.time()
        result = calc_hist_distances(extended_distance_matrix, subset, all_nodes)
        end_time = time.time()

        # Should complete histogram calculation efficiently
        assert (end_time - start_time) < 2.0, "Histogram calculation too slow"
        TestCatPvalHelpers.assert_histogram_structure(result)


# =============================================================================
# MAIN EXECUTION
# =============================================================================

if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])
