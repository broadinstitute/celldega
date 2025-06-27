# =============================================================================
# COMPREHENSIVE TEST SUITE FOR DATA_FORMATS.PY MODULE
# =============================================================================
"""
Comprehensive test suite for data_formats.py module.

This test suite provides comprehensive coverage for data format conversion utilities
with improved robustness, consistency, and maintainability. Tests cover normal operation,
edge cases, and error conditions for all public functions.
"""

# =============================================================================
# IMPORTS
# =============================================================================

from collections.abc import Generator
from contextlib import contextmanager
from typing import Any
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd
import pytest

from celldega.clust_old.core.data_formats import dat_to_df, df_to_dat, mat_to_numpy_arr


# =============================================================================
# MODULE-LEVEL CONSTANTS
# =============================================================================

# Basic test data
BASIC_ROW_NAMES = ["row1", "row2", "row3"]
BASIC_COL_NAMES = ["col1", "col2", "col3"]
BASIC_DATA_VALUES = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]

# Tuple-based test data
TUPLE_ROW_NAMES = [("row1", "group: X"), ("row2", "group: Y"), ("row3", "group: X")]
TUPLE_COL_NAMES = [("col1", "type: A"), ("col2", "type: B"), ("col3", "type: A")]

# Single cell test data
SINGLE_CELL_DATA = {"col1": [42]}
SINGLE_CELL_INDEX = ["row1"]

# Expected category values
EXPECTED_ROW_CATEGORIES = ["group: X", "group: Y", "group: X"]
EXPECTED_COL_CATEGORIES = ["type: A", "type: B", "type: A"]

# Metadata category values
METADATA_ROW_CATEGORIES = ["category1: A", "category1: B", "category1: A"]
METADATA_COL_CATEGORIES = ["category2: X", "category2: Y", "category2: X"]

# Unicode and special character test data
UNICODE_ROW_NAMES = ["röw_1", "row-2!@#"]
UNICODE_COL_NAMES = ["cøl_1", "col-2!@#", "col 3"]
UNICODE_DATA = [[1, 3, 5], [2, 4, 6]]

# Numeric label test data
NUMERIC_COL_NAMES = [1, 2.5, 0]
NUMERIC_ROW_NAMES = [100, 200]
NUMERIC_DATA = [[10, 30, 50], [20, 40, 60]]

# Large dimension test constants
WIDE_DATAFRAME_COLS = 1000
LARGE_DATAFRAME_SIZE = 100

# Category naming constants
CATEGORY_ZERO = "cat-0"
CATEGORY_ONE = "cat-1"
CATEGORY_TWO = "cat-2"

# =============================================================================
# HELPER CLASSES AND UTILITIES
# =============================================================================


class TestDataFormatHelpers:
    """Helper methods and utilities for data format testing."""

    @staticmethod
    def create_mock_network(has_metadata: bool = False, is_downsampled: bool = False) -> Mock:
        """
        Create a mock network object with standardized structure.

        Args:
            has_metadata: Whether to include metadata categories
            is_downsampled: Whether the network uses downsampled data

        Returns:
            Mock network object with required attributes
        """
        net = Mock()
        net.dat = {"mat": [], "nodes": {"row": [], "col": []}, "node_info": {"row": {}, "col": {}}}
        net.meta_cat = has_metadata
        net.is_downsampled = is_downsampled

        if has_metadata:
            net.row_cats = ["category1"]
            net.col_cats = ["category2"]
            net.meta_row = pd.DataFrame({"category1": ["A", "B", "A"]}, index=BASIC_ROW_NAMES)
            net.meta_col = pd.DataFrame({"category2": ["X", "Y", "X"]}, index=BASIC_COL_NAMES)

            if is_downsampled:
                net.meta_ds_row = net.meta_row.copy()
                net.meta_ds_col = net.meta_col.copy()

        return net

    @staticmethod
    @contextmanager
    def patch_dependencies() -> Generator[tuple[Mock, Mock], None, None]:
        """Context manager for patching common dependencies."""
        with (
            patch("celldega.clust_old.core.data_formats.make_unique_labels.main") as mock_unique,
            patch("celldega.clust_old.core.data_formats.categories.dict_cat") as mock_dict_cat,
        ):
            yield mock_unique, mock_dict_cat

    @staticmethod
    def assert_basic_conversion(
        net: Mock,
        expected_data: list[list[int]],
        expected_rows: list[str],
        expected_cols: list[str],
    ) -> None:
        """Assert basic data conversion results."""
        np.testing.assert_array_equal(net.dat["mat"], expected_data)
        assert net.dat["nodes"]["row"] == expected_rows
        assert net.dat["nodes"]["col"] == expected_cols

    @staticmethod
    def assert_tuple_categories(net: Mock, axis: str, expected_categories: list[str]) -> None:
        """Assert tuple-based category processing results."""
        assert CATEGORY_ZERO in net.dat["node_info"][axis]
        assert net.dat["node_info"][axis][CATEGORY_ZERO] == expected_categories


