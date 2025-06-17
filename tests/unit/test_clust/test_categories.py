# =============================================================================
# COMPREHENSIVE TEST SUITE FOR CATEGORIES.PY MODULE
# =============================================================================
"""
Comprehensive test suite for categories.py module.

This test suite provides extensive coverage for all functions in the categories module,
including edge cases, error conditions, and boundary value testing with improved
robustness, consistency, and maintainability.
"""

# =============================================================================
# IMPORTS
# =============================================================================

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
import sys
from typing import Any
from unittest.mock import Mock, patch

import pandas as pd
import pytest


# =============================================================================
# MODULE-LEVEL CONSTANTS
# =============================================================================

# Path and module constants
TEST_DATA_DIR = Path(__file__).parent.parent / "src"
MODULE_PATH = "celldega.clust.categories.categories"

# Test data constants
SAMPLE_HEADER_WITH_CATEGORIES = "col1\t\t\tval1\tval2\tval3"
SAMPLE_COL_CATEGORY_LINE = "\t\t\trow1_cat1\trow1_cat2"
MINIMAL_HEADER = "col1\tval1\tval2"
MINIMAL_DATA_ROW = "gene1\t10\t20"

# Expected color constants
FIRST_COLOR = "#393b79"
SECOND_COLOR = "#aec7e8"
LAST_COLOR = "#de9ed6"
FALSE_COLOR = "#eee"

# Mock data constants
MOCK_CATEGORIES_ROW = ["Type: type1", "Type: type1", "Type: type2", "Type: type2"]
MOCK_CATEGORIES_COL = ["Sample: sample1", "Sample: sample1", "Sample: sample2", "Sample: sample2"]
MOCK_NODES_ROW = ["gene1", "gene2", "gene3", "gene4"]
MOCK_NODES_COL = ["cell1", "cell2", "cell3", "cell4"]

# Test limits and performance constants
MAX_COLUMN_CATEGORY_LINES = 15
PERFORMANCE_TIMEOUT_SECONDS = 1.0
LARGE_DATASET_SIZE = 10000

# Dictionary keys
DICT_CAT_PREFIX = "dict_cat_"
CAT_INDEX_SUFFIX = "_index"
CAT_COLORS_KEY = "cat_colors"
GLOBAL_CAT_COLORS_KEY = "global_cat_colors"

# Axis constants
ROW_AXIS = "row"
COL_AXIS = "col"
VALID_AXES = [ROW_AXIS, COL_AXIS]

# Import the module under test
sys.path.insert(0, str(TEST_DATA_DIR))
from celldega.clust.categories import categories


# =============================================================================
# HELPER CLASSES AND UTILITIES
# =============================================================================


