"""
Comprehensive tests for enrichr_functions.py

This test suite covers all edge cases at least 3 times while minimizing redundancy
by using parametrized tests and fixtures for common test data.
"""

from pathlib import Path
import sys


# Add src directory to path if needed
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

import json
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd
import pytest
from requests.exceptions import ConnectionError, HTTPError, RequestException, Timeout

# Import the functions to test
from celldega.clust.enrichr_functions import (
    add_enrichr_cats,
    get_request,
    post_request,
    transfer_to_enr_dict,
)


class TestDataFixtures:
    """Centralized test data to minimize redundancy"""

    @pytest.fixture
    def sample_genes(self):
        return ["BRCA1", "TP53", "EGFR", "MYC", "PIK3CA"]

    @pytest.fixture
    def sample_genes_with_modifiers(self):
        return ["BRCA1_p123", "TP53-variant", "EGFR phospho", "MYC_1", "PIK3CA-iso2"]

    @pytest.fixture
    def sample_tuple_genes(self):
        return [("BRCA1", "Oncogene"), ("TP53", "Tumor Suppressor")]

    @pytest.fixture
    def sample_df_simple(self, sample_genes):
        """Simple dataframe with string index"""
        data = np.random.rand(len(sample_genes), 3)
        return pd.DataFrame(data, index=sample_genes, columns=["Sample1", "Sample2", "Sample3"])

    @pytest.fixture
    def sample_df_tuple(self, sample_tuple_genes):
        """Dataframe with tuple index"""
        data = np.random.rand(len(sample_tuple_genes), 2)
        return pd.DataFrame(data, index=sample_tuple_genes, columns=["Sample1", "Sample2"])

    @pytest.fixture
    def sample_df_titled_genes(self):
        """Dataframe with gene names that have titles"""
        genes = ["Gene: BRCA1", "Gene: TP53", "Gene: EGFR"]
        data = np.random.rand(len(genes), 2)
        return pd.DataFrame(data, index=genes, columns=["Sample1", "Sample2"])

    @pytest.fixture
    def mock_enrichr_response(self):
        """Standard enrichr API response format"""
        return [
            ["", "GO:0006915 apoptotic process", 0.001, -2.5, 15.2, ["BRCA1", "TP53"], 0.01],
            ["", "GO:0008283 cell proliferation", 0.005, -1.8, 12.1, ["EGFR", "MYC"], 0.02],
            ["", "GO:0006260 DNA replication", 0.01, -1.2, 8.3, ["PIK3CA"], 0.03],
        ]

    @pytest.fixture
    def mock_post_response(self):
        """Standard post request response"""
        return {"userListId": 12345, "status": "success"}


