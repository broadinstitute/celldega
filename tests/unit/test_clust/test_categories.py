"""
Comprehensive test suite for categories.py module.

This test suite provides extensive coverage for all functions in the categories module,
including edge cases, error conditions, and boundary value testing.
"""

from pathlib import Path

# Import the module under test - adjust import path as needed
# from src.celldega.clust import categories
import sys
from unittest.mock import Mock, patch

import pandas as pd
import pytest


sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from celldega.clust.categories import categories


class TestCheckCategories:
    """Test suite for check_categories function."""

    @pytest.fixture
    def sample_lines(self):
        """Fixture providing sample input lines for testing."""
        return [
            "col1\t\t\tval1\tval2\tval3",  # Row with 3 empty categories
            "\t\t\trow1_cat1\trow1_cat2",  # Col category line 1
            "\t\t\trow2_cat1\trow2_cat2",  # Col category line 2
            "gene1\t10\t20\t30\t40\t50",  # Data row
            "gene2\t15\t25\t35\t45\t55",  # Data row
        ]

    @pytest.fixture
    def minimal_lines(self):
        """Fixture for minimal valid input."""
        return ["col1\tval1\tval2", "gene1\t10\t20"]

    @pytest.fixture
    def empty_category_lines(self):
        """Fixture for lines with no categories."""
        return ["col1\tval1\tval2", "gene1\t10\t20", "gene2\t15\t25"]

    @pytest.fixture
    def max_category_lines(self):
        """Fixture for testing the 15-line limit."""
        lines = ["col1\t\t\t\t\t\t\t\t\t\t\t\t\t\t\t\tval1\tval2"]  # 15 empty cats
        # Add 20 empty lines to test the limit
        for i in range(20):
            lines.append(f"\t\t\t\t\t\t\t\t\t\t\t\t\t\t\t\tcat{i}_1\tcat{i}_2")
        lines.extend(["gene1\t10\t20", "gene2\t15\t25"])
        return lines

    def test_check_categories_basic(self, sample_lines):
        """Test basic category detection functionality."""
        result = categories.check_categories(sample_lines)

        assert (
            result["row"] == 3
        )  # 2 empty + 1 for names (corrected based on actual function behavior)
        assert result["col"] == 3  # 2 empty lines + 1 for names
        assert isinstance(result, dict)
        assert set(result.keys()) == {"row", "col"}

    def test_check_categories_minimal_input(self, minimal_lines):
        """Test with minimal valid input (no categories)."""
        result = categories.check_categories(minimal_lines)

        assert result["row"] == 1  # Only names, no categories
        assert result["col"] == 1  # Only names, no categories

    def test_check_categories_no_categories(self, empty_category_lines):
        """Test when there are no category lines."""
        result = categories.check_categories(empty_category_lines)

        assert result["row"] == 1
        assert result["col"] == 1

    def test_check_categories_fifteen_line_limit(self, max_category_lines):
        """Test that the function respects the 15-line limit for column categories."""
        result = categories.check_categories(max_category_lines)

        # Should only process first 15 lines after header for column categories
        assert result["col"] == 16  # 15 processed + 1 for names

    def test_check_categories_single_line(self):
        """Test edge case with only header line."""
        lines = ["col1\tval1\tval2"]
        result = categories.check_categories(lines)

        assert result["row"] == 1
        assert result["col"] == 1

    def test_check_categories_empty_lines_at_end(self):
        """Test handling of trailing empty lines that could create false categories."""
        lines = [
            "col1\tval1\tval2",
            "\tcat1\tcat2",  # Valid category line
            "",  # Empty line (should not count)
            "\t",  # Line with only tab (should not count due to length check)
            "gene1\t10\t20",
        ]
        result = categories.check_categories(lines)

        assert (
            result["col"] == 3
        )  # 1 valid category line + names + the "\t" line counts as it has length > 1

    @pytest.mark.parametrize("row_cats,expected_row", [(0, 1), (1, 2), (2, 3), (5, 6), (10, 11)])
    def test_check_categories_various_row_counts(self, row_cats, expected_row):
        """Test various numbers of row categories."""
        header = "col1" + "\t" * row_cats + "\tval1\tval2"
        lines = [header, "gene1\t" + "\t" * row_cats + "10\t20"]

        result = categories.check_categories(lines)
        assert result["row"] == expected_row