class TestCategoriesHelpers:
    """Helper methods and utilities for categories testing."""

    @staticmethod
    def create_mock_network(
        row_categories: dict[str, list[str]] | None = None,
        col_categories: dict[str, list[str]] | None = None,
        row_nodes: list[str] | None = None,
        col_nodes: list[str] | None = None,
        include_viz: bool = True,
    ) -> Mock:
        """Create a standardized mock network object for testing.

        Args:
            row_categories: Dictionary of row category data (None means use defaults, {} means empty)
            col_categories: Dictionary of column category data (None means use defaults, {} means empty)
            row_nodes: List of row node names
            col_nodes: List of column node names
            include_viz: Whether to include viz structure

        Returns:
            Mock network object with specified structure
        """
        net = Mock()
        net.persistent_cat_colors = True

        # Set default values if None provided, preserve {} if explicitly passed
        if row_categories is None:
            row_categories = {"cat-0": MOCK_CATEGORIES_ROW}
        if col_categories is None:
            col_categories = {"cat-0": MOCK_CATEGORIES_COL}

        row_nodes = row_nodes or MOCK_NODES_ROW
        col_nodes = col_nodes or MOCK_NODES_COL

        net.dat = {
            "node_info": {
                ROW_AXIS: row_categories,
                COL_AXIS: col_categories,
            },
            "nodes": {
                ROW_AXIS: row_nodes,
                COL_AXIS: col_nodes,
            },
        }

        if include_viz:
            net.viz = {CAT_COLORS_KEY: {ROW_AXIS: {}, COL_AXIS: {}}}

        return net

    @staticmethod
    def create_mock_dataframe(
        row_labels: list[str] | None = None, col_labels: list[str] | None = None
    ) -> Mock:
        """Create a mock DataFrame for testing add_cats functionality.

        Args:
            row_labels: List of row labels (default: gene names)
            col_labels: List of column labels (default: cell names)

        Returns:
            Mock DataFrame object
        """
        mock_df = Mock(spec=pd.DataFrame)
        mock_df.index.tolist.return_value = row_labels or ["gene1", "gene2", "gene3"]
        mock_df.columns.tolist.return_value = col_labels or ["cell1", "cell2", "cell3"]
        return mock_df

    @staticmethod
    def assert_category_counts(
        result: dict[str, int], expected_row: int, expected_col: int
    ) -> None:
        """Assert category count results match expected values.

        Args:
            result: Dictionary with 'row' and 'col' keys
            expected_row: Expected row category count
            expected_col: Expected column category count
        """
        assert isinstance(result, dict)
        assert set(result.keys()) == {ROW_AXIS, COL_AXIS}
        assert result[ROW_AXIS] == expected_row
        assert result[COL_AXIS] == expected_col

    @staticmethod
    @contextmanager
    def patch_pandas_series() -> Generator[Mock, None, None]:
        """Context manager for patching pandas.Series with error simulation."""
        with patch("pandas.Series", side_effect=Exception("Mock error")) as mock_series:
            yield mock_series

    @staticmethod
    def create_extended_category_network(num_categories: int = 2) -> Mock:
        """Create a network with multiple category levels for testing.

        Args:
            num_categories: Number of category levels to create

        Returns:
            Mock network with multiple categories
        """
        row_categories = {}
        col_categories = {}

        for i in range(num_categories):
            cat_key = f"cat-{i}"
            dict_key = f"dict_cat_{i}"

            row_categories[cat_key] = [f"RowCat{i}: value{j}" for j in range(4)]
            col_categories[cat_key] = [f"ColCat{i}: value{j}" for j in range(4)]

            row_categories[dict_key] = {
                f"RowCat{i}: value0": ["gene1", "gene2"],
                f"RowCat{i}: value1": ["gene3", "gene4"],
            }
            col_categories[dict_key] = {
                f"ColCat{i}: value0": ["cell1", "cell2"],
                f"ColCat{i}: value1": ["cell3", "cell4"],
            }

        return TestCategoriesHelpers.create_mock_network(
            row_categories=row_categories, col_categories=col_categories, include_viz=False
        )


# =============================================================================
# PYTEST FIXTURES
# =============================================================================


@pytest.fixture
def sample_lines() -> list[str]:
    """Fixture providing sample input lines for testing."""
    return [
        SAMPLE_HEADER_WITH_CATEGORIES,
        SAMPLE_COL_CATEGORY_LINE,
        "\t\t\trow2_cat1\trow2_cat2",
        "gene1\t10\t20\t30\t40\t50",
        "gene2\t15\t25\t35\t45\t55",
    ]


@pytest.fixture
def minimal_lines() -> list[str]:
    """Fixture for minimal valid input."""
    return [MINIMAL_HEADER, MINIMAL_DATA_ROW]


@pytest.fixture
def max_category_lines() -> list[str]:
    """Fixture for testing the 15-line limit."""
    lines = ["col1" + "\t" * 16 + "val1\tval2"]  # 16 empty categories
    # Add 20 empty lines to test the limit
    for i in range(20):
        lines.extend("\t" * 16 + f"cat{i}_1\tcat{i}_2")
    lines.extend(["gene1\t10\t20", "gene2\t15\t25"])
    return lines


