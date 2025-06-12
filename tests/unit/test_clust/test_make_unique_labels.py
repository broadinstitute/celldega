from pathlib import Path
import sys
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest


# Add the source directory to the path for imports
sys.path.insert(0, str(Path(__file__).parents[3] / "src"))

from celldega.clust.make_unique_labels import _has_duplicates, add_index_list, main


class TestMakeUniqueLabelsBase:
    """Base class with common utilities."""

    @staticmethod
    def create_mock_net(df=None):
        """Create mock network with optional DataFrame."""
        mock_net = Mock()
        if df is not None:
            mock_net.export_df.return_value = df
        return mock_net


class TestMainFunctionality(TestMakeUniqueLabelsBase):
    """Test core functionality."""

    @pytest.mark.parametrize(
        "df_setup,expected_unchanged",
        [
            # No duplicates cases
            (lambda: pd.DataFrame({"col1": [1, 2]}, index=["gene1", "gene2"]), True),
            (
                lambda: pd.DataFrame(
                    {"col1": [1, 2]}, index=[("gene1", "type1"), ("gene2", "type2")]
                ),
                True,
            ),
            (lambda: pd.DataFrame([[1, 2]], columns=["col1", "col2"]), True),
            (lambda: pd.DataFrame(), True),  # Empty DataFrame
        ],
    )
    def test_no_changes_when_no_duplicates(self, df_setup, expected_unchanged):
        """Test DataFrames without duplicates remain unchanged."""
        df = df_setup()
        original_df = df.copy()
        mock_net = self.create_mock_net()

        result = main(mock_net, df)

        if expected_unchanged:
            pd.testing.assert_frame_equal(result, original_df)

    @pytest.mark.parametrize(
        "axis,duplicates,expected",
        [
            ("rows", ["gene1", "gene1", "gene2"], ["gene1-1", "gene1-2", "gene2-3"]),
            ("cols", ["col1", "col1", "col2"], ["col1-1", "col1-2", "col2-3"]),
            (
                "both",
                (["gene1", "gene1"], ["col1", "col1"]),
                (["gene1-1", "gene1-2"], ["col1-1", "col1-2"]),
            ),
        ],
    )
    def test_string_duplicates_handling(self, axis, duplicates, expected, capsys):
        """Test string duplicate handling."""
        mock_net = self.create_mock_net()

        if axis == "rows":
            df = pd.DataFrame({"col1": [1, 2, 3]}, index=duplicates)
            result = main(mock_net, df)
            assert result.index.tolist() == expected
        elif axis == "cols":
            df = pd.DataFrame([[1, 2, 3]], columns=duplicates)
            result = main(mock_net, df)
            assert result.columns.tolist() == expected
        else:  # both
            df = pd.DataFrame([[1, 2], [3, 4]], index=duplicates[0], columns=duplicates[1])
            result = main(mock_net, df)
            assert result.index.tolist() == expected[0]
            assert result.columns.tolist() == expected[1]

        # Check warning messages
        captured = capsys.readouterr()
        if axis in ["rows", "both"]:
            assert "warning: making row names unique" in captured.out
        if axis in ["cols", "both"]:
            assert "warning: making col names unique" in captured.out

    @pytest.mark.parametrize(
        "tuples,expected",
        [
            (
                [("gene1", "type1"), ("gene1", "type2"), ("gene2", "type1")],
                [("gene1-1", "type1"), ("gene1-2", "type2"), ("gene2-3", "type1")],
            ),
            (
                [("gene1", "type1", "extra"), ("gene1", "type2")],
                [("gene1-1", "type1", "extra"), ("gene1-2", "type2")],
            ),
            (
                [(1, "type1"), (1, "type2"), (2, "type1")],
                [("1-1", "type1"), ("1-2", "type2"), ("2-3", "type1")],
            ),
        ],
    )
    def test_tuple_duplicates_handling(self, tuples, expected):
        """Test tuple duplicate handling."""
        mock_net = self.create_mock_net()
        df = pd.DataFrame({"col1": range(len(tuples))}, index=tuples)

        result = main(mock_net, df)
        assert result.index.tolist() == expected

    def test_net_vs_df_parameter_handling(self):
        """Test net vs df parameter precedence."""
        # Test df=None uses net.export_df()
        mock_df = pd.DataFrame({"col1": [1, 2]}, index=["gene1", "gene1"])
        mock_net = self.create_mock_net(mock_df)

        result = main(mock_net, df=None)
        mock_net.export_df.assert_called_once()
        assert result.index.tolist() == ["gene1-1", "gene1-2"]

        # Test df provided doesn't call net.export_df()
        mock_net.reset_mock()
        df = pd.DataFrame({"col1": [1, 2]}, index=["gene2", "gene2"])
        result = main(mock_net, df)
        mock_net.export_df.assert_not_called()
        assert result.index.tolist() == ["gene2-1", "gene2-2"]

    def test_in_place_modification(self):
        """Test function modifies original DataFrame in place."""
        mock_net = self.create_mock_net()
        df = pd.DataFrame({"col1": [1, 2]}, index=["gene1", "gene1"])
        original_values = df.values.copy()

        result = main(mock_net, df)

        assert result is df  # Same object
        assert df.index.tolist() == ["gene1-1", "gene1-2"]
        np.testing.assert_array_equal(df.values, original_values)


