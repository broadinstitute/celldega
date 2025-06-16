from pathlib import Path
import sys
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd
import pytest


# Add the source directory to the path for imports
sys.path.insert(0, str(Path(__file__).parents[3] / "src"))

from celldega.clust.data.load_vect_post import main


class TestLoadVectPostBase:
    """Base class with common utilities and fixtures."""

    @staticmethod
    def create_mock_net():
        """Create mock network object with required methods."""
        mock_net = Mock()
        mock_net.df_to_dat = Mock()
        return mock_net

    @staticmethod
    def create_mock_network_class():
        """Create mock Network class for deepcopy."""
        mock_network_instance = Mock()
        mock_network_instance.dat = {"nodes": {}}
        mock_network_instance.dat_to_df = Mock(
            return_value=pd.DataFrame({"col1": [1, 2]}, index=["row1", "row2"])
        )
        return mock_network_instance

    @staticmethod
    def create_valid_vect_post(rows=None, cols=None, values=None):
        """Create valid vect_post structure for testing."""
        if rows is None:
            rows = ["gene1", "gene2"]
        if cols is None:
            cols = ["sample1", "sample2"]
        if values is None:
            values = [[1.0, 2.0], [3.0, 4.0]]

        columns = []
        for col_idx, col_name in enumerate(cols):
            data = []
            for row_idx, row_name in enumerate(rows):
                if row_idx < len(values) and col_idx < len(values[row_idx]):
                    val = values[row_idx][col_idx]
                else:
                    val = 1.0
                data.append({"row_name": row_name, "val": val})
            columns.append({"col_name": col_name, "data": data})

        return {"columns": columns}


