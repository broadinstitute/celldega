"""
Comprehensive tests for celldega.clust.data_io.load_vect_post module.
Tests cover all functions with extensive edge case coverage and minimal redundancy.
"""

from pathlib import Path
import sys
from typing import Any
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd
import pytest


# Add the source directory to the path for imports
sys.path.insert(0, str(Path(__file__).parents[3] / "src"))

from celldega.clust.data_io.load_vect_post import main


# =============================================================================
# CONSTANTS
# =============================================================================

# Test gene names
GENE_ACTB = "ACTB"
GENE_GAPDH = "GAPDH"
GENE_TP53 = "TP53"
GENE_MYC = "MYC"
GENE_1 = "gene1"
GENE_2 = "gene2"
GENE_ALPHA = "gene_α"
GENE_BETA = "gene-β"
GENE_AT = "gene@1"

# Test sample/cell names
SAMPLE_1 = "sample1"
SAMPLE_2 = "sample2"
CELL_001 = "cell_001"
CELL_002 = "cell_002"

# Test values
VALUE_1_0 = 1.0
VALUE_1_5 = 1.5
VALUE_2_0 = 2.0
VALUE_2_5 = 2.5
VALUE_3_0 = 3.0
VALUE_3_4 = 3.4
VALUE_4_0 = 4.0
VALUE_8_9 = 8.9
VALUE_12_8 = 12.8
VALUE_13_1 = 13.1
VALUE_14_7 = 14.7
VALUE_15_2 = 15.2

# Large dataset simulation constants
LARGE_DATASET_GENES = 50
LARGE_DATASET_CELLS = 25
GENE_COVERAGE_RATIO = 0.7

# Error messages
ERROR_NOT_SUBSCRIPTABLE_NONE = "'NoneType' object is not subscriptable"
ERROR_STRING_INDICES_INT = "string indices must be integers"
ERROR_LIST_INDICES_INT = "list indices must be integers or slices, not str"
ERROR_INT_NOT_SUBSCRIPTABLE = "'int' object is not subscriptable"
ERROR_INT_NOT_ITERABLE = "'int' object is not iterable"
ERROR_NONE_NOT_ITERABLE = "'NoneType' object is not iterable"
ERROR_KEY_COLUMNS = "'columns'"
ERROR_KEY_COL_NAME = "'col_name'"
ERROR_KEY_DATA = "'data'"
ERROR_KEY_ROW_NAME = "'row_name'"
ERROR_KEY_VAL = "'val'"
ERROR_COMPARISON_NOT_SUPPORTED = "'<' not supported between instances"

# Test data keys
KEY_COLUMNS = "columns"
KEY_COL_NAME = "col_name"
KEY_DATA = "data"
KEY_ROW_NAME = "row_name"
KEY_VAL = "val"
KEY_WRONG = "wrong_key"

# Node keys
NODE_KEY_ROW = "row"
NODE_KEY_COL = "col"
NODE_KEY_NODES = "nodes"
NODE_KEY_MAT = "mat"

# Test tolerance for floating point comparisons
FLOAT_TOLERANCE = 1e-6

# =============================================================================
# UTILITIES
# =============================================================================


def create_test_gene_list(count: int) -> list[str]:
    """Generate a list of test gene names."""
    return [f"GENE_{i:03d}" for i in range(count)]


def create_test_cell_list(count: int) -> list[str]:
    """Generate a list of test cell names."""
    return [f"cell_{i:03d}" for i in range(count)]


def create_row_data(row_name: str, value: float) -> dict[str, Any]:
    """Create a single row data entry."""
    return {KEY_ROW_NAME: row_name, KEY_VAL: value}


def create_column_data(col_name: str, row_data_list: list[dict[str, Any]]) -> dict[str, Any]:
    """Create a column data structure."""
    return {KEY_COL_NAME: col_name, KEY_DATA: row_data_list}


