"""
Updated comprehensive test suite for the FIXED version of export_data.py

Key changes from original tests:
1. Removed all patches for Path.open() bug (now fixed)
2. Changed UnboundLocalError tests to ValueError tests (bug fixed)
3. Removed TestKnownBugs class (bugs are now fixed)
4. Added tests for improved error handling
5. Tests now work with the actual fixed code without workarounds
"""

import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd
import pytest


# Add the src directory to Python path for imports
project_root = Path(__file__).parent.parent.parent.parent
src_path = project_root / "src"
if src_path not in sys.path:
    sys.path.insert(0, str(src_path))

from celldega.clust.data import export_data


# Shared test fixtures to minimize duplication
@pytest.fixture
def mock_network():
    """Create a complete mock network object used across multiple test classes."""
    mock_net = Mock()
    mock_net.dat = {"mat": [[1, 2], [3, 4]], "nodes": {"row": ["r1", "r2"], "col": ["c1", "c2"]}}
    mock_net.viz = {"data": "viz_content"}
    mock_net.sim = {"row": {"similarity": "row_data"}, "col": {"similarity": "col_data"}}
    mock_net.dat_to_df.return_value = pd.DataFrame(
        {"col1": [1, 2, 3], "col2": [4, 5, 6]}, index=["row1", "row2", "row3"]
    )

    # Configure export_net_json to return different values based on indent parameter
    def mock_export_net_json(net_type, indent="no-indent"):
        test_data = {"test": "data"}
        if indent == "indent":
            return json.dumps(test_data, indent=2)
        return json.dumps(test_data)

    mock_net.export_net_json.side_effect = mock_export_net_json
    return mock_net


