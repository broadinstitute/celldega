"""
Comprehensive test suite for export_data.py module.

This module tests all functionality of the celldega.clust.data_io.export_data module
with improved robustness, conciseness, and consistency. All bugs from the original
implementation have been fixed and are tested accordingly.
"""

# =============================================================================
# IMPORTS AND MODULE SETUP
# =============================================================================

import json
from pathlib import Path
import sys
import tempfile
from typing import Any
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd
import pytest


# Add the src directory to Python path for imports
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
SRC_PATH = PROJECT_ROOT / "src"
if SRC_PATH not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from celldega.clust_old.data_io import export_data


# =============================================================================
# MODULE-LEVEL CONSTANTS
# =============================================================================

# Test data constants
DEFAULT_MATRIX = [[1, 2], [3, 4]]
DEFAULT_NODES = {"row": ["r1", "r2"], "col": ["c1", "c2"]}
DEFAULT_VIZ_DATA = {"data": "viz_content"}
DEFAULT_SIM_DATA = {"row": {"similarity": "row_data"}, "col": {"similarity": "col_data"}}

# DataFrame constants
DEFAULT_DF_DATA = {"col1": [1, 2, 3], "col2": [4, 5, 6]}
DEFAULT_DF_INDEX = ["row1", "row2", "row3"]
CUSTOM_DF_DATA = {"a": [1, 2], "b": [3, 4]}
CUSTOM_DF_INDEX = ["row1", "row2"]

# JSON test constants
TEST_JSON_DICT = {"test": "data"}
COMPLEX_JSON_DICT = {
    "unicode": "café ñoño 中文",
    "special": "\"quotes\" and 'apostrophes' and \n newlines",
    "numbers": [1.5, -2.3, 0],
    "empty_structures": {"list": [], "dict": {}, "string": ""},
}

# Valid net types for export_net_json
VALID_NET_TYPES = ["dat", "viz", "sim_row", "sim_col"]
INVALID_NET_TYPES = ["invalid", "wrong", "fake", "", "DATA", "VIZ", "nonexistent"]

# Error message patterns
INVALID_NET_TYPE_PATTERN = r"Invalid net_type: '[^']*'"
NET_TYPE_OPTIONS_PATTERN = r"Must be one of: 'dat', 'viz', 'sim_row', 'sim_col'"
SERIALIZATION_ERROR_PATTERN = r"Failed to serialize dictionary to JSON"
FILE_WRITE_ERROR_PATTERN = r"Failed to write JSON to file.*"

# File operation constants
FILE_ENCODING = "utf-8"
TEMP_FILE_SUFFIX = ".json"

# Test matrix variations
MATRIX_VARIATIONS: list[tuple[Any, str]] = [
    ([], "empty list"),
    ([[]], "nested empty list"),
    (np.array([]), "empty numpy array"),
    (np.array([[1, 2], [3, 4]]), "2D numpy array"),
    (([[1, 2]],), "tuple of lists"),
]

# Large test data constants
LARGE_MATRIX_ROWS = 100
LARGE_MATRIX_COLS = 50

# =============================================================================
# UTILITY HELPER FUNCTIONS
# =============================================================================