class TestEdgeCasesAndErrorHandling(TestMakeUniqueLabelsBase):
    """Test edge cases and error handling."""

    @pytest.mark.parametrize(
        "df_setup",
        [
            lambda: pd.DataFrame(),
            lambda: pd.DataFrame(columns=["col1", "col2"]),
            lambda: pd.DataFrame(index=["row1", "row2"]),
            lambda: pd.DataFrame({"col1": [42]}, index=["row1"]),
        ],
    )
    def test_empty_and_minimal_dataframes(self, df_setup):
        """Test empty and minimal DataFrames are handled gracefully."""
        mock_net = self.create_mock_net()
        df = df_setup()
        original_df = df.copy()

        result = main(mock_net, df)
        pd.testing.assert_frame_equal(result, original_df)

    @pytest.mark.parametrize(
        "empty_tuple_axis,error_msg",
        [
            ("index", "Empty tuples found in row index"),
            ("columns", "Empty tuples found in column index"),
        ],
    )
    def test_empty_tuple_error_handling(self, empty_tuple_axis, error_msg):
        """Test empty tuples raise clear error messages."""
        mock_net = self.create_mock_net()

        if empty_tuple_axis == "index":
            df = pd.DataFrame({"col1": [1, 2]}, index=[(), ("gene2", "type2")])
        else:
            df = pd.DataFrame([[1, 2]], columns=[(), ("col2", "cat2")])

        with pytest.raises(ValueError, match=error_msg):
            main(mock_net, df)

    @pytest.mark.parametrize(
        "setup_func,error_type,error_msg",
        [
            (lambda: (None, None), ValueError, "Either net or df must be provided"),
            (lambda: (Mock(**{"export_df.return_value": None}), None), AttributeError, None),
            (
                lambda: (Mock(**{"export_df.side_effect": RuntimeError("Network error")}), None),
                RuntimeError,
                "Network error",
            ),
        ],
    )
    def test_input_validation(self, setup_func, error_type, error_msg):
        """Test input validation and error handling."""
        net, df = setup_func()

        with pytest.raises(error_type, match=error_msg):
            main(net, df)


class TestSpecialValues(TestMakeUniqueLabelsBase):
    """Test handling of special values and types."""

    @pytest.mark.parametrize(
        "test_case",
        [
            {
                "input": [(None, "type1"), (None, "type2")],
                "expected": [("None-1", "type1"), ("None-2", "type2")],
            },
            {
                "input": [(1, "type1"), (1, "type2"), (2, "type1")],
                "expected": [("1-1", "type1"), ("1-2", "type2"), ("2-3", "type1")],
            },
            {
                "input": [(True, "type1"), (True, "type2")],
                "expected": [("True-1", "type1"), ("True-2", "type2")],
            },
            {
                "input": [(np.inf, "type1"), (np.inf, "type2")],
                "expected": [("inf-1", "type1"), ("inf-2", "type2")],
            },
        ],
    )
    def test_special_values_in_tuples(self, test_case):
        """Test handling of special values in tuple positions."""
        mock_net = self.create_mock_net()
        df = pd.DataFrame({"col1": range(len(test_case["input"]))}, index=test_case["input"])

        result = main(mock_net, df)
        assert result.index.tolist() == test_case["expected"]

    @pytest.mark.parametrize(
        "input_strings,expected",
        [
            (["", ""], ["-1", "-2"]),
            (["  ", "  "], ["  -1", "  -2"]),
            (["gene-1", "gene-1", "gene@2"], ["gene-1-1", "gene-1-2", "gene@2-3"]),
            (["gene🧬", "gene🧬"], ["gene🧬-1", "gene🧬-2"]),
        ],
    )
    def test_string_edge_cases(self, input_strings, expected):
        """Test edge cases with string names."""
        mock_net = self.create_mock_net()
        df = pd.DataFrame({"col1": range(len(input_strings))}, index=input_strings)

        result = main(mock_net, df)
        assert result.index.tolist() == expected

    def test_data_integrity_preservation(self):
        """Test data integrity is preserved during modifications."""
        mock_net = self.create_mock_net()

        original_data = {
            "int_col": [1, 2, 3],
            "float_col": [1.1, 2.2, 3.3],
            "str_col": ["a", "b", "c"],
            "bool_col": [True, False, True],
        }
        df = pd.DataFrame(original_data, index=["row1", "row1", "row2"])
        original_values = df.values.copy()

        result = main(mock_net, df)

        np.testing.assert_array_equal(result.values, original_values)
        for col in original_data:
            assert result[col].dtype == df[col].dtype
        assert result.index.tolist() == ["row1-1", "row1-2", "row2-3"]