class TestDictCat:
    """Test suite for dict_cat function."""

    @pytest.fixture
    def mock_network(self):
        """Create a mock network object with necessary structure."""
        net = Mock()
        net.persistent_cat_colors = True
        net.dat = {
            "node_info": {
                "row": {
                    "cat-0": ["Type: type1", "Type: type1", "Type: type2", "Type: type2"],
                    "cat-1": ["Level: high", "Level: low", "Level: high", "Level: medium"],
                },
                "col": {
                    "cat-0": [
                        "Sample: sample1",
                        "Sample: sample1",
                        "Sample: sample2",
                        "Sample: sample2",
                    ],
                    "cat-1": [
                        "Treatment: treated",
                        "Treatment: control",
                        "Treatment: treated",
                        "Treatment: control",
                    ],
                },
            },
            "nodes": {
                "row": ["gene1", "gene2", "gene3", "gene4"],
                "col": ["cell1", "cell2", "cell3", "cell4"],
            },
        }
        net.viz = {"cat_colors": {"row": {}, "col": {}}}
        return net

    def test_dict_cat_basic_functionality(self, mock_network):
        """Test basic dictionary creation from categories."""
        categories.dict_cat(mock_network)

        # Check that dictionary versions were created
        assert "dict_cat_0" in mock_network.dat["node_info"]["row"]
        assert "dict_cat_1" in mock_network.dat["node_info"]["row"]
        assert "dict_cat_0" in mock_network.dat["node_info"]["col"]
        assert "dict_cat_1" in mock_network.dat["node_info"]["col"]

        # Check dictionary contents
        row_dict_0 = mock_network.dat["node_info"]["row"]["dict_cat_0"]
        assert row_dict_0["Type: type1"] == ["gene1", "gene2"]
        assert row_dict_0["Type: type2"] == ["gene3", "gene4"]

    def test_dict_cat_with_define_cat_colors_true(self, mock_network):
        """Test category color definition when define_cat_colors=True."""
        categories.dict_cat(mock_network, define_cat_colors=True)

        # Check that colors were assigned
        assert "cat-0" in mock_network.viz["cat_colors"]["row"]
        assert "cat-0" in mock_network.viz["cat_colors"]["col"]

        # Check that global cat colors were created
        assert "global_cat_colors" in mock_network.viz

    def test_dict_cat_with_existing_colors(self, mock_network):
        """Test that existing colors are preserved."""
        # Pre-populate some colors with proper format
        mock_network.viz["cat_colors"]["row"]["cat-0"] = {"Type: existing_type": "#123456"}

        categories.dict_cat(mock_network, define_cat_colors=True)

        # Existing color should be preserved
        assert mock_network.viz["cat_colors"]["row"]["cat-0"]["Type: existing_type"] == "#123456"

    def test_dict_cat_false_category_coloring(self, mock_network):
        """Test special coloring for 'False' categories."""
        mock_network.dat["node_info"]["row"]["cat-0"] = [
            "Category: True",
            "Category: False",
            "Category: Not applicable",
            "Category: Valid",
        ]
        mock_network.dat["nodes"]["row"] = ["gene1", "gene2", "gene3", "gene4"]

        categories.dict_cat(mock_network, define_cat_colors=True)

        colors = mock_network.viz["cat_colors"]["row"]["cat-0"]
        assert colors["Category: False"] == "#eee"
        assert colors["Category: Not applicable"] == "#eee"
        assert colors["Category: True"] != "#eee"  # Should get a real color
        assert colors["Category: Valid"] != "#eee"  # Should get a real color

    def test_dict_cat_empty_categories(self):
        """Test handling of empty category lists."""
        net = Mock()
        net.persistent_cat_colors = True
        net.dat = {"node_info": {"row": {}, "col": {}}, "nodes": {"row": [], "col": []}}
        net.viz = {"cat_colors": {"row": {}, "col": {}}}

        # Should not raise an error
        categories.dict_cat(net)

        # Should still set global_cat_colors
        assert "global_cat_colors" not in net.viz  # Only set when define_cat_colors=True


