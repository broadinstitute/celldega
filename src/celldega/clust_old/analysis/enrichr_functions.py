"""
Enrichment analysis functions for gene set enrichment using Enrichr API.

This module provides functionality to:
- Submit gene lists to Enrichr API
- Retrieve enrichment results
- Process enrichment data for clustering
- Add enrichment categories to dataframes
"""

from copy import deepcopy
import json
import math
import time
from typing import Any

import numpy as np
import pandas as pd
import requests
from requests.exceptions import RequestException, Timeout


def add_enrichr_cats(
    df: pd.DataFrame, inst_rc: str, run_enrichr: str, num_terms: int = 10
) -> tuple[pd.DataFrame, list[float]]:
    """
    Add Enrichr gene enrichment categories to DataFrame index.

    Args:
        df: DataFrame with genes as index
        inst_rc: Analysis axis (currently only 'row' supported)
        run_enrichr: Enrichr library name for enrichment analysis
        num_terms: Maximum number of enrichment terms to include

    Returns:
        Tuple of (modified DataFrame with enrichment categories, combined scores)
    """
    # Extract and clean gene names from DataFrame index
    gene_names = _extract_gene_names(df.index.tolist())
    original_genes = deepcopy(gene_names)
    cleaned_genes = _clean_gene_names(gene_names)

    # Submit to Enrichr and get results
    user_list_id = post_request(cleaned_genes)
    _, response_list = get_request(run_enrichr, user_list_id, max_terms=20)

    # Process enrichment results and update DataFrame
    return _process_enrichment_results(response_list[:num_terms], original_genes, df)


def _extract_gene_names(index_list: list[Any]) -> list[str]:
    """Extract gene names from DataFrame index, handling tuples."""
    if not index_list:
        return []

    if isinstance(index_list[0], tuple):
        return [item[0] for item in index_list]
    return index_list


def _clean_gene_names(gene_names: list[str]) -> list[str]:
    """Clean gene names by removing titles and modifiers."""
    if not gene_names:
        return []

    cleaned = gene_names[:]

    # Remove titles (e.g., "Gene: BRCA1" -> "BRCA1")
    if cleaned and ": " in cleaned[0]:
        cleaned = [gene.split(": ", 1)[1] for gene in cleaned]

    # Remove common modifiers (PTMs, variants, etc.)
    separators = ["_", " ", "-"]
    for i, gene in enumerate(cleaned):
        for separator in separators:
            if separator in gene:
                cleaned[i] = gene.split(separator, 1)[0]
                break

    return cleaned


def _process_enrichment_results(
    enrichment_terms: list[list[Any]], original_genes: list[str], df: pd.DataFrame
) -> tuple[pd.DataFrame, list[float]]:
    """Process enrichment results and add categories to DataFrame."""
    combined_scores = []

    # Pre-create cleaned gene lookup for O(1) access
    cleaned_gene_lookup = {gene: _clean_gene_names([gene])[0] for gene in original_genes}

    # Initialize gene categories more efficiently
    categorized_genes = [[gene] for gene in original_genes]

    for term_data in enrichment_terms:
        term_name = term_data[1]
        p_value = term_data[2]
        combined_score = term_data[4]
        enriched_genes_set = set(term_data[5])

        p_value_html = f"<p> Pval {p_value}</p>"
        combined_scores.append(combined_score)

        # Single pass through genes with O(1) enrichment lookup
        for _, gene_data in enumerate(categorized_genes):
            cleaned_gene = cleaned_gene_lookup[gene_data[0]]
            enrichment_status = "True" if cleaned_gene in enriched_genes_set else "False"
            gene_data.append(f"{term_name}: {enrichment_status}{p_value_html}")

    # Update DataFrame with new categorized index
    df.index = [tuple(gene_data) for gene_data in categorized_genes]
    return df, combined_scores


