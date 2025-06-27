"""
Unit tests for proc_df_labels module with improved robustness and maintainability.

This module provides comprehensive testing for DataFrame label processing functions
including tuple string conversion, numeric to string conversion, and edge case handling.
"""

from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd
import pytest


# =============================================================================
# MODULE CONSTANTS AND CONFIGURATION
# =============================================================================

# Path configuration
SRC_ROOT = Path(__file__).parents[3] / "src"
sys.path.insert(0, str(SRC_ROOT))

# Test data constants - Basic DataFrames
BASIC_STRING_DF = pd.DataFrame(
    {"col1": [1, 2, 3], "col2": [4, 5, 6]}, index=["row1", "row2", "row3"]
)

NUMERIC_INDEX_DF = pd.DataFrame({"col1": [1, 2, 3], "col2": [4, 5, 6]}, index=[0, 1, 2])

NUMERIC_COLUMNS_DF = pd.DataFrame([[1, 2, 3], [4, 5, 6]], columns=[0, 1, 2])

# Tuple-related test data
TUPLE_STRING_INDEX_DF = pd.DataFrame(
    {"col1": [1, 2, 3], "col2": [4, 5, 6]},
    index=["('gene1', 'type1')", "('gene2', 'type2')", "('gene3', 'type1')"],
)

TUPLE_STRING_COLUMNS_DF = pd.DataFrame(
    {
        "('col1', 'cat1')": [1, 2, 3],
        "('col2', 'cat2')": [4, 5, 6],
        "('col3', 'cat1')": [7, 8, 9],
    },
    index=["row1", "row2", "row3"],
)

BOTH_TUPLE_STRINGS_DF = pd.DataFrame(
    {"('col1', 'cat1')": [1, 2], "('col2', 'cat2')": [3, 4]},
    index=["('row1', 'type1')", "('row2', 'type2')"],
)

# Special numeric types test data
FLOAT_INDEX_DF = pd.DataFrame({"col1": [1, 2], "col2": [3, 4]}, index=[0.5, 1.5])

NUMPY_INT64_DF = pd.DataFrame({"col1": [1, 2, 3]}, index=[np.int64(0), np.int64(1), np.int64(2)])

NEGATIVE_INDEX_DF = pd.DataFrame({"col1": [1, 2]}, index=[-1, -2])

LARGE_NUMBER_DF = pd.DataFrame({"col1": [1]}, index=[999999999999999])

# Edge case test data
EMPTY_DF = pd.DataFrame()

SINGLE_CELL_STRING_DF = pd.DataFrame({"col1": [42]}, index=["row1"])

SINGLE_CELL_NUMERIC_DF = pd.DataFrame([[42]], index=[0], columns=[1])

ACTUAL_TUPLE_INDEX_DF = pd.DataFrame(
    {"col1": [1, 2]}, index=[("gene1", "type1"), ("gene2", "type2")]
)

# Malformed tuple string test data
MALFORMED_TUPLE_STRINGS = [
    "(gene1, type1",  # Missing closing parenthesis
    "gene2, type2)",  # Missing opening parenthesis
    "(gene3)",  # No comma
    "gene4, type4",  # No parentheses
]

MALFORMED_TUPLE_DF = pd.DataFrame({"col1": [1, 2, 3, 4]}, index=MALFORMED_TUPLE_STRINGS)

# Complex tuple test data
COMPLEX_TUPLE_STRINGS = [
    "('gene1', 'type1')",
    "('gene with space', 'type2')",
    "('gene1', 1)",
    "(2, 'type2')",
    "('gene1', 'type1', 'cat1')",
]

INVALID_TUPLE_STRINGS = [
    "('gene1', 'type1')",
    "('gene2', 'type2']",  # Mismatched brackets
]

# Mixed data scenarios
MIXED_CONVERSION_DF = pd.DataFrame(
    {
        "col1": [1, 2],
        "('col2', 'cat1')": [3, 4],
    },
    index=[1, "('row2', 'type2')"],
)

MIXED_STRING_TUPLE_DF = pd.DataFrame(
    {"col1": [1, 2, 3]}, index=["regular_gene", "('gene2', 'type2')", "another_gene"]
)

# Boolean and special type test data
BOOLEAN_INDEX_DF = pd.DataFrame({"col1": [1, 2]}, index=[True, False])