# =============================================================================
# PYTEST FIXTURES
# =============================================================================


@pytest.fixture
def basic_dataframe() -> pd.DataFrame:
    """Standard DataFrame for basic testing scenarios."""
    return pd.DataFrame(
        dict(zip(BASIC_COL_NAMES, zip(*BASIC_DATA_VALUES, strict=False), strict=False)),
        index=BASIC_ROW_NAMES,
    )


@pytest.fixture
def tuple_dataframe() -> pd.DataFrame:
    """DataFrame with tuple indices/columns for category testing."""
    return pd.DataFrame(
        dict(zip(TUPLE_COL_NAMES, zip(*BASIC_DATA_VALUES, strict=False), strict=False)),
        index=TUPLE_ROW_NAMES,
    )


@pytest.fixture
def mock_network() -> Mock:
    """Basic mock network object."""
    return TestDataFormatHelpers.create_mock_network()


@pytest.fixture
def mock_network_with_metadata() -> Mock:
    """Mock network object with metadata categories."""
    return TestDataFormatHelpers.create_mock_network(has_metadata=True)


# =============================================================================
# TEST CLASSES - DF_TO_DAT FUNCTION
# =============================================================================


class TestDfToDat:
    """Tests for df_to_dat function - converts DataFrame to internal data structure."""

    def test_basic_dataframe_conversion(
        self, mock_network: Mock, basic_dataframe: pd.DataFrame
    ) -> None:
        """Test basic DataFrame to internal data structure conversion."""
        with TestDataFormatHelpers.patch_dependencies() as (mock_unique, mock_dict_cat):
            mock_unique.return_value = basic_dataframe

            df_to_dat(mock_network, basic_dataframe)

            TestDataFormatHelpers.assert_basic_conversion(
                mock_network, BASIC_DATA_VALUES, BASIC_ROW_NAMES, BASIC_COL_NAMES
            )

    def test_tuple_categories_processing(
        self, mock_network: Mock, tuple_dataframe: pd.DataFrame
    ) -> None:
        """Test processing of tuple-based categories in indices and columns."""
        with TestDataFormatHelpers.patch_dependencies() as (mock_unique, mock_dict_cat):
            mock_unique.return_value = tuple_dataframe

            df_to_dat(mock_network, tuple_dataframe)

            # Verify tuple categories are extracted correctly
            TestDataFormatHelpers.assert_tuple_categories(
                mock_network, "row", EXPECTED_ROW_CATEGORIES
            )
            TestDataFormatHelpers.assert_tuple_categories(
                mock_network, "col", EXPECTED_COL_CATEGORIES
            )

            # Verify base names are extracted (first tuple element)
            assert mock_network.dat["nodes"]["row"] == BASIC_ROW_NAMES
            assert mock_network.dat["nodes"]["col"] == BASIC_COL_NAMES

    def test_metadata_categories_processing(
        self, mock_network_with_metadata: Mock, basic_dataframe: pd.DataFrame
    ) -> None:
        """Test processing with metadata-based categories."""
        with TestDataFormatHelpers.patch_dependencies() as (mock_unique, mock_dict_cat):
            mock_unique.return_value = basic_dataframe

            df_to_dat(mock_network_with_metadata, basic_dataframe)

            # Verify metadata categories are processed correctly
            assert CATEGORY_ZERO in mock_network_with_metadata.dat["node_info"]["row"]
            assert CATEGORY_ZERO in mock_network_with_metadata.dat["node_info"]["col"]

            actual_row_cats = mock_network_with_metadata.dat["node_info"]["row"][CATEGORY_ZERO]
            actual_col_cats = mock_network_with_metadata.dat["node_info"]["col"][CATEGORY_ZERO]

            assert actual_row_cats == METADATA_ROW_CATEGORIES
            assert actual_col_cats == METADATA_COL_CATEGORIES

    @pytest.mark.parametrize(
        "is_downsampled,has_ds_metadata",
        [
            (True, True),  # Downsampled with ds metadata available
            (True, False),  # Downsampled but ds metadata missing (fallback)
            (False, False),  # Not downsampled
        ],
    )
    def test_downsampled_metadata_handling(
        self, basic_dataframe: pd.DataFrame, is_downsampled: bool, has_ds_metadata: bool
    ) -> None:
        """Test various downsampled metadata scenarios."""
        net = TestDataFormatHelpers.create_mock_network(
            has_metadata=True, is_downsampled=is_downsampled
        )

        if not has_ds_metadata and is_downsampled:
            # Remove downsampled metadata to test fallback
            delattr(net, "meta_ds_row")
            delattr(net, "meta_ds_col")

        with TestDataFormatHelpers.patch_dependencies() as (mock_unique, mock_dict_cat):
            mock_unique.return_value = basic_dataframe

            df_to_dat(net, basic_dataframe)

            # Should successfully process regardless of downsampling scenario
            assert CATEGORY_ZERO in net.dat["node_info"]["row"]
            assert CATEGORY_ZERO in net.dat["node_info"]["col"]

    @pytest.mark.parametrize(
        "dataframe_factory,expected_shape",
        [
            (lambda: pd.DataFrame(), (0, 0)),  # Empty DataFrame
            (
                lambda: pd.DataFrame(SINGLE_CELL_DATA, index=SINGLE_CELL_INDEX),
                (1, 1),
            ),  # Single cell
        ],
    )
    def test_edge_case_dataframes(
        self, mock_network: Mock, dataframe_factory, expected_shape
    ) -> None:
        """Test handling of edge case DataFrame dimensions."""
        df = dataframe_factory()

        with TestDataFormatHelpers.patch_dependencies() as (mock_unique, mock_dict_cat):
            mock_unique.return_value = df

            df_to_dat(mock_network, df)

            assert mock_network.dat["mat"].shape == expected_shape
            assert len(mock_network.dat["nodes"]["row"]) == expected_shape[0]
            assert len(mock_network.dat["nodes"]["col"]) == expected_shape[1]