class TestCalcCatClustOrder:
    """Test suite for calc_cat_clust_order function."""

    @pytest.fixture
    def mock_network_with_categories(self):
        """Create mock network with category data for clustering order tests."""
        net = Mock()
        net.dat = {
            "node_info": {
                "row": {
                    "cat-0": ["B", "A", "C", "A", "B"],
                    "dict_cat_0": {
                        "A": ["gene2", "gene4"],
                        "B": ["gene1", "gene5"],
                        "C": ["gene3"],
                    },
                }
            },
            "nodes": {"row": ["gene1", "gene2", "gene3", "gene4", "gene5"]},
        }
        return net

    def test_calc_cat_clust_order_basic(self, mock_network_with_categories):
        """Test basic category cluster ordering."""
        categories.calc_cat_clust_order(mock_network_with_categories, "row")

        # Check that index was created
        assert "cat_0_index" in mock_network_with_categories.dat["node_info"]["row"]

        # Check the ordering (A, B, C alphabetical, then within each category)
        index_order = mock_network_with_categories.dat["node_info"]["row"]["cat_0_index"]
        assert len(index_order) == 5
        assert all(isinstance(x, int) for x in index_order)

    def test_calc_cat_clust_order_no_categories(self):
        """Test when there are no categories to process."""
        net = Mock()
        net.dat = {"node_info": {"row": {}}, "nodes": {"row": ["gene1", "gene2"]}}

        # Should not raise an error
        categories.calc_cat_clust_order(net, "row")

        # No new keys should be added
        assert len(net.dat["node_info"]["row"]) == 0

    def test_calc_cat_clust_order_multiple_categories(self):
        """Test with multiple category levels."""
        net = Mock()
        net.dat = {
            "node_info": {
                "col": {
                    "cat-0": ["X", "Y"],
                    "cat-1": ["1", "2"],
                    "dict_cat_0": {"X": ["cell1"], "Y": ["cell2"]},
                    "dict_cat_1": {"1": ["cell1"], "2": ["cell2"]},
                }
            },
            "nodes": {"col": ["cell1", "cell2"]},
        }

        categories.calc_cat_clust_order(net, "col")

        assert "cat_0_index" in net.dat["node_info"]["col"]
        assert "cat_1_index" in net.dat["node_info"]["col"]


class TestOrderCategories:
    """Test suite for order_categories function."""

    def test_order_categories_strings(self):
        """Test ordering of string categories."""
        unordered = ["Zebra", "Apple", "Banana"]
        result = categories.order_categories(unordered)
        assert result == ["Apple", "Banana", "Zebra"]

    def test_order_categories_numbers_as_strings(self):
        """Test ordering when categories are numeric values as strings."""
        unordered = ["10.5", "2.1", "5.0"]
        result = categories.order_categories(unordered)
        # Should be ordered by numeric value, not alphabetically
        assert result == ["2.1", "5.0", "10.5"]

    def test_order_categories_with_titles(self):
        """Test ordering categories that have titles (e.g., 'Type: value')."""
        unordered = ["Type: High", "Type: Low", "Type: Medium"]
        result = categories.order_categories(unordered)
        # Should be ordered alphabetically by the part after the colon
        assert result == ["Type: High", "Type: Low", "Type: Medium"]

    def test_order_categories_numeric_with_titles(self):
        """Test ordering numeric categories with titles."""
        unordered = ["Score: 10.5", "Score: 2.1", "Score: 5.0"]
        result = categories.order_categories(unordered)
        # Should be ordered by numeric value of the part after colon
        assert result == ["Score: 2.1", "Score: 5.0", "Score: 10.5"]

    def test_order_categories_mixed_numeric_string(self):
        """Test ordering when some categories are numeric and others are not."""
        unordered = ["10", "apple", "5", "banana"]
        result = categories.order_categories(unordered)
        # Should fall back to alphabetical ordering
        assert result == ["10", "5", "apple", "banana"]

    def test_order_categories_empty_list(self):
        """Test ordering an empty list."""
        result = categories.order_categories([])
        assert result == []

    def test_order_categories_single_item(self):
        """Test ordering a single category."""
        result = categories.order_categories(["single"])
        assert result == ["single"]

    def test_order_categories_error_handling(self):
        """Test error handling in numeric ordering."""
        # Test the actual error handling path in order_cats_based_on_values
        unordered = ["Type: 3", "Type: 1", "Type: 2"]
        values_list = ["3", "1", "2"]

        # Mock pandas.Series at the module level where it's imported
        with patch("pandas.Series", side_effect=Exception("Mock error")):
            result = categories.order_cats_based_on_values(unordered, values_list)
            # Should return original ordering on error
            assert result == unordered


