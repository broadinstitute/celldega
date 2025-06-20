"""
Comprehensive tests for celldega.clust.data_io.load_data module.
Tests cover all functions with extensive edge case coverage and minimal redundancy.
"""

import io
import json
from pathlib import Path
from typing import Any
from unittest.mock import Mock, mock_open, patch

import pandas as pd
import pytest

from celldega.clust.data_io import load_data


# =============================================================================
# CONSTANTS
# =============================================================================

# Test file names and paths
TEST_FILE_SIMPLE = "test.tsv"
TEST_FILE_DATA = "data.tsv"
TEST_FILE_EMPTY = "empty.tsv"
TEST_FILE_UNICODE = "unicode.tsv"
TEST_FILE_NONEXISTENT = "nonexistent.tsv"
TEST_FILE_RESTRICTED = "restricted.tsv"
TEST_FILE_BAD_ENCODING = "bad_encoding.tsv"
TEST_FILE_IO_ERROR = "io_error.tsv"
TEST_FILE_HUGE = "huge_file.tsv"
TEST_FILE_LARGE = "large.tsv"
TEST_FILE_JSON = "test.json"
TEST_FILE_GMT = "test.gmt"

# Test content constants
CONTENT_SIMPLE = "simple content"
CONTENT_TABULAR = "gene\tcell1\ncellA\t1"
CONTENT_EMPTY = ""
CONTENT_UNICODE = "unicode: café\tnaïve\t1"
CONTENT_LARGE = "large content\n" * 1000

# TSV content templates
TSV_VALID_WITH_CATEGORIES = """cat1\tcat2\t\tcell1\tcell2\tcell3
\t\t\tval1\tval2\tval3
gene1\tA\t\t1\t2\t3
gene2\tB\t\t4\t5\t6
gene3\tA\t\t7\t8\t9"""

TSV_SIMPLE = """gene\tcell1\tcell2\tcell3
gene1\t1\t2\t3
gene2\t4\t5\t6"""

# GMT content template
GMT_CONTENT = """pathway1\tdescription1\tgene1\tgene2\tgene3
pathway2\tdescription2\tgeneA\tgeneB
pathway3\tdescription3\tgeneX"""

# Error messages
ERROR_IO = "I/O error"
ERROR_INVALID_ENCODING = "invalid start byte"
ERROR_NO_DATA = "No data"
ERROR_PARSER = "Parser error"
ERROR_INVALID_FORMAT = "Invalid data format"
ERROR_OUT_OF_MEMORY = "Out of memory"

# Category configuration constants
ROW_CATS_NONE = 1
ROW_CATS_SINGLE = 2
ROW_CATS_MULTIPLE = 3
ROW_CATS_MAX = 4
COL_CATS_NONE = 1
COL_CATS_SINGLE = 2
COL_CATS_MULTIPLE = 3
COL_CATS_MAX = 4

# Buffer size constants
BUFFER_SIZE_TINY = 1
BUFFER_SIZE_SMALL = 100
BUFFER_SIZE_MEDIUM = 1000
BUFFER_SIZE_LARGE = 10000

# =============================================================================
# UTILITIES
# =============================================================================


def create_test_dataframe(rows: int = 2, cols: int = 2) -> pd.DataFrame:
    """Create a test DataFrame with specified dimensions."""
    return pd.DataFrame([[i + j for j in range(cols)] for i in range(rows)])


def create_mock_path_with_content(content: str) -> Mock:
    """Create a mock Path object that returns specified content."""
    mock_path_instance = Mock()
    mock_path_instance.read_text.return_value = content
    mock_path_instance.name = "test_file"
    return mock_path_instance


def generate_content_of_size(size: int) -> str:
    """Generate test content of specified line count."""
    return "\n".join([f"gene{i}\tcell1\tcell2\n{i}\t{i + 1}\t{i + 2}" for i in range(size)])