NONE_INDEX_DF = pd.DataFrame({"col1": [1, 2]}, index=[None, "gene2"])

# Error messages
TYPE_ERROR_MSG = "Expected pandas DataFrame"
TUPLE_PARSE_ERROR_MSG = "Failed to parse tuple strings"
INVALID_TUPLE_ERROR_MSG = "Invalid tuple string"

# Test constants for parameterized tests
NUMERIC_TYPES = [int, float, np.int64, np.float64]
VALID_TUPLE_STRINGS = [
    "('gene1', 'type1')",
    "('gene with space', 'type2')",
    "('gene1', 1)",
    "(2, 'type2')",
    "('gene1', 'type1', 'cat1')",
]

EXPECTED_TUPLES = [
    ("gene1", "type1"),
    ("gene with space", "type2"),
    ("gene1", 1),
    (2, "type2"),
    ("gene1", "type1", "cat1"),
]

# Statistical tolerance for numerical comparisons
ARRAY_COMPARISON_TOLERANCE = 1e-10


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================


def create_test_dataframe(
    data: Any = None,
    index: list[Any] | None = None,
    columns: list[Any] | None = None,
    shape: tuple[int, int] | None = None,
) -> pd.DataFrame:
    """
    Create test DataFrame with specified properties.

    Args:
        data: DataFrame data (defaults to incremental integers)
        index: Index values
        columns: Column values
        shape: DataFrame shape as (rows, cols)

    Returns:
        Test DataFrame with specified structure
    """
    if shape:
        rows, cols = shape
        if data is None:
            data = np.arange(rows * cols).reshape(rows, cols)
        if index is None:
            index = list(range(rows))
        if columns is None:
            columns = list(range(cols))

    return pd.DataFrame(data=data, index=index, columns=columns)


def assert_index_conversion(
    result: pd.DataFrame, expected_index: list[Any], expected_types: type | tuple[type, ...]
) -> None:
    """Assert that index was converted correctly."""
    assert result.index.tolist() == expected_index
    if not isinstance(expected_types, tuple):
        expected_types = (expected_types,)
    assert all(isinstance(idx, expected_types) for idx in result.index)


def assert_columns_conversion(
    result: pd.DataFrame, expected_columns: list[Any], expected_types: type | tuple[type, ...]
) -> None:
    """Assert that columns were converted correctly."""
    assert result.columns.tolist() == expected_columns
    if not isinstance(expected_types, tuple):
        expected_types = (expected_types,)
    assert all(isinstance(col, expected_types) for col in result.columns)


def assert_dataframe_data_unchanged(original: pd.DataFrame, result: pd.DataFrame) -> None:
    """Assert that DataFrame data values remain unchanged."""
    if not original.empty and not result.empty:
        np.testing.assert_array_equal(original.values, result.values)


def assert_no_conversion_occurred(original: pd.DataFrame, result: pd.DataFrame) -> None:
    """Assert that no conversion occurred in the DataFrame."""
    pd.testing.assert_frame_equal(result, original)


def create_large_test_dataframe(
    n_rows: int = 1000, n_cols: int = 50, use_tuple_strings: bool = True
) -> pd.DataFrame:
    """Create large DataFrame for performance testing."""
    if use_tuple_strings:
        index = [f"('gene{i}', 'type{i % 5}')" for i in range(n_rows)]
        columns = [f"('sample{i}', 'condition{i % 3}')" for i in range(n_cols)]
    else:
        index = list(range(n_rows))
        columns = list(range(n_cols))

    data = np.random.randn(n_rows, n_cols)
    return pd.DataFrame(data, index=index, columns=columns)


def validate_tuple_conversion_correctness(result: pd.DataFrame, axis: str = "both") -> None:
    """Validate that tuple conversions were performed correctly."""
    if axis in ("both", "index"):
        assert all(isinstance(idx, tuple) for idx in result.index)
    if axis in ("both", "columns"):
        assert all(isinstance(col, tuple) for col in result.columns)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def basic_string_df():
    """Fixture providing basic DataFrame with string labels."""
    return BASIC_STRING_DF.copy()


@pytest.fixture
def numeric_index_df():
    """Fixture providing DataFrame with numeric index."""
    return NUMERIC_INDEX_DF.copy()