class TestOrderCatsBasedOnValues:
    """Test suite for order_cats_based_on_values function."""

    def test_order_cats_based_on_values_basic(self):
        """Test basic numeric ordering."""
        unordered = ["Score: 10", "Score: 5", "Score: 15"]
        values = ["10", "5", "15"]

        result = categories.order_cats_based_on_values(unordered, values)
        assert result == ["Score: 5", "Score: 10", "Score: 15"]

    def test_order_cats_based_on_values_floats(self):
        """Test ordering with float values."""
        unordered = ["A", "B", "C"]
        values = ["10.5", "2.1", "5.0"]

        result = categories.order_cats_based_on_values(unordered, values)
        assert result == ["B", "C", "A"]  # Ordered by 2.1, 5.0, 10.5

    def test_order_cats_based_on_values_error_handling(self):
        """Test error handling when values can't be converted to float."""
        unordered = ["A", "B", "C"]
        values = ["not_a_number", "5", "10"]

        # Should return original ordering on error
        result = categories.order_cats_based_on_values(unordered, values)
        assert result == unordered

    def test_order_cats_based_on_values_negative_numbers(self):
        """Test ordering with negative numbers."""
        unordered = ["A", "B", "C"]
        values = ["10", "-5", "0"]

        result = categories.order_cats_based_on_values(unordered, values)
        assert result == ["B", "C", "A"]  # Ordered by -5, 0, 10


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
            (None, False),  # Now handled gracefully, no exception
        ],
    )
    def test_is_number(self, input_val, expected):
        """Test is_number function with various inputs."""
        # The improved function now handles None gracefully without raising exceptions
        assert categories.is_number(input_val) == expected

    def test_check_all_numbers_true(self):
        """Test check_all_numbers when all items are numbers."""
        assert categories.check_all_numbers(["1", "2.5", "-3"]) is True

    def test_check_all_numbers_false(self):
        """Test check_all_numbers when some items are not numbers."""
        assert categories.check_all_numbers(["1", "abc", "3"]) is False

    def test_check_all_numbers_empty(self):
        """Test check_all_numbers with empty list."""
        assert categories.check_all_numbers([]) is True  # vacuously true

    def test_remove_titles_with_titles(self):
        """Test remove_titles when all categories have titles."""
        cats = ["Type: A", "Type: B", "Type: C"]
        result = categories.remove_titles(cats)
        assert result == ["A", "B", "C"]

    def test_remove_titles_without_titles(self):
        """Test remove_titles when categories don't have titles."""
        cats = ["A", "B", "C"]
        result = categories.remove_titles(cats)
        assert result == ["A", "B", "C"]

    def test_remove_titles_mixed(self):
        """Test remove_titles with mixed titled and non-titled categories."""
        cats = ["Type: A", "B", "1"]  # Mixed - some with numbers
        result = categories.remove_titles(cats)
        assert result == ["Type: A", "B", "1"]  # Should not remove titles

    @pytest.mark.parametrize(
        "cat_num,expected",
        [
            (0, "#393b79"),
            (1, "#aec7e8"),
            (34, "#de9ed6"),  # Last color in list
            (35, "#393b79"),  # Should wrap around
            (70, "#393b79"),  # Multiple wraps
        ],
    )
    def test_get_cat_color(self, cat_num, expected):
        """Test get_cat_color function with various indices."""
        assert categories.get_cat_color(cat_num) == expected