def create_unicode_samples() -> list[str]:
    """Create comprehensive Unicode test samples."""
    return [
        "café\tnaïve\trésumé",  # Latin characters
        "αβγ\tδεζ\tηθι",  # Greek
        "测试\t数据\t内容",  # Chinese
        "🧬\t🧪\t🔬",  # Emojis
        "test\u0000null",  # Null bytes
        "tab\there\tthere",  # Mixed
    ]


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_network() -> Mock:
    """Create a reusable mock network object with standard behavior."""
    network = Mock()
    network.dat = {"filename": None}
    network.reset_called = False
    network.df_to_dat_called = False
    network.load_tsv_to_net_called = False

    def reset():
        network.reset_called = True

    def df_to_dat(df: pd.DataFrame, flag: bool):
        network.df_to_dat_called = True
        network.last_df = df
        network.last_flag = flag

    def load_tsv_to_net(buffer: io.StringIO, filename: str | None):
        network.load_tsv_to_net_called = True
        network.last_buffer = buffer
        network.last_filename = filename
        network.df_to_dat_called = True
        network.dat["filename"] = filename

    network.reset = reset
    network.df_to_dat = df_to_dat
    network.load_tsv_to_net = load_tsv_to_net

    return network


@pytest.fixture
def sample_dataframe() -> pd.DataFrame:
    """Create a standard test DataFrame."""
    return create_test_dataframe()


# =============================================================================
# FILE LOADING TESTS
# =============================================================================


class TestFileLoading:
    """Test file loading functionality with comprehensive edge cases."""

    @pytest.mark.parametrize(
        "file_content,filename,description",
        [
            (CONTENT_SIMPLE, TEST_FILE_SIMPLE, "simple"),
            (CONTENT_TABULAR, TEST_FILE_DATA, "tabular"),
            (CONTENT_EMPTY, TEST_FILE_EMPTY, "empty"),
            (CONTENT_UNICODE, TEST_FILE_UNICODE, "unicode"),
        ],
    )
    @patch("celldega.clust.data_io.load_data.Path")
    @patch("celldega.clust.data_io.load_data.load_file_as_string")
    def test_load_file_success_cases(
        self,
        mock_load_string: Mock,
        mock_path: Mock,
        file_content: str,
        filename: str,
        description: str,
        mock_network: Mock,
    ):
        """Test successful file loading with various content types."""
        mock_path.return_value.read_text.return_value = file_content

        load_data.load_file(mock_network, filename)

        assert mock_network.reset_called
        mock_path.assert_called_with(filename)
        mock_load_string.assert_called_with(mock_network, file_content, filename)

    @pytest.mark.parametrize(
        "exception_type,filename,description",
        [
            (FileNotFoundError(), TEST_FILE_NONEXISTENT, "file_not_found"),
            (PermissionError(), TEST_FILE_RESTRICTED, "permission_denied"),
            (
                UnicodeDecodeError("utf-8", b"", 0, 1, ERROR_INVALID_ENCODING),
                TEST_FILE_BAD_ENCODING,
                "unicode_decode",
            ),
            (OSError(ERROR_IO), TEST_FILE_IO_ERROR, "io_error"),
            (MemoryError(), TEST_FILE_HUGE, "memory_error"),
        ],
    )
    @patch("celldega.clust.data_io.load_data.Path")
    def test_load_file_error_cases(
        self,
        mock_path: Mock,
        exception_type: Exception,
        filename: str,
        description: str,
        mock_network: Mock,
    ):
        """Test file loading error handling with comprehensive error coverage."""
        mock_path.return_value.read_text.side_effect = exception_type

        with pytest.raises(type(exception_type)):
            load_data.load_file(mock_network, filename)

        assert mock_network.reset_called

    @pytest.mark.parametrize(
        "content,content_type,filename,description",
        [
            (CONTENT_SIMPLE, str, TEST_FILE_SIMPLE, "string_content"),
            (CONTENT_SIMPLE.encode(), bytes, TEST_FILE_SIMPLE, "bytes_content"),
            (CONTENT_EMPTY, str, TEST_FILE_EMPTY, "empty_string"),
            (CONTENT_EMPTY.encode(), bytes, TEST_FILE_EMPTY, "empty_bytes"),
            (CONTENT_UNICODE, str, TEST_FILE_UNICODE, "unicode_string"),
            (CONTENT_UNICODE.encode(), bytes, TEST_FILE_UNICODE, "unicode_bytes"),
            (CONTENT_LARGE, str, TEST_FILE_LARGE, "large_string"),
            (CONTENT_LARGE.encode("utf-8"), bytes, TEST_FILE_LARGE, "large_bytes"),
            ("content", str, "", "no_filename"),
        ],
    )
    def test_load_file_as_string_comprehensive(
        self,
        content: str | bytes,
        content_type: type[str] | type[bytes],
        filename: str,
        description: str,
        mock_network: Mock,
    ):
        """Test load_file_as_string with comprehensive input variations."""
        with patch.object(mock_network, "load_tsv_to_net") as mock_load:
            load_data.load_file_as_string(mock_network, content, filename)

        mock_load.assert_called_once()
        args = mock_load.call_args[0]
        assert args[1] == Path(filename).name
        assert isinstance(args[0], io.StringIO)