def create_simple_vect_post(
    rows: list[str] | None = None,
    cols: list[str] | None = None,
    values: list[list[float]] | None = None,
) -> dict[str, Any]:
    """Create a simple valid vect_post structure for testing."""
    if rows is None:
        rows = [GENE_1, GENE_2]
    if cols is None:
        cols = [SAMPLE_1, SAMPLE_2]
    if values is None:
        values = [[VALUE_1_0, VALUE_2_0], [VALUE_3_0, VALUE_4_0]]

    columns = []
    for col_idx, col_name in enumerate(cols):
        data = []
        for row_idx, row_name in enumerate(rows):
            if row_idx < len(values) and col_idx < len(values[row_idx]):
                val = values[row_idx][col_idx]
            else:
                val = VALUE_1_0
            data.append(create_row_data(row_name, val))
        columns.append(create_column_data(col_name, data))

    return {KEY_COLUMNS: columns}


def create_gene_expression_vect_post() -> dict[str, Any]:
    """Create realistic gene expression data for testing."""
    return {
        KEY_COLUMNS: [
            create_column_data(
                CELL_001,
                [
                    create_row_data(GENE_ACTB, VALUE_15_2),
                    create_row_data(GENE_GAPDH, VALUE_12_8),
                    create_row_data(GENE_TP53, VALUE_3_4),
                ],
            ),
            create_column_data(
                CELL_002,
                [
                    create_row_data(GENE_ACTB, VALUE_14_7),
                    create_row_data(GENE_GAPDH, VALUE_13_1),
                    create_row_data(GENE_MYC, VALUE_8_9),
                ],
            ),
        ]
    }


def create_large_dataset_vect_post(n_genes: int, n_cells: int) -> dict[str, Any]:
    """Create large dataset for performance testing."""
    columns = []
    genes = create_test_gene_list(n_genes)

    for cell_i in range(n_cells):
        cell_name = f"cell_{cell_i:03d}"
        data = []
        # Only include ~70% of genes for sparse matrix simulation
        for gene_i in range(int(n_genes * GENE_COVERAGE_RATIO)):
            if (cell_i + gene_i) % 3 != 0:  # Create sparse pattern
                data.append(create_row_data(genes[gene_i], float(cell_i + gene_i)))
        columns.append(create_column_data(cell_name, data))

    return {KEY_COLUMNS: columns}


def assert_matrix_value_with_tolerance(
    actual: float, expected: float, tolerance: float = FLOAT_TOLERANCE
) -> None:
    """Assert matrix values with appropriate tolerance handling."""
    if np.isnan(expected):
        assert np.isnan(actual)
    elif np.isinf(expected):
        assert np.isinf(actual) and np.sign(actual) == np.sign(expected)
    elif tolerance > 0:
        assert abs(actual - expected) <= tolerance
    else:
        assert actual == expected


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_network() -> Mock:
    """Create a standard mock network object."""
    mock_net = Mock()
    mock_net.df_to_dat = Mock()
    return mock_net


@pytest.fixture
def mock_network_instance() -> Mock:
    """Create a mock Network instance for deepcopy scenarios."""
    mock_instance = Mock()
    mock_instance.dat = {NODE_KEY_NODES: {}}
    mock_instance.dat_to_df = Mock(
        return_value=pd.DataFrame({"col1": [1, 2]}, index=["row1", "row2"])
    )
    return mock_instance


@pytest.fixture
def sample_vect_post() -> dict[str, Any]:
    """Create a sample vect_post structure for testing."""
    return create_simple_vect_post()


@pytest.fixture
def gene_expression_data() -> dict[str, Any]:
    """Create realistic gene expression data."""
    return create_gene_expression_vect_post()


# =============================================================================
# INPUT VALIDATION TESTS
# =============================================================================