def clust_from_response(response_list: list[list[Any]]) -> Any:
    """
    Create clustering network from Enrichr response data.

    Args:
        response_list: Raw response data from Enrichr API

    Returns:
        Network object with clustering visualization data
    """
    # Local import to avoid dependency issues
    from clustergrammer import Network

    # Convert response to structured format and filter valid terms
    enrichment_data = transfer_to_enr_dict(response_list)
    valid_terms = [term for term in enrichment_data if term["combined_score"] > 0]

    if not valid_terms:
        return Network()

    # Calculate normalized scores and build network
    score_series = _calculate_enrichment_scores(valid_terms)
    return _build_clustering_network(valid_terms, score_series)


def _calculate_enrichment_scores(enrichment_terms: list[dict[str, Any]]) -> dict[str, pd.Series]:
    """Calculate and normalize enrichment scores."""
    if not enrichment_terms:
        return {
            "combined_score": pd.Series(dtype=float),
            "pval": pd.Series(dtype=float),
            "zscore": pd.Series(dtype=float),
        }

    # Extract all data at once instead of iterating multiple times
    term_names = [term["name"] for term in enrichment_terms]
    combined_scores = [term["combined_score"] for term in enrichment_terms]
    pvals = [term["pval"] for term in enrichment_terms]
    zscores = [term["zscore"] for term in enrichment_terms]

    # Create series efficiently
    scores = {
        "combined_score": pd.Series(combined_scores, index=term_names),
        "pval": pd.Series([-math.log(pval) for pval in pvals], index=term_names),
        "zscore": pd.Series([-zscore for zscore in zscores], index=term_names),
    }

    # Vectorized normalization and sorting
    for score_type, series in scores.items():
        if len(series) > 0:
            max_score = series.max()
            if max_score > 0:
                scores[score_type] = series / max_score
            scores[score_type] = scores[score_type].sort_values(ascending=False)

    return scores


def _build_clustering_network(
    enrichment_terms: list[dict[str, Any]], score_series: dict[str, pd.Series]
) -> Any:
    """Build clustering network from enrichment data."""
    # Determine term count thresholds
    num_terms = len(enrichment_terms)
    term_counts = {"ten": 10}
    if num_terms >= 10:
        term_counts["twenty"] = 20
    if num_terms >= 20:
        term_counts["thirty"] = 30

    # Get top terms for each score type and threshold
    top_terms = {
        score_type: {
            count_name: series.index.tolist()[:count_value]
            for count_name, count_value in term_counts.items()
        }
        for score_type, series in score_series.items()
    }

    # Collect unique terms to keep
    keep_terms = set()
    for score_dict in top_terms.values():
        for term_list in score_dict.values():
            keep_terms.update(term_list)

    # Filter enrichment terms and create network
    filtered_terms = [term for term in enrichment_terms if term["name"] in keep_terms]
    return _create_network_matrix(filtered_terms, score_series, top_terms, term_counts)


def _create_network_matrix(
    enrichment_terms: list[dict[str, Any]],
    score_series: dict[str, pd.Series],
    top_terms: dict[str, dict[str, list[str]]],
    term_counts: dict[str, int],
) -> Any:
    """Create and populate network matrix from enrichment data."""
    # Local import to avoid dependency issues
    from clustergrammer import Network

    # Extract genes and terms
    all_genes = set()
    term_names = []

    for term in enrichment_terms:
        term_names.append(term["name"])
        all_genes.update(term["int_genes"])

    gene_names = sorted(all_genes)

    # Create lookup dictionaries for O(1) index access
    gene_to_idx = {gene: idx for idx, gene in enumerate(gene_names)}
    term_to_idx = {term: idx for idx, term in enumerate(term_names)}

    # Initialize network structure
    net = Network()
    net.dat["nodes"]["row"] = gene_names
    net.dat["nodes"]["col"] = term_names
    net.dat["mat"] = np.zeros([len(gene_names), len(term_names)])
    net.dat["node_info"] = {"col": {"value": []}}

    # Populate matrix with O(1) lookups
    for term in enrichment_terms:
        term_name = term["name"]
        col_idx = term_to_idx[term_name]

        # Use combined score for full matrix - will not be seen in viz
        combined_score = score_series["combined_score"][term_name]
        net.dat["node_info"]["col"]["value"].append(combined_score)

        # Mark gene associations with O(1) lookups
        for gene in term["int_genes"]:
            if gene in gene_to_idx:
                row_idx = gene_to_idx[gene]
                net.dat["mat"][row_idx, col_idx] = 1

    # Perform clustering and create views
    _perform_clustering(net, score_series, top_terms, term_counts)
    return net