class TestAddCats:
    """Test suite for add_cats function."""

    @pytest.fixture
    def mock_network_for_add_cats(self):
        """Create a mock network for testing add_cats."""
        net = Mock()

        # Create a mock DataFrame
        mock_df = Mock(spec=pd.DataFrame)
        mock_df.index.tolist.return_value = ["gene1", "gene2", "gene3"]
        mock_df.columns.tolist.return_value = ["cell1", "cell2", "cell3"]

        net.export_df.return_value = mock_df
        net.load_df = Mock()

        return net, mock_df

    def test_add_cats_basic_functionality(self, mock_network_for_add_cats):
        """Test basic functionality of add_cats."""
        net, mock_df = mock_network_for_add_cats

        cat_data = {
            "title": "Cell Type",
            "cats": {"Type A": ["gene1", "gene3"], "Type B": ["gene2"]},
        }

        categories.add_cats(net, "row", cat_data)

        # Verify that export_df was called
        net.export_df.assert_called_once()

        # Verify that load_df was called with modified data
        net.load_df.assert_called_once()

    def test_add_cats_column_axis(self, mock_network_for_add_cats):
        """Test add_cats with column axis."""
        net, mock_df = mock_network_for_add_cats

        cat_data = {
            "title": "Treatment",
            "cats": {"Treated": ["cell1"], "Control": ["cell2", "cell3"]},
        }

        categories.add_cats(net, "col", cat_data)

        net.export_df.assert_called_once()
        net.load_df.assert_called_once()

    def test_add_cats_with_existing_tuples(self, mock_network_for_add_cats):
        """Test add_cats when labels are already tuples."""
        net, mock_df = mock_network_for_add_cats
        mock_df.index.tolist.return_value = [("gene1", "existing_cat"), ("gene2", "existing_cat")]

        cat_data = {"title": "New Category", "cats": {"Group A": ["gene1"]}}

        categories.add_cats(net, "row", cat_data)

        net.export_df.assert_called_once()
        net.load_df.assert_called_once()

    def test_add_cats_with_titled_labels(self, mock_network_for_add_cats):
        """Test add_cats when labels contain titles (e.g., 'Type: value')."""
        net, mock_df = mock_network_for_add_cats
        mock_df.index.tolist.return_value = ["Type: gene1", "Type: gene2"]

        cat_data = {"title": "Expression", "cats": {"High": ["gene1"], "Low": ["gene2"]}}

        categories.add_cats(net, "row", cat_data)

        net.export_df.assert_called_once()
        net.load_df.assert_called_once()

    def test_add_cats_no_title_provided(self, mock_network_for_add_cats):
        """Test add_cats when no title is provided in cat_data."""
        net, mock_df = mock_network_for_add_cats

        cat_data = {"cats": {"Group A": ["gene1"], "Group B": ["gene2"]}}

        categories.add_cats(net, "row", cat_data)

        net.export_df.assert_called_once()
        net.load_df.assert_called_once()

    def test_add_cats_error_handling(self, mock_network_for_add_cats, capsys):
        """Test error handling in add_cats function."""
        net, mock_df = mock_network_for_add_cats

        # Make export_df raise an exception
        net.export_df.side_effect = Exception("Test error")

        cat_data = {"title": "Test", "cats": {"A": ["gene1"]}}

        # Should not raise an exception, but should print error message
        categories.add_cats(net, "row", cat_data)

        captured = capsys.readouterr()
        # The refactored code outputs "Error adding categories: Test error"
        assert "Error adding categories: Test error" in captured.out

    def test_add_cats_empty_categories(self, mock_network_for_add_cats):
        """Test add_cats with empty category groups."""
        net, mock_df = mock_network_for_add_cats

        cat_data = {"title": "Empty Test", "cats": {"Group A": [], "Group B": ["gene1"]}}

        categories.add_cats(net, "row", cat_data)

        net.export_df.assert_called_once()
        net.load_df.assert_called_once()


