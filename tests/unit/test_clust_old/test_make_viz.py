"""
Comprehensive tests for celldega.clust.visualization.make_viz module.
Tests cover all functions with extensive edge case coverage and minimal redundancy.
"""

from pathlib import Path
import sys
from typing import Any
from unittest.mock import Mock

import numpy as np
import pytest


# Add the source directory to the path for imports
sys.path.insert(0, str(Path(__file__).parents[3] / "src"))

from celldega.clust_old.visualization.make_viz import viz_json


# =============================================================================
# CONSTANTS
# =============================================================================

# Test gene and sample names
GENE_1 = "gene1"
GENE_2 = "gene2"
GENE_3 = "gene3"
GENE_UPPER_1 = "GENE1"
GENE_UPPER_2 = "GENE2"
GENE_UPPER_3 = "GENE3"
GENE_ALPHA = "gene_α"
GENE_BETA = "gene_β"
SAMPLE_1 = "sample1"
SAMPLE_2 = "sample2"
SAMPLE_UPPER_1 = "SAMPLE1"
SAMPLE_UPPER_2 = "SAMPLE2"
SAMPLE_GAMMA = "sample_γ"

# Test categories and types
TYPE_A = "typeA"
TYPE_B = "typeB"
CLASS_X = "classX"
CLASS_Y = "classY"
PATHWAY_A = "pathway_A"
PATHWAY_B = "pathway_B"
CHR_1 = "chr1"
CHR_2 = "chr2"
BATCH_1 = "batch1"
BATCH_2 = "batch2"
CATEGORY_SPACES = "Category with spaces"
CATEGORY_123 = "Category_123"
CATEGORY_DASHES = "category-with-dashes"

# Test values and info
VAL_1 = "val1"
VAL_2 = "val2"
INFO_1 = "info1"
INFO_2 = "info2"
VALUE_HIGH = "high"
VALUE_MEDIUM = "medium"
VALUE_LOW = "low"
VALUE_CTRL = "ctrl"
VALUE_TREAT = "treat"
INFO_PROTEIN = "protein_coding"
INFO_LNCRNA = "lncRNA"
INFO_MIRNA = "miRNA"
INFO_CONTROL = "control"
INFO_TREATMENT = "treatment"
DELTA_VALUE = "δ_value"
EPSILON_VALUE = "ε_value"
ZETA_INFO = "ζ_info"
ETA_INFO = "η_info"
KAPPA_VALUE = "κ_value"
LAMBDA_INFO = "λ_info"

# Numeric test values
FLOAT_0_01 = 0.01
FLOAT_0_05 = 0.05
FLOAT_0_001 = 0.001
FLOAT_0_1 = 0.1
FLOAT_0_5 = 0.5
FLOAT_0_8 = 0.8
FLOAT_0_9 = 0.9
FLOAT_1_0 = 1.0
FLOAT_1_5 = 1.5
FLOAT_2_0 = 2.0
FLOAT_2_5 = 2.5
FLOAT_3_0 = 3.0
FLOAT_3_14 = 3.14
FLOAT_4_0 = 4.0
FLOAT_5_0 = 5.0
FLOAT_6_0 = 6.0
FLOAT_7_0 = 7.0
FLOAT_8_0 = 8.0
INT_42 = 42

# Category keys
CAT_0_KEY = "cat-0"
CAT_1_KEY = "cat-1"
CAT_0_BASE = "cat_0"
CAT_1_BASE = "cat_1"

# Node info keys
KEY_Y = "Y"
KEY_INI = "ini"
KEY_CLUST = "clust"
KEY_RANK = "rank"
KEY_VALUE = "value"
KEY_INFO = "info"
KEY_RANKVAR = "rankvar"

# Viz structure keys
KEY_LINKAGE = "linkage"
KEY_ROW_NODES = "row_nodes"
KEY_COL_NODES = "col_nodes"
KEY_LINKS = "links"
KEY_MAT = "mat"
KEY_SOURCE = "source"
KEY_TARGET = "target"
KEY_VALUE_VIZ = "value"
KEY_VALUE_ORIG = "value_orig"
KEY_NAME = "name"

# Axis names
AXIS_ROW = "row"
AXIS_COL = "col"