# =============================================================================
# TEST CLASSES - DAT_TO_DF FUNCTION
# =============================================================================


class TestDatToDf:
    """Tests for dat_to_df function - converts internal data to DataFrame."""

    def test_basic_conversion_to_dataframe(self, mock_network: Mock) -> None:
        """Test basic internal data to DataFrame conversion."""
        mock_network.dat.update(
            {
                "mat": [[1, 2, 3], [4, 5, 6]],
                "nodes": {"row": ["row1", "row2"], "col": BASIC_COL_NAMES},
            }
        )

        result_df = dat_to_df(mock_network)
        expected_df = pd.DataFrame(
            {"col1": [1, 4], "col2": [2, 5], "col3": [3, 6]}, index=["row1", "row2"]
        )

        pd.testing.assert_frame_equal(result_df, expected_df)

    def test_conversion_with_full_names(self, mock_network: Mock) -> None:
        """Test conversion when full tuple names are preserved."""
        mock_network.dat.update(
            {
                "mat": [[1, 2], [3, 4]],
                "nodes": {"row": ["r1", "r2"], "col": ["c1", "c2"]},
                "node_info": {
                    "row": {"full_names": [("r1", "cat: A"), ("r2", "cat: B")]},
                    "col": {"full_names": [("c1", "type: X"), ("c2", "type: Y")]},
                },
            }
        )

        result_df = dat_to_df(mock_network)

        # Verify tuple structure is restored
        expected_index = [("r1", "cat: A"), ("r2", "cat: B")]
        expected_columns = [("c1", "type: X"), ("c2", "type: Y")]

        assert list(result_df.index) == expected_index
        assert list(result_df.columns) == expected_columns
        np.testing.assert_array_equal(result_df.values, [[1, 2], [3, 4]])

    @pytest.mark.parametrize(
        "mat,rows,cols,should_raise",
        [
            ([], [], [], False),  # Empty data - valid
            ([[1, 2]], ["row1"], ["col1"], True),  # Mismatched dimensions - invalid
            (
                [[1, 2, 3], [4, 5, 6]],
                ["row1"],
                ["col1", "col2"],
                True,
            ),  # Mismatched dimensions - invalid
        ],
    )
    def test_dimension_validation(
        self, mock_network: Mock, mat: list, rows: list, cols: list, should_raise: bool
    ) -> None:
        """Test validation of matrix dimensions against node names."""
        mock_network.dat.update({"mat": mat, "nodes": {"row": rows, "col": cols}})

        if should_raise:
            with pytest.raises((ValueError, IndexError)):
                dat_to_df(mock_network)
        else:
            result_df = dat_to_df(mock_network)
            assert result_df.empty if not mat else not result_df.empty


