"""
Comprehensive tests for celldega.clust.data_io.make_unique_labels module.
Tests cover all functions with extensive edge case coverage and minimal redundancy.
"""

from pathlib import Path
import sys
from typing import Any
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest


# Add the source directory to the path for imports
sys.path.insert(0, str(Path(__file__).parents[3] / "src"))

from celldega.clust.data_io.make_unique_labels import _has_duplicates, add_index_list, main


# =============================================================================
# CONSTANTS
# =============================================================================

# Test gene names
GENE_1 = "gene1"
GENE_2 = "gene2"
GENE_3 = "gene3"
GENE_ACTB = "ACTB"
GENE_GAPDH = "GAPDH"
GENE_TP53 = "TP53"
GENE_1_UPPER = "GENE1"
GENE_2_UPPER = "GENE2"

# Test column names
COL_1 = "col1"
COL_2 = "col2"
SAMPLE_1 = "sample1"
SAMPLE_2 = "sample2"
EXPRESSION_COL = "expression"

# Test types and categories
TYPE_1 = "type1"
TYPE_2 = "type2"
TYPE_PROTEIN = "protein"
TYPE_RNA = "rna"
CONDITION_1 = "condition1"
CONDITION_2 = "condition2"

# Test row names
ROW_1 = "row1"
ROW_2 = "row2"

# Special string values
EMPTY_STRING = ""
WHITESPACE_STRING = "  "
TAB_STRING = "\t"
HYPHEN_GENE = "gene-1"
AT_GENE = "gene@2"
EMOJI_GENE = "gene🧬"

# Numeric test values
TEST_VALUE_1 = 1
TEST_VALUE_2 = 2
TEST_VALUE_3 = 3
TEST_VALUE_42 = 42
FLOAT_VALUE_1_1 = 1.1
FLOAT_VALUE_1_2 = 1.2
FLOAT_VALUE_1_5 = 1.5
FLOAT_VALUE_2_2 = 2.2
FLOAT_VALUE_2_3 = 2.3
FLOAT_VALUE_2_6 = 2.6
FLOAT_VALUE_3_3 = 3.3
FLOAT_VALUE_3_4 = 3.4
FLOAT_VALUE_3_7 = 3.7
FLOAT_VALUE_0_8 = 0.8
FLOAT_VALUE_1_9 = 1.9
FLOAT_VALUE_2_1 = 2.1

# Expected output patterns
SUFFIX_1 = "-1"
SUFFIX_2 = "-2"
SUFFIX_3 = "-3"
SUFFIX_4 = "-4"

# Warning messages
WARNING_ROW_UNIQUE = "warning: making row names unique"
WARNING_COL_UNIQUE = "warning: making col names unique"

# Error messages
ERROR_EITHER_NET_OR_DF = "Either net or df must be provided"
ERROR_EMPTY_TUPLES_ROW = "Empty tuples found in row index"
ERROR_EMPTY_TUPLES_COLUMN = "Empty tuples found in column index"
ERROR_NETWORK_ERROR = "Network error"

# Test data structure keys
DATA_KEY_INT_COL = "int_col"
DATA_KEY_FLOAT_COL = "float_col"
DATA_KEY_STR_COL = "str_col"
DATA_KEY_BOOL_COL = "bool_col"

# Large dataset constants
LARGE_DATASET_SIZE = 1000

# =============================================================================
# UTILITIES
# =============================================================================


def create_simple_dataframe(
    data: dict[str, list[Any]] | None = None,
    index: list[str] | None = None,
    columns: list[str] | None = None,
) -> pd.DataFrame:
    """Create a simple DataFrame with optional custom data, index, and columns."""
    if data is None:
        data = {COL_1: [TEST_VALUE_1, TEST_VALUE_2]}
    if index is None:
        index = [GENE_1, GENE_2]
    if columns is None and isinstance(data, dict):
        columns = list(data.keys())

    return pd.DataFrame(data, index=index, columns=columns)


def create_tuple_index_dataframe(
    tuples: list[tuple[Any, ...]], data: dict[str, list[Any]] | None = None
) -> pd.DataFrame:
    """Create DataFrame with tuple index."""
    if data is None:
        data = {COL_1: list(range(len(tuples)))}
    return pd.DataFrame(data, index=tuples)


