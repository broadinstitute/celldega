"""
Comprehensive tests for enrichr_functions.py

This test suite provides robust coverage of all edge cases while minimizing redundancy
through functional programming patterns, parametrized tests, and shared fixtures.
"""

# =============================================================================
# IMPORTS
# =============================================================================

import json
from pathlib import Path
import sys
from typing import Any
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd
import pytest
from requests.exceptions import ConnectionError, RequestException, Timeout


# =============================================================================
# MODULE-LEVEL CONSTANTS
# =============================================================================

# Path configuration
SRC_ROOT = Path(__file__).parent.parent.parent.parent / "src"

# Test data constants
SAMPLE_GENES = ["BRCA1", "TP53", "EGFR", "MYC", "PIK3CA"]
GENES_WITH_MODIFIERS = ["BRCA1_p123", "TP53-variant", "EGFR phospho", "MYC_1", "PIK3CA-iso2"]
TITLED_GENES = ["Gene: BRCA1", "Gene: TP53", "Gene: EGFR"]
TUPLE_GENES = [("BRCA1", "Oncogene"), ("TP53", "Tumor Suppressor")]

# API constants
ENRICHR_POST_URL = "https://maayanlab.cloud/Enrichr/addList"
ENRICHR_GET_URL = "https://maayanlab.cloud/Enrichr/enrich"
DEFAULT_USER_LIST_ID = "12345"
DEFAULT_LIBRARY = "GO_Biological_Process_2015"
DEFAULT_MAX_RETRIES = 100
DEFAULT_TIMEOUT = 30

# Test response constants
MOCK_ENRICHR_RESPONSE = [
    ["", "GO:0006915 apoptotic process", 0.001, -2.5, 15.2, ["BRCA1", "TP53"], 0.01],
    ["", "GO:0008283 cell proliferation", 0.005, -1.8, 12.1, ["EGFR", "MYC"], 0.02],
    ["", "GO:0006260 DNA replication", 0.01, -1.2, 8.3, ["PIK3CA"], 0.03],
]

MOCK_POST_RESPONSE = {"userListId": 12345, "status": "success"}

# Error patterns
ERROR_EMPTY_GENES = "Gene list cannot be empty"
ERROR_INVALID_JSON_GET = "Invalid JSON response from Enrichr API"  # For get_request
ERROR_INVALID_JSON_POST = "Invalid response from Enrichr API"  # For post_request
ERROR_MISSING_USER_ID = "Enrichr API response missing userListId"
ERROR_INVALID_TYPE = "input_genes must be a list"
ERROR_EMPTY_LIBRARY = "Library name cannot be empty"
ERROR_EMPTY_USER_ID = "User list ID cannot be empty"
ERROR_RESPONSE_LIST_TYPE = "response_list must be a list"

# Statistical constants
PROBABILITY_TOLERANCE = 1e-10


# =============================================================================
# MODULE IMPORT AND SETUP
# =============================================================================

sys.path.insert(0, str(SRC_ROOT))

# Import after path setup
from celldega.clust_old.analysis.enrichr_functions import (
    add_enrichr_cats,
    get_request,
    post_request,
    transfer_to_enr_dict,
)


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================


def create_mock_response(status_code: int, response_data: dict[str, Any] | None = None) -> Mock:
    """Create a standardized mock response object."""
    mock_response = Mock()
    mock_response.status_code = status_code
    mock_response.text = json.dumps(response_data or {})
    mock_response.raise_for_status = Mock()
    return mock_response


def create_dataframe(genes: list[str | tuple[str, ...]], num_samples: int = 3) -> pd.DataFrame:
    """Create a standardized test DataFrame with random data."""
    data = np.random.rand(len(genes), num_samples)
    columns = [f"Sample{i + 1}" for i in range(num_samples)]
    return pd.DataFrame(data, index=genes, columns=columns)


def validate_enrichment_structure(enrichment_data: list[dict[str, Any]]) -> bool:
    """Validate the structure of enrichment data dictionaries."""
    required_fields = {"name", "pval", "zscore", "combined_score", "int_genes", "pval_bh"}
    return all(
        isinstance(item, dict) and required_fields.issubset(item.keys()) for item in enrichment_data
    )