class TestInputValidationCurrentBehavior(TestLoadVectPostBase):
    """Test input validation errors matching current code behavior."""

    @pytest.mark.parametrize(
        "invalid_input,expected_error,error_msg_pattern",
        [
            # Type validation - current code tries to access ["columns"] directly
            (None, TypeError, "'NoneType' object is not subscriptable"),
            ("string", TypeError, "string indices must be integers"),
            ([], TypeError, "list indices must be integers or slices, not str"),
            (123, TypeError, "'int' object is not subscriptable"),
            # Missing keys - current code tries to access key directly
            ({}, KeyError, "'columns'"),
            ({"wrong_key": []}, KeyError, "'columns'"),
        ],
    )
    def test_top_level_access_errors(self, invalid_input, expected_error, error_msg_pattern):
        """Test errors when accessing vect_post["columns"] with invalid input."""
        mock_net = self.create_mock_net()

        with pytest.raises(expected_error, match=error_msg_pattern):
            main(mock_net, invalid_input)

    @pytest.mark.parametrize(
        "invalid_columns,expected_error,error_msg_pattern",
        [
            # Non-iterable columns
            ("string", TypeError, "string indices must be integers"),
            (123, TypeError, "'int' object is not iterable"),
            # None columns would cause iteration error
            (None, TypeError, "'NoneType' object is not iterable"),
        ],
    )
    def test_columns_iteration_errors(self, invalid_columns, expected_error, error_msg_pattern):
        """Test errors when iterating over invalid columns."""
        mock_net = self.create_mock_net()
        vect_post = {"columns": invalid_columns}

        with pytest.raises(expected_error, match=error_msg_pattern):
            main(mock_net, vect_post)

    @pytest.mark.parametrize(
        "invalid_column,expected_error,error_msg_pattern",
        [
            # Column access errors
            ("string", TypeError, "string indices must be integers"),
            ([], TypeError, "list indices must be integers or slices, not str"),
            (None, TypeError, "'NoneType' object is not subscriptable"),
            ({}, KeyError, "'col_name'"),
            ({"col_name": "test"}, KeyError, "'data'"),
            ({"data": []}, KeyError, "'col_name'"),
        ],
    )
    def test_column_access_errors(self, invalid_column, expected_error, error_msg_pattern):
        """Test errors when accessing column attributes."""
        mock_net = self.create_mock_net()
        vect_post = {"columns": [invalid_column]}

        with pytest.raises(expected_error, match=error_msg_pattern):
            main(mock_net, vect_post)

    @pytest.mark.parametrize(
        "invalid_data,expected_error,error_msg_pattern",
        [
            # Data iteration errors
            ("string", TypeError, "string indices must be integers"),
            (123, TypeError, "'int' object is not iterable"),
            (None, TypeError, "'NoneType' object is not iterable"),
        ],
    )
    def test_data_iteration_errors(self, invalid_data, expected_error, error_msg_pattern):
        """Test errors when iterating over invalid data."""
        mock_net = self.create_mock_net()
        vect_post = {"columns": [{"col_name": "sample1", "data": invalid_data}]}

        with pytest.raises(expected_error, match=error_msg_pattern):
            main(mock_net, vect_post)

    @pytest.mark.parametrize(
        "invalid_row_data,expected_error,error_msg_pattern",
        [
            # Row data access errors
            ("string", TypeError, "string indices must be integers"),
            ([], TypeError, "list indices must be integers or slices, not str"),
            (None, TypeError, "'NoneType' object is not subscriptable"),
            ({}, KeyError, "'row_name'"),
            ({"row_name": "gene1"}, KeyError, "'val'"),
            ({"val": 1.0}, KeyError, "'row_name'"),
        ],
    )
    def test_row_data_access_errors(self, invalid_row_data, expected_error, error_msg_pattern):
        """Test errors when accessing row data attributes."""
        mock_net = self.create_mock_net()
        vect_post = {"columns": [{"col_name": "sample1", "data": [invalid_row_data]}]}

        with pytest.raises(expected_error, match=error_msg_pattern):
            main(mock_net, vect_post)

    def test_empty_columns_list_behavior(self):
        """Test behavior with empty columns list - should work but create empty structures."""
        mock_net = self.create_mock_net()

        with (
            patch("celldega.clust.load_vect_post.deepcopy") as mock_deepcopy,
            patch("celldega.clust.load_vect_post.proc_df_labels") as mock_proc_df_labels,
        ):
            mock_net_instance = self.create_mock_network_class()
            mock_deepcopy.return_value = mock_net_instance
            mock_proc_df_labels.main.return_value = pd.DataFrame()

            vect_post = {"columns": []}

            main(mock_net, vect_post)

            # Should create empty structures
            assert mock_net_instance.dat["nodes"]["row"] == []
            assert mock_net_instance.dat["nodes"]["col"] == []
            assert mock_net_instance.dat["mat"].shape == (0, 0)