def create_tuple_columns_dataframe(
    tuples: list[tuple[Any, ...]], data: list[list[Any]] | None = None
) -> pd.DataFrame:
    """Create DataFrame with tuple columns."""
    if data is None:
        data = [[TEST_VALUE_1] * len(tuples)]
    return pd.DataFrame(data, columns=tuples)


def create_gene_expression_dataframe() -> pd.DataFrame:
    """Create realistic gene expression DataFrame with both tuple index and columns."""
    return pd.DataFrame(
        {
            (SAMPLE_1, CONDITION_1): [FLOAT_VALUE_1_2, FLOAT_VALUE_2_3, FLOAT_VALUE_3_4],
            (SAMPLE_2, CONDITION_1): [FLOAT_VALUE_1_5, FLOAT_VALUE_2_6, FLOAT_VALUE_3_7],
            (SAMPLE_1, CONDITION_2): [FLOAT_VALUE_0_8, FLOAT_VALUE_1_9, FLOAT_VALUE_2_1],
        },
        index=[
            (GENE_1_UPPER, TYPE_PROTEIN),
            (GENE_1_UPPER, TYPE_RNA),
            (GENE_2_UPPER, TYPE_PROTEIN),
        ],
    )


def create_mixed_data_types_dataframe() -> pd.DataFrame:
    """Create DataFrame with mixed data types for integrity testing."""
    return pd.DataFrame(
        {
            DATA_KEY_INT_COL: [TEST_VALUE_1, TEST_VALUE_2, TEST_VALUE_3],
            DATA_KEY_FLOAT_COL: [FLOAT_VALUE_1_1, FLOAT_VALUE_2_2, FLOAT_VALUE_3_3],
            DATA_KEY_STR_COL: ["a", "b", "c"],
            DATA_KEY_BOOL_COL: [True, False, True],
        },
        index=[ROW_1, ROW_1, ROW_2],
    )


def create_large_duplicates_dataframe(size: int = LARGE_DATASET_SIZE) -> pd.DataFrame:
    """Create DataFrame with many duplicates for performance testing."""
    return pd.DataFrame({COL_1: list(range(size))}, index=[GENE_1] * size)


def assert_dataframe_data_unchanged(
    result_df: pd.DataFrame, original_values: np.ndarray, original_dtypes: pd.Series | None = None
) -> None:
    """Assert that DataFrame data values and types remain unchanged."""
    np.testing.assert_array_equal(result_df.values, original_values)
    if original_dtypes is not None:
        for col in original_dtypes.index:
            assert result_df[col].dtype == original_dtypes[col]


def create_mock_network_with_df(df: pd.DataFrame | None = None) -> Mock:
    """Create mock network object with optional DataFrame export."""
    mock_net = Mock()
    if df is not None:
        mock_net.export_df.return_value = df
    return mock_net


def create_failing_mock_network(error: Exception) -> Mock:
    """Create mock network that raises an error on export_df."""
    mock_net = Mock()
    mock_net.export_df.side_effect = error
    return mock_net


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_network() -> Mock:
    """Create a standard mock network object."""
    return create_mock_network_with_df()


@pytest.fixture
def simple_dataframe() -> pd.DataFrame:
    """Create a simple test DataFrame."""
    return create_simple_dataframe()


@pytest.fixture
def gene_expression_dataframe() -> pd.DataFrame:
    """Create realistic gene expression DataFrame."""
    return create_gene_expression_dataframe()


@pytest.fixture
def mixed_types_dataframe() -> pd.DataFrame:
    """Create DataFrame with mixed data types."""
    return create_mixed_data_types_dataframe()


# =============================================================================
# MAIN FUNCTIONALITY TESTS
# =============================================================================