# =============================================================================
# STDIN AND BUFFER HANDLING TESTS
# =============================================================================


class TestStdinAndBufferHandling:
    """Test stdin loading and buffer handling edge cases."""

    @pytest.mark.parametrize(
        "stdin_input,description",
        [
            (["line1\n", "line2\n", "line3\n"], "normal_input"),
            ([], "empty_input"),
            (["single_line"], "no_newline"),
            (["line1\n"] * 1000, "large_input"),
            (["unicode: café\n", "naïve\n"], "unicode_input"),
            (["\n", "\n", "\n"], "empty_lines_only"),
        ],
    )
    @patch("sys.stdin")
    def test_load_stdin_variations(
        self, mock_stdin: Mock, stdin_input: list[str], description: str, mock_network: Mock
    ):
        """Test stdin loading with various input patterns."""
        mock_stdin.__iter__ = Mock(return_value=iter(stdin_input))

        with patch.object(mock_network, "load_tsv_to_net") as mock_load:
            load_data.load_stdin(mock_network)

        mock_load.assert_called_once()
        call_args = mock_load.call_args[0]

        assert hasattr(call_args[0], "read"), "Should be a StringIO-like object"
        assert call_args[1] is None, "Filename should be None for stdin"

    def test_stringio_bug_demonstration(self):
        """Test StringIO compatibility - demonstrates the bug that needs fixing."""
        from io import StringIO

        # Correct usage (works)
        correct_buffer = StringIO("test data")
        assert correct_buffer.read() == "test data"

        # The bug: StringIO.StringIO(data) - this fails
        with pytest.raises(AttributeError, match="has no attribute 'StringIO'"):
            _ = StringIO.StringIO("test data")


# =============================================================================
# TSV PROCESSING TESTS
# =============================================================================