@pytest.fixture
def mock_network() -> Mock:
    """Create a mock network object with comprehensive category structure."""
    return TestCategoriesHelpers.create_mock_network(
        row_categories={
            "cat-0": MOCK_CATEGORIES_ROW,
            "cat-1": ["Level: high", "Level: low", "Level: high", "Level: medium"],
        },
        col_categories={
            "cat-0": MOCK_CATEGORIES_COL,
            "cat-1": [
                "Treatment: treated",
                "Treatment: control",
                "Treatment: treated",
                "Treatment: control",
            ],
        },
    )


@pytest.fixture
def mock_network_for_add_cats() -> tuple[Mock, Mock]:
    """Create a mock network for testing add_cats."""
    net = Mock()
    mock_df = TestCategoriesHelpers.create_mock_dataframe()
    net.export_df.return_value = mock_df
    net.load_df = Mock()
    return net, mock_df


# =============================================================================
# TEST CLASSES - CHECK_CATEGORIES FUNCTION
# =============================================================================


class TestCheckCategories:
    """Test suite for check_categories function."""

    def test_empty_input(self) -> None:
        """Test check_categories with empty input."""
        result = categories.check_categories([])
        TestCategoriesHelpers.assert_category_counts(result, 1, 1)

    def test_basic_category_detection(self, sample_lines: list[str]) -> None:
        """Test basic category detection functionality."""
        result = categories.check_categories(sample_lines)
        TestCategoriesHelpers.assert_category_counts(result, 3, 3)  # 2 empty + 1, 2 empty lines + 1

    def test_minimal_input(self, minimal_lines: list[str]) -> None:
        """Test with minimal valid input (no categories)."""
        result = categories.check_categories(minimal_lines)
        TestCategoriesHelpers.assert_category_counts(result, 1, 1)

    def test_fifteen_line_limit(self, max_category_lines: list[str]) -> None:
        """Test that the function respects the 15-line limit for column categories."""
        result = categories.check_categories(max_category_lines)
        TestCategoriesHelpers.assert_category_counts(result, 16, 16)  # 15 processed + 1

    def test_single_line_input(self) -> None:
        """Test edge case with only header line."""
        result = categories.check_categories([MINIMAL_HEADER])
        TestCategoriesHelpers.assert_category_counts(result, 1, 1)

    @pytest.mark.parametrize("row_cats,expected_row", [(0, 1), (1, 2), (2, 3), (5, 6), (10, 11)])
    def test_various_row_counts(self, row_cats: int, expected_row: int) -> None:
        """Test various numbers of row categories."""
        header = "col1" + "\t" * row_cats + "\tval1\tval2"
        lines = [header, "gene1\t" + "\t" * row_cats + "10\t20"]

        result = categories.check_categories(lines)
        assert result[ROW_AXIS] == expected_row

    def test_malformed_lines(self) -> None:
        """Test handling of malformed input lines."""
        lines = [
            MINIMAL_HEADER,
            "\tcat1\tcat2",  # Valid category line
            "",  # Empty line
            "\t",  # Line with only tab
            MINIMAL_DATA_ROW,
        ]
        result = categories.check_categories(lines)
        TestCategoriesHelpers.assert_category_counts(result, 1, 3)  # 1 valid + empty line counts


# =============================================================================
# TEST CLASSES - DICT_CAT FUNCTION
# =============================================================================