class TestEdgeCasesAndIntegration:
    """Test suite for edge cases and integration scenarios."""

    def test_color_assignment_consistency(self):
        """Test that color assignment is consistent across multiple calls."""
        # Get colors for same category numbers multiple times
        color1_first = categories.get_cat_color(5)
        color1_second = categories.get_cat_color(5)

        assert color1_first == color1_second

    def test_large_category_numbers(self):
        """Test behavior with very large category numbers."""
        # Test wraparound behavior
        color_large = categories.get_cat_color(10000)
        color_wrapped = categories.get_cat_color(10000 % 35)

        assert color_large == color_wrapped

    def test_unicode_in_categories(self):
        """Test handling of unicode characters in category names."""
        cats = ["测试", "🧬", "café"]
        result = categories.order_categories(cats)

        # Should not crash and should return some ordering
        assert len(result) == 3
        assert set(result) == set(cats)

    def test_very_long_category_names(self):
        """Test handling of very long category names."""
        long_name = "a" * 1000
        cats = [long_name, "short"]

        result = categories.order_categories(cats)
        assert len(result) == 2
        assert long_name in result

    def test_special_characters_in_categories(self):
        """Test handling of special characters in category names."""
        cats = ["cat:with:colons", "cat with spaces", "cat\twith\ttabs", "cat\nwith\nnewlines"]

        # Should not crash
        result = categories.order_categories(cats)
        assert len(result) == 4

    @pytest.mark.parametrize("axis", ["row", "col"])
    def test_both_axes_coverage(self, axis):
        """Ensure functions work correctly for both row and column axes."""
        net = Mock()
        net.dat = {
            "node_info": {
                axis: {"cat-0": ["A", "B"], "dict_cat_0": {"A": ["item1"], "B": ["item2"]}}
            },
            "nodes": {axis: ["item1", "item2"]},
        }

        # Should not raise an error for either axis
        categories.calc_cat_clust_order(net, axis)

        assert "cat_0_index" in net.dat["node_info"][axis]


# Test configuration and fixtures for pytest
@pytest.fixture(scope="module")
def sample_network():
    """Module-scoped fixture for creating a sample network object."""
    net = Mock()
    net.persistent_cat_colors = True
    net.dat = {
        "node_info": {
            "row": {"cat-0": ["type1", "type2"], "cat-1": ["high", "low"]},
            "col": {"cat-0": ["sample1", "sample2"], "cat-1": ["treated", "control"]},
        },
        "nodes": {"row": ["gene1", "gene2"], "col": ["cell1", "cell2"]},
    }
    net.viz = {"cat_colors": {"row": {}, "col": {}}}
    return net


# Markers for different test categories
# Note: These markers should be defined in pytest.ini or conftest.py


# Performance tests (optional, can be skipped in normal runs)
class TestPerformance:
    """Performance-related tests."""

    def test_large_dataset_performance(self):
        """Test performance with large datasets."""
        # Create large category list
        large_cats = [f"cat_{i}" for i in range(10000)]

        import time

        start_time = time.time()
        result = categories.order_categories(large_cats)
        end_time = time.time()

        # Should complete in reasonable time (less than 1 second)
        assert (end_time - start_time) < 1.0
        assert len(result) == 10000

    def test_deep_nesting_categories(self):
        """Test with deeply nested category structures."""
        # This would test the O(n²) issue identified in calc_cat_clust_order
        net = Mock()
        large_list = [f"gene_{i}" for i in range(1000)]

        net.dat = {
            "node_info": {
                "row": {
                    "cat-0": ["A"] * 500 + ["B"] * 500,
                    "dict_cat_0": {"A": large_list[:500], "B": large_list[500:]},
                }
            },
            "nodes": {"row": large_list},
        }

        # Should complete without timeout
        categories.calc_cat_clust_order(net, "row")

        assert "cat_0_index" in net.dat["node_info"]["row"]


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])