class TestInputValidation:
    """Test input validation errors with comprehensive coverage."""

    @pytest.mark.parametrize(
        "invalid_input,expected_error,error_pattern,description",
        [
            (None, TypeError, ERROR_NOT_SUBSCRIPTABLE_NONE, "none_input"),
            ("string", TypeError, ERROR_STRING_INDICES_INT, "string_input"),
            ([], TypeError, ERROR_LIST_INDICES_INT, "empty_list"),
            (123, TypeError, ERROR_INT_NOT_SUBSCRIPTABLE, "integer_input"),
            ({}, KeyError, ERROR_KEY_COLUMNS, "empty_dict"),
            ({KEY_WRONG: []}, KeyError, ERROR_KEY_COLUMNS, "wrong_key"),
        ],
    )
    def test_top_level_access_errors(
        self,
        invalid_input: Any,
        expected_error: type[Exception],
        error_pattern: str,
        description: str,
        mock_network: Mock,
    ):
        """Test errors when accessing vect_post['columns'] with invalid input."""
        with pytest.raises(expected_error, match=error_pattern):
            main(mock_network, invalid_input)

    @pytest.mark.parametrize(
        "invalid_columns,expected_error,error_pattern,description",
        [
            ("string", TypeError, ERROR_STRING_INDICES_INT, "string_columns"),
            (123, TypeError, ERROR_INT_NOT_ITERABLE, "integer_columns"),
            (None, TypeError, ERROR_NONE_NOT_ITERABLE, "none_columns"),
        ],
    )
    def test_columns_iteration_errors(
        self,
        invalid_columns: Any,
        expected_error: type[Exception],
        error_pattern: str,
        description: str,
        mock_network: Mock,
    ):
        """Test errors when iterating over invalid columns."""
        vect_post = {KEY_COLUMNS: invalid_columns}
        with pytest.raises(expected_error, match=error_pattern):
            main(mock_network, vect_post)

    @pytest.mark.parametrize(
        "invalid_column,expected_error,error_pattern,description",
        [
            ("string", TypeError, ERROR_STRING_INDICES_INT, "string_column"),
            ([], TypeError, ERROR_LIST_INDICES_INT, "list_column"),
            (None, TypeError, ERROR_NOT_SUBSCRIPTABLE_NONE, "none_column"),
            ({}, KeyError, ERROR_KEY_COL_NAME, "empty_dict_column"),
            ({KEY_COL_NAME: "test"}, KeyError, ERROR_KEY_DATA, "missing_data"),
            ({KEY_DATA: []}, KeyError, ERROR_KEY_COL_NAME, "missing_col_name"),
        ],
    )
    def test_column_access_errors(
        self,
        invalid_column: Any,
        expected_error: type[Exception],
        error_pattern: str,
        description: str,
        mock_network: Mock,
    ):
        """Test errors when accessing column attributes."""
        vect_post = {KEY_COLUMNS: [invalid_column]}
        with pytest.raises(expected_error, match=error_pattern):
            main(mock_network, vect_post)

    @pytest.mark.parametrize(
        "invalid_data,expected_error,error_pattern,description",
        [
            ("string", TypeError, ERROR_STRING_INDICES_INT, "string_data"),
            (123, TypeError, ERROR_INT_NOT_ITERABLE, "integer_data"),
            (None, TypeError, ERROR_NONE_NOT_ITERABLE, "none_data"),
        ],
    )
    def test_data_iteration_errors(
        self,
        invalid_data: Any,
        expected_error: type[Exception],
        error_pattern: str,
        description: str,
        mock_network: Mock,
    ):
        """Test errors when iterating over invalid data."""
        vect_post = {KEY_COLUMNS: [create_column_data(SAMPLE_1, invalid_data)]}
        with pytest.raises(expected_error, match=error_pattern):
            main(mock_network, vect_post)

    @pytest.mark.parametrize(
        "invalid_row_data,expected_error,error_pattern,description",
        [
            ("string", TypeError, ERROR_STRING_INDICES_INT, "string_row_data"),
            ([], TypeError, ERROR_LIST_INDICES_INT, "list_row_data"),
            (None, TypeError, ERROR_NOT_SUBSCRIPTABLE_NONE, "none_row_data"),
            ({}, KeyError, ERROR_KEY_ROW_NAME, "empty_dict_row"),
            ({KEY_ROW_NAME: GENE_1}, KeyError, ERROR_KEY_VAL, "missing_val"),
            ({KEY_VAL: VALUE_1_0}, KeyError, ERROR_KEY_ROW_NAME, "missing_row_name"),
        ],
    )
    def test_row_data_access_errors(
        self,
        invalid_row_data: Any,
        expected_error: type[Exception],
        error_pattern: str,
        description: str,
        mock_network: Mock,
    ):
        """Test errors when accessing row data attributes."""
        vect_post = {KEY_COLUMNS: [create_column_data(SAMPLE_1, [invalid_row_data])]}
        with pytest.raises(expected_error, match=error_pattern):
            main(mock_network, vect_post)

    @patch("celldega.clust.data_io.load_vect_post.deepcopy")
    @patch("celldega.clust.data_io.load_vect_post.proc_df_labels")
    def test_empty_columns_list_behavior(
        self,
        mock_proc_df_labels: Mock,
        mock_deepcopy: Mock,
        mock_network: Mock,
        mock_network_instance: Mock,
    ):
        """Test behavior with empty columns list."""
        mock_deepcopy.return_value = mock_network_instance
        mock_proc_df_labels.main.return_value = pd.DataFrame()

        vect_post = {KEY_COLUMNS: []}
        main(mock_network, vect_post)

        assert mock_network_instance.dat[NODE_KEY_NODES][NODE_KEY_ROW] == []
        assert mock_network_instance.dat[NODE_KEY_NODES][NODE_KEY_COL] == []
        assert mock_network_instance.dat[NODE_KEY_MAT].shape == (0, 0)