class TestDictCat:
    """Test suite for dict_cat function."""

    def test_basic_functionality(self, mock_network: Mock) -> None:
        """Test basic dictionary creation from categories."""
        categories.dict_cat(mock_network)

        # Verify dictionary creation
        row_info = mock_network.dat["node_info"][ROW_AXIS]
        col_info = mock_network.dat["node_info"][COL_AXIS]

        assert "dict_cat_0" in row_info
        assert "dict_cat_1" in row_info
        assert "dict_cat_0" in col_info
        assert "dict_cat_1" in col_info

        # Verify dictionary contents
        row_dict_0 = row_info["dict_cat_0"]
        assert row_dict_0["Type: type1"] == ["gene1", "gene2"]
        assert row_dict_0["Type: type2"] == ["gene3", "gene4"]

    def test_color_assignment(self, mock_network: Mock) -> None:
        """Test category color definition."""
        categories.dict_cat(mock_network, define_cat_colors=True)

        # Verify color structure creation
        cat_colors = mock_network.viz[CAT_COLORS_KEY]
        assert "cat-0" in cat_colors[ROW_AXIS]
        assert "cat-0" in cat_colors[COL_AXIS]
        assert GLOBAL_CAT_COLORS_KEY in mock_network.viz

    def test_false_category_coloring(self) -> None:
        """Test special coloring for 'False' categories."""
        net = TestCategoriesHelpers.create_mock_network(
            row_categories={
                "cat-0": [
                    "Category: True",
                    "Category: False",
                    "Category: Not applicable",
                    "Category: Valid",
                ]
            },
            row_nodes=MOCK_NODES_ROW,
        )

        categories.dict_cat(net, define_cat_colors=True)

        colors = net.viz[CAT_COLORS_KEY][ROW_AXIS]["cat-0"]
        assert colors["Category: False"] == FALSE_COLOR
        assert colors["Category: Not applicable"] == FALSE_COLOR
        assert colors["Category: True"] != FALSE_COLOR
        assert colors["Category: Valid"] != FALSE_COLOR

    def test_empty_categories(self) -> None:
        """Test handling of empty category lists."""
        net = TestCategoriesHelpers.create_mock_network(
            row_categories={}, col_categories={}, row_nodes=[], col_nodes=[]
        )

        # Should not raise an error
        categories.dict_cat(net)

    def test_existing_colors_preserved(self, mock_network: Mock) -> None:
        """Test that existing colors are preserved."""
        existing_color = "#123456"
        mock_network.viz[CAT_COLORS_KEY][ROW_AXIS]["cat-0"] = {
            "Type: existing_type": existing_color
        }

        categories.dict_cat(mock_network, define_cat_colors=True)

        assert (
            mock_network.viz[CAT_COLORS_KEY][ROW_AXIS]["cat-0"]["Type: existing_type"]
            == existing_color
        )


# =============================================================================
# TEST CLASSES - CALC_CAT_CLUST_ORDER FUNCTION
# =============================================================================