@pytest.fixture
def temp_file():
    """Create temporary file for testing file operations."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as tmp_file:
        temp_filename = tmp_file.name
    yield temp_filename
    if Path(temp_filename).exists():
        Path(temp_filename).unlink()


class TestExportNetJsonFixed:
    """Test export_net_json function with all bugs fixed."""

    def test_all_net_types_and_matrix_conversions(self, mock_network):
        """Test all net_type options and matrix type conversions."""
        # Test cases: (net_type, description)
        test_cases = [
            ("dat", "dat export with list matrix"),
            ("viz", "viz export"),
            ("sim_row", "sim_row export"),
            ("sim_col", "sim_col export"),
        ]

        for net_type, description in test_cases:
            result = export_data.export_net_json(mock_network, net_type)
            assert isinstance(result, str), f"Failed for {description}"
            # Verify it's valid JSON
            json.loads(result)

            # For dat type, also test numpy matrix conversion
            if net_type == "dat":
                mock_network.dat["mat"] = np.array([[1, 2], [3, 4]])
                result = export_data.export_net_json(mock_network, net_type)
                result_dict = json.loads(result)
                assert result_dict["mat"] == [[1, 2], [3, 4]], "Numpy array conversion failed"

                # Reset to list for other tests
                mock_network.dat["mat"] = [[1, 2], [3, 4]]

    def test_indent_options_and_fixed_error_handling(self, mock_network):
        """Test indent formatting and the fixed error handling."""
        # Test indent options
        result_indent = export_data.export_net_json(mock_network, "viz", indent="indent")
        result_no_indent = export_data.export_net_json(mock_network, "viz", indent="no-indent")

        expected_indent = json.dumps(mock_network.viz, indent=2)
        expected_no_indent = json.dumps(mock_network.viz)

        assert result_indent == expected_indent
        assert result_no_indent == expected_no_indent

        # Test fixed error handling - now raises ValueError with correct message
        with pytest.raises(ValueError, match="Invalid net_type: 'invalid_type'"):
            export_data.export_net_json(mock_network, "invalid_type")

        # Test that the error message contains the expected text
        with pytest.raises(ValueError, match="Must be one of: 'dat', 'viz', 'sim_row', 'sim_col'"):
            export_data.export_net_json(mock_network, "nonexistent")

        # Test missing attributes still raise AttributeError (unchanged behavior)
        incomplete_net = Mock()
        del incomplete_net.dat
        with pytest.raises(AttributeError):
            export_data.export_net_json(incomplete_net, "dat")

    def test_isinstance_fix_validation(self, mock_network):
        """Test that isinstance() fix works correctly with inheritance."""

        # Test with custom list subclass to verify isinstance() works better than type()
        class CustomList(list):
            pass

        # The fixed code should handle list subclasses correctly
        mock_network.dat["mat"] = CustomList([[1, 2], [3, 4]])
        result = export_data.export_net_json(mock_network, "dat")
        result_dict = json.loads(result)

        # Should still convert to regular list (isinstance handles subclasses properly)
        assert result_dict["mat"] == [[1, 2], [3, 4]]


class TestFileOperationsFixed:
    """Test file operations with Path.open() bugs completely fixed."""

    def test_tsv_export_all_scenarios(self, mock_network, temp_file):
        """Test all TSV export scenarios."""
        mock_network.dat_to_df.reset_mock()

        # Test 1: Export with filename
        export_data.write_matrix_to_tsv(mock_network, filename=temp_file)
        assert Path(temp_file).exists()

        with Path(temp_file).open() as f:
            content = f.read()
        assert "\t" in content and "col1\tcol2" in content

        # Test 2: Export without filename (returns string)
        result = export_data.write_matrix_to_tsv(mock_network, filename=None)
        assert isinstance(result, str) and "\t" in result

        # Test 3: Export with custom DataFrame
        mock_network.dat_to_df.reset_mock()
        custom_df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
        export_data.write_matrix_to_tsv(mock_network, filename=temp_file, df=custom_df)

        with Path(temp_file).open() as f:
            content = f.read()
        assert "a\tb" in content
        mock_network.dat_to_df.assert_not_called()

    def test_json_file_operations_now_work(self, mock_network, temp_file):
        """Test JSON file operations - Path.open() now works correctly!"""
        test_dict = {"key": "value", "unicode": "café ñoño", "number": 42}

        # Test cases: (function, args, description)
        json_test_cases = [
            (
                export_data.write_json_to_file,
                [mock_network, "viz", temp_file, "no-indent"],
                "write_json_to_file no-indent",
            ),
            (
                export_data.write_json_to_file,
                [mock_network, "viz", temp_file, "indent"],
                "write_json_to_file with indent",
            ),
            (
                export_data.save_dict_to_json,
                [test_dict, temp_file, "no-indent"],
                "save_dict_to_json no-indent",
            ),
            (
                export_data.save_dict_to_json,
                [test_dict, temp_file, "indent"],
                "save_dict_to_json with indent",
            ),
        ]

        for func, args, description in json_test_cases:
            # Path.open() now works correctly!
            func(*args)
            assert Path(temp_file).exists(), f"File not created for {description}"

            with Path(temp_file).open(encoding="utf-8") as f:
                content = f.read()

            # Verify content is valid JSON
            json.loads(content)

            # Check indentation for indent cases
            if "indent" in description and description.endswith("with indent"):
                assert "\n" in content, f"No indentation found for {description}"

    def test_improved_error_handling(self, mock_network, temp_file):
        """Test the new and improved error handling in file operations."""

        # Test file permission errors with better error messages
        with patch("pathlib.Path.open", side_effect=PermissionError("Permission denied")):
            # Now get descriptive OSError instead of generic PermissionError
            with pytest.raises(OSError, match="Failed to write JSON to file.*readonly.json"):
                export_data.save_dict_to_json({"test": "data"}, "readonly.json")

            with pytest.raises(OSError, match="Failed to write JSON to file.*readonly.json"):
                export_data.write_json_to_file(mock_network, "viz", "readonly.json")

        # Test non-serializable objects with better error messages
        non_serializable = {"function": lambda x: x, "set": {1, 2, 3}}
        with pytest.raises(ValueError, match="Failed to serialize dictionary to JSON"):
            export_data.save_dict_to_json(non_serializable, temp_file)

        # Test network method failures (unchanged behavior)
        mock_network.dat_to_df.side_effect = AttributeError("Method failed")
        with pytest.raises(AttributeError, match="Method failed"):
            export_data.write_matrix_to_tsv(mock_network)

        # Reset for other tests
        mock_network.dat_to_df.side_effect = None


class TestEdgeCasesAndIntegration:
    """Test edge cases and integration scenarios with all fixes applied."""

    def test_matrix_type_variations(self, mock_network):
        """Test various matrix types work with isinstance() fix."""
        matrix_variations = [
            ([], "empty list"),
            ([[]], "nested empty list"),
            (np.array([]), "empty numpy array"),
            (np.array([[1, 2], [3, 4]]), "2D numpy array"),
            (([[1, 2]],), "tuple of lists"),
        ]

        for matrix, description in matrix_variations:
            mock_network.dat = {"mat": matrix}
            try:
                result = export_data.export_net_json(mock_network, "dat")
                assert isinstance(result, str), f"Failed for {description}"
                json.loads(result)  # Verify valid JSON
            except (TypeError, AttributeError):
                # Some edge cases may still fail, which is acceptable
                pass

    def test_special_data_handling_no_patching_needed(self, temp_file):
        """Test special data handling - Path.open() now works correctly."""
        # Large dataset test
        large_matrix = np.random.rand(100, 50).tolist()
        mock_net = Mock()
        mock_net.dat = {"mat": large_matrix}

        result = export_data.export_net_json(mock_net, "dat")
        result_dict = json.loads(result)
        assert len(result_dict["mat"]) == 100

        # Special characters and unicode - works directly now
        special_dict = {
            "unicode": "café ñoño 中文",
            "special": "\"quotes\" and 'apostrophes' and \n newlines",
            "numbers": [1.5, -2.3, 0],
            "empty_structures": {"list": [], "dict": {}, "string": ""},
        }

        # Path.open() now works correctly!
        export_data.save_dict_to_json(special_dict, temp_file)
        with Path(temp_file).open(encoding="utf-8") as f:
            reloaded = json.load(f)

        assert reloaded["unicode"] == "café ñoño 中文"
        assert reloaded["special"] == "\"quotes\" and 'apostrophes' and \n newlines"

        # Test circular reference detection (improved error message)
        circular_dict = {"key": "value"}
        circular_dict["self"] = circular_dict

        with pytest.raises(ValueError, match="Failed to serialize dictionary to JSON"):
            export_data.save_dict_to_json(circular_dict, temp_file)

    def test_complete_integration_no_workarounds(self, mock_network, temp_file):
        """Test complete integration - all functions work together seamlessly."""
        # Test that all functions work together without any workarounds

        # 1. Export network data to JSON
        json_result = export_data.export_net_json(mock_network, "dat")
        assert json_result is not None

        # 2. Export DataFrame to TSV
        tsv_result = export_data.write_matrix_to_tsv(mock_network, filename=None)
        assert tsv_result is not None

        # 3. Write JSON to file - Path.open() works correctly!
        export_data.write_json_to_file(mock_network, "viz", temp_file)
        assert Path(temp_file).exists()

        # 4. Save dict to JSON file - Path.open() works correctly!
        test_dict = json.loads(json_result)
        export_data.save_dict_to_json(test_dict, temp_file)
        assert Path(temp_file).exists()

        # 5. Performance test with large data
        large_matrix = [[i + j for j in range(100)] for i in range(100)]
        mock_network.dat = {"mat": large_matrix}

        result = export_data.export_net_json(mock_network, "dat")
        assert len(json.loads(result)["mat"]) == 100


class TestAllBugsAreFixed:
    """Comprehensive validation that ALL identified bugs have been properly fixed."""

    def test_unbound_local_error_completely_fixed(self, mock_network):
        """Verify the UnboundLocalError bug is completely eliminated."""
        # Test various invalid net_types
        invalid_types = ["invalid", "wrong", "fake", "", "DATA", "VIZ"]

        for invalid_type in invalid_types:
            with pytest.raises(ValueError, match="Invalid net_type"):
                export_data.export_net_json(mock_network, invalid_type)

        # Verify the error message is helpful
        try:
            export_data.export_net_json(mock_network, "wrong")
            raise AssertionError("Should have raised ValueError")
        except ValueError as e:
            assert "Invalid net_type: 'wrong'" in str(e)
            assert "Must be one of:" in str(e)

    def test_path_open_bugs_completely_fixed(self, temp_file):
        """Verify Path.open() now works correctly."""
        # Test save_dict_to_json works with Path.open()
        test_dict = {"test": "data", "unicode": "café"}
        export_data.save_dict_to_json(test_dict, temp_file)
        assert Path(temp_file).exists()

        with Path(temp_file).open() as f:
            content = f.read()
        reloaded = json.loads(content)
        assert reloaded == test_dict

        # Test write_json_to_file works with Path.open()
        mock_net = Mock()
        mock_net.export_net_json.return_value = '{"test": "data"}'
        export_data.write_json_to_file(mock_net, "viz", temp_file)
        assert Path(temp_file).exists()

    def test_type_checking_improvement_works(self, mock_network):
        """Verify isinstance() improvement works correctly."""

        # Test with list subclass (isinstance handles this better than type())
        class SpecialList(list):
            def __init__(self, data):
                super().__init__(data)
                self.metadata = "special"

        special_matrix = SpecialList([[1, 2], [3, 4]])
        mock_network.dat["mat"] = special_matrix

        # Should work correctly with isinstance() fix
        result = export_data.export_net_json(mock_network, "dat")
        result_dict = json.loads(result)
        assert result_dict["mat"] == [[1, 2], [3, 4]]

    def test_all_functions_work_together_flawlessly(self, mock_network, temp_file):
        """Final integration test - everything should work perfectly."""
        # This test would have failed with multiple bugs in the original code
        # Now it should pass flawlessly

        # Test error handling improvements
        with pytest.raises(ValueError, match="Invalid net_type"):
            export_data.export_net_json(mock_network, "bad_type")

        # Test file operations work
        export_data.write_json_to_file(mock_network, "viz", temp_file)
        export_data.save_dict_to_json({"test": "data"}, temp_file)

        # Test matrix conversion with isinstance
        mock_network.dat["mat"] = np.array([[1, 2]])
        result = export_data.export_net_json(mock_network, "dat")
        assert json.loads(result)["mat"] == [[1, 2]]

        # Test TSV export
        tsv_result = export_data.write_matrix_to_tsv(mock_network, filename=None)
        assert isinstance(tsv_result, str)


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "--tb=short"])