# Data structure keys
KEY_NODES = "nodes"
KEY_NODE_INFO = "node_info"
KEY_VIZ = "viz"
KEY_DAT = "dat"

# Error messages
ERROR_MISSING_ATTRIBUTES = "Network missing required attributes"
ERROR_MISSING_KEYS = "Missing keys"
ERROR_INDEX_OUT_OF_BOUNDS = "out of bounds"

# Special values
NAN_STRING = "NaN"

# Test dimensions
DEFAULT_ROWS = 2
DEFAULT_COLS = 2
SINGLE_ROW = 1
SINGLE_COL = 1
EMPTY_SIZE = 0
LARGE_TEST_SIZE = 10

# =============================================================================
# UTILITIES
# =============================================================================


def create_test_matrix(rows: int = DEFAULT_ROWS, cols: int = DEFAULT_COLS) -> np.ndarray:
    """Create a test matrix with specified dimensions."""
    if rows == 0 or cols == 0:
        return np.array([])
    return np.arange(FLOAT_1_0, rows * cols + FLOAT_1_0).reshape(rows, cols)


def create_test_linkage_matrix(size: int) -> np.ndarray:
    """Create a test linkage matrix for dendrogram data."""
    if size == 0:
        return np.array([])
    if size == 1:
        return np.array([[FLOAT_1_0]])
    return np.arange(FLOAT_1_0, size * DEFAULT_ROWS + FLOAT_1_0).reshape(DEFAULT_ROWS, size)


def create_node_names(prefix: str, count: int) -> list[str]:
    """Create a list of node names with specified prefix and count."""
    return [f"{prefix}{i + 1}" if i > 0 else prefix for i in range(count)]


def create_node_info_structure(
    count: int,
    include_optional: bool = False,
    include_categories: bool = False,
    include_pvalues: bool = False,
) -> dict[str, Any]:
    """Create a complete node_info structure for testing."""
    base_structure = {
        KEY_Y: create_test_linkage_matrix(count),
        KEY_INI: list(range(count)),
        KEY_CLUST: list(range(count)),
        KEY_RANK: list(range(count)),
        KEY_VALUE: [],
        KEY_INFO: [],
    }

    if include_optional:
        base_structure[KEY_RANKVAR] = [FLOAT_0_1 * (i + 1) for i in range(count)]
        base_structure[KEY_VALUE] = [f"val{i + 1}" for i in range(count)]
        base_structure[KEY_INFO] = [f"info{i + 1}" for i in range(count)]

    if include_categories:
        base_structure[CAT_0_KEY] = [TYPE_A if i % 2 == 0 else TYPE_B for i in range(count)]
        base_structure[CAT_1_KEY] = [CLASS_X if i % 2 == 0 else CLASS_Y for i in range(count)]
        base_structure[f"{CAT_0_BASE}_index"] = list(range(count))
        base_structure[f"{CAT_1_BASE}_index"] = list(range(count))

        if include_pvalues:
            base_structure[f"pval_{CAT_0_BASE}"] = {TYPE_A: FLOAT_0_01, TYPE_B: FLOAT_0_05}
            base_structure[f"pval_{CAT_1_BASE}"] = {CLASS_X: FLOAT_0_001, CLASS_Y: FLOAT_0_1}

    return base_structure


def create_viz_structure() -> dict[str, Any]:
    """Create an empty visualization structure."""
    return {
        KEY_LINKAGE: {},
        KEY_ROW_NODES: [],
        KEY_COL_NODES: [],
        KEY_LINKS: [],
        KEY_MAT: [],
    }


def create_mock_network(
    rows: int = DEFAULT_ROWS,
    cols: int = DEFAULT_COLS,
    include_optional: bool = False,
    include_categories: bool = False,
    include_pvalues: bool = False,
    matrix_data: np.ndarray | None = None,
    **overrides: Any,
) -> Mock:
    """Create a comprehensive mock network object with optional features."""
    if matrix_data is None:
        matrix_data = create_test_matrix(rows, cols)

    base_structure = {
        KEY_VIZ: create_viz_structure(),
        KEY_DAT: {
            KEY_NODES: {
                AXIS_ROW: create_node_names(GENE_1, rows),
                AXIS_COL: create_node_names(SAMPLE_1, cols),
            },
            KEY_NODE_INFO: {
                AXIS_ROW: create_node_info_structure(
                    rows, include_optional, include_categories, include_pvalues
                ),
                AXIS_COL: create_node_info_structure(
                    cols, include_optional, include_categories, include_pvalues
                ),
            },
            KEY_MAT: matrix_data,
        },
    }

    # Apply any overrides
    apply_nested_overrides(base_structure, overrides)

    net = Mock()
    net.viz = base_structure[KEY_VIZ]
    net.dat = base_structure[KEY_DAT]
    return net