def _perform_clustering(
    net: Any,
    score_series: dict[str, pd.Series],
    top_terms: dict[str, dict[str, list[str]]],
    term_counts: dict[str, int],
) -> None:
    """Perform clustering on network and create score-based views."""
    # Cluster full matrix
    # Do not make multiple views
    views = [""]

    if len(net.dat["nodes"]["row"]) > 1:
        net.cluster(dist_type="jaccard", views=views, dendro=False)
    else:
        net.cluster(dist_type="jaccard", views=views, dendro=False, run_clustering=False)

    # Get dataframe from full matrix
    df = net.dat_to_df()

    # Create views for different score types and term counts
    for score_type in score_series:
        for count_name in term_counts:
            term_list = top_terms[score_type][count_name]
            _create_score_view(
                net,
                df,
                score_type,
                count_name,
                term_list,
                term_counts[count_name],
                score_series[score_type],
                len(net.dat["nodes"]["row"]) > 1,
            )


def _create_score_view(
    net: Any,
    df: pd.DataFrame,
    score_type: str,
    count_name: str,
    term_list: list[str],
    count_value: int,
    score_series: pd.Series,
    should_cluster: bool,
) -> None:
    """Create a single score-based view for the network."""
    # Local import to avoid dependency issues
    from copy import deepcopy

    from clustergrammer import Network

    if not term_list:
        return

    # Create subset and new network
    inst_df = deepcopy(df)
    inst_net = deepcopy(Network())

    inst_df = inst_df[term_list]

    # Load back into net
    inst_net.df_to_dat(inst_df)

    # Make views
    if should_cluster:
        inst_net.cluster(dist_type="jaccard", views=["N_row_sum"], dendro=False)
    else:
        inst_net.cluster(
            dist_type="jaccard", views=["N_row_sum"], dendro=False, run_clustering=False
        )

    inst_views = inst_net.viz["views"]

    # Create lookup dictionary for term positions
    term_to_rank = {term: len(term_list) - idx for idx, term in enumerate(term_list)}

    # Add score_type to views
    for inst_view in inst_views:
        inst_view["N_col_sum"] = count_value
        inst_view["enr_score_type"] = score_type

        # Add values to col_nodes and order according to rank
        for inst_col in inst_view["nodes"]["col_nodes"]:
            inst_name = inst_col["name"]
            inst_col["rank"] = term_to_rank[inst_name]
            inst_col["value"] = score_series[inst_name]

    # Add views to main network
    net.viz["views"].extend(inst_views)