@pytest.fixture
def tuple_string_df():
    """Fixture providing DataFrame with tuple string index."""
    return TUPLE_STRING_INDEX_DF.copy()


@pytest.fixture
def empty_df():
    """Fixture providing empty DataFrame."""
    return EMPTY_DF.copy()


@pytest.fixture
def mixed_conversion_df():
    """Fixture providing DataFrame requiring mixed conversions."""
    return MIXED_CONVERSION_DF.copy()


# =============================================================================
# IMPORT AND BASIC FUNCTIONALITY
# =============================================================================

from celldega.clust_old.data_io.proc_df_labels import main


# =============================================================================
# BASIC FUNCTIONALITY TESTS
# =============================================================================


class TestProcDfLabelsBasicFunctionality:
    """Test core functionality of proc_df_labels.main function."""

    def test_no_changes_needed_with_string_labels(self, basic_string_df):
        """Test DataFrame with string labels that need no conversion."""
        original_df = basic_string_df.copy()
        result = main(basic_string_df)

        assert_no_conversion_occurred(original_df, result)
        assert_index_conversion(result, ["row1", "row2", "row3"], str)
        assert_columns_conversion(result, ["col1", "col2"], str)

    @pytest.mark.parametrize("numeric_type", NUMERIC_TYPES)
    def test_numeric_to_string_conversion_index(self, numeric_type):
        """Test conversion of various numeric types to strings for index."""
        index_values = [numeric_type(i) for i in range(3)]
        df = create_test_dataframe(
            data=[[1, 2], [3, 4], [5, 6]], index=index_values, columns=["col1", "col2"]
        )

        result = main(df)

        expected_index = [str(val) for val in index_values]
        assert_index_conversion(result, expected_index, str)

    @pytest.mark.parametrize("numeric_type", NUMERIC_TYPES)
    def test_numeric_to_string_conversion_columns(self, numeric_type):
        """Test conversion of various numeric types to strings for columns."""
        column_values = [numeric_type(i) for i in range(3)]
        df = create_test_dataframe(
            data=[[1, 2, 3], [4, 5, 6]], index=["row1", "row2"], columns=column_values
        )

        result = main(df)

        expected_columns = [str(val) for val in column_values]
        assert_columns_conversion(result, expected_columns, str)

    @pytest.mark.parametrize(
        "tuple_string,expected_tuple", zip(VALID_TUPLE_STRINGS, EXPECTED_TUPLES, strict=False)
    )
    def test_tuple_string_to_tuple_conversion(self, tuple_string, expected_tuple):
        """Test conversion of valid tuple strings to actual tuples."""
        df = create_test_dataframe(data=[[1]], index=[tuple_string], columns=["col1"])

        result = main(df)

        assert_index_conversion(result, [expected_tuple], tuple)

    def test_both_index_and_columns_tuple_conversion(self):
        """Test conversion when both index and columns have tuple strings."""
        df = BOTH_TUPLE_STRINGS_DF.copy()
        result = main(df)

        expected_index = [("row1", "type1"), ("row2", "type2")]
        expected_columns = [("col1", "cat1"), ("col2", "cat2")]

        assert_index_conversion(result, expected_index, tuple)
        assert_columns_conversion(result, expected_columns, tuple)

    def test_function_modifies_dataframe_in_place(self):
        """Test that function modifies the original DataFrame in-place."""
        df = NUMERIC_INDEX_DF.copy()
        original_values = df.values.copy()

        result = main(df)

        # Both original and result should have string indices
        assert_index_conversion(df, ["0", "1", "2"], str)
        assert_index_conversion(result, ["0", "1", "2"], str)

        # Data values should remain unchanged
        assert_dataframe_data_unchanged(pd.DataFrame(original_values), df)


# =============================================================================
# PARAMETER VALIDATION AND ERROR HANDLING TESTS
# =============================================================================