class TestCalcCatClustOrder:
    """Test suite for calc_cat_clust_order function."""

    @pytest.fixture
    def mock_network_with_categories(self) -> Mock:
        """Create mock network with category data for clustering order tests."""
        return TestCategoriesHelpers.create_mock_network(
            row_categories={
                "cat-0": ["B", "A", "C", "A", "B"],
                "dict_cat_0": {
                    "A": ["gene2", "gene4"],
                    "B": ["gene1", "gene5"],
                    "C": ["gene3"],
                },
            },
            row_nodes=["gene1", "gene2", "gene3", "gene4", "gene5"],
            include_viz=False,
        )

    def test_basic_ordering(self, mock_network_with_categories: Mock) -> None:
        """Test basic category cluster ordering."""
        categories.calc_cat_clust_order(mock_network_with_categories, ROW_AXIS)

        row_info = mock_network_with_categories.dat["node_info"][ROW_AXIS]
        assert "cat_0_index" in row_info

        index_order = row_info["cat_0_index"]
        assert len(index_order) == 5
        assert all(isinstance(x, int) for x in index_order)

    def test_no_categories(self) -> None:
        """Test when there are no categories to process."""
        net = TestCategoriesHelpers.create_mock_network(
            row_categories={},  # Explicitly empty
            row_nodes=["gene1", "gene2"],
            include_viz=False,
        )

        categories.calc_cat_clust_order(net, ROW_AXIS)
        # Should have no 'cat-' keys, so no processing occurs
        cat_keys = [k for k in net.dat["node_info"][ROW_AXIS] if "cat-" in k]
        assert len(cat_keys) == 0

    def test_multiple_categories(self) -> None:
        """Test with multiple category levels."""
        net = TestCategoriesHelpers.create_mock_network(
            col_categories={
                "cat-0": ["X", "Y"],
                "cat-1": ["1", "2"],
                "dict_cat_0": {"X": ["cell1"], "Y": ["cell2"]},
                "dict_cat_1": {"1": ["cell1"], "2": ["cell2"]},
            },
            col_nodes=["cell1", "cell2"],
            include_viz=False,
        )

        categories.calc_cat_clust_order(net, COL_AXIS)

        col_info = net.dat["node_info"][COL_AXIS]
        assert "cat_0_index" in col_info
        assert "cat_1_index" in col_info

    @pytest.mark.parametrize("axis", VALID_AXES)
    def test_both_axes(self, axis: str) -> None:
        """Test calc_cat_clust_order works for both axes."""
        net = TestCategoriesHelpers.create_mock_network(include_viz=False)
        net.dat["node_info"][axis] = {
            "cat-0": ["A", "B"],
            "dict_cat_0": {"A": ["item1"], "B": ["item2"]},
        }
        net.dat["nodes"][axis] = ["item1", "item2"]

        categories.calc_cat_clust_order(net, axis)
        assert "cat_0_index" in net.dat["node_info"][axis]


# =============================================================================
# TEST CLASSES - ORDER_CATEGORIES FUNCTION
# =============================================================================


class TestOrderCategories:
    """Test suite for order_categories function."""

    @pytest.mark.parametrize(
        "input_cats,expected",
        [
            (["Zebra", "Apple", "Banana"], ["Apple", "Banana", "Zebra"]),
            (["10.5", "2.1", "5.0"], ["2.1", "5.0", "10.5"]),
            (
                ["Type: High", "Type: Low", "Type: Medium"],
                ["Type: High", "Type: Low", "Type: Medium"],
            ),
            (
                ["Score: 10.5", "Score: 2.1", "Score: 5.0"],
                ["Score: 2.1", "Score: 5.0", "Score: 10.5"],
            ),
            ([], []),
            (["single"], ["single"]),
        ],
    )
    def test_ordering_scenarios(self, input_cats: list[str], expected: list[str]) -> None:
        """Test various ordering scenarios."""
        result = categories.order_categories(input_cats)
        assert result == expected

    def test_mixed_numeric_string_fallback(self) -> None:
        """Test ordering when some categories are numeric and others are not."""
        unordered = ["10", "apple", "5", "banana"]
        result = categories.order_categories(unordered)
        # Should fall back to alphabetical ordering
        assert result == ["10", "5", "apple", "banana"]

    def test_error_handling_in_ordering(self) -> None:
        """Test error handling in numeric ordering."""
        with TestCategoriesHelpers.patch_pandas_series():
            unordered = ["Type: 3", "Type: 1", "Type: 2"]
            values_list = ["3", "1", "2"]

            result = categories.order_cats_based_on_values(unordered, values_list)
            assert result == unordered


# =============================================================================
# TEST CLASSES - ORDER_CATS_BASED_ON_VALUES FUNCTION
# =============================================================================


