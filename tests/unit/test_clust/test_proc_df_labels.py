from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest


# Add the source directory to the path for imports
sys.path.insert(0, str(Path(__file__).parents[3] / "src"))

from celldega.clust.data.proc_df_labels import main


class TestProcDfLabelsBasic:
    """Test basic functionality of proc_df_labels.main function."""

    def test_no_changes_needed_string_labels(self):
        """Test DataFrame with string labels that need no conversion."""
        df = pd.DataFrame({"col1": [1, 2, 3], "col2": [4, 5, 6]}, index=["row1", "row2", "row3"])
        original_df = df.copy()

        result = main(df)

        # Should return the same DataFrame
        pd.testing.assert_frame_equal(result, original_df)
        assert result.index.tolist() == ["row1", "row2", "row3"]
        assert result.columns.tolist() == ["col1", "col2"]

    def test_convert_string_tuples_to_actual_tuples_rows(self):
        """Test conversion of string representations of tuples to actual tuples for rows."""
        df = pd.DataFrame(
            {"col1": [1, 2, 3], "col2": [4, 5, 6]},
            index=["('gene1', 'type1')", "('gene2', 'type2')", "('gene3', 'type1')"],
        )

        result = main(df)

        # Should convert string tuples to actual tuples
        expected_index = [("gene1", "type1"), ("gene2", "type2"), ("gene3", "type1")]
        assert result.index.tolist() == expected_index
        assert all(isinstance(idx, tuple) for idx in result.index)

    def test_convert_string_tuples_to_actual_tuples_columns(self):
        """Test conversion of string representations of tuples to actual tuples for columns."""
        df = pd.DataFrame(
            {
                "('col1', 'cat1')": [1, 2, 3],
                "('col2', 'cat2')": [4, 5, 6],
                "('col3', 'cat1')": [7, 8, 9],
            },
            index=["row1", "row2", "row3"],
        )

        result = main(df)

        # Should convert string tuples to actual tuples
        expected_columns = [("col1", "cat1"), ("col2", "cat2"), ("col3", "cat1")]
        assert result.columns.tolist() == expected_columns
        assert all(isinstance(col, tuple) for col in result.columns)

    def test_convert_both_rows_and_columns_tuples(self):
        """Test conversion when both rows and columns have string tuples."""
        df = pd.DataFrame(
            {"('col1', 'cat1')": [1, 2], "('col2', 'cat2')": [3, 4]},
            index=["('row1', 'type1')", "('row2', 'type2')"],
        )

        result = main(df)

        expected_index = [("row1", "type1"), ("row2", "type2")]
        expected_columns = [("col1", "cat1"), ("col2", "cat2")]

        assert result.index.tolist() == expected_index
        assert result.columns.tolist() == expected_columns

    def test_convert_numeric_indices_to_strings_rows(self):
        """Test conversion of numeric row indices to strings."""
        df = pd.DataFrame({"col1": [1, 2, 3], "col2": [4, 5, 6]}, index=[0, 1, 2])

        result = main(df)

        assert result.index.tolist() == ["0", "1", "2"]
        assert all(isinstance(idx, str) for idx in result.index)

    def test_convert_numeric_indices_to_strings_columns(self):
        """Test conversion of numeric column indices to strings."""
        df = pd.DataFrame([[1, 2, 3], [4, 5, 6]], columns=[0, 1, 2])

        result = main(df)

        assert result.columns.tolist() == ["0", "1", "2"]
        assert all(isinstance(col, str) for col in result.columns)

    def test_convert_float_indices_to_strings(self):
        """Test conversion of float indices to strings."""
        df = pd.DataFrame({"col1": [1, 2], "col2": [3, 4]}, index=[0.5, 1.5])

        result = main(df)

        assert result.index.tolist() == ["0.5", "1.5"]
        assert all(isinstance(idx, str) for idx in result.index)

    def test_convert_numpy_int64_indices_to_strings(self):
        """Test conversion of numpy int64 indices to strings."""
        df = pd.DataFrame({"col1": [1, 2, 3]}, index=[np.int64(0), np.int64(1), np.int64(2)])

        result = main(df)

        assert result.index.tolist() == ["0", "1", "2"]
        assert all(isinstance(idx, str) for idx in result.index)

    def test_mixed_conversions_fixed(self):
        """Test DataFrame requiring mixed conversions - CORRECTED VERSION."""
        # If first element is numeric, it converts ALL to strings
        df = pd.DataFrame(
            {
                "col1": [1, 2],
                "('col2', 'cat1')": [3, 4],  # Column conversion based on first column
            },
            index=[1, "('row2', 'type2')"],  # Row conversion based on first row
        )

        result = main(df)

        # Both indices should be converted to strings since first is numeric
        expected_index = ["1", "('row2', 'type2')"]
        # Columns remain unchanged since first column is string, not tuple string
        expected_columns = ["col1", "('col2', 'cat1')"]

        assert result.index.tolist() == expected_index
        assert result.columns.tolist() == expected_columns

    def test_original_dataframe_modified_in_place(self):
        """Test that the function DOES modify the original DataFrame in-place."""
        df = pd.DataFrame({"col1": [1, 2]}, index=[0, 1])
        original_values = df.values.copy()  # Save the data values

        result = main(df)

        # The function modifies the original DataFrame in-place
        # Both the original df and result should have string indices now
        assert df.index.tolist() == ["0", "1"]
        assert result.index.tolist() == ["0", "1"]

        # But the data values should remain the same
        np.testing.assert_array_equal(df.values, original_values)
        np.testing.assert_array_equal(result.values, original_values)


class TestProcDfLabelsEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_dataframe_handled_gracefully(self):
        """Test with empty DataFrame - ADJUSTED for improved behavior."""
        df = pd.DataFrame()

        # ADJUSTED: The optimized function handles empty DataFrames gracefully
        # instead of crashing like the original
        result = main(df)

        # Should return the empty DataFrame unchanged
        assert result.empty
        pd.testing.assert_frame_equal(result, df)

    def test_single_cell_dataframe_string(self):
        """Test with single cell DataFrame with string labels."""
        df = pd.DataFrame({"col1": [42]}, index=["row1"])

        result = main(df)

        assert result.index.tolist() == ["row1"]
        assert result.columns.tolist() == ["col1"]

    def test_single_cell_dataframe_numeric(self):
        """Test with single cell DataFrame with numeric labels."""
        df = pd.DataFrame([[42]], index=[0], columns=[1])

        result = main(df)

        assert result.index.tolist() == ["0"]
        assert result.columns.tolist() == ["1"]

    def test_already_tuple_indices(self):
        """Test DataFrame that already has actual tuple indices."""
        df = pd.DataFrame({"col1": [1, 2]}, index=[("gene1", "type1"), ("gene2", "type2")])

        result = main(df)

        # Should remain as tuples
        assert result.index.tolist() == [("gene1", "type1"), ("gene2", "type2")]
        assert all(isinstance(idx, tuple) for idx in result.index)

    def test_malformed_tuple_strings(self):
        """Test with malformed tuple-like strings."""
        df = pd.DataFrame(
            {"col1": [1, 2, 3, 4]},
            index=[
                "(gene1, type1",  # Missing closing parenthesis
                "gene2, type2)",  # Missing opening parenthesis
                "(gene3)",  # No comma
                "gene4, type4",  # No parentheses
            ],
        )

        result = main(df)

        # Should not convert malformed strings
        expected_index = ["(gene1, type1", "gene2, type2)", "(gene3)", "gene4, type4"]
        assert result.index.tolist() == expected_index
        assert all(isinstance(idx, str) for idx in result.index)

    def test_tuple_strings_with_nested_quotes(self):
        """Test tuple strings containing quoted elements."""
        df = pd.DataFrame(
            {"col1": [1, 2]}, index=["('gene1', 'type1')", "('gene with space', 'type2')"]
        )

        result = main(df)

        expected_index = [("gene1", "type1"), ("gene with space", "type2")]
        assert result.index.tolist() == expected_index

    def test_tuple_strings_with_numbers(self):
        """Test tuple strings containing numbers."""
        df = pd.DataFrame({"col1": [1, 2]}, index=["('gene1', 1)", "(2, 'type2')"])

        result = main(df)

        expected_index = [("gene1", 1), (2, "type2")]
        assert result.index.tolist() == expected_index

    def test_complex_tuple_strings(self):
        """Test tuple strings with more than 2 elements."""
        df = pd.DataFrame(
            {"col1": [1, 2]}, index=["('gene1', 'type1', 'cat1')", "('gene2', 'type2', 'cat2')"]
        )

        result = main(df)

        expected_index = [("gene1", "type1", "cat1"), ("gene2", "type2", "cat2")]
        assert result.index.tolist() == expected_index

    def test_mixed_string_and_tuple_indices(self):
        """Test mix of regular strings and tuple strings."""
        df = pd.DataFrame(
            {"col1": [1, 2, 3]}, index=["regular_gene", "('gene2', 'type2')", "another_gene"]
        )

        result = main(df)

        # Only the first element is checked, so if it's not a tuple string,
        # no conversion happens for any of them
        expected_index = ["regular_gene", "('gene2', 'type2')", "another_gene"]
        assert result.index.tolist() == expected_index

    def test_negative_numbers(self):
        """Test with negative numeric indices."""
        df = pd.DataFrame({"col1": [1, 2]}, index=[-1, -2])

        result = main(df)

        assert result.index.tolist() == ["-1", "-2"]

    def test_zero_values_corrected(self):
        """Test with zero numeric indices - CORRECTED."""
        df = pd.DataFrame({"col1": [1, 2]}, index=[0, 0.0])

        result = main(df)

        # When first element is int, all elements get converted with str()
        # Both 0 and 0.0 become "0.0" when pandas converts the index to float64 first
        assert result.index.tolist() == ["0.0", "0.0"]

    def test_very_large_numbers(self):
        """Test with very large numeric indices."""
        large_num = 999999999999999
        df = pd.DataFrame({"col1": [1]}, index=[large_num])

        result = main(df)

        assert result.index.tolist() == [str(large_num)]