class TestMainFunctionality:
    """Test core functionality of the main function."""

    @pytest.mark.parametrize(
        "df_factory,description",
        [
            (lambda: create_simple_dataframe(index=[GENE_1, GENE_2]), "no_row_duplicates"),
            (
                lambda: create_tuple_index_dataframe([(GENE_1, TYPE_1), (GENE_2, TYPE_2)]),
                "no_tuple_duplicates",
            ),
            (lambda: create_simple_dataframe(columns=[COL_1, COL_2]), "no_col_duplicates"),
            (lambda: pd.DataFrame(), "empty_dataframe"),
        ],
    )
    def test_no_changes_when_no_duplicates(
        self, df_factory: callable, description: str, mock_network: Mock
    ):
        """Test DataFrames without duplicates remain unchanged."""
        df = df_factory()
        original_df = df.copy()

        result = main(mock_network, df)

        pd.testing.assert_frame_equal(result, original_df)

    @pytest.mark.parametrize(
        "axis,duplicates,expected,description",
        [
            (
                "rows",
                [GENE_1, GENE_1, GENE_2],
                [GENE_1 + SUFFIX_1, GENE_1 + SUFFIX_2, GENE_2 + SUFFIX_3],
                "row_duplicates",
            ),
            (
                "cols",
                [COL_1, COL_1, COL_2],
                [COL_1 + SUFFIX_1, COL_1 + SUFFIX_2, COL_2 + SUFFIX_3],
                "col_duplicates",
            ),
        ],
    )
    def test_string_duplicates_handling(
        self,
        axis: str,
        duplicates: list[str],
        expected: list[str],
        description: str,
        mock_network: Mock,
        capsys: pytest.CaptureFixture[str],
    ):
        """Test string duplicate handling with warning messages."""
        if axis == "rows":
            df = create_simple_dataframe(
                data={COL_1: [TEST_VALUE_1, TEST_VALUE_2, TEST_VALUE_3]}, index=duplicates
            )
            result = main(mock_network, df)
            assert result.index.tolist() == expected

            captured = capsys.readouterr()
            assert WARNING_ROW_UNIQUE in captured.out

        else:  # cols
            df = pd.DataFrame([[TEST_VALUE_1, TEST_VALUE_2, TEST_VALUE_3]], columns=duplicates)
            result = main(mock_network, df)
            assert result.columns.tolist() == expected

            captured = capsys.readouterr()
            assert WARNING_COL_UNIQUE in captured.out

    def test_both_axes_duplicates(self, mock_network: Mock, capsys: pytest.CaptureFixture[str]):
        """Test handling duplicates in both rows and columns."""
        row_duplicates = [GENE_1, GENE_1]
        col_duplicates = [COL_1, COL_1]
        expected_rows = [GENE_1 + SUFFIX_1, GENE_1 + SUFFIX_2]
        expected_cols = [COL_1 + SUFFIX_1, COL_1 + SUFFIX_2]

        df = pd.DataFrame(
            [[TEST_VALUE_1, TEST_VALUE_2], [TEST_VALUE_3, TEST_VALUE_42]],
            index=row_duplicates,
            columns=col_duplicates,
        )

        result = main(mock_network, df)

        assert result.index.tolist() == expected_rows
        assert result.columns.tolist() == expected_cols

        captured = capsys.readouterr()
        assert WARNING_ROW_UNIQUE in captured.out
        assert WARNING_COL_UNIQUE in captured.out

    @pytest.mark.parametrize(
        "tuples,expected,description",
        [
            (
                [(GENE_1, TYPE_1), (GENE_1, TYPE_2), (GENE_2, TYPE_1)],
                [
                    (GENE_1 + SUFFIX_1, TYPE_1),
                    (GENE_1 + SUFFIX_2, TYPE_2),
                    (GENE_2 + SUFFIX_3, TYPE_1),
                ],
                "tuple_duplicates",
            ),
            (
                [(GENE_1, TYPE_1, "extra"), (GENE_1, TYPE_2)],
                [(GENE_1 + SUFFIX_1, TYPE_1, "extra"), (GENE_1 + SUFFIX_2, TYPE_2)],
                "mixed_tuple_lengths",
            ),
            (
                [(TEST_VALUE_1, TYPE_1), (TEST_VALUE_1, TYPE_2), (TEST_VALUE_2, TYPE_1)],
                [("1" + SUFFIX_1, TYPE_1), ("1" + SUFFIX_2, TYPE_2), ("2" + SUFFIX_3, TYPE_1)],
                "numeric_first_elements",
            ),
        ],
    )
    def test_tuple_duplicates_handling(
        self,
        tuples: list[tuple[Any, ...]],
        expected: list[tuple[Any, ...]],
        description: str,
        mock_network: Mock,
    ):
        """Test tuple duplicate handling."""
        df = create_tuple_index_dataframe(tuples)
        result = main(mock_network, df)
        assert result.index.tolist() == expected

    def test_net_vs_df_parameter_handling(self):
        """Test net vs df parameter precedence."""
        # Test df=None uses net.export_df()
        mock_df = create_simple_dataframe(index=[GENE_1, GENE_1])
        mock_net = create_mock_network_with_df(mock_df)

        result = main(mock_net, df=None)
        mock_net.export_df.assert_called_once()
        assert result.index.tolist() == [GENE_1 + SUFFIX_1, GENE_1 + SUFFIX_2]

        # Test df provided doesn't call net.export_df()
        mock_net.reset_mock()
        df = create_simple_dataframe(index=[GENE_2, GENE_2])
        result = main(mock_net, df)
        mock_net.export_df.assert_not_called()
        assert result.index.tolist() == [GENE_2 + SUFFIX_1, GENE_2 + SUFFIX_2]

    def test_in_place_modification(self, mock_network: Mock):
        """Test function modifies original DataFrame in place."""
        df = create_simple_dataframe(index=[GENE_1, GENE_1])
        original_values = df.values.copy()

        result = main(mock_network, df)

        assert result is df  # Same object reference
        assert df.index.tolist() == [GENE_1 + SUFFIX_1, GENE_1 + SUFFIX_2]
        np.testing.assert_array_equal(df.values, original_values)