class TestOrderCatsBasedOnValues:
    """Test suite for order_cats_based_on_values function."""

    @pytest.mark.parametrize(
        "categories_list,values,expected",
        [
            (
                ["Score: 10", "Score: 5", "Score: 15"],
                ["10", "5", "15"],
                ["Score: 5", "Score: 10", "Score: 15"],
            ),
            (["A", "B", "C"], ["10.5", "2.1", "5.0"], ["B", "C", "A"]),
            (["A", "B", "C"], ["10", "-5", "0"], ["B", "C", "A"]),
        ],
    )
    def test_numeric_ordering(
        self, categories_list: list[str], values: list[str], expected: list[str]
    ) -> None:
        """Test numeric ordering with various inputs."""
        result = categories.order_cats_based_on_values(categories_list, values)
        assert result == expected

    def test_error_handling(self) -> None:
        """Test error handling when values can't be converted to float."""
        unordered = ["A", "B", "C"]
        values = ["not_a_number", "5", "10"]

        result = categories.order_cats_based_on_values(unordered, values)
        assert result == unordered


# =============================================================================
# TEST CLASSES - HELPER FUNCTIONS
# =============================================================================


class TestHelperFunctions:
    """Test suite for helper functions."""

    @pytest.mark.parametrize(
        "input_val,expected",
        [
            ("123", True),
            ("123.45", True),
            ("-123", True),
            ("-123.45", True),
            ("0", True),
            ("0.0", True),
            ("abc", False),
            ("", False),
            ("123abc", False),
            ("12.34.56", False),
            (None, False),
        ],
    )
    def test_is_number(self, input_val: Any, expected: bool) -> None:
        """Test is_number function with various inputs."""
        assert categories.is_number(input_val) == expected

    @pytest.mark.parametrize(
        "input_list,expected",
        [
            (["1", "2.5", "-3"], True),
            (["1", "abc", "3"], False),
            ([], True),  # vacuously true
        ],
    )
    def test_check_all_numbers(self, input_list: list[str], expected: bool) -> None:
        """Test check_all_numbers function."""
        assert categories.check_all_numbers(input_list) == expected

    @pytest.mark.parametrize(
        "input_cats,expected",
        [
            (["Type: A", "Type: B", "Type: C"], ["A", "B", "C"]),
            (["A", "B", "C"], ["A", "B", "C"]),
            (["Type: A", "B", "1"], ["Type: A", "B", "1"]),  # Mixed - should not remove
        ],
    )
    def test_remove_titles(self, input_cats: list[str], expected: list[str]) -> None:
        """Test remove_titles function."""
        result = categories.remove_titles(input_cats)
        assert result == expected

    @pytest.mark.parametrize(
        "cat_num,expected",
        [
            (0, FIRST_COLOR),
            (1, SECOND_COLOR),
            (34, LAST_COLOR),
            (35, FIRST_COLOR),  # Should wrap around
            (70, FIRST_COLOR),  # Multiple wraps
        ],
    )
    def test_get_cat_color(self, cat_num: int, expected: str) -> None:
        """Test get_cat_color function with various indices."""
        assert categories.get_cat_color(cat_num) == expected


# =============================================================================
# TEST CLASSES - ADD_CATS FUNCTION
# =============================================================================