class TestDataProcessingCurrentBehavior(TestLoadVectPostBase):
    """Test core data processing functionality with current code behavior."""

    @patch("celldega.clust.load_vect_post.deepcopy")
    @patch("celldega.clust.load_vect_post.proc_df_labels")
    def test_successful_basic_processing(self, mock_proc_df_labels, mock_deepcopy):
        """Test successful processing of valid data."""
        mock_net_instance = self.create_mock_network_class()
        mock_deepcopy.return_value = mock_net_instance
        mock_proc_df_labels.main.return_value = pd.DataFrame({"col1": [1]}, index=["row1"])

        real_net = self.create_mock_net()
        vect_post = self.create_valid_vect_post(
            rows=["gene1", "gene2"], cols=["sample1"], values=[[1.5], [2.5]]
        )

        main(real_net, vect_post)

        # Verify network setup
        assert mock_net_instance.dat["nodes"]["row"] == ["gene1", "gene2"]
        assert mock_net_instance.dat["nodes"]["col"] == ["sample1"]

        # Verify matrix creation
        matrix = mock_net_instance.dat["mat"]
        assert matrix.shape == (2, 1)
        assert matrix[0, 0] == 1.5
        assert matrix[1, 0] == 2.5

        # Verify processing pipeline
        mock_net_instance.dat_to_df.assert_called_once()
        mock_proc_df_labels.main.assert_called_once()
        real_net.df_to_dat.assert_called_once()

    @patch("celldega.clust.load_vect_post.deepcopy")
    @patch("celldega.clust.load_vect_post.proc_df_labels")
    def test_matrix_ordering_and_nan_filling(self, mock_proc_df_labels, mock_deepcopy):
        """Test matrix ordering and NaN filling for missing values."""
        mock_net_instance = self.create_mock_network_class()
        mock_deepcopy.return_value = mock_net_instance
        mock_proc_df_labels.main.return_value = pd.DataFrame()

        real_net = self.create_mock_net()

        vect_post = {
            "columns": [
                {"col_name": "sample2", "data": [{"row_name": "gene2", "val": 2.0}]},
                {
                    "col_name": "sample1",
                    "data": [{"row_name": "gene1", "val": 1.0}, {"row_name": "gene2", "val": 3.0}],
                },
            ]
        }

        main(real_net, vect_post)

        # Verify alphabetical ordering
        assert mock_net_instance.dat["nodes"]["row"] == ["gene1", "gene2"]
        assert mock_net_instance.dat["nodes"]["col"] == ["sample1", "sample2"]

        # Verify matrix values and NaN placement
        matrix = mock_net_instance.dat["mat"]
        assert matrix.shape == (2, 2)

        assert matrix[0, 0] == 1.0  # gene1, sample1
        assert matrix[1, 0] == 3.0  # gene2, sample1
        assert np.isnan(matrix[0, 1])  # gene1, sample2 (missing)
        assert matrix[1, 1] == 2.0  # gene2, sample2

    @pytest.mark.parametrize(
        "numeric_values,expected_tolerance",
        [
            # Different numeric types - use tolerance for floating point comparisons
            ([1, 2.5, np.float32(3.2), np.int64(4)], 1e-6),
            ([float("inf"), float("-inf"), 0.0, -0.0], 0),  # Exact for special values
            ([1e308, 1e-308, -1e308], 0),  # Large numbers should be exact
        ],
    )
    @patch("celldega.clust.load_vect_post.deepcopy")
    @patch("celldega.clust.load_vect_post.proc_df_labels")
    def test_numeric_value_handling(
        self, mock_proc_df_labels, mock_deepcopy, numeric_values, expected_tolerance
    ):
        """Test handling of various numeric value types."""
        mock_net_instance = self.create_mock_network_class()
        mock_deepcopy.return_value = mock_net_instance
        mock_proc_df_labels.main.return_value = pd.DataFrame()

        real_net = self.create_mock_net()

        data = []
        for i, val in enumerate(numeric_values):
            data.append({"row_name": f"gene{i}", "val": val})

        vect_post = {"columns": [{"col_name": "sample1", "data": data}]}

        main(real_net, vect_post)

        matrix = mock_net_instance.dat["mat"]
        for i, expected in enumerate(numeric_values):
            actual = matrix[i, 0]
            if np.isnan(expected):
                assert np.isnan(actual)
            elif np.isinf(expected):
                assert np.isinf(actual) and np.sign(actual) == np.sign(expected)
            elif expected_tolerance > 0:
                assert abs(actual - expected) <= expected_tolerance
            else:
                assert actual == expected

    @pytest.mark.parametrize(
        "invalid_numeric_value,expected_error",
        [
            ("string_value", ValueError),  # Can't convert to float
            ([], ValueError),  # Can't set array element with sequence
            ({}, TypeError),  # Can't convert dict to float
        ],
    )
    @patch("celldega.clust.load_vect_post.deepcopy")
    @patch("celldega.clust.load_vect_post.proc_df_labels")
    def test_invalid_numeric_values(
        self, mock_proc_df_labels, mock_deepcopy, invalid_numeric_value, expected_error
    ):
        """Test behavior with invalid numeric values."""
        mock_net_instance = self.create_mock_network_class()
        mock_deepcopy.return_value = mock_net_instance
        mock_proc_df_labels.main.return_value = pd.DataFrame()

        real_net = self.create_mock_net()

        vect_post = {
            "columns": [
                {
                    "col_name": "sample1",
                    "data": [{"row_name": "gene1", "val": invalid_numeric_value}],
                }
            ]
        }

        with pytest.raises(expected_error):
            main(real_net, vect_post)

    @pytest.mark.parametrize(
        "string_values",
        [
            ["gene_α", "gene-β", "gene@1"],
            ["", "  ", "\t"],
            ["123", "1.5", "-42"],
        ],
    )
    @patch("celldega.clust.load_vect_post.deepcopy")
    @patch("celldega.clust.load_vect_post.proc_df_labels")
    def test_string_name_handling(self, mock_proc_df_labels, mock_deepcopy, string_values):
        """Test handling of various string name types."""
        mock_net_instance = self.create_mock_network_class()
        mock_deepcopy.return_value = mock_net_instance
        mock_proc_df_labels.main.return_value = pd.DataFrame()

        real_net = self.create_mock_net()

        data = [{"row_name": string_values[0], "val": 1.0}]
        vect_post = {
            "columns": [
                {
                    "col_name": string_values[1] if len(string_values) > 1 else "sample1",
                    "data": data,
                }
            ]
        }

        main(real_net, vect_post)

        assert string_values[0] in mock_net_instance.dat["nodes"]["row"]