# =============================================================================
# EDGE CASES AND ERROR HANDLING TESTS
# =============================================================================


class TestEdgeCasesAndErrorHandling:
    """Test edge cases and error handling scenarios."""

    @pytest.mark.parametrize(
        "df_factory,description",
        [
            (lambda: pd.DataFrame(), "completely_empty"),
            (lambda: pd.DataFrame(columns=[COL_1, COL_2]), "empty_with_columns"),
            (lambda: pd.DataFrame(index=[ROW_1, ROW_2]), "empty_with_index"),
            (
                lambda: create_simple_dataframe(data={COL_1: [TEST_VALUE_42]}, index=[ROW_1]),
                "single_cell",
            ),
        ],
    )
    def test_empty_and_minimal_dataframes(
        self, df_factory: callable, description: str, mock_network: Mock
    ):
        """Test empty and minimal DataFrames are handled gracefully."""
        df = df_factory()
        original_df = df.copy()

        result = main(mock_network, df)
        pd.testing.assert_frame_equal(result, original_df)

    @pytest.mark.parametrize(
        "empty_tuple_axis,error_msg,description",
        [
            ("index", ERROR_EMPTY_TUPLES_ROW, "empty_tuple_in_index"),
            ("columns", ERROR_EMPTY_TUPLES_COLUMN, "empty_tuple_in_columns"),
        ],
    )
    def test_empty_tuple_error_handling(
        self, empty_tuple_axis: str, error_msg: str, description: str, mock_network: Mock
    ):
        """Test empty tuples raise clear error messages."""
        if empty_tuple_axis == "index":
            df = create_tuple_index_dataframe([(), (GENE_2, TYPE_2)])
        else:
            df = create_tuple_columns_dataframe([(), (COL_2, "cat2")])

        with pytest.raises(ValueError, match=error_msg):
            main(mock_network, df)

    @pytest.mark.parametrize(
        "setup_func,error_type,error_msg,description",
        [
            (lambda: (None, None), ValueError, ERROR_EITHER_NET_OR_DF, "both_none"),
            (
                lambda: (Mock(**{"export_df.return_value": None}), None),
                AttributeError,
                None,
                "net_returns_none",
            ),
            (
                lambda: (create_failing_mock_network(RuntimeError(ERROR_NETWORK_ERROR)), None),
                RuntimeError,
                ERROR_NETWORK_ERROR,
                "network_export_error",
            ),
        ],
    )
    def test_input_validation(
        self,
        setup_func: callable,
        error_type: type[Exception],
        error_msg: str | None,
        description: str,
    ):
        """Test input validation and error handling."""
        net, df = setup_func()

        if error_msg:
            with pytest.raises(error_type, match=error_msg):
                main(net, df)
        else:
            with pytest.raises(error_type):
                main(net, df)