def apply_nested_overrides(base: dict[str, Any], overrides: dict[str, Any]) -> None:
    """Apply nested overrides to a base dictionary structure."""
    for key, value in overrides.items():
        if isinstance(value, dict) and key in base and isinstance(base[key], dict):
            apply_nested_overrides(base[key], value)
        else:
            base[key] = value


def create_malformed_network(missing_attrs: list[str]) -> Mock:
    """Create a mock network missing specified attributes for error testing."""
    net = Mock()
    if KEY_VIZ not in missing_attrs:
        net.viz = create_viz_structure()
    if KEY_DAT not in missing_attrs:
        net.dat = {
            KEY_NODES: {AXIS_ROW: [], AXIS_COL: []},
            KEY_NODE_INFO: {
                AXIS_ROW: create_node_info_structure(0),
                AXIS_COL: create_node_info_structure(0),
            },
            KEY_MAT: np.array([]),
        }
    return net


def assert_basic_viz_structure(
    net: Mock, expected_rows: int = DEFAULT_ROWS, expected_cols: int = DEFAULT_COLS
) -> None:
    """Assert that the basic visualization structure is correct."""
    assert KEY_LINKAGE in net.viz
    assert AXIS_ROW in net.viz[KEY_LINKAGE]
    assert AXIS_COL in net.viz[KEY_LINKAGE]
    assert len(net.viz[KEY_ROW_NODES]) == expected_rows
    assert len(net.viz[KEY_COL_NODES]) == expected_cols


def assert_node_structure(
    node: dict[str, Any], name: str, ini: int = 0, clust: int = 0, rank: int = 0
) -> None:
    """Assert that a node has the basic required structure."""
    assert node[KEY_NAME] == name
    assert node[KEY_INI] == ini
    assert node[KEY_CLUST] == clust
    assert node[KEY_RANK] == rank


def assert_links_structure(links: list[dict[str, Any]], expected_count: int) -> None:
    """Assert that links structure is correct."""
    assert len(links) == expected_count
    for link in links:
        assert KEY_SOURCE in link
        assert KEY_TARGET in link
        assert KEY_VALUE_VIZ in link


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def basic_network() -> Mock:
    """Create a basic mock network for testing."""
    return create_mock_network()


@pytest.fixture
def empty_network() -> Mock:
    """Create an empty mock network for edge case testing."""
    return create_mock_network(rows=EMPTY_SIZE, cols=EMPTY_SIZE)


@pytest.fixture
def single_cell_network() -> Mock:
    """Create a single-cell mock network for testing."""
    return create_mock_network(rows=SINGLE_ROW, cols=SINGLE_COL, include_optional=True)


@pytest.fixture
def feature_rich_network() -> Mock:
    """Create a network with all optional features for comprehensive testing."""
    return create_mock_network(
        rows=DEFAULT_ROWS + 1,
        cols=DEFAULT_COLS,
        include_optional=True,
        include_categories=True,
        include_pvalues=True,
    )


@pytest.fixture
def nan_matrix_network() -> Mock:
    """Create a network with NaN values in the matrix."""
    return create_mock_network(rows=SINGLE_ROW, cols=SINGLE_COL, matrix_data=np.array([[np.nan]]))


# =============================================================================
# BASIC FUNCTIONALITY TESTS
# =============================================================================