class TestProcDfLabelsTypeHandling:
    """Test various data types and their handling."""

    def test_boolean_indices_not_converted_in_optimized_version(self):
        """Test boolean indices behavior in optimized version - ADJUSTED."""
        df = pd.DataFrame({"col1": [1, 2]}, index=[True, False])

        result = main(df)

        # ADJUSTED: The optimized version uses `int | float | np.int64` which doesn't
        # include bool explicitly, so booleans are NOT converted to strings
        assert result.index.tolist() == [True, False]

    def test_none_values_handled_gracefully(self):
        """Test handling of None values - ADJUSTED for improved behavior."""
        df = pd.DataFrame({"col1": [1, 2]}, index=[None, "gene2"])

        # ADJUSTED: The optimized function handles None gracefully
        # instead of crashing like the original
        result = main(df)

        # Should leave the DataFrame unchanged since None doesn't trigger any conversions
        assert result.index.tolist() == [None, "gene2"]

    def test_multiindex_dataframe(self):
        """Test with MultiIndex DataFrame."""
        arrays = [["gene1", "gene1", "gene2", "gene2"], ["type1", "type2", "type1", "type2"]]
        index = pd.MultiIndex.from_arrays(arrays, names=["gene", "type"])

        df = pd.DataFrame({"col1": [1, 2, 3, 4]}, index=index)

        result = main(df)

        # MultiIndex should remain unchanged
        pd.testing.assert_index_equal(result.index, df.index)

    def test_datetime_index_handled_gracefully(self):
        """Test with datetime index - ADJUSTED for improved behavior."""
        dates = pd.date_range("2023-01-01", periods=3)
        df = pd.DataFrame({"col1": [1, 2, 3]}, index=dates)

        # ADJUSTED: The optimized function handles datetime gracefully
        # instead of crashing like the original
        result = main(df)

        # Should leave the DataFrame unchanged since datetime doesn't trigger conversions
        pd.testing.assert_index_equal(result.index, df.index)

    def test_object_dtype_with_mixed_types(self):
        """Test index with mixed object types."""
        df = pd.DataFrame({"col1": [1, 2, 3]}, index=["string", 42, ("tuple", "element")])

        result = main(df)

        # Only checks first element, which is string, so no conversion
        expected_index = ["string", 42, ("tuple", "element")]
        assert result.index.tolist() == expected_index