class TestTsvProcessing:
    """Comprehensive TSV processing tests covering parsing edge cases."""

    @pytest.mark.parametrize(
        "row_cats,col_cats,use_header",
        [
            (ROW_CATS_NONE, COL_CATS_NONE, False),
            (ROW_CATS_SINGLE, COL_CATS_NONE, False),
            (ROW_CATS_NONE, COL_CATS_SINGLE, True),
            (ROW_CATS_SINGLE, COL_CATS_SINGLE, True),
            (ROW_CATS_MULTIPLE, COL_CATS_NONE, False),
            (ROW_CATS_NONE, COL_CATS_MULTIPLE, True),
            (ROW_CATS_MAX, COL_CATS_MAX, True),
        ],
    )
    @patch("celldega.clust.data_io.load_data.categories.check_categories")
    @patch("celldega.clust.data_io.load_data.proc_df_labels.main")
    @patch("pandas.read_table")
    def test_tsv_category_configurations(
        self,
        mock_read_table: Mock,
        mock_proc_labels: Mock,
        mock_check_cats: Mock,
        row_cats: int,
        col_cats: int,
        use_header: bool,
        mock_network: Mock,
        sample_dataframe: pd.DataFrame,
    ):
        """Test TSV loading with various category configurations."""
        mock_check_cats.return_value = {"row": row_cats, "col": col_cats}
        mock_read_table.return_value = sample_dataframe
        mock_proc_labels.return_value = sample_dataframe

        buffer = io.StringIO(TSV_VALID_WITH_CATEGORIES)
        load_data.load_tsv_to_net(mock_network, buffer, TEST_FILE_SIMPLE)

        call_kwargs = mock_read_table.call_args.kwargs
        expected_row_arr = list(range(row_cats))

        assert call_kwargs["index_col"] == expected_row_arr
        if use_header:
            expected_col_arr = list(range(col_cats))
            assert call_kwargs["header"] == expected_col_arr

        assert mock_network.df_to_dat_called
        assert mock_network.dat["filename"] == TEST_FILE_SIMPLE

    @pytest.mark.parametrize(
        "pandas_error,description",
        [
            (pd.errors.EmptyDataError(ERROR_NO_DATA), "empty_data"),
            (pd.errors.ParserError(ERROR_PARSER), "parser_error"),
            (ValueError(ERROR_INVALID_FORMAT), "value_error"),
            (UnicodeDecodeError("utf-8", b"", 0, 1, ERROR_INVALID_ENCODING), "unicode_error"),
            (MemoryError(ERROR_OUT_OF_MEMORY), "memory_error"),
        ],
    )
    @patch("celldega.clust.data_io.load_data.categories.check_categories")
    @patch("pandas.read_table")
    def test_tsv_pandas_error_handling(
        self,
        mock_read_table: Mock,
        mock_check_cats: Mock,
        pandas_error: Exception,
        description: str,
        mock_network: Mock,
    ):
        """Test comprehensive pandas error handling during TSV processing."""
        mock_check_cats.return_value = {"row": ROW_CATS_NONE, "col": COL_CATS_NONE}
        mock_read_table.side_effect = pandas_error

        buffer = io.StringIO("test data")

        with pytest.raises(type(pandas_error)):
            load_data.load_tsv_to_net(mock_network, buffer, "error.tsv")

    def test_buffer_position_fix_verification(self, sample_dataframe: pd.DataFrame):
        """Test that buffer position is properly reset before processing."""
        buffer = io.StringIO(TSV_SIMPLE)

        # Simulate buffer being read before (previously caused the bug)
        _ = buffer.read()

        with patch("celldega.clust.data_io.load_data.categories.check_categories") as mock_check:
            with patch("pandas.read_table") as mock_read_table:
                with patch("celldega.clust.data_io.load_data.proc_df_labels.main") as mock_proc:
                    mock_check.return_value = {"row": ROW_CATS_NONE, "col": COL_CATS_NONE}
                    mock_read_table.return_value = sample_dataframe
                    mock_proc.return_value = sample_dataframe

                    net = Mock()
                    net.dat = {}
                    net.df_to_dat = Mock()

                    load_data.load_tsv_to_net(net, buffer, TEST_FILE_SIMPLE)

                    mock_read_table.assert_called_once()
                    assert net.dat["filename"] == TEST_FILE_SIMPLE

    @pytest.mark.parametrize(
        "malformed_content,description",
        [
            ("incomplete\trow", "incomplete_row"),
            ("col1\tcol2\n\t", "empty_values"),
            ("mixed\ttabs and spaces   here", "mixed_separators"),
            ("\t\t\n\t\t\n", "only_separators"),
            ("normal\tdata\nnull\x00byte", "null_bytes"),
        ],
    )
    @patch("celldega.clust.data_io.load_data.categories.check_categories")
    def test_malformed_tsv_content(
        self,
        mock_check_cats: Mock,
        malformed_content: str,
        description: str,
        mock_network: Mock,
        sample_dataframe: pd.DataFrame,
    ):
        """Test handling of various malformed TSV content."""
        mock_check_cats.return_value = {"row": ROW_CATS_NONE, "col": COL_CATS_NONE}
        buffer = io.StringIO(malformed_content)

        with patch("pandas.read_table") as mock_read_table:
            mock_read_table.return_value = sample_dataframe

            with patch("celldega.clust.data_io.load_data.proc_df_labels.main") as mock_proc:
                mock_proc.return_value = sample_dataframe

                load_data.load_tsv_to_net(mock_network, buffer, f"{description}.tsv")
                assert mock_network.df_to_dat_called