# =============================================================================
# DATA PROCESSING TESTS
# =============================================================================


class TestDataProcessing:
    """Test core data processing functionality."""

    @patch("celldega.clust.data_io.load_vect_post.deepcopy")
    @patch("celldega.clust.data_io.load_vect_post.proc_df_labels")
    def test_successful_basic_processing(
        self,
        mock_proc_df_labels: Mock,
        mock_deepcopy: Mock,
        mock_network: Mock,
        mock_network_instance: Mock,
    ):
        """Test successful processing of valid data."""
        mock_deepcopy.return_value = mock_network_instance
        mock_proc_df_labels.main.return_value = pd.DataFrame({"col1": [1]}, index=["row1"])

        vect_post = create_simple_vect_post(
            rows=[GENE_1, GENE_2], cols=[SAMPLE_1], values=[[VALUE_1_5], [VALUE_2_5]]
        )

        main(mock_network, vect_post)

        # Verify network setup
        assert mock_network_instance.dat[NODE_KEY_NODES][NODE_KEY_ROW] == [GENE_1, GENE_2]
        assert mock_network_instance.dat[NODE_KEY_NODES][NODE_KEY_COL] == [SAMPLE_1]

        # Verify matrix creation
        matrix = mock_network_instance.dat[NODE_KEY_MAT]
        assert matrix.shape == (2, 1)
        assert matrix[0, 0] == VALUE_1_5
        assert matrix[1, 0] == VALUE_2_5

        # Verify processing pipeline
        mock_network_instance.dat_to_df.assert_called_once()
        mock_proc_df_labels.main.assert_called_once()
        mock_network.df_to_dat.assert_called_once()

    @patch("celldega.clust.data_io.load_vect_post.deepcopy")
    @patch("celldega.clust.data_io.load_vect_post.proc_df_labels")
    def test_matrix_ordering_and_nan_filling(
        self,
        mock_proc_df_labels: Mock,
        mock_deepcopy: Mock,
        mock_network: Mock,
        mock_network_instance: Mock,
    ):
        """Test matrix ordering and NaN filling for missing values."""
        mock_deepcopy.return_value = mock_network_instance
        mock_proc_df_labels.main.return_value = pd.DataFrame()

        vect_post = {
            KEY_COLUMNS: [
                create_column_data(SAMPLE_2, [create_row_data(GENE_2, VALUE_2_0)]),
                create_column_data(
                    SAMPLE_1,
                    [
                        create_row_data(GENE_1, VALUE_1_0),
                        create_row_data(GENE_2, VALUE_3_0),
                    ],
                ),
            ]
        }

        main(mock_network, vect_post)

        # Verify alphabetical ordering
        assert mock_network_instance.dat[NODE_KEY_NODES][NODE_KEY_ROW] == [GENE_1, GENE_2]
        assert mock_network_instance.dat[NODE_KEY_NODES][NODE_KEY_COL] == [SAMPLE_1, SAMPLE_2]

        # Verify matrix values and NaN placement
        matrix = mock_network_instance.dat[NODE_KEY_MAT]
        assert matrix.shape == (2, 2)

        assert matrix[0, 0] == VALUE_1_0  # gene1, sample1
        assert matrix[1, 0] == VALUE_3_0  # gene2, sample1
        assert np.isnan(matrix[0, 1])  # gene1, sample2 (missing)
        assert matrix[1, 1] == VALUE_2_0  # gene2, sample2

    @pytest.mark.parametrize(
        "numeric_values,tolerance,description",
        [
            ([1, 2.5, np.float32(3.2), np.int64(4)], FLOAT_TOLERANCE, "mixed_numeric_types"),
            ([float("inf"), float("-inf"), 0.0, -0.0], 0, "special_float_values"),
            ([1e308, 1e-308, -1e308], 0, "extreme_values"),
        ],
    )
    @patch("celldega.clust.data_io.load_vect_post.deepcopy")
    @patch("celldega.clust.data_io.load_vect_post.proc_df_labels")
    def test_numeric_value_handling(
        self,
        mock_proc_df_labels: Mock,
        mock_deepcopy: Mock,
        numeric_values: list[float],
        tolerance: float,
        description: str,
        mock_network: Mock,
        mock_network_instance: Mock,
    ):
        """Test handling of various numeric value types."""
        mock_deepcopy.return_value = mock_network_instance
        mock_proc_df_labels.main.return_value = pd.DataFrame()

        data = [create_row_data(f"gene{i}", val) for i, val in enumerate(numeric_values)]
        vect_post = {KEY_COLUMNS: [create_column_data(SAMPLE_1, data)]}

        main(mock_network, vect_post)

        matrix = mock_network_instance.dat[NODE_KEY_MAT]
        for i, expected in enumerate(numeric_values):
            actual = matrix[i, 0]
            assert_matrix_value_with_tolerance(actual, expected, tolerance)

    @pytest.mark.parametrize(
        "invalid_value,expected_error,description",
        [
            ("string_value", ValueError, "string_numeric"),
            ([], ValueError, "list_numeric"),
            ({}, TypeError, "dict_numeric"),
        ],
    )
    @patch("celldega.clust.data_io.load_vect_post.deepcopy")
    @patch("celldega.clust.data_io.load_vect_post.proc_df_labels")
    def test_invalid_numeric_values(
        self,
        mock_proc_df_labels: Mock,
        mock_deepcopy: Mock,
        invalid_value: Any,
        expected_error: type[Exception],
        description: str,
        mock_network: Mock,
        mock_network_instance: Mock,
    ):
        """Test behavior with invalid numeric values."""
        mock_deepcopy.return_value = mock_network_instance
        mock_proc_df_labels.main.return_value = pd.DataFrame()

        vect_post = {
            KEY_COLUMNS: [create_column_data(SAMPLE_1, [create_row_data(GENE_1, invalid_value)])]
        }

        with pytest.raises(expected_error):
            main(mock_network, vect_post)

    @pytest.mark.parametrize(
        "string_values,description",
        [
            ([GENE_ALPHA, GENE_BETA, GENE_AT], "special_chars"),
            (["", "  ", "\t"], "whitespace"),
            (["123", "1.5", "-42"], "numeric_strings"),
        ],
    )
    @patch("celldega.clust.data_io.load_vect_post.deepcopy")
    @patch("celldega.clust.data_io.load_vect_post.proc_df_labels")
    def test_string_name_handling(
        self,
        mock_proc_df_labels: Mock,
        mock_deepcopy: Mock,
        string_values: list[str],
        description: str,
        mock_network: Mock,
        mock_network_instance: Mock,
    ):
        """Test handling of various string name types."""
        mock_deepcopy.return_value = mock_network_instance
        mock_proc_df_labels.main.return_value = pd.DataFrame()

        data = [create_row_data(string_values[0], VALUE_1_0)]
        col_name = string_values[1] if len(string_values) > 1 else SAMPLE_1
        vect_post = {KEY_COLUMNS: [create_column_data(col_name, data)]}

        main(mock_network, vect_post)

        assert string_values[0] in mock_network_instance.dat[NODE_KEY_NODES][NODE_KEY_ROW]