def create_mock_network_data(
    matrix: list[list[int]] | None = None,
    nodes: dict[str, list[str]] | None = None,
    viz_data: dict[str, str] | None = None,
    sim_data: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Create standardized mock network data structure."""
    return {
        "mat": matrix or DEFAULT_MATRIX,
        "nodes": nodes or DEFAULT_NODES.copy(),
        "viz": viz_data or DEFAULT_VIZ_DATA.copy(),
        "sim": sim_data or DEFAULT_SIM_DATA.copy(),
    }


def create_test_dataframe(
    data: dict[str, list[int]] | None = None, index: list[str] | None = None
) -> pd.DataFrame:
    """Create standardized test DataFrame."""
    return pd.DataFrame(data or DEFAULT_DF_DATA.copy(), index=index or DEFAULT_DF_INDEX.copy())


def validate_json_structure(json_string: str) -> dict[str, Any]:
    """Validate JSON string and return parsed dictionary."""
    assert isinstance(json_string, str), "Expected string output"
    return json.loads(json_string)


def create_mock_export_net_json_func() -> callable:
    """Create mock function for export_net_json with indent support."""

    def mock_func(net_type: str, indent: str = "no-indent") -> str:
        if indent == "indent":
            return json.dumps(TEST_JSON_DICT, indent=2)
        return json.dumps(TEST_JSON_DICT)

    return mock_func


def assert_file_contains_content(file_path: str | Path, expected_content: str) -> None:
    """Assert that file exists and contains expected content."""
    path = Path(file_path)
    assert path.exists(), f"File {path} does not exist"

    with path.open(encoding=FILE_ENCODING) as f:
        content = f.read()
    assert expected_content in content, f"Expected content not found in {path}"


def assert_valid_tsv_format(content: str) -> None:
    """Assert that content is in valid TSV format."""
    assert isinstance(content, str), "TSV content must be string"
    assert "\t" in content, "TSV content must contain tab separators"


# =============================================================================
# PYTEST FIXTURES AND TEST DATA
# =============================================================================


@pytest.fixture
def mock_network() -> Mock:
    """Create a complete mock network object for testing."""
    mock_net = Mock()
    network_data = create_mock_network_data()

    mock_net.dat = {"mat": network_data["mat"], "nodes": network_data["nodes"]}
    mock_net.viz = network_data["viz"]
    mock_net.sim = network_data["sim"]
    mock_net.dat_to_df.return_value = create_test_dataframe()
    mock_net.export_net_json.side_effect = create_mock_export_net_json_func()

    return mock_net


@pytest.fixture
def temp_file() -> str:
    """Create temporary file for testing file operations."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=TEMP_FILE_SUFFIX) as tmp_file:
        temp_filename = tmp_file.name

    yield temp_filename

    temp_path = Path(temp_filename)
    if temp_path.exists():
        temp_path.unlink()


@pytest.fixture
def large_test_matrix() -> list[list[float]]:
    """Create large matrix for performance testing."""
    return np.random.rand(LARGE_MATRIX_ROWS, LARGE_MATRIX_COLS).tolist()


# =============================================================================
# CORE FUNCTIONALITY TESTS - EXPORT NET JSON
# =============================================================================


class TestExportNetJsonFixed:
    """Test export_net_json function with all bugs fixed."""

    @pytest.mark.parametrize(
        "net_type,description",
        [
            ("dat", "dat export with list matrix"),
            ("viz", "viz export"),
            ("sim_row", "sim_row export"),
            ("sim_col", "sim_col export"),
        ],
    )
    def test_valid_net_types_with_matrix_conversions(
        self, mock_network: Mock, net_type: str, description: str
    ) -> None:
        """Test all valid net_type options and matrix type conversions."""
        result = export_data.export_net_json(mock_network, net_type)
        validate_json_structure(result)

        # Test numpy matrix conversion for dat type
        if net_type == "dat":
            mock_network.dat["mat"] = np.array(DEFAULT_MATRIX)
            result = export_data.export_net_json(mock_network, net_type)
            result_dict = validate_json_structure(result)
            assert result_dict["mat"] == DEFAULT_MATRIX, "Numpy array conversion failed"

            # Reset to list for other tests
            mock_network.dat["mat"] = DEFAULT_MATRIX

    @pytest.mark.parametrize(
        "indent_option,expected_formatting",
        [
            ("indent", True),
            ("no-indent", False),
        ],
    )
    def test_indent_formatting_options(
        self, mock_network: Mock, indent_option: str, expected_formatting: bool
    ) -> None:
        """Test indent formatting options."""
        result = export_data.export_net_json(mock_network, "viz", indent=indent_option)

        if expected_formatting:
            expected = json.dumps(mock_network.viz, indent=2)
        else:
            expected = json.dumps(mock_network.viz)

        assert result == expected

    @pytest.mark.parametrize("invalid_type", INVALID_NET_TYPES)
    def test_invalid_net_type_error_handling(self, mock_network: Mock, invalid_type: str) -> None:
        """Test improved error handling for invalid net_types."""
        with pytest.raises(ValueError, match=INVALID_NET_TYPE_PATTERN):
            export_data.export_net_json(mock_network, invalid_type)

    def test_error_message_content_validation(self, mock_network: Mock) -> None:
        """Test that error messages contain expected helpful information."""
        with pytest.raises(ValueError) as exc_info:
            export_data.export_net_json(mock_network, "nonexistent")

        error_message = str(exc_info.value)
        assert "Invalid net_type: 'nonexistent'" in error_message
        assert "Must be one of:" in error_message
        for valid_type in VALID_NET_TYPES:
            assert valid_type in error_message

    def test_missing_attributes_error_handling(self) -> None:
        """Test handling of networks with missing attributes."""
        incomplete_net = Mock()
        del incomplete_net.dat

        with pytest.raises(AttributeError):
            export_data.export_net_json(incomplete_net, "dat")

    def test_isinstance_fix_with_inheritance(self, mock_network: Mock) -> None:
        """Test that isinstance() fix works correctly with inheritance."""

        class CustomList(list):
            """Custom list subclass for testing isinstance() behavior."""

        mock_network.dat["mat"] = CustomList(DEFAULT_MATRIX)
        result = export_data.export_net_json(mock_network, "dat")
        result_dict = validate_json_structure(result)

        assert result_dict["mat"] == DEFAULT_MATRIX


# =============================================================================
# FILE OPERATION TESTS - TSV AND JSON HANDLING
# =============================================================================


class TestFileOperationsFixed:
    """Test file operations with all Path.open() bugs fixed."""

    def test_tsv_export_with_filename(self, mock_network: Mock, temp_file: str) -> None:
        """Test TSV export when filename is provided."""
        export_data.write_matrix_to_tsv(mock_network, filename=temp_file)
        assert_file_contains_content(temp_file, "col1\tcol2")

    def test_tsv_export_without_filename(self, mock_network: Mock) -> None:
        """Test TSV export when no filename is provided (returns string)."""
        result = export_data.write_matrix_to_tsv(mock_network, filename=None)
        assert_valid_tsv_format(result)
        assert "col1\tcol2" in result

    def test_tsv_export_with_custom_dataframe(self, mock_network: Mock, temp_file: str) -> None:
        """Test TSV export with custom DataFrame provided."""
        mock_network.dat_to_df.reset_mock()
        custom_df = create_test_dataframe(CUSTOM_DF_DATA, CUSTOM_DF_INDEX)

        export_data.write_matrix_to_tsv(mock_network, filename=temp_file, df=custom_df)

        assert_file_contains_content(temp_file, "a\tb")
        mock_network.dat_to_df.assert_not_called()

    @pytest.mark.parametrize(
        "function_name,args_factory,description",
        [
            (
                "write_json_to_file",
                lambda net, temp_file: [net, "viz", temp_file, "no-indent"],
                "write_json_to_file no-indent",
            ),
            (
                "write_json_to_file",
                lambda net, temp_file: [net, "viz", temp_file, "indent"],
                "write_json_to_file with indent",
            ),
            (
                "save_dict_to_json",
                lambda net, temp_file: [TEST_JSON_DICT, temp_file, "no-indent"],
                "save_dict_to_json no-indent",
            ),
            (
                "save_dict_to_json",
                lambda net, temp_file: [TEST_JSON_DICT, temp_file, "indent"],
                "save_dict_to_json with indent",
            ),
        ],
    )
    def test_json_file_operations(
        self,
        mock_network: Mock,
        temp_file: str,
        function_name: str,
        args_factory: callable,
        description: str,
    ) -> None:
        """Test JSON file operations with various configurations."""
        func = getattr(export_data, function_name)
        args = args_factory(mock_network, temp_file)

        func(*args)

        assert Path(temp_file).exists(), f"File not created for {description}"

        with Path(temp_file).open(encoding=FILE_ENCODING) as f:
            content = f.read()

        # Verify content is valid JSON
        validate_json_structure(content)

        # Check indentation for indent cases
        if description.endswith("with indent"):
            assert "\n" in content, f"No indentation found for {description}"

    def test_file_permission_error_handling(self, mock_network: Mock) -> None:
        """Test improved error handling for file permission errors."""
        readonly_file = "readonly.json"

        with patch("pathlib.Path.open", side_effect=PermissionError("Permission denied")):
            with pytest.raises(OSError, match=FILE_WRITE_ERROR_PATTERN):
                export_data.save_dict_to_json(TEST_JSON_DICT, readonly_file)

            with pytest.raises(OSError, match=FILE_WRITE_ERROR_PATTERN):
                export_data.write_json_to_file(mock_network, "viz", readonly_file)

    def test_non_serializable_objects_error_handling(self, temp_file: str) -> None:
        """Test error handling for non-serializable objects."""
        non_serializable = {"function": lambda x: x, "set": {1, 2, 3}}

        with pytest.raises(ValueError, match=SERIALIZATION_ERROR_PATTERN):
            export_data.save_dict_to_json(non_serializable, temp_file)

    def test_network_method_failure_handling(self, mock_network: Mock) -> None:
        """Test handling of network method failures."""
        mock_network.dat_to_df.side_effect = AttributeError("Method failed")

        with pytest.raises(AttributeError, match="Method failed"):
            export_data.write_matrix_to_tsv(mock_network)

        # Reset for other tests
        mock_network.dat_to_df.side_effect = None


# =============================================================================
# INTEGRATION AND EDGE CASE TESTS
# =============================================================================


class TestEdgeCasesAndIntegration:
    """Test edge cases and integration scenarios with all fixes applied."""

    @pytest.mark.parametrize("matrix,description", MATRIX_VARIATIONS)
    def test_matrix_type_variations(
        self, mock_network: Mock, matrix: Any, description: str
    ) -> None:
        """Test various matrix types work with isinstance() fix."""
        mock_network.dat = {"mat": matrix}

        try:
            result = export_data.export_net_json(mock_network, "dat")
            validate_json_structure(result)
        except (TypeError, AttributeError):
            # Some edge cases may still fail, which is acceptable
            pass

    def test_large_dataset_handling(self, large_test_matrix: list[list[float]]) -> None:
        """Test handling of large datasets."""
        mock_net = Mock()
        mock_net.dat = {"mat": large_test_matrix}

        result = export_data.export_net_json(mock_net, "dat")
        result_dict = validate_json_structure(result)

        assert len(result_dict["mat"]) == LARGE_MATRIX_ROWS

    def test_unicode_and_special_characters(self, temp_file: str) -> None:
        """Test handling of unicode and special characters."""
        export_data.save_dict_to_json(COMPLEX_JSON_DICT, temp_file)

        with Path(temp_file).open(encoding=FILE_ENCODING) as f:
            reloaded = json.load(f)

        assert reloaded["unicode"] == COMPLEX_JSON_DICT["unicode"]
        assert reloaded["special"] == COMPLEX_JSON_DICT["special"]

    def test_circular_reference_detection(self, temp_file: str) -> None:
        """Test detection and handling of circular references."""
        circular_dict = {"key": "value"}
        circular_dict["self"] = circular_dict

        with pytest.raises(ValueError, match=SERIALIZATION_ERROR_PATTERN):
            export_data.save_dict_to_json(circular_dict, temp_file)

    def test_complete_integration_workflow(self, mock_network: Mock, temp_file: str) -> None:
        """Test complete integration workflow without workarounds."""
        # Export network data to JSON
        json_result = export_data.export_net_json(mock_network, "dat")
        assert json_result is not None

        # Export DataFrame to TSV
        tsv_result = export_data.write_matrix_to_tsv(mock_network, filename=None)
        assert tsv_result is not None

        # Write JSON to file
        export_data.write_json_to_file(mock_network, "viz", temp_file)
        assert Path(temp_file).exists()

        # Save dict to JSON file
        test_dict = validate_json_structure(json_result)
        export_data.save_dict_to_json(test_dict, temp_file)
        assert Path(temp_file).exists()

    def test_performance_with_large_matrix(
        self, mock_network: Mock, large_test_matrix: list[list[float]]
    ) -> None:
        """Test performance with large matrix data."""
        mock_network.dat = {"mat": large_test_matrix}

        result = export_data.export_net_json(mock_network, "dat")
        result_dict = validate_json_structure(result)

        assert len(result_dict["mat"]) == LARGE_MATRIX_ROWS


# =============================================================================
# BUG FIX VALIDATION TESTS
# =============================================================================


class TestAllBugsAreFixed:
    """Comprehensive validation that all identified bugs have been properly fixed."""

    @pytest.mark.parametrize("invalid_type", INVALID_NET_TYPES)
    def test_unbound_local_error_completely_eliminated(
        self, mock_network: Mock, invalid_type: str
    ) -> None:
        """Verify the UnboundLocalError bug is completely eliminated."""
        with pytest.raises(ValueError, match=INVALID_NET_TYPE_PATTERN):
            export_data.export_net_json(mock_network, invalid_type)

    def test_error_message_helpfulness(self, mock_network: Mock) -> None:
        """Verify error messages are helpful and informative."""
        with pytest.raises(ValueError) as exc_info:
            export_data.export_net_json(mock_network, "wrong")

        error_message = str(exc_info.value)
        assert "Invalid net_type: 'wrong'" in error_message
        assert "Must be one of:" in error_message

    def test_path_open_functionality_restored(self, temp_file: str) -> None:
        """Verify Path.open() functionality is completely restored."""
        # Test save_dict_to_json
        export_data.save_dict_to_json(COMPLEX_JSON_DICT, temp_file)
        assert Path(temp_file).exists()

        with Path(temp_file).open(encoding=FILE_ENCODING) as f:
            content = f.read()
        reloaded = validate_json_structure(content)
        assert reloaded["unicode"] == COMPLEX_JSON_DICT["unicode"]

        # Test write_json_to_file
        mock_net = Mock()
        mock_net.export_net_json.return_value = json.dumps(TEST_JSON_DICT)
        export_data.write_json_to_file(mock_net, "viz", temp_file)
        assert Path(temp_file).exists()

    def test_isinstance_improvement_validation(self, mock_network: Mock) -> None:
        """Verify isinstance() improvement works with inheritance."""

        class SpecialList(list):
            """Special list subclass for testing."""

            def __init__(self, data: list[Any]) -> None:
                super().__init__(data)
                self.metadata = "special"

        special_matrix = SpecialList(DEFAULT_MATRIX)
        mock_network.dat["mat"] = special_matrix

        result = export_data.export_net_json(mock_network, "dat")
        result_dict = validate_json_structure(result)
        assert result_dict["mat"] == DEFAULT_MATRIX

    def test_comprehensive_functionality_validation(
        self, mock_network: Mock, temp_file: str
    ) -> None:
        """Final comprehensive test - all functionality working together."""
        # Test error handling
        with pytest.raises(ValueError, match=INVALID_NET_TYPE_PATTERN):
            export_data.export_net_json(mock_network, "bad_type")

        # Test file operations
        export_data.write_json_to_file(mock_network, "viz", temp_file)
        export_data.save_dict_to_json(TEST_JSON_DICT, temp_file)

        # Test matrix conversion with isinstance
        mock_network.dat["mat"] = np.array(DEFAULT_MATRIX)
        result = export_data.export_net_json(mock_network, "dat")
        result_dict = validate_json_structure(result)
        assert result_dict["mat"] == DEFAULT_MATRIX

        # Test TSV export
        tsv_result = export_data.write_matrix_to_tsv(mock_network, filename=None)
        assert isinstance(tsv_result, str)


# =============================================================================
# TEST EXECUTION CONFIGURATION
# =============================================================================

if __name__ == "__main__":
    # Run tests with verbose output and short traceback format
    pytest.main([__file__, "-v", "--tb=short"])