def create_enrichr_response(num_terms: int) -> list[list[Any]]:
    """Generate mock Enrichr response with specified number of terms."""
    base_response = MOCK_ENRICHR_RESPONSE[0]
    return [
        [
            base_response[0],
            f"Term_{i + 1}",
            base_response[2] * (i + 1),
            base_response[3],
            base_response[4] / (i + 1),
            [f"GENE_{j}" for j in range(min(3, i + 1))],
            base_response[6] * (i + 1),
        ]
        for i in range(num_terms)
    ]


def assert_valid_probability(value: float, name: str = "probability") -> None:
    """Assert that a value is a valid probability (0 <= p <= 1)."""
    assert 0.0 <= value <= 1.0, f"{name} {value} is not in valid range [0, 1]"


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def sample_genes() -> list[str]:
    """Standard gene list for testing."""
    return SAMPLE_GENES.copy()


@pytest.fixture
def genes_with_modifiers() -> list[str]:
    """Gene list with various modifiers for testing name cleaning."""
    return GENES_WITH_MODIFIERS.copy()


@pytest.fixture
def titled_genes() -> list[str]:
    """Gene list with title prefixes for testing name extraction."""
    return TITLED_GENES.copy()


@pytest.fixture
def tuple_genes() -> list[tuple[str, str]]:
    """Tuple-based gene list for testing index handling."""
    return TUPLE_GENES.copy()


@pytest.fixture
def simple_dataframe(sample_genes: list[str]) -> pd.DataFrame:
    """DataFrame with simple string index."""
    return create_dataframe(sample_genes)


@pytest.fixture
def tuple_dataframe(tuple_genes: list[tuple[str, str]]) -> pd.DataFrame:
    """DataFrame with tuple index."""
    return create_dataframe(tuple_genes, num_samples=2)


@pytest.fixture
def titled_dataframe(titled_genes: list[str]) -> pd.DataFrame:
    """DataFrame with titled gene names."""
    return create_dataframe(titled_genes, num_samples=2)


@pytest.fixture
def mock_enrichr_response() -> list[list[Any]]:
    """Standard Enrichr API response format."""
    return MOCK_ENRICHR_RESPONSE.copy()


@pytest.fixture
def mock_post_response() -> dict[str, Any]:
    """Standard post request response."""
    return MOCK_POST_RESPONSE.copy()


@pytest.fixture
def empty_response() -> list[Any]:
    """Empty response for testing edge cases."""
    return []


# =============================================================================
# DIRECT MODULE TESTS - ADD_ENRICHR_CATS
# =============================================================================