# =============================================================================
# NETWORK INTEGRATION TESTS
# =============================================================================


class TestNetworkIntegration:
    """Test integration with Network class and error propagation."""

    @patch("celldega.clust.data_io.load_vect_post.deepcopy")
    def test_network_initialization_failure(
        self, mock_deepcopy: Mock, mock_network: Mock, sample_vect_post: dict[str, Any]
    ):
        """Test handling of Network initialization failures."""
        mock_deepcopy.side_effect = RuntimeError("Network init failed")

        with pytest.raises(RuntimeError, match="Network init failed"):
            main(mock_network, sample_vect_post)

    @patch("celldega.clust.data_io.load_vect_post.deepcopy")
    def test_dat_to_df_failure(
        self,
        mock_deepcopy: Mock,
        mock_network: Mock,
        mock_network_instance: Mock,
        sample_vect_post: dict[str, Any],
    ):
        """Test handling of dat_to_df method failures."""
        mock_network_instance.dat_to_df.side_effect = AttributeError("dat_to_df failed")
        mock_deepcopy.return_value = mock_network_instance

        with pytest.raises(AttributeError, match="dat_to_df failed"):
            main(mock_network, sample_vect_post)

    @patch("celldega.clust.data_io.load_vect_post.deepcopy")
    @patch("celldega.clust.data_io.load_vect_post.proc_df_labels")
    def test_proc_df_labels_failure(
        self,
        mock_proc_df_labels: Mock,
        mock_deepcopy: Mock,
        mock_network: Mock,
        mock_network_instance: Mock,
        sample_vect_post: dict[str, Any],
    ):
        """Test handling of proc_df_labels failures."""
        mock_deepcopy.return_value = mock_network_instance
        mock_proc_df_labels.main.side_effect = ValueError("Processing failed")

        with pytest.raises(ValueError, match="Processing failed"):
            main(mock_network, sample_vect_post)

    @patch("celldega.clust.data_io.load_vect_post.deepcopy")
    @patch("celldega.clust.data_io.load_vect_post.proc_df_labels")
    def test_df_to_dat_failure(
        self,
        mock_proc_df_labels: Mock,
        mock_deepcopy: Mock,
        mock_network: Mock,
        mock_network_instance: Mock,
        sample_vect_post: dict[str, Any],
    ):
        """Test handling of df_to_dat method failures."""
        mock_deepcopy.return_value = mock_network_instance
        mock_proc_df_labels.main.return_value = pd.DataFrame()
        mock_network.df_to_dat.side_effect = RuntimeError("df_to_dat failed")

        with pytest.raises(RuntimeError, match="df_to_dat failed"):
            main(mock_network, sample_vect_post)