class TestProcDfLabelsIntegration:
    """Integration tests with realistic data scenarios."""

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

        assert result.index.tolist() == expected_index
        assert result.columns.tolist() == expected_columns

    def test_numeric_data_with_conversions(self):
        """Test numeric data that needs string conversion."""
        df = pd.DataFrame(np.random.randn(5, 3), index=[0, 1, 2, 3, 4], columns=[100, 200, 300])

        result = main(df)

        assert result.index.tolist() == ["0", "1", "2", "3", "4"]
        assert result.columns.tolist() == ["100", "200", "300"]
        # Data should remain unchanged
        np.testing.assert_array_equal(result.values, df.values)

    def test_mixed_realistic_scenario(self):
        """Test mixed scenario with some conversions needed."""
        df = pd.DataFrame(
            {"normal_col": [1, 2, 3], "('sample', 'type')": [4, 5, 6], 1: [7, 8, 9]},
            index=["gene1", "('GENE2', 'protein')", 2],
        )

        result = main(df)

        # Based on first element being normal string, no row conversion
        # Based on first column being normal string, no column conversion
        expected_index = ["gene1", "('GENE2', 'protein')", 2]
        expected_columns = ["normal_col", "('sample', 'type')", 1]

        assert result.index.tolist() == expected_index
        assert result.columns.tolist() == expected_columns

    def test_large_dataframe_performance(self):
        """Test with larger DataFrame to check performance."""
        # Create larger DataFrame with tuple strings
        n_rows, n_cols = 1000, 50
        index = [f"('gene{i}', 'type{i % 5}')" for i in range(n_rows)]
        columns = [f"('sample{i}', 'condition{i % 3}')" for i in range(n_cols)]

        df = pd.DataFrame(np.random.randn(n_rows, n_cols), index=index, columns=columns)

        result = main(df)

        # Check that conversions happened
        assert all(isinstance(idx, tuple) for idx in result.index)
        assert all(isinstance(col, tuple) for col in result.columns)
        assert len(result) == n_rows
        assert len(result.columns) == n_cols


class TestProcDfLabelsErrorHandling:
    """Test error handling and robustness."""

    def test_malformed_tuple_with_syntax_error(self):
        """Test tuple string that would cause syntax error in literal_eval."""
        df = pd.DataFrame(
            {"col1": [1, 2]},
            index=["('gene1', 'type1')", "('gene2', 'type2']"],  # Mismatched brackets
        )

        # This should raise a SyntaxError or ValueError when literal_eval is called
        with pytest.raises((SyntaxError, ValueError)):
            main(df)

    def test_tuple_with_invalid_python_syntax(self):
        """Test tuple string with invalid Python syntax."""
        df = pd.DataFrame(
            {"col1": [1]},
            index=["('gene1', 'type1', )"],  # Valid tuple syntax
        )

        result = main(df)

        expected_index = [("gene1", "type1")]
        assert result.index.tolist() == expected_index

    def test_very_long_tuple_strings(self):
        """Test with very long tuple strings."""
        long_tuple_str = "('" + "gene" * 1000 + "', '" + "type" * 1000 + "')"
        df = pd.DataFrame({"col1": [1]}, index=[long_tuple_str])

        result = main(df)

        expected_tuple = ("gene" * 1000, "type" * 1000)
        assert result.index.tolist() == [expected_tuple]

    def test_unicode_in_tuple_strings(self):
        """Test tuple strings with unicode characters."""
        df = pd.DataFrame({"col1": [1, 2]}, index=["('gene_α', 'type_β')", "('gene_γ', 'type_δ')"])

        result = main(df)

        expected_index = [("gene_α", "type_β"), ("gene_γ", "type_δ")]
        assert result.index.tolist() == expected_index


class TestProcDfLabelsActualBehavior:
    """Test the actual behavior based on understanding the implementation."""

    def test_first_element_determines_all_conversions(self):
        """Test that only the first element determines conversion for all elements."""
        # If first row is numeric, ALL rows get converted to strings
        df = pd.DataFrame({"col1": [1, 2, 3]}, index=[42, "string_row", ("tuple", "row")])

        result = main(df)

        # All should become strings because first element is numeric
        # Note: The tuple gets converted to its string representation
        assert result.index.tolist() == ["42", "string_row", "('tuple', 'row')"]

    def test_first_element_tuple_string_converts_all(self):
        """Test that if first element is tuple string, all get converted to tuples."""
        df = pd.DataFrame(
            {"col1": [1, 2, 3]},
            index=["('gene1', 'type1')", "('gene2', 'type2')", "('gene3', 'type3')"],
        )

        result = main(df)

        # All should become tuples because first element is tuple string
        expected_index = [("gene1", "type1"), ("gene2", "type2"), ("gene3", "type3")]
        assert result.index.tolist() == expected_index


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "--tb=short"])