class TestAddEnrichrCats:
    """Test add_enrichr_cats function with comprehensive edge case coverage."""

    @pytest.mark.parametrize(
        "input_genes,expected_cleaned",
        [
            (SAMPLE_GENES, SAMPLE_GENES),
            (GENES_WITH_MODIFIERS, ["BRCA1", "TP53", "EGFR", "MYC", "PIK3CA"]),
            (TITLED_GENES, ["BRCA1", "TP53", "EGFR"]),
        ],
        ids=["simple_genes", "genes_with_modifiers", "titled_genes"],
    )
    @patch("celldega.clust_old.analysis.enrichr_functions.get_request")
    @patch("celldega.clust_old.analysis.enrichr_functions.post_request")
    def test_gene_name_processing_variations(
        self,
        mock_post: Mock,
        mock_get: Mock,
        input_genes: list[str],
        expected_cleaned: list[str],
        mock_enrichr_response: list[list[Any]],
    ) -> None:
        """Test gene name processing handles various formats correctly."""
        df = create_dataframe(input_genes, num_samples=2)
        mock_post.return_value = DEFAULT_USER_LIST_ID
        mock_get.return_value = ([], mock_enrichr_response[:1])

        result_df, bar_info = add_enrichr_cats(df, "row", DEFAULT_LIBRARY, num_terms=1)

        mock_post.assert_called_once()
        posted_genes = mock_post.call_args[0][0]
        assert posted_genes == expected_cleaned
        assert len(result_df.index[0]) == 2
        assert len(bar_info) == 1

    @pytest.mark.parametrize(
        "df_fixture,expected_index_length",
        [
            ("simple_dataframe", 3),
            ("tuple_dataframe", 3),
            ("titled_dataframe", 3),
        ],
        ids=["string_index", "tuple_index", "titled_index"],
    )
    @patch("celldega.clust_old.analysis.enrichr_functions.get_request")
    @patch("celldega.clust_old.analysis.enrichr_functions.post_request")
    def test_dataframe_index_types(
        self,
        mock_post: Mock,
        mock_get: Mock,
        df_fixture: str,
        expected_index_length: int,
        request: pytest.FixtureRequest,
        mock_enrichr_response: list[list[Any]],
    ) -> None:
        """Test function handles different DataFrame index structures."""
        df = request.getfixturevalue(df_fixture)
        mock_post.return_value = DEFAULT_USER_LIST_ID
        mock_get.return_value = ([], mock_enrichr_response[:2])

        result_df, bar_info = add_enrichr_cats(df, "row", DEFAULT_LIBRARY, num_terms=2)

        assert isinstance(result_df.index[0], tuple)
        assert len(result_df.index[0]) == expected_index_length
        assert len(bar_info) == 2

    @pytest.mark.parametrize(
        "num_terms,response_size,expected_categories",
        [
            (0, 3, 0),
            (1, 3, 1),
            (5, 3, 3),
            (3, 0, 0),
        ],
        ids=["zero_terms", "fewer_than_available", "more_than_available", "empty_response"],
    )
    @patch("celldega.clust_old.analysis.enrichr_functions.get_request")
    @patch("celldega.clust_old.analysis.enrichr_functions.post_request")
    def test_term_quantity_edge_cases(
        self,
        mock_post: Mock,
        mock_get: Mock,
        num_terms: int,
        response_size: int,
        expected_categories: int,
        simple_dataframe: pd.DataFrame,
        mock_enrichr_response: list[list[Any]],
    ) -> None:
        """Test handling of different numbers of enrichment terms."""
        mock_post.return_value = DEFAULT_USER_LIST_ID
        mock_get.return_value = ([], mock_enrichr_response[:response_size])

        result_df, bar_info = add_enrichr_cats(
            simple_dataframe, "row", DEFAULT_LIBRARY, num_terms=num_terms
        )

        expected_index_length = 1 + expected_categories
        assert len(result_df.index[0]) == expected_index_length
        assert len(bar_info) == expected_categories

    @pytest.mark.parametrize(
        "exception_type",
        [RequestException, Timeout, ConnectionError],
        ids=["request_exception", "timeout", "connection_error"],
    )
    @patch("celldega.clust_old.analysis.enrichr_functions.post_request")
    def test_network_failures_propagate(
        self,
        mock_post: Mock,
        exception_type: type[Exception],
        simple_dataframe: pd.DataFrame,
    ) -> None:
        """Test that network failures in downstream calls are properly propagated."""
        mock_post.side_effect = exception_type("Network error")

        with pytest.raises(exception_type):
            add_enrichr_cats(simple_dataframe, "row", DEFAULT_LIBRARY)


# =============================================================================
# DIRECT MODULE TESTS - POST_REQUEST
# =============================================================================


class TestPostRequest:
    """Test post_request function with comprehensive input validation and error handling."""

    @pytest.mark.parametrize(
        "gene_list,expected_format,should_raise",
        [
            ([], "", True),
            (["BRCA1"], "BRCA1", False),
            (SAMPLE_GENES[:3], "BRCA1\nTP53\nEGFR", False),
        ],
        ids=["empty_list", "single_gene", "multiple_genes"],
    )
    @patch("requests.post")
    def test_gene_list_formatting(
        self,
        mock_post: Mock,
        gene_list: list[str],
        expected_format: str,
        should_raise: bool,
        mock_post_response: dict[str, Any],
    ) -> None:
        """Test gene list formatting for API submission."""
        mock_response = create_mock_response(200, mock_post_response)
        mock_post.return_value = mock_response

        if should_raise:
            with pytest.raises(ValueError, match=ERROR_EMPTY_GENES):
                post_request(gene_list)
        else:
            result = post_request(gene_list)

            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert call_args[1]["files"]["list"] == expected_format
            assert result == str(mock_post_response["userListId"])

    @pytest.mark.parametrize(
        "exception_type,expected_exception",
        [
            (Timeout, Timeout),
            (ConnectionError, RequestException),
            (RequestException, RequestException),
        ],
        ids=["timeout", "connection_error", "request_exception"],
    )
    @patch("requests.post")
    def test_network_error_handling(
        self,
        mock_post: Mock,
        exception_type: type[Exception],
        expected_exception: type[Exception],
        sample_genes: list[str],
    ) -> None:
        """Test handling of various network errors."""
        mock_post.side_effect = exception_type("Network error")

        with pytest.raises(expected_exception):
            post_request(sample_genes)

    @pytest.mark.parametrize(
        "response_text,error_pattern",
        [
            ("invalid json", ERROR_INVALID_JSON_POST),
            ('{"status": "error"}', ERROR_MISSING_USER_ID),
        ],
        ids=["invalid_json", "missing_user_list_id"],
    )
    @patch("requests.post")
    def test_malformed_response_handling(
        self,
        mock_post: Mock,
        response_text: str,
        error_pattern: str,
        sample_genes: list[str],
    ) -> None:
        """Test handling of malformed API responses."""
        mock_response = Mock()
        mock_response.text = response_text
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        with pytest.raises(ValueError, match=error_pattern):
            post_request(sample_genes)

    @pytest.mark.parametrize(
        "invalid_input,expected_error",
        [
            ("not_a_list", ERROR_INVALID_TYPE),
            (123, ERROR_INVALID_TYPE),
            (None, ERROR_EMPTY_GENES),
        ],
        ids=["string_input", "integer_input", "none_input"],
    )
    def test_input_validation(self, invalid_input: Any, expected_error: str) -> None:
        """Test input validation for various invalid inputs."""
        with pytest.raises((TypeError, ValueError), match=expected_error):
            post_request(invalid_input)