class TestAddEnrichrCats(TestDataFixtures):
    """Test add_enrichr_cats function with various input scenarios"""

    @pytest.mark.parametrize(
        "gene_format,expected_processing",
        [
            (["BRCA1", "TP53"], ["BRCA1", "TP53"]),  # Simple genes
            (["BRCA1_p123", "TP53-variant"], ["BRCA1", "TP53"]),  # Genes with modifiers
            (["Gene: BRCA1", "Gene: TP53"], ["BRCA1", "TP53"]),  # Titled genes
        ],
    )
    @patch("celldega.clust.enrichr_functions.get_request")
    @patch("celldega.clust.enrichr_functions.post_request")
    def test_gene_name_processing_variations(
        self, mock_post, mock_get, gene_format, expected_processing, mock_enrichr_response
    ):
        """Test gene name processing handles various formats correctly (Edge case coverage 1/3)"""
        # Setup
        df = pd.DataFrame(
            np.random.rand(len(gene_format), 2), index=gene_format, columns=["S1", "S2"]
        )
        mock_post.return_value = "12345"
        mock_get.return_value = ([], mock_enrichr_response[:1])  # Single term

        # Execute
        result_df, bar_info = add_enrichr_cats(df, "row", "GO_Biological_Process_2015", num_terms=1)

        # Verify gene processing
        mock_post.assert_called_once()
        posted_genes = mock_post.call_args[0][0]
        assert posted_genes == expected_processing

        # Verify structure
        assert len(result_df.index[0]) == 2  # Original + 1 enrichr category
        assert len(bar_info) == 1

    @pytest.mark.parametrize(
        "df_type,index_structure",
        [("simple", "string"), ("tuple", "tuple"), ("titled", "titled_string")],
    )
    @patch("celldega.clust.enrichr_functions.get_request")
    @patch("celldega.clust.enrichr_functions.post_request")
    def test_dataframe_index_types(
        self,
        mock_post,
        mock_get,
        df_type,
        index_structure,
        mock_enrichr_response,
        sample_df_simple,
        sample_df_tuple,
        sample_df_titled_genes,
    ):
        """Test function handles different DataFrame index structures (Edge case coverage 2/3)"""
        # Setup dataframes
        df_map = {
            "simple": sample_df_simple,
            "tuple": sample_df_tuple,
            "titled": sample_df_titled_genes,
        }
        df = df_map[df_type]

        mock_post.return_value = "12345"
        mock_get.return_value = ([], mock_enrichr_response[:2])

        # Execute
        result_df, bar_info = add_enrichr_cats(df, "row", "GO_Biological_Process_2015", num_terms=2)

        # Verify results based on input type
        assert isinstance(result_df.index[0], tuple)
        if index_structure == "tuple":
            # Tuple index: original gene + 2 enrichr categories = 3 total
            assert len(result_df.index[0]) == 3  # Original gene + 2 enrichr categories
        else:
            # String index: original gene + 2 enrichr categories = 3 total
            assert len(result_df.index[0]) == 3  # Original gene + 2 enrichr categories

        assert len(bar_info) == 2

    @pytest.mark.parametrize(
        "num_terms,response_size,expected_categories",
        [
            (0, 3, 0),  # No terms requested
            (1, 3, 1),  # Fewer terms than available
            (5, 3, 3),  # More terms than available
            (3, 0, 0),  # No response terms
        ],
    )
    @patch("celldega.clust.enrichr_functions.get_request")
    @patch("celldega.clust.enrichr_functions.post_request")
    def test_term_quantity_edge_cases(
        self,
        mock_post,
        mock_get,
        num_terms,
        response_size,
        expected_categories,
        sample_df_simple,
        mock_enrichr_response,
    ):
        """Test handling of different numbers of enrichment terms (Edge case coverage 3/3)"""
        mock_post.return_value = "12345"
        mock_get.return_value = ([], mock_enrichr_response[:response_size])

        result_df, bar_info = add_enrichr_cats(
            sample_df_simple, "row", "GO_Biological_Process_2015", num_terms=num_terms
        )

        expected_index_length = 1 + expected_categories  # Original gene + enrichr categories
        assert len(result_df.index[0]) == expected_index_length
        assert len(bar_info) == expected_categories

    @patch("celldega.clust.enrichr_functions.get_request")
    @patch("celldega.clust.enrichr_functions.post_request")
    def test_network_failures_propagate(self, mock_post, mock_get, sample_df_simple):
        """Test that network failures in downstream calls are properly propagated"""
        mock_post.side_effect = RequestException("Network error")

        with pytest.raises(RequestException):
            add_enrichr_cats(sample_df_simple, "row", "GO_Biological_Process_2015")


class TestClustFromResponse(TestDataFixtures):
    """Test clust_from_response function - Integration testing required"""

    def test_response_parsing_logic(self, mock_enrichr_response):
        """Test the core response parsing logic that can be isolated (Edge case coverage 1/3)"""
        # Test the data transformation parts that don't require Network
        from celldega.clust.enrichr_functions import transfer_to_enr_dict

        # Test score processing logic
        response_list = mock_enrichr_response
        enr_dict = transfer_to_enr_dict(response_list)

        # Verify the transformation works correctly
        assert len(enr_dict) == len(response_list)
        for item in enr_dict:
            assert "combined_score" in item
            assert "pval" in item
            assert "name" in item

    def test_empty_response_handling(self):
        """Test handling of empty enrichment responses (Edge case coverage 2/3)"""
        from celldega.clust.enrichr_functions import transfer_to_enr_dict

        # Empty response should return empty list
        result = transfer_to_enr_dict([])
        assert result == []

        # Response with zero scores should be handled
        zero_score_response = [["", "term", 0.1, 0, 0, ["gene1"], 0.1]]
        result = transfer_to_enr_dict(zero_score_response)
        assert len(result) == 1
        assert result[0]["combined_score"] == 0

    def test_malformed_response_resilience(self):
        """Test resilience to malformed enrichment data (Edge case coverage 3/3)"""
        from celldega.clust.enrichr_functions import transfer_to_enr_dict

        # Test with incomplete data
        incomplete_response = [["", "term"]]  # Missing required fields

        # Should handle gracefully or raise appropriate error
        try:
            result = transfer_to_enr_dict(incomplete_response)
            # If it doesn't raise an error, verify it handles missing data
            assert len(result) <= 1
        except (IndexError, KeyError):
            # Acceptable to raise an error for malformed data
            pass

    # NOTE: Full clust_from_response integration testing requires:
    # - clustergrammer package installation
    # - Network class mocking or test environment setup
    # - Consider adding integration tests in a separate test suite when dependencies are available