class TestNetworkIntegrationCurrentBehavior(TestLoadVectPostBase):
    """Test integration with Network class and error propagation."""

    @patch("celldega.clust.load_vect_post.deepcopy")
    def test_network_initialization_failure(self, mock_deepcopy):
        """Test handling of Network initialization failures."""
        mock_deepcopy.side_effect = RuntimeError("Network init failed")

        real_net = self.create_mock_net()
        vect_post = self.create_valid_vect_post()

        # Current code doesn't wrap this error
        with pytest.raises(RuntimeError, match="Network init failed"):
            main(real_net, vect_post)

    @patch("celldega.clust.load_vect_post.deepcopy")
    def test_dat_to_df_failure(self, mock_deepcopy):
        """Test handling of dat_to_df method failures."""
        mock_net_instance = self.create_mock_network_class()
        mock_net_instance.dat_to_df.side_effect = AttributeError("dat_to_df failed")
        mock_deepcopy.return_value = mock_net_instance

        real_net = self.create_mock_net()
        vect_post = self.create_valid_vect_post()

        # Current code doesn't wrap this error
        with pytest.raises(AttributeError, match="dat_to_df failed"):
            main(real_net, vect_post)

    @patch("celldega.clust.load_vect_post.deepcopy")
    @patch("celldega.clust.load_vect_post.proc_df_labels")
    def test_proc_df_labels_failure(self, mock_proc_df_labels, mock_deepcopy):
        """Test handling of proc_df_labels failures."""
        mock_net_instance = self.create_mock_network_class()
        mock_deepcopy.return_value = mock_net_instance
        mock_proc_df_labels.main.side_effect = ValueError("Processing failed")

        real_net = self.create_mock_net()
        vect_post = self.create_valid_vect_post()

        # Current code doesn't wrap this error
        with pytest.raises(ValueError, match="Processing failed"):
            main(real_net, vect_post)

    @patch("celldega.clust.load_vect_post.deepcopy")
    @patch("celldega.clust.load_vect_post.proc_df_labels")
    def test_df_to_dat_failure(self, mock_proc_df_labels, mock_deepcopy):
        """Test handling of df_to_dat method failures."""
        mock_net_instance = self.create_mock_network_class()
        mock_deepcopy.return_value = mock_net_instance
        mock_proc_df_labels.main.return_value = pd.DataFrame()

        real_net = self.create_mock_net()
        real_net.df_to_dat.side_effect = RuntimeError("df_to_dat failed")
        vect_post = self.create_valid_vect_post()

        # Current code doesn't wrap this error
        with pytest.raises(RuntimeError, match="df_to_dat failed"):
            main(real_net, vect_post)