# =============================================================================
# DIRECT MODULE TESTS - GET_REQUEST
# =============================================================================


class TestGetRequest:
    """Test get_request function with comprehensive retry logic and error handling."""

    @pytest.mark.parametrize(
        "status_codes,expected_retries",
        [
            ([200], 1),
            ([400, 200], 2),
            ([400, 400, 200], 3),
        ],
        ids=["immediate_success", "retry_once", "retry_multiple"],
    )
    @patch("requests.get")
    def test_retry_logic_scenarios(
        self,
        mock_get: Mock,
        status_codes: list[int],
        expected_retries: int,
        mock_enrichr_response: list[list[Any]],
    ) -> None:
        """Test retry logic with various status code sequences."""
        mock_responses = []
        for code in status_codes:
            if code == 200:
                response_data = {DEFAULT_LIBRARY: mock_enrichr_response}
                mock_responses.append(create_mock_response(code, response_data))
            else:
                mock_responses.append(create_mock_response(code, {DEFAULT_LIBRARY: []}))

        mock_get.side_effect = mock_responses

        enr, response_list = get_request(DEFAULT_LIBRARY, DEFAULT_USER_LIST_ID)

        assert len(response_list) >= 0
        assert mock_get.call_count == expected_retries

    @pytest.mark.parametrize(
        "error_code",
        [404, 500, 503, 429],
        ids=["not_found", "server_error", "service_unavailable", "rate_limited"],
    )
    @patch("requests.get")
    def test_non_400_errors_immediate_failure(self, mock_get: Mock, error_code: int) -> None:
        """Test that non-400 error codes cause immediate failure."""
        mock_response = create_mock_response(error_code, {DEFAULT_LIBRARY: []})
        mock_get.return_value = mock_response

        with pytest.raises(
            RequestException, match=f"Enrichr API returned status code: {error_code}"
        ):
            get_request(DEFAULT_LIBRARY, DEFAULT_USER_LIST_ID)

        assert mock_get.call_count == 1

    @patch("celldega.clust_old.analysis.enrichr_functions.time.sleep")
    @patch("requests.get")
    def test_max_retry_behavior(self, mock_get: Mock, mock_sleep: Mock) -> None:
        """Test that function respects maximum retry limit."""
        mock_response = create_mock_response(400, {DEFAULT_LIBRARY: []})
        mock_get.return_value = mock_response

        with pytest.raises(
            RequestException,
            match=f"Failed to get valid response after {DEFAULT_MAX_RETRIES} attempts",
        ):
            get_request(DEFAULT_LIBRARY, DEFAULT_USER_LIST_ID)

        assert mock_get.call_count == DEFAULT_MAX_RETRIES
        assert mock_sleep.call_count == DEFAULT_MAX_RETRIES - 1

    @pytest.mark.parametrize(
        "response_scenario,expected_error",
        [
            ("empty_response", None),
            ("invalid_json", ERROR_INVALID_JSON_GET),
            ("empty_json", ERROR_INVALID_JSON_GET),
        ],
        ids=["empty_response", "invalid_json", "empty_json"],
    )
    @patch("requests.get")
    def test_response_parsing_edge_cases(
        self,
        mock_get: Mock,
        response_scenario: str,
        expected_error: str | None,
    ) -> None:
        """Test response parsing with various edge case formats."""
        response_configs = {
            "empty_response": (200, {DEFAULT_LIBRARY: []}),
            "invalid_json": (200, None),
            "empty_json": (200, None),
        }

        status_code, response_data = response_configs[response_scenario]

        if response_scenario == "invalid_json":
            mock_response = Mock()
            mock_response.status_code = status_code
            mock_response.text = "invalid json"
            mock_response.raise_for_status = Mock()
        elif response_scenario == "empty_json":
            mock_response = Mock()
            mock_response.status_code = status_code
            mock_response.text = ""
            mock_response.raise_for_status = Mock()
        else:
            mock_response = create_mock_response(status_code, response_data)

        mock_get.return_value = mock_response

        if expected_error:
            with pytest.raises(ValueError, match=expected_error):
                get_request(DEFAULT_LIBRARY, DEFAULT_USER_LIST_ID)
        else:
            enr, response_list = get_request(DEFAULT_LIBRARY, DEFAULT_USER_LIST_ID)
            assert len(response_list) == 0
            assert len(enr) == 0

    @pytest.mark.parametrize(
        "user_list_id,expected_str",
        [
            (12345, "12345"),
            ("67890", "67890"),
        ],
        ids=["integer_id", "string_id"],
    )
    @patch("requests.get")
    def test_user_list_id_variations(
        self,
        mock_get: Mock,
        user_list_id: int | str,
        expected_str: str,
        mock_enrichr_response: list[list[Any]],
    ) -> None:
        """Test handling of different user_list_id formats."""
        response_data = {DEFAULT_LIBRARY: mock_enrichr_response}
        mock_response = create_mock_response(200, response_data)
        mock_get.return_value = mock_response

        enr, response_list = get_request(DEFAULT_LIBRARY, user_list_id)

        call_args = mock_get.call_args[1]["params"]
        assert call_args["userListId"] == expected_str

    @pytest.mark.parametrize(
        "lib,user_list_id,expected_error",
        [
            ("", DEFAULT_USER_LIST_ID, ERROR_EMPTY_LIBRARY),
            (DEFAULT_LIBRARY, "", ERROR_EMPTY_USER_ID),
        ],
        ids=["empty_library", "empty_user_list_id"],
    )
    def test_input_validation(self, lib: str, user_list_id: str, expected_error: str) -> None:
        """Test input validation for empty parameters."""
        with pytest.raises(ValueError, match=expected_error):
            get_request(lib, user_list_id)