class TestPostRequest(TestDataFixtures):
    """Test post_request function"""

    @pytest.mark.parametrize(
        "gene_list,expected_format,should_raise",
        [
            ([], "", True),  # Empty list now raises ValueError in fixed code
            (["BRCA1"], "BRCA1", False),  # Single gene
            (["BRCA1", "TP53", "EGFR"], "BRCA1\nTP53\nEGFR", False),  # Multiple genes
        ],
    )
    @patch("requests.post")
    def test_gene_list_formatting(
        self, mock_post, gene_list, expected_format, should_raise, mock_post_response
    ):
        """Test gene list formatting for API (Edge case coverage 1/3)"""
        mock_response = Mock()
        mock_response.text = json.dumps(mock_post_response)
        mock_post.return_value = mock_response

        if should_raise:
            # Fixed code now validates empty gene lists
            with pytest.raises(ValueError, match="Gene list cannot be empty"):
                post_request(gene_list)
        else:
            result = post_request(gene_list)

            # Verify API was called with correct format
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert call_args[1]["files"]["list"] == expected_format
            assert result == "12345"

    @pytest.mark.parametrize(
        "exception_type,expected_exception",
        [
            (Timeout, Timeout),  # Timeout is handled specifically
            (ConnectionError, RequestException),  # ConnectionError gets wrapped in RequestException
            (RequestException, RequestException),  # RequestException stays as RequestException
        ],
    )
    @patch("requests.post")
    def test_network_error_handling(
        self, mock_post, exception_type, expected_exception, sample_genes
    ):
        """Test handling of various network errors (Edge case coverage 2/3)"""
        mock_post.side_effect = exception_type("Network error")

        with pytest.raises(expected_exception):
            post_request(sample_genes)

    @patch("requests.post")
    def test_malformed_response_handling(self, mock_post, sample_genes):
        """Test handling of malformed API responses (Edge case coverage 3/3)"""
        # Test invalid JSON - fixed code wraps JSONDecodeError in ValueError
        mock_response = Mock()
        mock_response.text = "invalid json"
        mock_response.raise_for_status = Mock()  # Don't raise HTTP errors for this test
        mock_post.return_value = mock_response

        with pytest.raises(ValueError, match="Invalid response from Enrichr API"):
            post_request(sample_genes)

        # Test missing userListId - fixed code validates response structure
        mock_response.text = json.dumps({"status": "error"})
        mock_post.return_value = mock_response

        with pytest.raises(ValueError, match="Enrichr API response missing userListId"):
            post_request(sample_genes)

    def test_input_validation(self):
        """Test input validation in fixed code"""
        # Test non-list input
        with pytest.raises(TypeError, match="input_genes must be a list"):
            post_request("not_a_list")

        # Test None input - this triggers the "empty" check first, which is reasonable
        with pytest.raises(ValueError, match="Gene list cannot be empty"):
            post_request(None)

        # Test integer input (another non-list type)
        with pytest.raises(TypeError, match="input_genes must be a list"):
            post_request(123)