# =============================================================================
# SPECIAL VALUES TESTS
# =============================================================================


class TestSpecialValues:
    """Test handling of special values and types."""

    @pytest.mark.parametrize(
        "input_tuples,expected,description",
        [
            (
                [(None, TYPE_1), (None, TYPE_2)],
                [("None" + SUFFIX_1, TYPE_1), ("None" + SUFFIX_2, TYPE_2)],
                "none_values",
            ),
            (
                [(TEST_VALUE_1, TYPE_1), (TEST_VALUE_1, TYPE_2), (TEST_VALUE_2, TYPE_1)],
                [("1" + SUFFIX_1, TYPE_1), ("1" + SUFFIX_2, TYPE_2), ("2" + SUFFIX_3, TYPE_1)],
                "integer_values",
            ),
            (
                [(True, TYPE_1), (True, TYPE_2)],
                [("True" + SUFFIX_1, TYPE_1), ("True" + SUFFIX_2, TYPE_2)],
                "boolean_values",
            ),
            (
                [(np.inf, TYPE_1), (np.inf, TYPE_2)],
                [("inf" + SUFFIX_1, TYPE_1), ("inf" + SUFFIX_2, TYPE_2)],
                "infinity_values",
            ),
        ],
    )
    def test_special_values_in_tuples(
        self,
        input_tuples: list[tuple[Any, ...]],
        expected: list[tuple[Any, ...]],
        description: str,
        mock_network: Mock,
    ):
        """Test handling of special values in tuple positions."""
        df = create_tuple_index_dataframe(input_tuples)
        result = main(mock_network, df)
        assert result.index.tolist() == expected

    @pytest.mark.parametrize(
        "input_strings,expected,description",
        [
            (
                [EMPTY_STRING, EMPTY_STRING],
                [EMPTY_STRING + SUFFIX_1, EMPTY_STRING + SUFFIX_2],
                "empty_strings",
            ),
            (
                [WHITESPACE_STRING, WHITESPACE_STRING],
                [WHITESPACE_STRING + SUFFIX_1, WHITESPACE_STRING + SUFFIX_2],
                "whitespace_strings",
            ),
            (
                [HYPHEN_GENE, HYPHEN_GENE, AT_GENE],
                [HYPHEN_GENE + SUFFIX_1, HYPHEN_GENE + SUFFIX_2, AT_GENE + SUFFIX_3],
                "special_chars",
            ),
            (
                [EMOJI_GENE, EMOJI_GENE],
                [EMOJI_GENE + SUFFIX_1, EMOJI_GENE + SUFFIX_2],
                "unicode_emoji",
            ),
        ],
    )
    def test_string_edge_cases(
        self, input_strings: list[str], expected: list[str], description: str, mock_network: Mock
    ):
        """Test edge cases with string names."""
        df = create_simple_dataframe(
            data={COL_1: list(range(len(input_strings)))}, index=input_strings
        )
        result = main(mock_network, df)
        assert result.index.tolist() == expected

    def test_data_integrity_preservation(
        self, mock_network: Mock, mixed_types_dataframe: pd.DataFrame
    ):
        """Test data integrity is preserved during modifications."""
        original_values = mixed_types_dataframe.values.copy()
        original_dtypes = mixed_types_dataframe.dtypes.copy()

        result = main(mock_network, mixed_types_dataframe)

        assert_dataframe_data_unchanged(result, original_values, original_dtypes)
        assert result.index.tolist() == [ROW_1 + SUFFIX_1, ROW_1 + SUFFIX_2, ROW_2 + SUFFIX_3]


# =============================================================================
# HELPER FUNCTIONS TESTS
# =============================================================================