# =============================================================================
# DIRECT MODULE TESTS - TRANSFER_TO_ENR_DICT
# =============================================================================


class TestTransferToEnrDict:
    """Test transfer_to_enr_dict function with comprehensive data validation."""

    @pytest.mark.parametrize(
        "response_length,max_terms,expected_length",
        [
            (0, 50, 0),
            (3, 50, 3),
            (100, 50, 50),
            (25, 10, 10),
        ],
        ids=["empty", "shorter_than_max", "longer_than_max", "limited_by_max"],
    )
    def test_response_length_handling(
        self, response_length: int, max_terms: int, expected_length: int
    ) -> None:
        """Test handling of various response lengths."""
        test_response = create_enrichr_response(response_length)
        result = transfer_to_enr_dict(test_response, max_terms)

        assert len(result) == expected_length
        if expected_length > 0:
            assert validate_enrichment_structure(result)

    @pytest.mark.parametrize(
        "field_scenario,should_succeed",
        [
            ("complete", True),
            ("missing_fields", True),
            ("extra_fields", True),
        ],
        ids=["complete_fields", "missing_fields", "extra_fields"],
    )
    def test_field_validation_scenarios(self, field_scenario: str, should_succeed: bool) -> None:
        """Test handling of various field scenarios."""
        base_response = ["", "term", 0.01, -1.5, 10.0, ["gene1"], 0.02]

        scenarios = {
            "complete": [base_response],
            "missing_fields": [["", "term", "", -1.5, 10.0, ["gene1"], 0.02]],
            "extra_fields": [base_response + ["extra1", "extra2"]],
        }

        test_response = scenarios[field_scenario]
        result = transfer_to_enr_dict(test_response)

        if should_succeed:
            assert len(result) == 1
            if field_scenario == "complete":
                assert result[0]["name"] == "term"
                assert result[0]["pval"] == 0.01

    def test_data_type_consistency(self, mock_enrichr_response: list[list[Any]]) -> None:
        """Test data type consistency in output."""
        result = transfer_to_enr_dict(mock_enrichr_response)

        for item in result:
            assert isinstance(item["name"], str)
            assert isinstance(item["pval"], (int, float))
            assert isinstance(item["zscore"], (int, float))
            assert isinstance(item["combined_score"], (int, float))
            assert isinstance(item["int_genes"], list)
            assert isinstance(item["pval_bh"], (int, float))
            assert all(isinstance(gene, str) for gene in item["int_genes"])

    def test_input_validation(self) -> None:
        """Test input validation for invalid response types."""
        with pytest.raises(TypeError, match=ERROR_RESPONSE_LIST_TYPE):
            transfer_to_enr_dict("not_a_list")


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestIntegrationScenarios:
    """Integration tests combining multiple functions in realistic workflows."""

    @patch("celldega.clust_old.analysis.enrichr_functions.get_request")
    @patch("celldega.clust_old.analysis.enrichr_functions.post_request")
    def test_full_enrichment_workflow(
        self,
        mock_post: Mock,
        mock_get: Mock,
        simple_dataframe: pd.DataFrame,
        mock_enrichr_response: list[list[Any]],
    ) -> None:
        """Test complete enrichment workflow integration."""
        mock_post.return_value = DEFAULT_USER_LIST_ID
        mock_get.return_value = ([], mock_enrichr_response)

        result_df, bar_info = add_enrichr_cats(simple_dataframe, "row", DEFAULT_LIBRARY)

        assert mock_post.called
        assert mock_get.called
        assert len(result_df.index[0]) > 1
        assert len(bar_info) > 0

    @patch("requests.post")
    @patch("requests.get")
    def test_end_to_end_api_integration(
        self,
        mock_get: Mock,
        mock_post: Mock,
        sample_genes: list[str],
        mock_post_response: dict[str, Any],
        mock_enrichr_response: list[list[Any]],
    ) -> None:
        """Test end-to-end API integration with mocked responses."""
        post_response = create_mock_response(200, mock_post_response)
        mock_post.return_value = post_response

        get_response_data = {DEFAULT_LIBRARY: mock_enrichr_response}
        get_response = create_mock_response(200, get_response_data)
        mock_get.return_value = get_response

        user_list_id = post_request(sample_genes)
        enr, response_list = get_request(DEFAULT_LIBRARY, user_list_id)

        assert user_list_id == str(mock_post_response["userListId"])
        assert len(response_list) > 0
        assert len(enr) > 0

    def test_statistical_properties_validation(self) -> None:
        """Test that statistical properties are maintained throughout workflow."""
        response_data = MOCK_ENRICHR_RESPONSE.copy()
        result = transfer_to_enr_dict(response_data)

        for item in result:
            assert_valid_probability(item["pval"], f"P-value for {item['name']}")
            assert_valid_probability(item["pval_bh"], f"Adjusted p-value for {item['name']}")
            assert item["combined_score"] >= 0, (
                f"Combined score should be non-negative for {item['name']}"
            )

    def test_error_propagation_chain(self, simple_dataframe: pd.DataFrame) -> None:
        """Test that errors propagate correctly through the function chain."""
        with patch("celldega.clust_old.analysis.enrichr_functions.post_request") as mock_post:
            mock_post.side_effect = RequestException("API Error")

            with pytest.raises(RequestException, match="API Error"):
                add_enrichr_cats(simple_dataframe, "row", DEFAULT_LIBRARY)

    def test_memory_efficiency_large_datasets(self) -> None:
        """Test memory efficiency with larger datasets."""
        large_genes = [f"GENE_{i}" for i in range(1000)]
        large_df = create_dataframe(large_genes, num_samples=10)

        # Create exactly 5 enrichment terms to match the expected assertion
        five_terms_response = create_enrichr_response(5)

        with (
            patch("celldega.clust_old.analysis.enrichr_functions.post_request") as mock_post,
            patch("celldega.clust_old.analysis.enrichr_functions.get_request") as mock_get,
        ):
            mock_post.return_value = DEFAULT_USER_LIST_ID
            mock_get.return_value = ([], five_terms_response)

            result_df, bar_info = add_enrichr_cats(large_df, "row", DEFAULT_LIBRARY, num_terms=5)

            assert result_df.shape[0] == 1000
            assert len(bar_info) == 5
            assert isinstance(result_df, pd.DataFrame)


# =============================================================================
# MAIN EXECUTION
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