class TestProcDfLabelsParameterValidation:
    """Test parameter validation and error handling."""

    @pytest.mark.parametrize(
        "invalid_input,expected_error",
        [
            (None, TypeError),
            ("not a dataframe", TypeError),
            (42, TypeError),
            ([], TypeError),
            ({}, TypeError),
        ],
    )
    def test_invalid_input_type_raises_error(self, invalid_input, expected_error):
        """Test that invalid input types raise TypeError."""
        with pytest.raises(expected_error, match=TYPE_ERROR_MSG):
            main(invalid_input)

    def test_malformed_tuple_strings_raise_error(self):
        """Test that malformed tuple strings raise appropriate errors."""
        df = pd.DataFrame({"col1": [1, 2]}, index=INVALID_TUPLE_STRINGS)

        with pytest.raises((SyntaxError, ValueError)):
            main(df)

    def test_empty_dataframe_handled_gracefully(self, empty_df):
        """Test that empty DataFrame is handled without errors."""
        result = main(empty_df)

        assert result.empty
        assert_no_conversion_occurred(empty_df, result)


# =============================================================================
# EDGE CASES AND BOUNDARY CONDITIONS TESTS
# =============================================================================


class TestProcDfLabelsEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_single_cell_dataframe_string_labels(self):
        """Test single cell DataFrame with string labels."""
        df = SINGLE_CELL_STRING_DF.copy()
        result = main(df)

        assert_index_conversion(result, ["row1"], str)
        assert_columns_conversion(result, ["col1"], str)

    def test_single_cell_dataframe_numeric_labels(self):
        """Test single cell DataFrame with numeric labels."""
        df = SINGLE_CELL_NUMERIC_DF.copy()
        result = main(df)

        assert_index_conversion(result, ["0"], str)
        assert_columns_conversion(result, ["1"], str)

    def test_already_tuple_indices_unchanged(self):
        """Test DataFrame with actual tuple indices remains unchanged."""
        df = ACTUAL_TUPLE_INDEX_DF.copy()
        result = main(df)

        expected_index = [("gene1", "type1"), ("gene2", "type2")]
        assert_index_conversion(result, expected_index, tuple)

    def test_malformed_tuple_strings_no_conversion(self):
        """Test that malformed tuple-like strings are not converted."""
        df = MALFORMED_TUPLE_DF.copy()
        result = main(df)

        # Should not convert malformed strings
        assert_index_conversion(result, MALFORMED_TUPLE_STRINGS, str)

    @pytest.mark.parametrize(
        "test_index,expected_index",
        [
            ([-1, -2], ["-1", "-2"]),
            ([0, 0.0], ["0.0", "0.0"]),  # Both become 0.0 due to pandas type coercion
            ([999999999999999], ["999999999999999"]),
        ],
    )
    def test_special_numeric_values_conversion(self, test_index, expected_index):
        """Test conversion of special numeric values."""
        # Create data with correct dimensions: rows x columns
        data = [[i] for i in range(len(test_index))]
        df = create_test_dataframe(data=data, index=test_index, columns=["col1"])

        result = main(df)
        assert_index_conversion(result, expected_index, str)

    def test_mixed_string_and_tuple_indices_first_element_rule(self):
        """Test that first element determines conversion behavior."""
        df = MIXED_STRING_TUPLE_DF.copy()
        result = main(df)

        # First element is regular string, so no conversion occurs
        expected_index = ["regular_gene", "('gene2', 'type2')", "another_gene"]
        assert_index_conversion(result, expected_index, str)

    def test_first_element_determines_all_conversions(self):
        """Test that first element determines conversion for all elements."""
        df = create_test_dataframe(
            data=[[1], [2], [3]], index=[42, "string_row", ("tuple", "row")], columns=["col1"]
        )

        result = main(df)

        # All should become strings because first element is numeric
        expected_index = ["42", "string_row", "('tuple', 'row')"]
        assert_index_conversion(result, expected_index, str)


# =============================================================================
# TYPE HANDLING AND SPECIAL CASES TESTS
# =============================================================================