# =============================================================================
# EDGE CASE TESTS
# =============================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.parametrize(
        "scenario_name,rows,cols,values,expected_shape",
        [
            ("single_cell", [GENE_1], [SAMPLE_1], [[VALUE_1_0]], (1, 1)),
            (
                "single_row_multi_col",
                [GENE_1],
                [SAMPLE_1, SAMPLE_2],
                [[VALUE_1_0, VALUE_2_0]],
                (1, 2),
            ),
            (
                "multi_row_single_col",
                [GENE_1, GENE_2],
                [SAMPLE_1],
                [[VALUE_1_0], [VALUE_2_0]],
                (2, 1),
            ),
            (
                "square_matrix",
                [GENE_1, GENE_2],
                [SAMPLE_1, SAMPLE_2],
                [[VALUE_1_0, VALUE_2_0], [VALUE_3_0, VALUE_4_0]],
                (2, 2),
            ),
        ],
    )
    @patch("celldega.clust.data_io.load_vect_post.deepcopy")
    @patch("celldega.clust.data_io.load_vect_post.proc_df_labels")
    def test_matrix_size_scenarios(
        self,
        mock_proc_df_labels: Mock,
        mock_deepcopy: Mock,
        scenario_name: str,
        rows: list[str],
        cols: list[str],
        values: list[list[float]],
        expected_shape: tuple[int, int],
        mock_network: Mock,
        mock_network_instance: Mock,
    ):
        """Test various matrix size scenarios."""
        mock_deepcopy.return_value = mock_network_instance
        mock_proc_df_labels.main.return_value = pd.DataFrame()

        vect_post = create_simple_vect_post(rows=rows, cols=cols, values=values)
        main(mock_network, vect_post)

        matrix = mock_network_instance.dat[NODE_KEY_MAT]
        assert matrix.shape == expected_shape
        assert len(mock_network_instance.dat[NODE_KEY_NODES][NODE_KEY_ROW]) == expected_shape[0]
        assert len(mock_network_instance.dat[NODE_KEY_NODES][NODE_KEY_COL]) == expected_shape[1]

    @patch("celldega.clust.data_io.load_vect_post.deepcopy")
    @patch("celldega.clust.data_io.load_vect_post.proc_df_labels")
    def test_duplicate_names_handling(
        self,
        mock_proc_df_labels: Mock,
        mock_deepcopy: Mock,
        mock_network: Mock,
        mock_network_instance: Mock,
    ):
        """Test handling of duplicate row/column names."""
        mock_deepcopy.return_value = mock_network_instance
        mock_proc_df_labels.main.return_value = pd.DataFrame()

        vect_post = {
            KEY_COLUMNS: [
                create_column_data(
                    SAMPLE_1,
                    [
                        create_row_data(GENE_1, VALUE_1_0),
                        create_row_data(GENE_1, VALUE_2_0),  # Duplicate row name
                    ],
                )
            ]
        }

        main(mock_network, vect_post)

        # Should only have one entry for gene1, with the last value
        assert mock_network_instance.dat[NODE_KEY_NODES][NODE_KEY_ROW] == [GENE_1]
        matrix = mock_network_instance.dat[NODE_KEY_MAT]
        assert matrix.shape == (1, 1)
        assert matrix[0, 0] == VALUE_2_0  # Last value wins

    @patch("celldega.clust.data_io.load_vect_post.deepcopy")
    @patch("celldega.clust.data_io.load_vect_post.proc_df_labels")
    def test_network_dat_structure_population(
        self,
        mock_proc_df_labels: Mock,
        mock_deepcopy: Mock,
        mock_network: Mock,
        sample_vect_post: dict[str, Any],
    ):
        """Test that dat structure is populated correctly."""
        mock_net_instance = Mock()
        mock_net_instance.dat = {NODE_KEY_NODES: {}}
        mock_net_instance.dat_to_df = Mock(return_value=pd.DataFrame())
        mock_deepcopy.return_value = mock_net_instance
        mock_proc_df_labels.main.return_value = pd.DataFrame()

        main(mock_network, sample_vect_post)

        # Should populate dat structure correctly
        assert NODE_KEY_NODES in mock_net_instance.dat
        assert NODE_KEY_ROW in mock_net_instance.dat[NODE_KEY_NODES]
        assert NODE_KEY_COL in mock_net_instance.dat[NODE_KEY_NODES]
        assert NODE_KEY_MAT in mock_net_instance.dat

        # Check that the nodes contain the expected data
        assert mock_net_instance.dat[NODE_KEY_NODES][NODE_KEY_ROW] == [GENE_1, GENE_2]
        assert mock_net_instance.dat[NODE_KEY_NODES][NODE_KEY_COL] == [SAMPLE_1, SAMPLE_2]

    def test_non_comparable_column_names_error(self, mock_network: Mock):
        """Test error when column names can't be sorted (mixed types)."""
        vect_post = {
            KEY_COLUMNS: [
                create_column_data("string_name", [create_row_data(GENE_1, VALUE_1_0)]),
                create_column_data(123, [create_row_data(GENE_2, VALUE_2_0)]),  # int name
            ]
        }

        with pytest.raises(TypeError, match=ERROR_COMPARISON_NOT_SUPPORTED):
            main(mock_network, vect_post)