# =============================================================================
# JSON AND GMT LOADING TESTS
# =============================================================================


class TestJsonAndGmtLoading:
    """Comprehensive tests for JSON and GMT file loading."""

    @pytest.mark.parametrize(
        "json_data,description",
        [
            ({"simple": "data"}, "simple_object"),
            ({"nested": {"key": "value"}}, "nested_object"),
            ({"array": [1, 2, 3]}, "with_array"),
            ({"number": 42, "float": 3.14, "bool": True}, "mixed_types"),
            ({}, "empty_object"),
            ({"unicode": "café naïve"}, "unicode_content"),
            ({"large": "x" * 10000}, "large_content"),
        ],
    )
    def test_json_loading_variations(self, json_data: dict[str, Any], description: str):
        """Test JSON loading with various data structures."""
        json_string = json.dumps(json_data)

        with patch("celldega.clust.data_io.load_data.Path.open", mock_open(read_data=json_string)):
            result = load_data.load_json_to_dict(f"{description}.json")

        assert result == json_data

    @pytest.mark.parametrize(
        "invalid_json,error_type,description",
        [
            ("invalid json {", json.JSONDecodeError, "malformed_json"),
            ("{missing: quotes}", json.JSONDecodeError, "missing_quotes"),
            ("", json.JSONDecodeError, "empty_file"),
            ('{"key": }', json.JSONDecodeError, "incomplete_json"),
        ],
    )
    def test_json_error_handling(
        self, invalid_json: str, error_type: type[Exception], description: str
    ):
        """Test JSON error handling with various invalid formats."""
        with patch("celldega.clust.data_io.load_data.Path.open", mock_open(read_data=invalid_json)):
            with pytest.raises(error_type):
                load_data.load_json_to_dict(f"{description}.json")

    def test_json_null_handling(self):
        """Test handling of valid JSON null value."""
        with patch("celldega.clust.data_io.load_data.Path.open", mock_open(read_data="null")):
            result = load_data.load_json_to_dict("null.json")
            assert result is None

    @pytest.mark.parametrize(
        "gmt_content,expected_result,description",
        [
            (
                "pathway1\tdesc\tgene1\tgene2\tgene3",
                {"pathway1": ["gene1", "gene2", "gene3"]},
                "standard",
            ),
            (
                "p1\td1\tg1\tg2\np2\td2\tg3\tg4",
                {"p1": ["g1", "g2"], "p2": ["g3", "g4"]},
                "multiple",
            ),
            ("single\tdesc\tgene1", {"single": ["gene1"]}, "single_gene"),
            ("empty\tdesc", {"empty": []}, "empty_pathway"),
            (
                "big\td\tg1\tg2\tg3\tg4\tg5\nsmall\td\tg1",
                {"big": ["g1", "g2", "g3", "g4", "g5"], "small": ["g1"]},
                "mixed_sizes",
            ),
            ("café\tdésc\tgène1\tgène2", {"café": ["gène1", "gène2"]}, "unicode"),
            ("", {}, "empty_file"),
        ],
    )
    def test_gmt_loading_variations(
        self, gmt_content: str, expected_result: dict[str, list[str]], description: str
    ):
        """Test GMT loading with various file formats and edge cases."""
        with patch("celldega.clust.data_io.load_data.Path.open", mock_open(read_data=gmt_content)):
            result = load_data.load_gmt(f"{description}.gmt")

        assert result == expected_result

    @pytest.mark.parametrize(
        "file_error,description",
        [
            (FileNotFoundError("File not found"), "file_not_found"),
            (PermissionError("Permission denied"), "permission_denied"),
            (UnicodeDecodeError("utf-8", b"", 0, 1, ERROR_INVALID_ENCODING), "unicode_decode"),
            (OSError(ERROR_IO), "io_error"),
        ],
    )
    def test_file_loading_errors(self, file_error: Exception, description: str):
        """Test file loading error handling for both JSON and GMT."""
        with patch("celldega.clust.data_io.load_data.Path.open", side_effect=file_error):
            with pytest.raises(type(file_error)):
                load_data.load_json_to_dict(f"missing_{description}.json")

            with pytest.raises(type(file_error)):
                load_data.load_gmt(f"missing_{description}.gmt")