class TestProcDfLabelsTypeHandling:
    """Test handling of various data types and special cases."""

    def test_boolean_indices_not_converted(self):
        """Test that boolean indices are not converted to strings."""
        df = BOOLEAN_INDEX_DF.copy()
        result = main(df)

        # Boolean is not in the conversion types, so should remain unchanged
        assert result.index.tolist() == [True, False]

    def test_none_values_handled_gracefully(self):
        """Test that None values are handled without errors."""
        df = NONE_INDEX_DF.copy()
        result = main(df)

        # None doesn't trigger conversions, should remain unchanged
        assert result.index.tolist() == [None, "gene2"]

    def test_multiindex_dataframe_unchanged(self):
        """Test that MultiIndex DataFrame remains unchanged."""
        arrays = [["gene1", "gene1", "gene2", "gene2"], ["type1", "type2", "type1", "type2"]]
        index = pd.MultiIndex.from_arrays(arrays, names=["gene", "type"])
        df = pd.DataFrame({"col1": [1, 2, 3, 4]}, index=index)

        result = main(df)

        # MultiIndex should remain unchanged
        pd.testing.assert_index_equal(result.index, df.index)

    def test_datetime_index_handled_gracefully(self):
        """Test that datetime index is handled without errors."""
        dates = pd.date_range("2023-01-01", periods=3)
        df = pd.DataFrame({"col1": [1, 2, 3]}, index=dates)

        result = main(df)

        # Datetime doesn't trigger conversions, should remain unchanged
        pd.testing.assert_index_equal(result.index, df.index)

    def test_object_dtype_with_mixed_types(self):
        """Test index with mixed object types."""
        df = create_test_dataframe(
            data=[[1], [2], [3]], index=["string", 42, ("tuple", "element")], columns=["col1"]
        )

        result = main(df)

        # First element is string, so no conversion
        expected_index = ["string", 42, ("tuple", "element")]
        assert result.index.tolist() == expected_index


# =============================================================================
# COMPLEX SCENARIOS AND INTEGRATION TESTS
# =============================================================================


class TestProcDfLabelsComplexScenarios:
    """Test complex scenarios and integration with realistic data."""

    def test_gene_expression_data_scenario(self):
        """Test typical gene expression data with tuple gene names."""
        df = pd.DataFrame(
            {
                "('sample1', 'condition1')": [1.2, 2.3, 3.4],
                "('sample2', 'condition1')": [1.5, 2.6, 3.7],
                "('sample3', 'condition2')": [0.8, 1.9, 2.1],
            },
            index=["('GENE1', 'protein')", "('GENE2', 'rna')", "('GENE3', 'protein')"],
        )

        result = main(df)

        expected_index = [("GENE1", "protein"), ("GENE2", "rna"), ("GENE3", "protein")]
        expected_columns = [
            ("sample1", "condition1"),
            ("sample2", "condition1"),
            ("sample3", "condition2"),
        ]

        assert_index_conversion(result, expected_index, tuple)
        assert_columns_conversion(result, expected_columns, tuple)

    def test_numeric_data_with_conversions(self):
        """Test numeric data that needs string conversion."""
        df = create_test_dataframe(
            data=np.random.randn(5, 3), index=[0, 1, 2, 3, 4], columns=[100, 200, 300]
        )
        original_values = df.values.copy()

        result = main(df)

        assert_index_conversion(result, ["0", "1", "2", "3", "4"], str)
        assert_columns_conversion(result, ["100", "200", "300"], str)
        assert_dataframe_data_unchanged(pd.DataFrame(original_values), result)

    def test_mixed_realistic_scenario(self, mixed_conversion_df):
        """Test mixed scenario with some conversions needed."""
        result = main(mixed_conversion_df)

        # First element determines behavior
        # Index: first is numeric (1), so all convert to strings
        # Columns: first is string ("col1"), so no conversion
        expected_index = ["1", "('row2', 'type2')"]
        expected_columns = ["col1", "('col2', 'cat1')"]

        assert_index_conversion(result, expected_index, str)
        assert result.columns.tolist() == expected_columns

    def test_large_dataframe_performance(self):
        """Test performance with larger DataFrame."""
        n_rows, n_cols = 1000, 50
        df = create_large_test_dataframe(n_rows, n_cols, use_tuple_strings=True)

        result = main(df)

        # Verify conversions occurred correctly
        validate_tuple_conversion_correctness(result, axis="both")
        assert len(result) == n_rows
        assert len(result.columns) == n_cols


# =============================================================================
# ERROR HANDLING AND ROBUSTNESS TESTS
# =============================================================================