class TestEdgeCasesCurrentBehavior(TestLoadVectPostBase):
    """Test edge cases with current code behavior."""

    @pytest.mark.parametrize(
        "scenario_name,rows,cols,values,expected_shape",
        [
            ("single_cell", ["gene1"], ["sample1"], [[1.0]], (1, 1)),
            ("single_row_multi_col", ["gene1"], ["sample1", "sample2"], [[1.0, 2.0]], (1, 2)),
            ("multi_row_single_col", ["gene1", "gene2"], ["sample1"], [[1.0], [2.0]], (2, 1)),
            (
                "square_matrix",
                ["gene1", "gene2"],
                ["sample1", "sample2"],
                [[1.0, 2.0], [3.0, 4.0]],
                (2, 2),
            ),
        ],
    )
    @patch("celldega.clust.load_vect_post.deepcopy")
    @patch("celldega.clust.load_vect_post.proc_df_labels")
    def test_matrix_size_scenarios(
        self, mock_proc_df_labels, mock_deepcopy, scenario_name, rows, cols, values, expected_shape
    ):
        """Test various matrix size scenarios."""
        mock_net_instance = self.create_mock_network_class()
        mock_deepcopy.return_value = mock_net_instance
        mock_proc_df_labels.main.return_value = pd.DataFrame()

        real_net = self.create_mock_net()
        vect_post = self.create_valid_vect_post(rows=rows, cols=cols, values=values)

        main(real_net, vect_post)

        matrix = mock_net_instance.dat["mat"]
        assert matrix.shape == expected_shape
        assert len(mock_net_instance.dat["nodes"]["row"]) == expected_shape[0]
        assert len(mock_net_instance.dat["nodes"]["col"]) == expected_shape[1]

    @patch("celldega.clust.load_vect_post.deepcopy")
    @patch("celldega.clust.load_vect_post.proc_df_labels")
    def test_duplicate_names_handling(self, mock_proc_df_labels, mock_deepcopy):
        """Test handling of duplicate row/column names."""
        mock_net_instance = self.create_mock_network_class()
        mock_deepcopy.return_value = mock_net_instance
        mock_proc_df_labels.main.return_value = pd.DataFrame()

        real_net = self.create_mock_net()

        vect_post = {
            "columns": [
                {
                    "col_name": "sample1",
                    "data": [
                        {"row_name": "gene1", "val": 1.0},
                        {"row_name": "gene1", "val": 2.0},  # Duplicate row name
                    ],
                }
            ]
        }

        main(real_net, vect_post)

        # Should only have one entry for gene1, with the last value
        assert mock_net_instance.dat["nodes"]["row"] == ["gene1"]
        matrix = mock_net_instance.dat["mat"]
        assert matrix.shape == (1, 1)
        assert matrix[0, 0] == 2.0  # Last value wins

    @patch("celldega.clust.load_vect_post.deepcopy")
    @patch("celldega.clust.load_vect_post.proc_df_labels")
    def test_network_dat_structure_population(self, mock_proc_df_labels, mock_deepcopy):
        """Test that dat structure is populated correctly."""
        # Create network with realistic initial dat structure (as Network() would provide)
        mock_net_instance = Mock()
        mock_net_instance.dat = {"nodes": {}}  # Realistic initial structure
        mock_net_instance.dat_to_df = Mock(return_value=pd.DataFrame())
        mock_deepcopy.return_value = mock_net_instance
        mock_proc_df_labels.main.return_value = pd.DataFrame()

        real_net = self.create_mock_net()
        vect_post = self.create_valid_vect_post()

        main(real_net, vect_post)

        # Should populate dat structure correctly
        assert "nodes" in mock_net_instance.dat
        assert "row" in mock_net_instance.dat["nodes"]
        assert "col" in mock_net_instance.dat["nodes"]
        assert "mat" in mock_net_instance.dat

        # Check that the nodes contain the expected data
        assert mock_net_instance.dat["nodes"]["row"] == ["gene1", "gene2"]
        assert mock_net_instance.dat["nodes"]["col"] == ["sample1", "sample2"]

    def test_non_comparable_column_names_error(self):
        """Test error when column names can't be sorted (mixed types)."""
        mock_net = self.create_mock_net()

        # Create vect_post with mixed types that can't be compared for sorting
        vect_post = {
            "columns": [
                {"col_name": "string_name", "data": [{"row_name": "gene1", "val": 1.0}]},
                {"col_name": 123, "data": [{"row_name": "gene2", "val": 2.0}]},  # int name
            ]
        }

        # This should fail when trying to sort mixed types
        with pytest.raises(TypeError, match="'<' not supported between instances"):
            main(mock_net, vect_post)