# =============================================================================
# INTEGRATION SCENARIO TESTS
# =============================================================================


class TestIntegrationScenarios:
    """Integration tests for realistic scenarios."""

    @patch("celldega.clust.data_io.load_vect_post.deepcopy")
    @patch("celldega.clust.data_io.load_vect_post.proc_df_labels")
    def test_gene_expression_scenario(
        self,
        mock_proc_df_labels: Mock,
        mock_deepcopy: Mock,
        mock_network: Mock,
        mock_network_instance: Mock,
        gene_expression_data: dict[str, Any],
    ):
        """Test realistic gene expression data scenario."""
        mock_deepcopy.return_value = mock_network_instance
        mock_proc_df_labels.main.return_value = pd.DataFrame()

        main(mock_network, gene_expression_data)

        expected_genes = [GENE_ACTB, GENE_GAPDH, GENE_MYC, GENE_TP53]
        expected_cells = [CELL_001, CELL_002]

        assert mock_network_instance.dat[NODE_KEY_NODES][NODE_KEY_ROW] == expected_genes
        assert mock_network_instance.dat[NODE_KEY_NODES][NODE_KEY_COL] == expected_cells

        matrix = mock_network_instance.dat[NODE_KEY_MAT]
        assert matrix.shape == (4, 2)

        # Check specific values and NaN placement
        gene_idx = {gene: i for i, gene in enumerate(expected_genes)}
        cell_idx = {cell: i for i, cell in enumerate(expected_cells)}

        assert matrix[gene_idx[GENE_ACTB], cell_idx[CELL_001]] == VALUE_15_2
        assert matrix[gene_idx[GENE_ACTB], cell_idx[CELL_002]] == VALUE_14_7
        assert matrix[gene_idx[GENE_TP53], cell_idx[CELL_001]] == VALUE_3_4
        assert np.isnan(matrix[gene_idx[GENE_TP53], cell_idx[CELL_002]])
        assert np.isnan(matrix[gene_idx[GENE_MYC], cell_idx[CELL_001]])
        assert matrix[gene_idx[GENE_MYC], cell_idx[CELL_002]] == VALUE_8_9

    @patch("celldega.clust.data_io.load_vect_post.deepcopy")
    @patch("celldega.clust.data_io.load_vect_post.proc_df_labels")
    def test_large_dataset_simulation(
        self,
        mock_proc_df_labels: Mock,
        mock_deepcopy: Mock,
        mock_network: Mock,
        mock_network_instance: Mock,
    ):
        """Test performance with larger dataset."""
        mock_deepcopy.return_value = mock_network_instance
        mock_proc_df_labels.main.return_value = pd.DataFrame()

        vect_post = create_large_dataset_vect_post(LARGE_DATASET_GENES, LARGE_DATASET_CELLS)
        main(mock_network, vect_post)

        assert len(mock_network_instance.dat[NODE_KEY_NODES][NODE_KEY_COL]) == LARGE_DATASET_CELLS
        matrix = mock_network_instance.dat[NODE_KEY_MAT]
        assert matrix.shape[1] == LARGE_DATASET_CELLS
        assert matrix.shape[0] <= LARGE_DATASET_GENES


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