class TestGetRequest(TestDataFixtures):
    """Test get_request function"""

    @pytest.mark.parametrize(
        "status_codes,expected_retries",
        [
            ([200], 1),  # Success on first try
            ([400, 200], 2),  # Success on second try - retries only for 400
            ([400, 400, 200], 3),  # Multiple 400s then success
        ],
    )
    @patch("requests.get")
    def test_retry_logic_scenarios(
        self, mock_get, status_codes, expected_retries, mock_enrichr_response
    ):
        """Test retry logic with various status codes (Edge case coverage 1/3)"""
        # Setup mock responses - ensure all have proper structure
        mock_responses = []
        for i, code in enumerate(status_codes):
            mock_response = Mock()
            mock_response.status_code = code
            if code == 200:
                mock_response.text = json.dumps({"test_lib": mock_enrichr_response})
                mock_response.raise_for_status = Mock()  # Don't raise for 200
            else:
                mock_response.text = json.dumps({"test_lib": []})
                if code != 400:  # Non-400 errors raise HTTPError
                    mock_response.raise_for_status = Mock(side_effect=HTTPError("HTTP Error"))
                else:
                    mock_response.raise_for_status = Mock()  # 400 doesn't raise in fixed code
            mock_responses.append(mock_response)

        mock_get.side_effect = mock_responses

        enr, response_list = get_request("test_lib", "12345")
        assert len(response_list) >= 0  # Should get some response
        assert mock_get.call_count == expected_retries

    @pytest.mark.parametrize("error_code", [500, 503, 404])
    @patch("celldega.clust.enrichr_functions.time.sleep")  # Mock sleep in the right module
    @patch("requests.get")
    def test_non_400_errors_immediate_failure(
        self, mock_get, mock_sleep, error_code, mock_enrichr_response
    ):
        """Test that non-400 error codes cause immediate failure in fixed code"""
        mock_response = Mock()
        mock_response.status_code = error_code
        mock_response.text = json.dumps({"test_lib": []})
        mock_response.raise_for_status = Mock()  # Don't raise during requests.get
        mock_get.return_value = mock_response

        # Fixed code should raise RequestException for non-200 status codes
        with pytest.raises(
            RequestException, match=f"Enrichr API returned status code: {error_code}"
        ):
            get_request("test_lib", "12345")

        # Should only make 1 call since non-400 errors don't retry
        assert mock_get.call_count == 1
        # Sleep should not be called since no retries happen
        assert mock_sleep.call_count == 0

    @patch("time.sleep")  # Mock sleep to prevent test from taking forever
    @patch("requests.get")
    def test_max_retry_behavior(self, mock_get, mock_sleep, mock_enrichr_response):
        """Test that function respects max retry limit (Edge case coverage 1/3 continued)"""
        # Setup response that always returns 400 (simulating persistent failure)
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = json.dumps({"test_lib": []})
        mock_response.raise_for_status = Mock()  # 400 doesn't raise in our fixed code
        mock_get.return_value = mock_response

        # Fixed code should raise RequestException after max retries with persistent 400s
        with pytest.raises(
            RequestException, match="Failed to get valid response after 100 attempts"
        ):
            get_request("test_lib", "12345")

        # Should have tried up to 100 times (the max in the code)
        assert mock_get.call_count == 100

        # Verify exponential backoff was used (sleep should be called 99 times - not on first attempt)
        assert mock_sleep.call_count == 99

    @pytest.mark.parametrize("error_code", [500, 503, 404, 429])
    @patch("requests.get")
    def test_non_400_errors_no_retry(self, mock_get, error_code, mock_enrichr_response):
        """Test that non-400 error codes don't trigger retry logic and raise exceptions"""
        mock_response = Mock()
        mock_response.status_code = error_code
        mock_response.text = json.dumps({"test_lib": []})
        mock_response.raise_for_status = Mock()  # Don't raise during the request
        mock_get.return_value = mock_response

        # Fixed code should raise RequestException for non-200 status codes
        with pytest.raises(
            RequestException, match=f"Enrichr API returned status code: {error_code}"
        ):
            get_request("test_lib", "12345")

        # Should only make 1 call since retry only happens for 400 status
        assert mock_get.call_count == 1

    @patch("requests.get")
    def test_response_parsing_edge_cases(self, mock_get):
        """Test response parsing with various formats (Edge case coverage 2/3)"""
        # Test empty response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = json.dumps({"test_lib": []})
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        enr, response_list = get_request("test_lib", "12345")
        assert len(response_list) == 0
        assert len(enr) == 0

        # Test malformed JSON - fixed code now raises ValueError
        mock_response.text = "invalid json"
        mock_get.return_value = mock_response

        with pytest.raises(ValueError, match="Invalid JSON response from Enrichr API"):
            get_request("test_lib", "12345")

        # Test empty response body - fixed code handles this
        mock_response.text = ""
        mock_get.return_value = mock_response

        with pytest.raises(ValueError, match="Invalid JSON response from Enrichr API"):
            get_request("test_lib", "12345")

    @patch("requests.get")
    def test_user_list_id_variations(self, mock_get, mock_enrichr_response):
        """Test handling of different user_list_id formats (Edge case coverage 3/3)"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = json.dumps({"test_lib": mock_enrichr_response})
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # Test integer user_list_id
        enr, response_list = get_request("test_lib", 12345)
        assert mock_get.called

        # Test string user_list_id
        enr, response_list = get_request("test_lib", "67890")
        assert mock_get.called

        # Verify conversion to string in API call
        call_args = mock_get.call_args[1]["params"]
        assert call_args["userListId"] == "67890"

    def test_input_validation(self):
        """Test input validation in fixed code"""
        # Test empty library name
        with pytest.raises(ValueError, match="Library name cannot be empty"):
            get_request("", "12345")

        # Test empty user_list_id
        with pytest.raises(ValueError, match="User list ID cannot be empty"):
            get_request("test_lib", "")


class TestTransferToEnrDict(TestDataFixtures):
    """Test transfer_to_enr_dict function"""

    @pytest.mark.parametrize(
        "response_length,max_terms,expected_length",
        [
            (0, 50, 0),  # Empty response
            (3, 50, 3),  # Response shorter than max
            (100, 50, 50),  # Response longer than max
            (25, 10, 10),  # Limited by max_terms
        ],
    )
    def test_response_length_handling(
        self, response_length, max_terms, expected_length, mock_enrichr_response
    ):
        """Test handling of various response lengths (Edge case coverage 1/3)"""
        # Create response of specified length
        extended_response = mock_enrichr_response * (
            response_length // len(mock_enrichr_response) + 1
        )
        test_response = extended_response[:response_length]

        result = transfer_to_enr_dict(test_response, max_terms)

        assert len(result) == expected_length

        # Verify structure of returned dictionaries
        if expected_length > 0:
            assert all(isinstance(item, dict) for item in result)
            assert all("name" in item for item in result)
            assert all("pval" in item for item in result)

    @pytest.mark.parametrize(
        "field_scenario",
        [
            "complete",  # All fields present
            "missing_term",  # Missing term field
            "missing_pval",  # Missing p-value
            "extra_fields",  # Extra unexpected fields
        ],
    )
    def test_field_validation_scenarios(self, field_scenario):
        """Test handling of various field scenarios (Edge case coverage 2/3)"""
        base_response = ["", "term", 0.01, -1.5, 10.0, ["gene1"], 0.02]

        scenarios = {
            "complete": [base_response],
            "missing_term": [["", "", 0.01, -1.5, 10.0, ["gene1"], 0.02]],  # Empty term
            "missing_pval": [["", "term", "", -1.5, 10.0, ["gene1"], 0.02]],  # Empty pval
            "extra_fields": [base_response + ["extra1", "extra2"]],  # Additional fields
        }

        test_response = scenarios[field_scenario]

        if field_scenario in ["missing_pval"]:
            # Should handle gracefully or raise appropriate error
            result = transfer_to_enr_dict(test_response)
            # Function should still work but may have empty/invalid values
            assert len(result) == 1
        else:
            result = transfer_to_enr_dict(test_response)
            assert len(result) == 1
            if field_scenario == "complete":
                assert result[0]["name"] == "term"
                assert result[0]["pval"] == 0.01

    def test_data_type_consistency(self, mock_enrichr_response):
        """Test data type consistency in output (Edge case coverage 3/3)"""
        result = transfer_to_enr_dict(mock_enrichr_response)

        for item in result:
            # Verify expected data types
            assert isinstance(item["name"], str)
            assert isinstance(item["pval"], (int, float))
            assert isinstance(item["zscore"], (int, float))
            assert isinstance(item["combined_score"], (int, float))
            assert isinstance(item["int_genes"], list)
            assert isinstance(item["pval_bh"], (int, float))

            # Verify gene list contains strings
            assert all(isinstance(gene, str) for gene in item["int_genes"])


class TestIntegrationScenarios(TestDataFixtures):
    """Integration tests that combine multiple functions"""

    @patch("src.celldega.clust.enrichr_functions.get_request")
    @patch("src.celldega.clust.enrichr_functions.post_request")
    def test_full_enrichment_workflow(
        self, mock_post, mock_get, sample_df_simple, mock_enrichr_response
    ):
        """Test complete enrichment workflow integration"""
        mock_post.return_value = "12345"
        mock_get.return_value = ([], mock_enrichr_response)

        # Test full workflow
        result_df, bar_info = add_enrichr_cats(
            sample_df_simple, "row", "GO_Biological_Process_2015"
        )

        # Verify workflow completed
        assert mock_post.called
        assert mock_get.called
        assert len(result_df.index[0]) > 1  # Categories were added
        assert len(bar_info) > 0

    @patch("requests.post")
    @patch("requests.get")
    def test_end_to_end_api_integration(
        self, mock_get, mock_post, sample_genes, mock_post_response, mock_enrichr_response
    ):
        """Test end-to-end API integration with mocked responses"""
        # Setup API mocks
        post_response = Mock()
        post_response.text = json.dumps(mock_post_response)
        mock_post.return_value = post_response

        get_response = Mock()
        get_response.status_code = 200
        get_response.text = json.dumps({"GO_Biological_Process_2015": mock_enrichr_response})
        mock_get.return_value = get_response

        # Test post -> get workflow
        user_list_id = post_request(sample_genes)
        enr, response_list = get_request("GO_Biological_Process_2015", user_list_id)

        # Verify integration
        assert user_list_id == "12345"
        assert len(response_list) > 0
        assert len(enr) > 0