class TestProcDfLabelsErrorHandling:
    """Test error handling and robustness scenarios."""

    def test_malformed_tuple_with_syntax_error_raises_exception(self):
        """Test that malformed tuple strings raise appropriate exceptions."""
        df = pd.DataFrame(
            {"col1": [1, 2]},
            index=["('gene1', 'type1')", "('gene2', 'type2']"],  # Mismatched brackets
        )

        with pytest.raises((SyntaxError, ValueError)):
            main(df)

    def test_valid_tuple_with_trailing_comma(self):
        """Test valid tuple syntax with trailing comma."""
        df = pd.DataFrame({"col1": [1]}, index=["('gene1', 'type1', )"])

        result = main(df)

        expected_index = [("gene1", "type1")]
        assert_index_conversion(result, expected_index, tuple)

    def test_very_long_tuple_strings(self):
        """Test handling of very long tuple strings."""
        long_tuple_str = "('" + "gene" * 1000 + "', '" + "type" * 1000 + "')"
        df = create_test_dataframe(data=[[1]], index=[long_tuple_str], columns=["col1"])

        result = main(df)

        expected_tuple = ("gene" * 1000, "type" * 1000)
        assert_index_conversion(result, [expected_tuple], tuple)

    def test_unicode_in_tuple_strings(self):
        """Test tuple strings with unicode characters."""
        df = create_test_dataframe(
            data=[[1], [2]],
            index=["('gene_α', 'type_β')", "('gene_γ', 'type_δ')"],
            columns=["col1"],
        )

        result = main(df)

        expected_index = [("gene_α", "type_β"), ("gene_γ", "type_δ")]
        assert_index_conversion(result, expected_index, tuple)

    @pytest.mark.parametrize(
        "problematic_data",
        [
            {"index": [float("inf")], "columns": ["col1"]},
            {"index": [float("nan")], "columns": ["col1"]},
            {"index": ["normal"], "columns": [float("inf")]},
        ],
    )
    def test_special_float_values_handling(self, problematic_data):
        """Test handling of special float values like inf and nan."""
        df = create_test_dataframe(data=[[1]], **problematic_data)

        # Should handle gracefully or convert appropriately
        result = main(df)
        assert isinstance(result, pd.DataFrame)

    def test_extremely_large_dataframe_memory_efficiency(self):
        """Test memory efficiency with very large DataFrames."""
        # Create smaller test for CI/CD limitations, but test the concept
        n_rows, n_cols = 100, 20
        df = create_large_test_dataframe(n_rows, n_cols, use_tuple_strings=True)

        result = main(df)

        # Should complete without memory errors
        validate_tuple_conversion_correctness(result, axis="both")
        assert result.shape == (n_rows, n_cols)


# =============================================================================
# BEHAVIORAL CONSISTENCY TESTS
# =============================================================================


class TestProcDfLabelsBehavioralConsistency:
    """Test behavioral consistency and edge case handling."""

    def test_first_element_tuple_string_converts_all(self):
        """Test that if first element is tuple string, all get converted."""
        df = create_test_dataframe(
            data=[[1], [2], [3]],
            index=["('gene1', 'type1')", "('gene2', 'type2')", "('gene3', 'type3')"],
            columns=["col1"],
        )

        result = main(df)

        expected_index = [("gene1", "type1"), ("gene2", "type2"), ("gene3", "type3")]
        assert_index_conversion(result, expected_index, tuple)

    def test_consistency_across_multiple_calls(self):
        """Test that function behavior is consistent across multiple calls."""
        df = TUPLE_STRING_INDEX_DF.copy()

        result1 = main(df.copy())
        result2 = main(df.copy())

        pd.testing.assert_frame_equal(result1, result2)

    def test_idempotency_with_already_processed_data(self):
        """Test that applying function twice gives same result."""
        df = TUPLE_STRING_INDEX_DF.copy()

        result1 = main(df.copy())
        result2 = main(result1.copy())

        pd.testing.assert_frame_equal(result1, result2)

    @pytest.mark.parametrize("axis_to_test", ["index", "columns"])
    def test_axis_independence(self, axis_to_test):
        """Test that index and column processing are independent."""
        if axis_to_test == "index":
            df = pd.DataFrame(
                {"normal_col": [1, 2]}, index=["('gene1', 'type1')", "('gene2', 'type2')"]
            )
            result = main(df)
            assert all(isinstance(idx, tuple) for idx in result.index)
            assert all(isinstance(col, str) for col in result.columns)
        else:
            df = pd.DataFrame({"('col1', 'cat1')": [1, 2]}, index=["normal_row1", "normal_row2"])
            result = main(df)
            assert all(isinstance(idx, str) for idx in result.index)
            assert all(isinstance(col, tuple) for col in result.columns)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