class TestHelperFunctions:
    """Test helper functions independently."""

    @pytest.mark.parametrize(
        "input_list,expected,description",
        [
            (
                [GENE_1, GENE_2, GENE_3],
                [GENE_1 + SUFFIX_1, GENE_2 + SUFFIX_2, GENE_3 + SUFFIX_3],
                "normal_strings",
            ),
            ([], [], "empty_list"),
            ([GENE_1], [GENE_1 + SUFFIX_1], "single_item"),
            (
                [GENE_1, "42", GENE_3],
                [GENE_1 + SUFFIX_1, "42" + SUFFIX_2, GENE_3 + SUFFIX_3],
                "mixed_strings",
            ),
        ],
    )
    def test_add_index_list(self, input_list: list[Any], expected: list[str], description: str):
        """Test add_index_list function."""
        original_list = input_list.copy()
        result = add_index_list(input_list)

        assert result == expected
        # Original list should not be modified
        assert input_list == original_list

    @pytest.mark.parametrize(
        "input_list,has_dupes,description",
        [
            (["a", "b", "a"], True, "string_duplicates"),
            ([TEST_VALUE_1, TEST_VALUE_2, TEST_VALUE_1], True, "integer_duplicates"),
            ([("a", "b"), ("a", "b")], True, "tuple_duplicates"),
            (["a", "b", "c"], False, "no_duplicates"),
            ([TEST_VALUE_1, TEST_VALUE_2, TEST_VALUE_3], False, "no_integer_duplicates"),
            ([], False, "empty_list"),
            (["a"], False, "single_item"),
            ([None, None], True, "none_duplicates"),
        ],
    )
    def test_has_duplicates(self, input_list: list[Any], has_dupes: bool, description: str):
        """Test _has_duplicates function."""
        assert _has_duplicates(input_list) == has_dupes


# =============================================================================
# INTEGRATION SCENARIO TESTS
# =============================================================================


class TestIntegrationScenarios:
    """Integration tests for realistic scenarios."""

    def test_gene_expression_scenario(
        self, mock_network: Mock, gene_expression_dataframe: pd.DataFrame
    ):
        """Test realistic gene expression data scenario."""
        result = main(mock_network, gene_expression_dataframe)

        expected_index = [
            (GENE_1_UPPER + SUFFIX_1, TYPE_PROTEIN),
            (GENE_1_UPPER + SUFFIX_2, TYPE_RNA),
            (GENE_2_UPPER + SUFFIX_3, TYPE_PROTEIN),
        ]
        expected_columns = [
            (SAMPLE_1 + SUFFIX_1, CONDITION_1),
            (SAMPLE_2 + SUFFIX_2, CONDITION_1),
            (SAMPLE_1 + SUFFIX_3, CONDITION_2),
        ]

        assert result.index.tolist() == expected_index
        assert result.columns.tolist() == expected_columns
        np.testing.assert_array_equal(result.values, gene_expression_dataframe.values)

    def test_network_integration_simulation(self):
        """Test integration with network object."""
        test_df = create_simple_dataframe(
            data={
                EXPRESSION_COL: [FLOAT_VALUE_1_5, FLOAT_VALUE_2_3, FLOAT_VALUE_0_8, FLOAT_VALUE_1_2]
            },
            index=[GENE_1_UPPER, GENE_1_UPPER, GENE_2_UPPER, GENE_3],
        )
        mock_net = create_mock_network_with_df(test_df)

        result = main(mock_net)

        assert result.index.tolist() == [
            GENE_1_UPPER + SUFFIX_1,
            GENE_1_UPPER + SUFFIX_2,
            GENE_2_UPPER + SUFFIX_3,
            GENE_3 + SUFFIX_4,
        ]
        mock_net.export_df.assert_called_once()

    def test_performance_with_many_duplicates(self, mock_network: Mock):
        """Test performance with large number of duplicates."""
        df = create_large_duplicates_dataframe()
        result = main(mock_network, df)

        assert len(result.index) == LARGE_DATASET_SIZE
        assert len(set(result.index)) == LARGE_DATASET_SIZE  # All unique
        assert result.index[0] == GENE_1 + SUFFIX_1
        assert result.index[-1] == f"{GENE_1}-{LARGE_DATASET_SIZE}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