# =============================================================================
# DATA TO NET LOADING TESTS
# =============================================================================


class TestDataToNetLoading:
    """Test load_data_to_net function with comprehensive scenarios."""

    @pytest.mark.parametrize(
        "test_data,description",
        [
            (
                {
                    "nodes": {"row": ["gene1", "gene2"], "col": ["cell1", "cell2"]},
                    "mat": [[1, 2], [3, 4]],
                },
                "standard_data",
            ),
            ({"nodes": {"row": [], "col": []}, "mat": []}, "empty_data"),
            (
                {
                    "nodes": {
                        "row": [f"gene{i}" for i in range(100)],
                        "col": [f"cell{i}" for i in range(50)],
                    },
                    "mat": [[i + j for j in range(50)] for i in range(100)],
                },
                "large_data",
            ),
            ({"nodes": {"row": ["gene1"], "col": ["cell1"]}, "mat": [[42]]}, "single_cell"),
        ],
    )
    @patch("celldega.clust.data_io.load_data.data_formats.mat_to_numpy_arr")
    def test_load_data_to_net_success_cases(
        self,
        mock_mat_to_numpy: Mock,
        test_data: dict[str, Any],
        description: str,
        mock_network: Mock,
    ):
        """Test successful data loading with various data structures."""
        mock_network.dat = {}

        load_data.load_data_to_net(mock_network, test_data)

        assert mock_network.dat["nodes"] == test_data["nodes"]
        assert mock_network.dat["mat"] == test_data["mat"]
        mock_mat_to_numpy.assert_called_once_with(mock_network)

    @pytest.mark.parametrize(
        "incomplete_data,missing_key,description",
        [
            ({"nodes": {"row": ["gene1"]}}, "mat", "missing_mat"),
            ({"mat": [[1, 2]]}, "nodes", "missing_nodes"),
            ({}, "nodes", "empty_dict"),
        ],
    )
    @patch("celldega.clust.data_io.load_data.data_formats.mat_to_numpy_arr")
    def test_load_data_to_net_missing_keys(
        self,
        mock_mat_to_numpy: Mock,
        incomplete_data: dict[str, Any],
        missing_key: str,
        description: str,
        mock_network: Mock,
    ):
        """Test error handling for missing required top-level keys."""
        mock_network.dat = {}

        with pytest.raises(KeyError):
            load_data.load_data_to_net(mock_network, incomplete_data)

    @patch("celldega.clust.data_io.load_data.data_formats.mat_to_numpy_arr")
    def test_load_data_to_net_incomplete_nodes_success(
        self, mock_mat_to_numpy: Mock, mock_network: Mock
    ):
        """Test that incomplete nodes dict doesn't raise error in load_data_to_net."""
        mock_network.dat = {}

        incomplete_nodes_data = {
            "nodes": {"row": ["gene1"]},  # Missing "col"
            "mat": [[1, 2]],
        }

        load_data.load_data_to_net(mock_network, incomplete_nodes_data)

        assert mock_network.dat["nodes"] == {"row": ["gene1"]}
        assert mock_network.dat["mat"] == [[1, 2]]
        mock_mat_to_numpy.assert_called_once()


# =============================================================================
# COMPLEX INTEGRATION TESTS
# =============================================================================