def post_request(input_genes: list[str], meta: str = "") -> str:
    """
    Submit gene list to Enrichr API.

    Args:
        input_genes: List of gene symbols
        meta: Metadata (unused but preserved for compatibility)

    Returns:
        User list ID for subsequent requests
    """
    # Input validation
    if not input_genes:
        raise ValueError("Gene list cannot be empty")

    if not isinstance(input_genes, list):
        raise TypeError("input_genes must be a list")

    # Stringify list
    input_genes_str = "\n".join(input_genes)

    # Define post url
    post_url = "https://maayanlab.cloud/Enrichr/addList"

    # Define parameters
    params = {"list": input_genes_str, "description": ""}

    try:
        # Make request: post the gene list
        post_response = requests.post(post_url, files=params, timeout=30)
        post_response.raise_for_status()
    except Timeout as e:
        raise Timeout("Request to Enrichr API timed out") from e
    except RequestException as e:
        raise RequestException(f"Failed to submit gene list to Enrichr: {e}") from e

    # Load json
    try:
        inst_dict = json.loads(post_response.text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid response from Enrichr API: {e}") from e

    if "userListId" not in inst_dict:
        raise ValueError("Enrichr API response missing userListId")

    # Return the user_list_id that is needed to reference the list later
    return str(inst_dict["userListId"])


def get_request(
    lib: str, user_list_id: str | int, max_terms: int = 50
) -> tuple[list[dict[str, Any]], list[list[Any]]]:
    """
    Retrieve enrichment results from Enrichr API.

    Args:
        lib: Enrichr library name
        user_list_id: User list ID from post_request
        max_terms: Maximum number of terms to return

    Returns:
        Tuple of (processed enrichment data, raw response list)
    """
    # Input validation
    if not lib:
        raise ValueError("Library name cannot be empty")

    if not user_list_id:
        raise ValueError("User list ID cannot be empty")

    # Make request with retry logic
    url = "https://maayanlab.cloud/Enrichr/enrich"
    params = {"backgroundType": lib, "userListId": str(user_list_id)}
    response_data = _make_enrichr_request_with_retry(url, params)

    # Process and return results
    enrichment_dict = transfer_to_enr_dict(response_data, max_terms)
    return enrichment_dict, response_data


def _make_enrichr_request_with_retry(
    url: str, params: dict[str, str], max_retries: int = 100
) -> list[list[Any]]:
    """Make request to Enrichr API with exponential backoff retry logic."""
    base_delay = 0.5
    inst_status_code = 400  # Start with 400 to enter loop
    num_try = 0

    while inst_status_code == 400 and num_try < max_retries:
        num_try += 1

        # Add exponential backoff delay (skip first attempt)
        if num_try > 1:
            delay = min(base_delay * (2 ** (num_try - 2)), 30)
            time.sleep(delay)

        try:
            response = requests.get(url, params=params, timeout=30)
            inst_status_code = response.status_code

            # Handle non-200, non-400 status codes immediately
            if inst_status_code != 400 and inst_status_code != 200:
                raise RequestException(f"Enrichr API returned status code: {inst_status_code}")

            # Process successful response
            if inst_status_code == 200:
                try:
                    response_json = json.loads(response.text)
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid JSON response from Enrichr API: {e}") from e

                if not response_json:
                    raise ValueError("Empty response from Enrichr API")

                # Extract and return data
                library_key = next(iter(response_json.keys()))
                return response_json[library_key]

        except Timeout:
            print(f"Request timeout on attempt {num_try}, retrying...")
            inst_status_code = 400  # Continue retrying on timeout
            continue
        except RequestException:
            # For RequestException (non-400 status codes), re-raise immediately
            raise
        except Exception as e:
            print(f"Unexpected error on attempt {num_try}: {e}")
            # For other exceptions (JSON decode errors, etc.), re-raise immediately
            raise

    raise RequestException(f"Failed to get valid response after {max_retries} attempts")


def transfer_to_enr_dict(
    response_list: list[list[Any]], max_terms: int = 50
) -> list[dict[str, Any]]:
    """
    Convert Enrichr response list to structured dictionary format.

    Args:
        response_list: Raw response from Enrichr API
        max_terms: Maximum number of terms to process

    Returns:
        List of enrichment term dictionaries
    """
    # Input validation
    if not isinstance(response_list, list):
        raise TypeError("response_list must be a list")

    if not response_list:
        return []

    # Process terms up to max_terms limit
    num_terms = min(len(response_list), max_terms)
    enrichment_data = []

    for i in range(num_terms):
        term_data = response_list[i]

        # Validate term structure
        if not isinstance(term_data, list) or len(term_data) < 7:
            print(f"Warning: Skipping malformed enrichment entry at index {i}")
            continue

        try:
            enrichment_entry = {
                "name": term_data[1],  # Term name
                "pval": term_data[2],  # P-value
                "zscore": term_data[3],  # Z-score
                "combined_score": term_data[4],  # Combined score
                "int_genes": term_data[5],  # Intersecting genes
                "pval_bh": term_data[6],  # Adjusted p-value
            }
            enrichment_data.append(enrichment_entry)

        except (IndexError, TypeError) as e:
            print(f"Warning: Error processing enrichment entry at index {i}: {e}")
            continue

    return enrichment_data