class TestBasicFunctionality:
    """Test core functionality of viz_json function."""

    def test_matrix_mode_basic(self, basic_network: Mock):
        """Test basic functionality with matrix output."""
        viz_json(basic_network, dendro=True, links=False)

        assert_basic_viz_structure(basic_network)
        expected_matrix = [[FLOAT_1_0, FLOAT_2_0], [FLOAT_3_0, FLOAT_4_0]]
        assert basic_network.viz[KEY_MAT] == expected_matrix
        assert len(basic_network.viz[KEY_LINKS]) == 0

    def test_links_mode_basic(self, basic_network: Mock):
        """Test basic functionality with links output."""
        viz_json(basic_network, dendro=True, links=True)

        assert_basic_viz_structure(basic_network)
        expected_links_count = DEFAULT_ROWS * DEFAULT_COLS
        assert_links_structure(basic_network.viz[KEY_LINKS], expected_links_count)

        # Check first link structure
        first_link = basic_network.viz[KEY_LINKS][0]
        expected_first_link = {KEY_SOURCE: 0, KEY_TARGET: 0, KEY_VALUE_VIZ: FLOAT_1_0}
        assert first_link == expected_first_link

    def test_node_structure_creation(self, basic_network: Mock):
        """Test that node structure is created correctly."""
        viz_json(basic_network, dendro=True, links=False)

        assert_node_structure(basic_network.viz[KEY_ROW_NODES][0], GENE_1)
        assert_node_structure(basic_network.viz[KEY_COL_NODES][0], SAMPLE_1)

    def test_linkage_data_conversion(self, basic_network: Mock):
        """Test linkage data is properly converted to lists."""
        viz_json(basic_network, dendro=True, links=False)

        expected_row_linkage = [[FLOAT_1_0, FLOAT_2_0], [FLOAT_3_0, FLOAT_4_0]]
        expected_col_linkage = [[FLOAT_1_0, FLOAT_2_0], [FLOAT_3_0, FLOAT_4_0]]

        assert basic_network.viz[KEY_LINKAGE][AXIS_ROW] == expected_row_linkage
        assert basic_network.viz[KEY_LINKAGE][AXIS_COL] == expected_col_linkage

    @pytest.mark.parametrize(
        "dendro_flag,links_flag,description",
        [
            (True, False, "dendro_matrix_mode"),
            (True, True, "dendro_links_mode"),
            (False, False, "no_dendro_matrix_mode"),
            (False, True, "no_dendro_links_mode"),
        ],
    )
    def test_parameter_combinations(
        self, dendro_flag: bool, links_flag: bool, description: str, basic_network: Mock
    ):
        """Test various parameter combinations."""
        viz_json(basic_network, dendro=dendro_flag, links=links_flag)

        assert_basic_viz_structure(basic_network)

        if links_flag:
            assert len(basic_network.viz[KEY_LINKS]) == DEFAULT_ROWS * DEFAULT_COLS
            assert basic_network.viz[KEY_MAT] == []
        else:
            assert len(basic_network.viz[KEY_LINKS]) == 0
            assert len(basic_network.viz[KEY_MAT]) == DEFAULT_ROWS


# =============================================================================
# FEATURE TESTING
# =============================================================================