# =============================================================================
# TEST CLASSES - MAT_TO_NUMPY_ARR FUNCTION
# =============================================================================


class TestMatToNumpyArr:
    """Tests for mat_to_numpy_arr function - converts matrix to numpy array."""

    @pytest.mark.parametrize(
        "input_data,expected_type",
        [
            ([[1, 2, 3], [4, 5, 6]], np.ndarray),  # List to array
            (np.array([[1, 2], [3, 4]]), np.ndarray),  # Already array
            ([], np.ndarray),  # Empty list
            ([[], []], np.ndarray),  # Nested empty lists
        ],
    )
    def test_matrix_conversion_scenarios(self, input_data: Any, expected_type: type) -> None:
        """Test various matrix conversion scenarios."""
        mock_network = Mock()
        mock_network.dat = {"mat": input_data}

        mat_to_numpy_arr(mock_network)

        assert isinstance(mock_network.dat["mat"], expected_type)
        if hasattr(input_data, "shape"):
            # For numpy arrays, verify shape is preserved
            np.testing.assert_array_equal(mock_network.dat["mat"], input_data)


# =============================================================================
# TEST CLASSES - EDGE CASES AND ERROR CONDITIONS
# =============================================================================


class TestEdgeCasesAndErrorConditions:
    """Comprehensive edge case and error condition testing."""

    @pytest.mark.parametrize(
        "row_names,col_names,data",
        [
            (UNICODE_ROW_NAMES, UNICODE_COL_NAMES, UNICODE_DATA),  # Unicode characters
            (NUMERIC_ROW_NAMES, NUMERIC_COL_NAMES, NUMERIC_DATA),  # Numeric labels
        ],
    )
    def test_special_character_handling(
        self, mock_network: Mock, row_names: list, col_names: list, data: list
    ) -> None:
        """Test handling of special characters and numeric labels."""
        df = pd.DataFrame(
            dict(zip(col_names, zip(*data, strict=False), strict=False)), index=row_names
        )

        with TestDataFormatHelpers.patch_dependencies() as (mock_unique, mock_dict_cat):
            mock_unique.return_value = df

            df_to_dat(mock_network, df)

            assert mock_network.dat["nodes"]["row"] == row_names
            assert mock_network.dat["nodes"]["col"] == col_names

    def test_missing_metadata_attributes(self, basic_dataframe: pd.DataFrame) -> None:
        """Test behavior when expected metadata attributes are missing."""
        net = TestDataFormatHelpers.create_mock_network(has_metadata=True)
        delattr(net, "row_cats")  # Remove row_cats to test graceful handling

        with TestDataFormatHelpers.patch_dependencies() as (mock_unique, mock_dict_cat):
            mock_unique.return_value = basic_dataframe

            df_to_dat(net, basic_dataframe)

            # Should still process col_cats without crashing
            assert CATEGORY_ZERO in net.dat["node_info"]["col"]
            assert CATEGORY_ZERO not in net.dat["node_info"]["row"]

    def test_metadata_index_mismatch(self, basic_dataframe: pd.DataFrame) -> None:
        """Test handling when metadata indices don't match DataFrame indices."""
        net = TestDataFormatHelpers.create_mock_network(has_metadata=True)
        net.meta_row.index = ["different1", "different2", "different3"]

        with TestDataFormatHelpers.patch_dependencies() as (mock_unique, mock_dict_cat):
            mock_unique.return_value = basic_dataframe

            with pytest.raises(KeyError):
                df_to_dat(net, basic_dataframe)

    def test_complex_tuple_structures(self, mock_network: Mock) -> None:
        """Test handling of tuples with multiple category levels."""
        complex_df = pd.DataFrame(
            {
                ("col1", "cat1: A", "cat2: X", "cat3: I"): [1, 2],
                ("col2", "cat1: B", "cat2: Y", "cat3: J"): [3, 4],
            },
            index=[
                ("row1", "grp1: P", "grp2: M"),
                ("row2", "grp1: Q", "grp2: N"),
            ],
        )

        with TestDataFormatHelpers.patch_dependencies() as (mock_unique, mock_dict_cat):
            mock_unique.return_value = complex_df

            df_to_dat(mock_network, complex_df)

            # Row tuples have 3 elements (name + 2 categories), so expect cat-0 and cat-1
            row_categories = [CATEGORY_ZERO, CATEGORY_ONE]
            for category in row_categories:
                assert category in mock_network.dat["node_info"]["row"]

            # Column tuples have 4 elements (name + 3 categories), so expect cat-0, cat-1, and cat-2
            col_categories = [CATEGORY_ZERO, CATEGORY_ONE, CATEGORY_TWO]
            for category in col_categories:
                assert category in mock_network.dat["node_info"]["col"]

    @pytest.mark.parametrize(
        "row_cats,col_cats",
        [
            (None, ["category2"]),  # None row_cats
            (["category1"], None),  # None col_cats
            (None, None),  # Both None
        ],
    )
    def test_none_category_handling(
        self, basic_dataframe: pd.DataFrame, row_cats: list[str] | None, col_cats: list[str] | None
    ) -> None:
        """Test handling of None category lists."""
        net = TestDataFormatHelpers.create_mock_network(has_metadata=True)
        net.row_cats = row_cats
        net.col_cats = col_cats

        with TestDataFormatHelpers.patch_dependencies() as (mock_unique, mock_dict_cat):
            mock_unique.return_value = basic_dataframe

            # Should not crash with None category lists
            df_to_dat(net, basic_dataframe)

            # Verify appropriate category processing based on None values
            if row_cats is None:
                assert CATEGORY_ZERO not in net.dat["node_info"]["row"]
            if col_cats is None:
                assert CATEGORY_ZERO not in net.dat["node_info"]["col"]

    def test_mixed_data_types_preservation(self, mock_network: Mock) -> None:
        """Test that mixed data types in matrices are preserved correctly."""
        mixed_df = pd.DataFrame(
            {"col1": [1, 2.5, np.nan], "col2": [3.0, np.inf, -np.inf], "col3": [0, 1e-10, 1e10]},
            index=BASIC_ROW_NAMES,
        )

        with TestDataFormatHelpers.patch_dependencies() as (mock_unique, mock_dict_cat):
            mock_unique.return_value = mixed_df

            df_to_dat(mock_network, mixed_df)

            # Verify special values are preserved
            matrix = mock_network.dat["mat"]
            assert np.isnan(matrix[2][0])  # NaN preserved
            assert np.isinf(matrix[1][1])  # Inf preserved
            assert matrix[2][2] == 1e10  # Large numbers preserved

    def test_large_dataframe_handling(self, mock_network: Mock) -> None:
        """Test memory efficiency with large data structures."""
        large_data = np.random.randn(LARGE_DATAFRAME_SIZE, LARGE_DATAFRAME_SIZE)
        large_df = pd.DataFrame(
            data=large_data,
            columns=[f"col_{i}" for i in range(LARGE_DATAFRAME_SIZE)],
            index=[f"row_{i}" for i in range(LARGE_DATAFRAME_SIZE)],
        )

        with TestDataFormatHelpers.patch_dependencies() as (mock_unique, mock_dict_cat):
            mock_unique.return_value = large_df

            df_to_dat(mock_network, large_df)

            # Verify data integrity is maintained for large datasets
            np.testing.assert_array_equal(mock_network.dat["mat"], large_data)
            assert len(mock_network.dat["nodes"]["row"]) == LARGE_DATAFRAME_SIZE
            assert len(mock_network.dat["nodes"]["col"]) == LARGE_DATAFRAME_SIZE