class TestAddCats:
    """Test suite for add_cats function."""

    @pytest.mark.parametrize("axis", VALID_AXES)
    def test_basic_functionality(
        self, mock_network_for_add_cats: tuple[Mock, Mock], axis: str
    ) -> None:
        """Test basic functionality of add_cats for both axes."""
        net, mock_df = mock_network_for_add_cats

        cat_data = {
            "title": "Cell Type" if axis == ROW_AXIS else "Treatment",
            "cats": {"Type A": ["gene1", "gene3"], "Type B": ["gene2"]}
            if axis == ROW_AXIS
            else {"Treated": ["cell1"], "Control": ["cell2", "cell3"]},
        }

        categories.add_cats(net, axis, cat_data)

        net.export_df.assert_called_once()
        net.load_df.assert_called_once()

    def test_with_existing_tuples(self, mock_network_for_add_cats: tuple[Mock, Mock]) -> None:
        """Test add_cats when labels are already tuples."""
        net, mock_df = mock_network_for_add_cats
        mock_df.index.tolist.return_value = [("gene1", "existing_cat"), ("gene2", "existing_cat")]

        cat_data = {"title": "New Category", "cats": {"Group A": ["gene1"]}}
        categories.add_cats(net, ROW_AXIS, cat_data)

        net.export_df.assert_called_once()
        net.load_df.assert_called_once()

    def test_with_titled_labels(self, mock_network_for_add_cats: tuple[Mock, Mock]) -> None:
        """Test add_cats when labels contain titles."""
        net, mock_df = mock_network_for_add_cats
        mock_df.index.tolist.return_value = ["Type: gene1", "Type: gene2"]

        cat_data = {"title": "Expression", "cats": {"High": ["gene1"], "Low": ["gene2"]}}
        categories.add_cats(net, ROW_AXIS, cat_data)

        net.export_df.assert_called_once()
        net.load_df.assert_called_once()

    def test_no_title_provided(self, mock_network_for_add_cats: tuple[Mock, Mock]) -> None:
        """Test add_cats when no title is provided."""
        net, mock_df = mock_network_for_add_cats
        cat_data = {"cats": {"Group A": ["gene1"], "Group B": ["gene2"]}}

        categories.add_cats(net, ROW_AXIS, cat_data)

        net.export_df.assert_called_once()
        net.load_df.assert_called_once()

    def test_error_handling(
        self, mock_network_for_add_cats: tuple[Mock, Mock], capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test error handling in add_cats function."""
        net, mock_df = mock_network_for_add_cats
        net.export_df.side_effect = Exception("Test error")

        cat_data = {"title": "Test", "cats": {"A": ["gene1"]}}
        categories.add_cats(net, ROW_AXIS, cat_data)

        captured = capsys.readouterr()
        assert "Error adding categories: Test error" in captured.out

    def test_invalid_axis(
        self, mock_network_for_add_cats: tuple[Mock, Mock], capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test add_cats with invalid axis parameter."""
        net, mock_df = mock_network_for_add_cats
        cat_data = {"title": "Test", "cats": {"A": ["gene1"]}}

        # The function catches all exceptions and prints error message
        categories.add_cats(net, "invalid", cat_data)

        captured = capsys.readouterr()
        assert "Invalid axis 'invalid'. Must be 'row' or 'col'." in captured.out

    def test_empty_categories(self, mock_network_for_add_cats: tuple[Mock, Mock]) -> None:
        """Test add_cats with empty category groups."""
        net, mock_df = mock_network_for_add_cats
        cat_data = {"title": "Empty Test", "cats": {"Group A": [], "Group B": ["gene1"]}}

        categories.add_cats(net, ROW_AXIS, cat_data)

        net.export_df.assert_called_once()
        net.load_df.assert_called_once()


# =============================================================================
# TEST CLASSES - EDGE CASES AND ERROR CONDITIONS
# =============================================================================


class TestEdgeCasesAndErrorConditions:
    """Test suite for edge cases and error conditions."""

    def test_color_assignment_consistency(self) -> None:
        """Test that color assignment is consistent across multiple calls."""
        color1_first = categories.get_cat_color(5)
        color1_second = categories.get_cat_color(5)
        assert color1_first == color1_second

    @pytest.mark.parametrize(
        "large_num,expected_wrapped", [(10000, 10000 % 35), (100000, 100000 % 35)]
    )
    def test_large_category_numbers(self, large_num: int, expected_wrapped: int) -> None:
        """Test behavior with very large category numbers."""
        color_large = categories.get_cat_color(large_num)
        color_wrapped = categories.get_cat_color(expected_wrapped)
        assert color_large == color_wrapped

    @pytest.mark.parametrize(
        "special_cats",
        [
            ["测试", "🧬", "café"],  # Unicode
            ["cat:with:colons", "cat with spaces", "cat\twith\ttabs"],  # Special chars
            ["a" * 1000, "short"],  # Very long names
        ],
    )
    def test_special_character_handling(self, special_cats: list[str]) -> None:
        """Test handling of special characters and unicode in category names."""
        result = categories.order_categories(special_cats)
        assert len(result) == len(special_cats)
        assert set(result) == set(special_cats)

    def test_none_value_handling(self) -> None:
        """Test handling of None values in various functions."""
        # Test is_number with None
        assert categories.is_number(None) is False

        # Test order_categories with None values (should be filtered out)
        with_none = ["A", None, "B"]
        # The function should handle this gracefully
        try:
            result = categories.order_categories(with_none)
            # If it succeeds, ensure None is handled appropriately
            assert None not in result or result == with_none
        except (TypeError, AttributeError):
            # This is acceptable behavior for None values
            pass

    def test_extremely_long_category_names(self) -> None:
        """Test handling of extremely long category names."""
        long_name = "category_" + "x" * 10000
        result = categories.order_categories([long_name, "short"])
        assert len(result) == 2
        assert long_name in result
        assert "short" in result


# =============================================================================
# TEST CLASSES - PERFORMANCE AND INTEGRATION TESTS
# =============================================================================


class TestPerformanceAndIntegration:
    """Performance-related and integration tests."""

    def test_large_dataset_performance(self) -> None:
        """Test performance with large datasets."""
        import time

        large_cats = [f"cat_{i}" for i in range(LARGE_DATASET_SIZE)]

        start_time = time.time()
        result = categories.order_categories(large_cats)
        end_time = time.time()

        # Should complete in reasonable time
        assert (end_time - start_time) < PERFORMANCE_TIMEOUT_SECONDS
        assert len(result) == LARGE_DATASET_SIZE

    def test_deep_nesting_categories(self) -> None:
        """Test with deeply nested category structures."""
        net = TestCategoriesHelpers.create_mock_network(include_viz=False)
        large_list = [f"gene_{i}" for i in range(1000)]

        net.dat["node_info"][ROW_AXIS] = {
            "cat-0": ["A"] * 500 + ["B"] * 500,
            "dict_cat_0": {"A": large_list[:500], "B": large_list[500:]},
        }
        net.dat["nodes"][ROW_AXIS] = large_list

        # Should complete without timeout
        categories.calc_cat_clust_order(net, ROW_AXIS)
        assert "cat_0_index" in net.dat["node_info"][ROW_AXIS]

    def test_integration_multiple_functions(self) -> None:
        """Test integration of multiple functions working together."""
        net = TestCategoriesHelpers.create_extended_category_network(num_categories=3)

        # Test dictionary creation
        categories.dict_cat(net, define_cat_colors=True)

        # Verify all dictionaries were created
        for axis in VALID_AXES:
            node_info = net.dat["node_info"][axis]
            for i in range(3):
                assert f"dict_cat_{i}" in node_info

        # Test cluster ordering for both axes
        for axis in VALID_AXES:
            categories.calc_cat_clust_order(net, axis)
            node_info = net.dat["node_info"][axis]
            for i in range(3):
                assert f"cat_{i}_index" in node_info

    def test_memory_efficiency_large_categories(self) -> None:
        """Test memory efficiency with large category lists."""
        # Create a network with many categories
        large_categories = {}
        for i in range(100):
            cat_key = f"cat-{i}"
            large_categories[cat_key] = [f"Category_{i}_{j}" for j in range(100)]

        net = TestCategoriesHelpers.create_mock_network(
            row_categories=large_categories,
            row_nodes=[f"gene_{i}" for i in range(100)],
            include_viz=False,
        )

        # Should handle large category structures without issues
        categories.dict_cat(net)

        # Verify some dictionaries were created (spot check)
        node_info = net.dat["node_info"][ROW_AXIS]
        assert "dict_cat_0" in node_info
        assert "dict_cat_99" in node_info


# =============================================================================
# MAIN EXECUTION
# =============================================================================

if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])