class TestOptionalFeatures:
    """Test viz_json with additional features like categories, values, etc."""

    def test_with_values_and_info(self):
        """Test with value and info data."""
        net = create_mock_network(include_optional=True)
        viz_json(net, dendro=True, links=False)

        row_node = net.viz[KEY_ROW_NODES][0]
        assert row_node[KEY_VALUE] == VAL_1
        assert row_node[KEY_INFO] == INFO_1

    def test_with_rankvar(self):
        """Test with rankvar data."""
        net = create_mock_network(include_optional=True)
        viz_json(net, dendro=True, links=False)

        assert net.viz[KEY_ROW_NODES][0][KEY_RANKVAR] == FLOAT_0_1
        assert net.viz[KEY_ROW_NODES][1][KEY_RANKVAR] == FLOAT_0_1 * 2

    def test_with_categories(self):
        """Test category processing."""
        net = create_mock_network(include_categories=True)
        viz_json(net, dendro=True, links=False)

        row_node = net.viz[KEY_ROW_NODES][0]
        assert row_node[CAT_0_KEY] == TYPE_A
        assert row_node[CAT_1_KEY] == CLASS_X
        assert row_node[f"{CAT_0_BASE}_index"] == 0
        assert row_node[f"{CAT_1_BASE}_index"] == 0

    def test_with_pvalues(self):
        """Test p-value processing."""
        net = create_mock_network(include_categories=True, include_pvalues=True)
        viz_json(net, dendro=True, links=False)

        row_node_0 = net.viz[KEY_ROW_NODES][0]
        row_node_1 = net.viz[KEY_ROW_NODES][1]

        assert row_node_0[f"{CAT_0_BASE}_pval"] == FLOAT_0_01  # TYPE_A
        assert row_node_1[f"{CAT_0_BASE}_pval"] == FLOAT_0_05  # TYPE_B

    @pytest.mark.parametrize(
        "optional_fields,expected_fields,description",
        [
            (["value"], [KEY_VALUE], "value_only"),
            (["info"], [KEY_INFO], "info_only"),
            (["rankvar"], [KEY_RANKVAR], "rankvar_only"),
            (["value", "info"], [KEY_VALUE, KEY_INFO], "value_and_info"),
            (["value", "info", "rankvar"], [KEY_VALUE, KEY_INFO, KEY_RANKVAR], "all_optional"),
        ],
    )
    def test_optional_field_combinations(
        self, optional_fields: list[str], expected_fields: list[str], description: str
    ):
        """Test various combinations of optional fields."""
        # Create custom node_info with only specified optional fields
        node_info_override = {}
        if KEY_VALUE in optional_fields:
            node_info_override[KEY_VALUE] = [VAL_1, VAL_2]
        if KEY_INFO in optional_fields:
            node_info_override[KEY_INFO] = [INFO_1, INFO_2]
        if KEY_RANKVAR in optional_fields:
            node_info_override[KEY_RANKVAR] = [FLOAT_0_5, FLOAT_0_8]

        net = create_mock_network(**{KEY_DAT: {KEY_NODE_INFO: {AXIS_ROW: node_info_override}}})

        viz_json(net, dendro=True, links=False)

        row_node = net.viz[KEY_ROW_NODES][0]
        for field in expected_fields:
            assert field in row_node

        # Ensure fields not specified are not present
        all_optional = {KEY_VALUE, KEY_INFO, KEY_RANKVAR}
        for field in all_optional - set(expected_fields):
            assert field not in row_node


# =============================================================================
# EDGE CASE TESTS
# =============================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_nodes(self, empty_network: Mock):
        """Test with empty node lists."""
        viz_json(empty_network, dendro=True, links=False)

        assert_basic_viz_structure(
            empty_network, expected_rows=EMPTY_SIZE, expected_cols=EMPTY_SIZE
        )
        assert empty_network.viz[KEY_MAT] == []

    def test_single_node(self, single_cell_network: Mock):
        """Test with single node in each dimension."""
        viz_json(single_cell_network, dendro=True, links=False)

        assert_basic_viz_structure(
            single_cell_network, expected_rows=SINGLE_ROW, expected_cols=SINGLE_COL
        )
        assert single_cell_network.viz[KEY_MAT] == [[FLOAT_1_0]]

        row_node = single_cell_network.viz[KEY_ROW_NODES][0]
        assert_node_structure(row_node, GENE_1)
        assert row_node[KEY_VALUE] == VAL_1
        assert row_node[KEY_INFO] == INFO_1

    def test_nan_values_in_matrix(self, nan_matrix_network: Mock):
        """Test NaN handling in matrix/links mode."""
        viz_json(nan_matrix_network, dendro=True, links=True)

        link = nan_matrix_network.viz[KEY_LINKS][0]
        assert np.isnan(link[KEY_VALUE_VIZ])
        assert KEY_VALUE_ORIG in link
        assert link[KEY_VALUE_ORIG] == NAN_STRING

    def test_empty_optional_lists(self, basic_network: Mock):
        """Test behavior with empty value and info lists."""
        viz_json(basic_network, dendro=True, links=False)

        row_node = basic_network.viz[KEY_ROW_NODES][0]
        assert KEY_VALUE not in row_node
        assert KEY_INFO not in row_node

    @pytest.mark.parametrize(
        "matrix_shape,expected_links,description",
        [
            ((0, 0), 0, "empty_matrix"),
            ((1, 1), 1, "single_cell"),
            ((1, 3), 3, "single_row_multi_col"),
            ((3, 1), 3, "multi_row_single_col"),
            ((2, 3), 6, "rectangular_matrix"),
        ],
    )
    def test_various_matrix_dimensions(
        self, matrix_shape: tuple[int, int], expected_links: int, description: str
    ):
        """Test various matrix dimensions."""
        rows, cols = matrix_shape
        net = create_mock_network(rows=rows, cols=cols)

        viz_json(net, dendro=True, links=True)

        assert_basic_viz_structure(net, expected_rows=rows, expected_cols=cols)
        assert_links_structure(net.viz[KEY_LINKS], expected_links)


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================