class TestHelperFunctions:
    """Test helper functions."""

    @pytest.mark.parametrize(
        "input_list,expected",
        [
            (["gene1", "gene2", "gene3"], ["gene1-1", "gene2-2", "gene3-3"]),
            ([], []),
            (["gene1"], ["gene1-1"]),
            (["gene1", "42", "gene3"], ["gene1-1", "42-2", "gene3-3"]),
        ],
    )
    def test_add_index_list(self, input_list, expected):
        """Test add_index_list function."""
        result = add_index_list(input_list)
        assert result == expected

        # Original list should not be modified
        original = input_list.copy()
        add_index_list(input_list)
        assert input_list == original

    @pytest.mark.parametrize(
        "input_list,has_dupes",
        [
            (["a", "b", "a"], True),
            ([1, 2, 1], True),
            ([("a", "b"), ("a", "b")], True),
            (["a", "b", "c"], False),
            ([1, 2, 3], False),
            ([], False),
            (["a"], False),
            ([None, None], True),
        ],
    )
    def test_has_duplicates(self, input_list, has_dupes):
        """Test _has_duplicates function."""
        assert _has_duplicates(input_list) == has_dupes


class TestIntegrationScenarios(TestMakeUniqueLabelsBase):
    """Integration tests for realistic scenarios."""

    def test_gene_expression_scenario(self):
        """Test realistic gene expression data scenario."""
        mock_net = self.create_mock_net()

        df = pd.DataFrame(
            {
                ("sample1", "condition1"): [1.2, 2.3, 3.4],
                ("sample2", "condition1"): [1.5, 2.6, 3.7],
                ("sample1", "condition2"): [0.8, 1.9, 2.1],
            },
            index=[("GENE1", "protein"), ("GENE1", "rna"), ("GENE2", "protein")],
        )

        result = main(mock_net, df)

        expected_index = [("GENE1-1", "protein"), ("GENE1-2", "rna"), ("GENE2-3", "protein")]
        expected_columns = [
            ("sample1-1", "condition1"),
            ("sample2-2", "condition1"),
            ("sample1-3", "condition2"),
        ]

        assert result.index.tolist() == expected_index
        assert result.columns.tolist() == expected_columns
        np.testing.assert_array_equal(result.values, df.values)

    def test_network_integration_simulation(self):
        """Test integration with network object."""
        mock_net = self.create_mock_net()
        mock_net.export_df.return_value = pd.DataFrame(
            {"expression": [1.5, 2.3, 0.8, 1.2]}, index=["GENE1", "GENE1", "GENE2", "GENE3"]
        )

        result = main(mock_net)

        assert result.index.tolist() == ["GENE1-1", "GENE1-2", "GENE2-3", "GENE3-4"]
        mock_net.export_df.assert_called_once()

    def test_performance_with_many_duplicates(self):
        """Test performance with large number of duplicates."""
        mock_net = self.create_mock_net()

        # Create manageable test size
        n_duplicates = 1000
        df = pd.DataFrame({"col1": range(n_duplicates)}, index=["gene1"] * n_duplicates)

        result = main(mock_net, df)

        assert len(result.index) == n_duplicates
        assert len(set(result.index)) == n_duplicates  # All unique
        assert result.index[0] == "gene1-1"
        assert result.index[-1] == f"gene1-{n_duplicates}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