class TestIntegrationScenariosCurrentBehavior(TestLoadVectPostBase):
    """Integration tests for realistic scenarios."""

    @patch("celldega.clust.load_vect_post.deepcopy")
    @patch("celldega.clust.load_vect_post.proc_df_labels")
    def test_gene_expression_scenario(self, mock_proc_df_labels, mock_deepcopy):
        """Test realistic gene expression data scenario."""
        mock_net_instance = self.create_mock_network_class()
        mock_deepcopy.return_value = mock_net_instance
        mock_proc_df_labels.main.return_value = pd.DataFrame()

        real_net = self.create_mock_net()

        vect_post = {
            "columns": [
                {
                    "col_name": "cell_001",
                    "data": [
                        {"row_name": "ACTB", "val": 15.2},
                        {"row_name": "GAPDH", "val": 12.8},
                        {"row_name": "TP53", "val": 3.4},
                    ],
                },
                {
                    "col_name": "cell_002",
                    "data": [
                        {"row_name": "ACTB", "val": 14.7},
                        {"row_name": "GAPDH", "val": 13.1},
                        {"row_name": "MYC", "val": 8.9},
                    ],
                },
            ]
        }

        main(real_net, vect_post)

        expected_genes = ["ACTB", "GAPDH", "MYC", "TP53"]
        expected_cells = ["cell_001", "cell_002"]

        assert mock_net_instance.dat["nodes"]["row"] == expected_genes
        assert mock_net_instance.dat["nodes"]["col"] == expected_cells

        matrix = mock_net_instance.dat["mat"]
        assert matrix.shape == (4, 2)

        # Check specific values and NaN placement
        gene_idx = {gene: i for i, gene in enumerate(expected_genes)}
        cell_idx = {cell: i for i, cell in enumerate(expected_cells)}

        assert matrix[gene_idx["ACTB"], cell_idx["cell_001"]] == 15.2
        assert matrix[gene_idx["ACTB"], cell_idx["cell_002"]] == 14.7
        assert matrix[gene_idx["TP53"], cell_idx["cell_001"]] == 3.4
        assert np.isnan(matrix[gene_idx["TP53"], cell_idx["cell_002"]])
        assert np.isnan(matrix[gene_idx["MYC"], cell_idx["cell_001"]])
        assert matrix[gene_idx["MYC"], cell_idx["cell_002"]] == 8.9

    @patch("celldega.clust.load_vect_post.deepcopy")
    @patch("celldega.clust.load_vect_post.proc_df_labels")
    def test_large_dataset_simulation(self, mock_proc_df_labels, mock_deepcopy):
        """Test performance with larger dataset."""
        mock_net_instance = self.create_mock_network_class()
        mock_deepcopy.return_value = mock_net_instance
        mock_proc_df_labels.main.return_value = pd.DataFrame()

        real_net = self.create_mock_net()

        n_genes = 50  # Smaller for faster tests
        n_cells = 25

        columns = []
        for cell_i in range(n_cells):
            data = []
            for gene_i in range(int(n_genes * 0.7)):
                if (cell_i + gene_i) % 3 != 0:
                    data.append({"row_name": f"GENE_{gene_i:03d}", "val": float(cell_i + gene_i)})
            columns.append({"col_name": f"cell_{cell_i:03d}", "data": data})

        vect_post = {"columns": columns}

        main(real_net, vect_post)

        assert len(mock_net_instance.dat["nodes"]["col"]) == n_cells
        matrix = mock_net_instance.dat["mat"]
        assert matrix.shape[1] == n_cells
        assert matrix.shape[0] <= n_genes


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