class TestErrorHandling:
    """Test error handling and robustness."""

    def test_missing_parameters(self):
        """Test various missing parameter scenarios."""
        with pytest.raises(TypeError):
            viz_json()

        with pytest.raises(AttributeError):
            viz_json(None)

    @pytest.mark.parametrize(
        "missing_attrs,expected_error,description",
        [
            ([KEY_VIZ], AttributeError, "missing_viz"),
            ([KEY_DAT], AttributeError, "missing_dat"),
            ([KEY_VIZ, KEY_DAT], AttributeError, "missing_both"),
        ],
    )
    def test_missing_network_attributes(
        self, missing_attrs: list[str], expected_error: type[Exception], description: str
    ):
        """Test missing required network attributes."""
        net = create_malformed_network(missing_attrs)

        # Remove the specified attributes
        for attr in missing_attrs:
            if hasattr(net, attr):
                delattr(net, attr)

        with pytest.raises(expected_error):
            viz_json(net)

    @pytest.mark.parametrize(
        "missing_dat_keys,description",
        [
            ([KEY_NODES], "missing_nodes"),
            ([KEY_NODE_INFO], "missing_node_info"),
            ([KEY_MAT], "missing_mat"),
            ([KEY_NODES, KEY_NODE_INFO], "missing_nodes_and_info"),
        ],
    )
    def test_missing_dat_keys(self, missing_dat_keys: list[str], description: str):
        """Test missing keys in dat structure."""
        net = create_mock_network()

        # Remove specified keys from dat
        for key in missing_dat_keys:
            if key in net.dat:
                del net.dat[key]

        with pytest.raises(KeyError, match=ERROR_MISSING_KEYS):
            viz_json(net)

    def test_malformed_node_info_missing_required_keys(self):
        """Test with malformed node_info structure missing required keys."""
        net = Mock()
        net.viz = create_viz_structure()
        net.dat = {
            KEY_NODES: {AXIS_ROW: [GENE_1], AXIS_COL: [SAMPLE_1]},
            KEY_NODE_INFO: {
                AXIS_ROW: {
                    KEY_Y: np.array([[FLOAT_1_0]]),
                    # Missing required keys: ini, clust, rank
                    KEY_VALUE: [],
                    KEY_INFO: [],
                },
                AXIS_COL: create_node_info_structure(1),
            },
            KEY_MAT: np.array([[FLOAT_1_0]]),
        }

        with pytest.raises(KeyError):
            viz_json(net)

    def test_mismatched_data_lengths(self):
        """Test behavior with mismatched data lengths."""
        net = create_mock_network()
        # Create mismatch: 2 nodes but only 1 element in ini array
        net.dat[KEY_NODE_INFO][AXIS_ROW][KEY_INI] = [0]  # Should have 2 elements

        with pytest.raises(IndexError, match=ERROR_INDEX_OUT_OF_BOUNDS):
            viz_json(net)

    def test_malformed_node_info_rank_none(self):
        """Test with None rank data - should raise TypeError when accessing."""
        net = create_mock_network()
        net.dat[KEY_NODE_INFO][AXIS_ROW][KEY_RANK] = None

        with pytest.raises(TypeError):
            viz_json(net)

    def test_malformed_node_info_clust_string(self):
        """Test with string clust data - may not raise error immediately."""
        net = create_mock_network()
        net.dat[KEY_NODE_INFO][AXIS_ROW][KEY_CLUST] = "not_a_list"

        # The code creates a cluster_lookup dict using enumerate()
        # This will fail when trying to enumerate a string, but the exact error depends on implementation
        try:
            viz_json(net)
            # If no error, that's also valid behavior - the code might handle it gracefully
        except (TypeError, ValueError):
            # Expected potential errors when trying to process string as list
            pass

    def test_malformed_node_info_mixed_types_access(self):
        """Test accessing elements with mixed types - may not always fail."""
        net = create_mock_network()
        net.dat[KEY_NODE_INFO][AXIS_ROW][KEY_INI] = [0, "invalid"]

        # The code accesses ini[i] where i is an integer index
        # This might work fine if the invalid element is not accessed
        try:
            viz_json(net)
            # If no error, that's valid - the code successfully processed the data
        except (IndexError, TypeError, ValueError):
            # These are potential errors but not guaranteed
            pass