# =============================================================================
# TEST CLASSES - INTEGRATION SCENARIOS
# =============================================================================


class TestIntegrationScenarios:
    """Integration tests combining multiple features and edge cases."""

    def test_real_world_bioinformatics_scenario(self) -> None:
        """Test a complex scenario mimicking real-world bioinformatics usage."""
        # Create complex DataFrame representing gene expression data
        gene_expression_df = pd.DataFrame(
            {"gene_1": [1.5, 2.0, 0.5], "gene_2": [3.2, 1.1, 2.8], "gene_3": [0.0, 4.5, 1.9]},
            index=["cell_001", "cell_002", "cell_003"],
        )

        # Create network with comprehensive metadata
        net = TestDataFormatHelpers.create_mock_network(has_metadata=True)

        # Enhanced metadata with multiple categories
        net.meta_col = pd.DataFrame(
            {
                "gene_type": ["oncogene", "tumor_suppressor", "oncogene"],
                "chromosome": ["chr1", "chr2", "chr1"],
            },
            index=["gene_1", "gene_2", "gene_3"],
        )

        net.meta_row = pd.DataFrame(
            {
                "cell_type": ["T_cell", "B_cell", "T_cell"],
                "treatment": ["control", "treated", "control"],
            },
            index=["cell_001", "cell_002", "cell_003"],
        )

        net.col_cats = ["gene_type", "chromosome"]
        net.row_cats = ["cell_type", "treatment"]

        with TestDataFormatHelpers.patch_dependencies() as (mock_unique, mock_dict_cat):
            mock_unique.return_value = gene_expression_df

            df_to_dat(net, gene_expression_df)

            # Verify all categories are processed correctly
            for axis in ["row", "col"]:
                assert CATEGORY_ZERO in net.dat["node_info"][axis]
                assert CATEGORY_ONE in net.dat["node_info"][axis]

            # Verify matrix integrity for scientific data
            np.testing.assert_array_equal(net.dat["mat"], gene_expression_df.values)

            # Test round-trip conversion
            reconstructed_df = dat_to_df(net)
            pd.testing.assert_frame_equal(
                reconstructed_df,
                gene_expression_df,
                check_exact=False,
                rtol=1e-10,  # Allow for floating point precision
            )

    def test_round_trip_data_integrity(self, basic_dataframe: pd.DataFrame) -> None:
        """Test that data maintains integrity through conversion cycles."""
        net = TestDataFormatHelpers.create_mock_network()

        with TestDataFormatHelpers.patch_dependencies() as (mock_unique, mock_dict_cat):
            mock_unique.return_value = basic_dataframe

            # Convert DataFrame to internal format
            df_to_dat(net, basic_dataframe)

            # Convert numpy array format
            mat_to_numpy_arr(net)

            # Convert back to DataFrame
            result_df = dat_to_df(net)

            # Verify complete round-trip integrity
            pd.testing.assert_frame_equal(result_df, basic_dataframe)
            assert isinstance(net.dat["mat"], np.ndarray)


# =============================================================================
# MAIN EXECUTION
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