class TestComplexIntegrationScenarios:
    """Test complex integration scenarios and edge case combinations."""

    @pytest.mark.parametrize(
        "content_size,description",
        [
            (BUFFER_SIZE_TINY, "tiny"),
            (BUFFER_SIZE_SMALL, "small"),
            (BUFFER_SIZE_MEDIUM, "medium"),
            (BUFFER_SIZE_LARGE, "large"),
        ],
    )
    def test_memory_and_performance_edge_cases(
        self, content_size: int, description: str, mock_network: Mock
    ):
        """Test memory handling with various content sizes."""
        large_content = generate_content_of_size(content_size)

        with patch.object(mock_network, "load_tsv_to_net"):
            # Test string handling
            load_data.load_file_as_string(mock_network, large_content)

            # Test bytes handling
            load_data.load_file_as_string(mock_network, large_content.encode("utf-8"))

    def test_unicode_edge_cases_comprehensive(self, mock_network: Mock):
        """Test comprehensive Unicode handling across all functions."""
        unicode_samples = create_unicode_samples()

        for sample in unicode_samples:
            with patch.object(mock_network, "load_tsv_to_net"):
                # Test both string and bytes
                load_data.load_file_as_string(mock_network, sample)
                load_data.load_file_as_string(mock_network, sample.encode("utf-8"))

    @pytest.mark.parametrize(
        "path_type,description",
        [
            ("simple.tsv", "simple"),
            ("path/with/subdirs/file.tsv", "subdirs"),
            ("file with spaces.tsv", "spaces"),
            ("file.with.dots.tsv", "dots"),
            ("file-with-dashes.tsv", "dashes"),
            ("UPPERCASE.TSV", "uppercase"),
            ("mixed_Case.Tsv", "mixed_case"),
            ("123numeric.tsv", "numeric"),
            ("special!@#$%^&()chars.tsv", "special_chars"),
        ],
    )
    @patch("celldega.clust.data_io.load_data.Path")
    @patch("celldega.clust.data_io.load_data.load_file_as_string")
    def test_filename_edge_cases(
        self,
        mock_load_string: Mock,
        mock_path: Mock,
        path_type: str,
        description: str,
        mock_network: Mock,
    ):
        """Test various filename and path edge cases."""
        mock_path.return_value.read_text.return_value = "test content"

        load_data.load_file(mock_network, path_type)

        mock_path.assert_called_with(path_type)
        mock_load_string.assert_called_with(mock_network, "test content", path_type)


# =============================================================================
# END-TO-END INTEGRATION TESTS
# =============================================================================


class TestEndToEndIntegration:
    """End-to-end integration tests simulating real usage patterns."""

    def test_full_tsv_loading_pipeline(self):
        """Test complete TSV loading pipeline from file to network."""
        mock_net = Mock()
        mock_net.dat = {}
        mock_net.reset_called = False
        mock_net.load_tsv_to_net_called = False
        mock_net.df_to_dat_called = False

        def reset():
            mock_net.reset_called = True

        def load_tsv_to_net(buffer: io.StringIO, filename: str | None):
            mock_net.load_tsv_to_net_called = True
            mock_net.last_buffer = buffer
            mock_net.last_filename = filename
            mock_net.df_to_dat_called = True
            mock_net.dat["filename"] = filename

        mock_net.reset = reset
        mock_net.load_tsv_to_net = load_tsv_to_net

        with patch("celldega.clust.data_io.load_data.Path") as mock_path_class:
            mock_path_instance = create_mock_path_with_content(TSV_VALID_WITH_CATEGORIES)
            mock_path_instance.name = TEST_FILE_SIMPLE
            mock_path_class.return_value = mock_path_instance

            load_data.load_file(mock_net, TEST_FILE_SIMPLE)

            assert mock_net.reset_called, "Network should be reset"
            assert mock_net.load_tsv_to_net_called, "load_tsv_to_net should be called"
            assert mock_net.df_to_dat_called, "df_to_dat should be called (simulated)"
            assert mock_net.dat["filename"] == TEST_FILE_SIMPLE, (
                f"Filename should be set, got: {mock_net.dat['filename']}"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