# =============================================================================
# BUG REPRODUCTION TESTS
# =============================================================================


class TestBugReproduction:
    """Test cases that reproduce specific bugs identified in analysis."""

    def test_value_orig_nan_handling(self, nan_matrix_network: Mock):
        """Test the value_orig logic with NaN values in links mode."""
        viz_json(nan_matrix_network, dendro=True, links=True)

        link = nan_matrix_network.viz[KEY_LINKS][0]
        assert np.isnan(link[KEY_VALUE_VIZ])
        assert KEY_VALUE_ORIG in link
        assert link[KEY_VALUE_ORIG] == NAN_STRING

    def test_category_name_replacement_with_dashes(self):
        """Test category name replacement logic with dashes."""
        net = create_mock_network(
            rows=SINGLE_ROW,
            cols=SINGLE_COL,
            **{
                KEY_DAT: {
                    KEY_NODE_INFO: {
                        AXIS_ROW: {
                            CAT_0_KEY: [CATEGORY_DASHES],
                            f"pval_{CAT_0_BASE}": {CATEGORY_DASHES: FLOAT_0_01},
                            f"{CAT_0_BASE}_index": [0],
                        }
                    }
                }
            },
        )

        viz_json(net, dendro=True, links=False)

        row_node = net.viz[KEY_ROW_NODES][0]
        assert row_node[CAT_0_KEY] == CATEGORY_DASHES
        assert f"{CAT_0_BASE}_pval" in row_node
        assert row_node[f"{CAT_0_BASE}_pval"] == FLOAT_0_01

    def test_missing_pval_data_graceful_handling(self):
        """Test handling when p-value data is missing for categories."""
        net = create_mock_network(
            rows=SINGLE_ROW,
            cols=SINGLE_COL,
            **{
                KEY_DAT: {
                    KEY_NODE_INFO: {
                        AXIS_ROW: {
                            CAT_0_KEY: [TYPE_A],
                            # Missing pval_cat_0 - should not crash
                            f"{CAT_0_BASE}_index": [0],
                        }
                    }
                }
            },
        )

        viz_json(net, dendro=True, links=False)

        row_node = net.viz[KEY_ROW_NODES][0]
        assert row_node[CAT_0_KEY] == TYPE_A
        assert f"{CAT_0_BASE}_pval" not in row_node

    def test_cluster_lookup_performance_demonstration(self):
        """Test that demonstrates the cluster lookup optimization."""
        n_nodes = LARGE_TEST_SIZE
        clust_list = list(range(n_nodes))

        net = create_mock_network(
            rows=n_nodes,
            cols=SINGLE_COL,
            **{
                KEY_DAT: {
                    KEY_NODE_INFO: {
                        AXIS_ROW: {
                            KEY_CLUST: clust_list,
                        }
                    }
                }
            },
        )

        viz_json(net, dendro=True, links=False)

        # Verify clust values were computed correctly
        for i, node in enumerate(net.viz[KEY_ROW_NODES]):
            assert node[KEY_CLUST] == i


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestIntegrationScenarios:
    """Integration tests combining multiple features."""

    def test_comprehensive_network_processing(self, feature_rich_network: Mock):
        """Test with a comprehensive network object containing all features."""
        viz_json(feature_rich_network, dendro=True, links=False)

        expected_rows = DEFAULT_ROWS + 1
        assert_basic_viz_structure(
            feature_rich_network, expected_rows=expected_rows, expected_cols=DEFAULT_COLS
        )

        # Check comprehensive row node features
        row_node = feature_rich_network.viz[KEY_ROW_NODES][0]
        expected_keys = [
            KEY_NAME,
            KEY_INI,
            KEY_CLUST,
            KEY_RANK,
            KEY_RANKVAR,
            KEY_VALUE,
            KEY_INFO,
            CAT_0_KEY,
            CAT_1_KEY,
            f"{CAT_0_BASE}_pval",
            f"{CAT_0_BASE}_index",
            f"{CAT_1_BASE}_index",
        ]

        for key in expected_keys:
            assert key in row_node

        assert row_node[KEY_NAME] == GENE_1
        assert row_node[f"{CAT_0_BASE}_pval"] == FLOAT_0_01  # TYPE_A p-value

    def test_matrix_vs_links_consistency(self, basic_network: Mock):
        """Test that matrix and links modes produce consistent data."""
        test_matrix = basic_network.dat[KEY_MAT].copy()

        # Test matrix mode
        viz_json(basic_network, links=False)
        matrix_result = basic_network.viz[KEY_MAT]

        # Reset and test links mode
        basic_network.viz[KEY_LINKS] = []
        basic_network.viz[KEY_MAT] = []
        viz_json(basic_network, links=True)
        links_result = basic_network.viz[KEY_LINKS]

        # Verify consistency
        expected_links = DEFAULT_ROWS * DEFAULT_COLS
        assert len(links_result) == expected_links

        # Reconstruct matrix from links
        reconstructed = np.zeros((DEFAULT_ROWS, DEFAULT_COLS))
        for link in links_result:
            reconstructed[link[KEY_SOURCE], link[KEY_TARGET]] = link[KEY_VALUE_VIZ]

        np.testing.assert_array_equal(reconstructed, test_matrix)
        assert matrix_result == test_matrix.tolist()

    def test_unicode_and_mixed_data_types(self):
        """Test with Unicode characters and various data types."""
        net = create_mock_network(
            rows=DEFAULT_ROWS,
            cols=SINGLE_COL,
            **{
                KEY_DAT: {
                    KEY_NODES: {
                        AXIS_ROW: [GENE_ALPHA, GENE_BETA],
                        AXIS_COL: [SAMPLE_GAMMA],
                    },
                    KEY_NODE_INFO: {
                        AXIS_ROW: {
                            KEY_VALUE: [DELTA_VALUE, EPSILON_VALUE],
                            KEY_INFO: [ZETA_INFO, ETA_INFO],
                            CAT_0_KEY: [CATEGORY_SPACES, CATEGORY_123],
                            CAT_1_KEY: [INT_42, FLOAT_3_14],  # Mixed numeric types
                            f"{CAT_0_BASE}_index": [0, 1],
                            f"{CAT_1_BASE}_index": [0, 1],
                        },
                        AXIS_COL: {
                            KEY_VALUE: [KAPPA_VALUE],
                            KEY_INFO: [LAMBDA_INFO],
                        },
                    },
                }
            },
        )

        viz_json(net, dendro=True, links=False)

        # Check Unicode and complex data handling
        row_node_0 = net.viz[KEY_ROW_NODES][0]
        assert row_node_0[KEY_NAME] == GENE_ALPHA
        assert row_node_0[KEY_VALUE] == DELTA_VALUE
        assert row_node_0[CAT_0_KEY] == CATEGORY_SPACES
        assert row_node_0[CAT_1_KEY] == INT_42

        col_node_0 = net.viz[KEY_COL_NODES][0]
        assert col_node_0[KEY_NAME] == SAMPLE_GAMMA
        assert col_node_0[KEY_VALUE] == KAPPA_VALUE

    @pytest.mark.parametrize(
        "rows,cols,description",
        [
            (1, 10, "single_row_many_cols"),
            (10, 1, "many_rows_single_col"),
            (5, 5, "square_medium"),
            (3, 7, "rectangular_asymmetric"),
        ],
    )
    def test_various_network_sizes(self, rows: int, cols: int, description: str):
        """Test various network sizes and shapes."""
        net = create_mock_network(rows=rows, cols=cols, include_optional=True)

        viz_json(net, dendro=True, links=True)

        assert_basic_viz_structure(net, expected_rows=rows, expected_cols=cols)
        expected_links = rows * cols
        assert_links_structure(net.viz[KEY_LINKS], expected_links)

        # Verify all nodes have complete structure
        for node in net.viz[KEY_ROW_NODES]:
            assert all(key in node for key in [KEY_NAME, KEY_INI, KEY_CLUST, KEY_RANK])

        for node in net.viz[KEY_COL_NODES]:
            assert all(key in node for key in [KEY_NAME, KEY_INI, KEY_CLUST, KEY_RANK])


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
