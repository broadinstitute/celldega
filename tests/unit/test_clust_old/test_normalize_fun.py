"""
Unit tests for normalize_fun module with improved robustness and maintainability.

This module provides comprehensive testing for normalization functions including
z-score, quantile normalization, UMI normalization, and clipping operations.
"""

from pathlib import Path
import sys
from typing import Any
from unittest.mock import Mock
import warnings

import numpy as np
import pandas as pd
import pytest


# =============================================================================
# MODULE CONSTANTS AND CONFIGURATION
# =============================================================================

# Path configuration
SRC_ROOT = Path(__file__).parents[3] / "src"
sys.path.insert(0, str(SRC_ROOT))

# Test data constants
BASIC_TEST_DF = pd.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]}, index=["row1", "row2", "row3"])

ZSCORE_TEST_DF = pd.DataFrame(
    {"A": [1, 4, 7], "B": [2, 5, 8], "C": [3, 6, 9]}, index=["row1", "row2", "row3"]
)

QN_TEST_DF = pd.DataFrame({"A": [1, 2, 3], "B": [10, 20, 30]}, index=["row1", "row2", "row3"])

UMI_TEST_DF = pd.DataFrame({"sample1": [100, 200], "sample2": [300, 600]}, index=["gene1", "gene2"])

NAN_TEST_DF = pd.DataFrame(
    {"A": [1, np.nan, 3], "B": [4, 5, np.nan]}, index=["row1", "row2", "row3"]
)

CONSTANT_COL_DF = pd.DataFrame({"A": [5, 5, 5], "B": [1, 2, 3]}, index=["row1", "row2", "row3"])

LARGE_VALUES_DF = pd.DataFrame({"A": [1e10, 1e11, 1e12], "B": [1, 2, 3]})

INFINITE_VALUES_DF = pd.DataFrame({"A": [1, np.inf, 3], "B": [-np.inf, 2, 3]})

ZERO_DF = pd.DataFrame({"A": [0, 0, 0], "B": [0, 0, 0]})

SINGLE_VALUE_DF = pd.DataFrame({"A": [5]})

EMPTY_DF = pd.DataFrame()

# Normalization type constants
NORM_TYPES = ["zscore", "qn", "umi"]
AXIS_OPTIONS = ["row", "col"]
INVALID_NORM_TYPES = ["invalid", "log", "standard"]
INVALID_AXES = ["invalid", "axis", "both"]

# Clipping test constants
CLIP_BOUNDS_TEST_CASES = [
    (-3, 3),  # Both bounds
    (-2, None),  # Lower only
    (None, 2),  # Upper only
    (None, None),  # No bounds
]

# Statistical tolerance for numerical comparisons
STATISTICAL_TOLERANCE = 1e-10

# Error messages
INVALID_NORM_TYPE_MSG = "Invalid norm_type"
INVALID_AXIS_MSG = "Invalid axis"
INVALID_Z_CLIP_MSG = "z_clip must be positive"
CONSTANT_COLUMNS_WARNING = "Constant columns detected in z-score normalization"


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================


def create_mock_network(dat_structure: dict[str, Any] | None = None) -> Mock:
    """
    Create a mock network object with configurable dat structure.

    Args:
        dat_structure: Custom dat structure (merged with defaults)

    Returns:
        Mock network object with specified structure
    """
    mock_net = Mock()
    mock_net.dat = dat_structure or {}
    mock_net.dat_to_df.return_value = BASIC_TEST_DF
    return mock_net


def assert_dataframe_normalized_by_axis(df: pd.DataFrame, axis: str) -> None:
    """Assert that DataFrame is properly normalized along specified axis."""
    if axis == "col":
        means = df.mean(axis=0)
        assert np.allclose(means, 0, atol=STATISTICAL_TOLERANCE), (
            f"Column means not zero: {means.values}"
        )
    elif axis == "row":
        means = df.mean(axis=1)
        assert np.allclose(means, 0, atol=STATISTICAL_TOLERANCE), (
            f"Row means not zero: {means.values}"
        )


def assert_umi_normalization_correct(df: pd.DataFrame, result: pd.DataFrame) -> None:
    """Assert that UMI normalization produced correct results."""
    # Each column should sum to 1.0 (unless it was all zeros)
    col_sums = result.sum(axis=0)
    non_zero_cols = df.sum(axis=0) != 0

    if non_zero_cols.any():
        expected_sums = non_zero_cols.astype(float)
        actual_sums = col_sums[non_zero_cols]
        assert np.allclose(actual_sums, 1.0, atol=STATISTICAL_TOLERANCE), (
            f"UMI normalized columns don't sum to 1.0: {actual_sums.values}"
        )


def assert_values_clipped_correctly(
    result: pd.DataFrame, lower: float | None, upper: float | None
) -> None:
    """Assert that values are clipped within specified bounds."""
    if lower is not None:
        assert (result >= lower).all().all() or result.isna().all().all(), (
            f"Values below lower bound {lower} found"
        )

    if upper is not None:
        assert (result <= upper).all().all() or result.isna().all().all(), (
            f"Values above upper bound {upper} found"
        )


def assert_dataframe_unchanged(original: pd.DataFrame, after_operation: pd.DataFrame) -> None:
    """Assert that original DataFrame was not modified by operation."""
    pd.testing.assert_frame_equal(original, after_operation, check_dtype=True, check_exact=True)


def create_test_data_with_properties(
    has_nan: bool = False,
    has_constant_cols: bool = False,
    has_zero_cols: bool = False,
    has_negative: bool = False,
    single_row: bool = False,
    single_col: bool = False,
) -> pd.DataFrame:
    """Create test DataFrame with specified properties."""
    if single_row and single_col:
        return pd.DataFrame({"A": [1]})
    if single_row:
        return pd.DataFrame({"A": [1], "B": [2]})
    if single_col:
        return pd.DataFrame({"A": [1, 2, 3]})

    base_data = {"A": [1, 2, 3], "B": [4, 5, 6], "C": [7, 8, 9]}

    if has_constant_cols:
        base_data["D"] = [10, 10, 10]

    if has_zero_cols:
        base_data["E"] = [0, 0, 0]

    if has_negative:
        base_data["F"] = [-1, -2, -3]

    df = pd.DataFrame(base_data)

    if has_nan:
        df.iloc[1, 0] = np.nan
        df.iloc[2, 1] = np.nan

    return df


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def standard_mock_net():
    """Fixture providing a standard mock network for common test scenarios."""
    return create_mock_network()


@pytest.fixture
def empty_mock_net():
    """Fixture providing a mock network that returns empty DataFrame."""
    mock_net = create_mock_network()
    mock_net.dat_to_df.return_value = EMPTY_DF
    return mock_net


@pytest.fixture
def nan_data_mock_net():
    """Fixture providing a mock network with NaN data."""
    mock_net = create_mock_network()
    mock_net.dat_to_df.return_value = NAN_TEST_DF
    return mock_net


# =============================================================================
# IMPORT AND BASIC FUNCTIONALITY
# =============================================================================

from celldega.clust_old.preprocessing.normalize_fun import (
    calc_common_dist,
    qn_df,
    run_norm,
    swap_in_common_dist,
    umi_norm,
    z_clip_fun,
    zscore_df,
)


# =============================================================================
# RUN_NORM FUNCTION TESTS
# =============================================================================


class TestRunNormParameterValidation:
    """Test run_norm parameter validation and basic functionality."""

    @pytest.mark.parametrize("norm_type", NORM_TYPES)
    def test_valid_norm_types(self, standard_mock_net, norm_type):
        """Test that all valid normalization types work correctly."""
        run_norm(standard_mock_net, norm_type=norm_type)
        standard_mock_net.df_to_dat.assert_called_once()

    @pytest.mark.parametrize("invalid_norm_type", INVALID_NORM_TYPES)
    def test_invalid_norm_type_raises_error(self, standard_mock_net, invalid_norm_type):
        """Test that invalid normalization types raise ValueError."""
        with pytest.raises(ValueError, match=INVALID_NORM_TYPE_MSG):
            run_norm(standard_mock_net, norm_type=invalid_norm_type)

    @pytest.mark.parametrize("axis", AXIS_OPTIONS)
    def test_valid_axes(self, standard_mock_net, axis):
        """Test that all valid axis options work correctly."""
        run_norm(standard_mock_net, axis=axis)
        standard_mock_net.df_to_dat.assert_called_once()

    @pytest.mark.parametrize("invalid_axis", INVALID_AXES)
    def test_invalid_axis_raises_error(self, standard_mock_net, invalid_axis):
        """Test that invalid axis values raise ValueError."""
        with pytest.raises(ValueError, match=INVALID_AXIS_MSG):
            run_norm(standard_mock_net, axis=invalid_axis)

    @pytest.mark.parametrize(
        "z_clip_value,should_raise",
        [
            (1.0, False),
            (2.5, False),
            (0.1, False),
            (0.0, True),
            (-1.0, True),
            (-0.1, True),
        ],
    )
    def test_z_clip_validation(self, standard_mock_net, z_clip_value, should_raise):
        """Test z_clip parameter validation."""
        if should_raise:
            with pytest.raises(ValueError, match=INVALID_Z_CLIP_MSG):
                run_norm(standard_mock_net, z_clip=z_clip_value)
        else:
            run_norm(standard_mock_net, norm_type="zscore", z_clip=z_clip_value)
            standard_mock_net.df_to_dat.assert_called_once()


class TestRunNormNormalizationTypes:
    """Test different normalization type implementations in run_norm."""

    def test_zscore_normalization_with_metadata_storage(self, standard_mock_net):
        """Test z-score normalization stores pre_zscore metadata."""
        run_norm(standard_mock_net, norm_type="zscore", axis="row")

        # Should store pre_zscore metadata
        assert "pre_zscore" in standard_mock_net.dat
        assert "mean" in standard_mock_net.dat["pre_zscore"]
        assert "std" in standard_mock_net.dat["pre_zscore"]
        assert isinstance(standard_mock_net.dat["pre_zscore"]["mean"], list)
        assert isinstance(standard_mock_net.dat["pre_zscore"]["std"], list)

    def test_zscore_with_custom_dataframe(self, standard_mock_net):
        """Test z-score normalization with provided DataFrame."""
        custom_df = pd.DataFrame({"A": [0, 1, 2], "B": [3, 4, 5]})

        run_norm(standard_mock_net, df=custom_df, norm_type="zscore", axis="col")

        # Should not call dat_to_df when df is provided
        standard_mock_net.dat_to_df.assert_not_called()
        standard_mock_net.df_to_dat.assert_called_once()

    def test_qn_normalization_no_metadata(self, standard_mock_net):
        """Test quantile normalization doesn't store zscore metadata."""
        run_norm(standard_mock_net, norm_type="qn", axis="col")

        # Should not store pre_zscore for qn
        assert "pre_zscore" not in standard_mock_net.dat
        standard_mock_net.df_to_dat.assert_called_once()

    def test_umi_normalization_basic(self, standard_mock_net):
        """Test UMI normalization basic functionality."""
        run_norm(standard_mock_net, norm_type="umi")
        standard_mock_net.df_to_dat.assert_called_once()

    def test_zscore_with_clipping_applied(self, standard_mock_net):
        """Test z-score normalization with clipping parameter."""
        standard_mock_net.dat_to_df.return_value = pd.DataFrame({"A": [1, 10, 2], "B": [3, 4, 5]})

        run_norm(standard_mock_net, norm_type="zscore", z_clip=2.0)
        standard_mock_net.df_to_dat.assert_called_once()


# =============================================================================
# ZSCORE_DF FUNCTION TESTS
# =============================================================================


class TestZscoreDfBasicFunctionality:
    """Test basic zscore_df functionality and parameter handling."""

    @pytest.mark.parametrize("axis", AXIS_OPTIONS)
    def test_zscore_basic_normalization(self, axis):
        """Test basic z-score normalization for both axes."""
        df = ZSCORE_TEST_DF.copy()
        result_df, ser_mean, ser_std = zscore_df(df, axis=axis)

        # Check normalization worked
        assert_dataframe_normalized_by_axis(result_df, axis)

        # Check return value structure
        assert isinstance(result_df, pd.DataFrame)
        assert isinstance(ser_mean, pd.Series)
        assert isinstance(ser_std, pd.Series)

        # Check dimensions
        assert result_df.shape == df.shape
        expected_stats_len = len(df.columns) if axis == "row" else len(df.index)
        assert len(ser_mean) == expected_stats_len
        assert len(ser_std) == expected_stats_len

    def test_zscore_with_constant_columns_warning(self):
        """Test z-score with constant columns produces appropriate warning."""
        df = CONSTANT_COL_DF.copy()

        with pytest.warns(UserWarning, match=CONSTANT_COLUMNS_WARNING):
            result_df, ser_mean, ser_std = zscore_df(df, axis="col")

        # Column A should have inf or NaN values due to division by zero
        assert np.any(np.isinf(result_df["A"]) | np.isnan(result_df["A"]))

        # Column B should be properly normalized
        assert np.allclose(result_df["B"].mean(), 0, atol=STATISTICAL_TOLERANCE)

    @pytest.mark.parametrize(
        "z_clip_value,expected_range",
        [
            (1.0, (-1.0, 1.0)),
            (2.0, (-2.0, 2.0)),
            (0.5, (-0.5, 0.5)),
        ],
    )
    def test_zscore_with_clipping(self, z_clip_value, expected_range):
        """Test z-score with various clipping values."""
        df = pd.DataFrame({"A": [1, 10, 2], "B": [3, 4, 5]})

        result_df, _, _ = zscore_df(df, axis="col", z_clip=z_clip_value)

        # All values should be within clipping range
        lower, upper = expected_range
        assert (result_df >= lower).all().all()
        assert (result_df <= upper).all().all()

    def test_zscore_with_nan_values_preserved(self):
        """Test z-score preserves NaN values appropriately."""
        df = NAN_TEST_DF.copy()

        result_df, ser_mean, ser_std = zscore_df(df, axis="col")

        # NaN values should be preserved in output
        assert np.isnan(result_df.iloc[1, 0])  # A, row2
        assert np.isnan(result_df.iloc[2, 1])  # B, row3
        assert result_df.shape == df.shape

    def test_zscore_original_dataframe_unchanged(self):
        """Test that original DataFrame is not modified."""
        df = BASIC_TEST_DF.copy()
        original_data = df.copy()

        zscore_df(df, axis="col")

        assert_dataframe_unchanged(original_data, df)


class TestZscoreDfEdgeCases:
    """Test zscore_df edge cases and boundary conditions."""

    def test_zscore_empty_dataframe(self):
        """Test z-score with empty DataFrame."""
        result_df, ser_mean, ser_std = zscore_df(EMPTY_DF, axis="col")

        assert result_df.empty
        assert len(ser_mean) == 0
        assert len(ser_std) == 0

    def test_zscore_single_row_produces_nan(self):
        """Test z-score with single row DataFrame."""
        df = pd.DataFrame({"A": [1], "B": [2]})

        result_df, ser_mean, ser_std = zscore_df(df, axis="col")

        # Single value per column means std=0, so should get NaN
        assert np.isnan(result_df.iloc[0, 0])
        assert np.isnan(result_df.iloc[0, 1])

    def test_zscore_single_column(self):
        """Test z-score with single column DataFrame."""
        df = pd.DataFrame({"A": [1, 2, 3]})

        result_df, ser_mean, ser_std = zscore_df(df, axis="col")

        assert_dataframe_normalized_by_axis(result_df, "col")
        assert result_df.shape == df.shape

    def test_zscore_with_negative_values(self):
        """Test z-score handles negative values correctly."""
        df = pd.DataFrame({"A": [-1, -2, -3], "B": [1, 2, 3]})

        result_df, ser_mean, ser_std = zscore_df(df, axis="col")

        assert_dataframe_normalized_by_axis(result_df, "col")
        assert result_df.shape == df.shape


# =============================================================================
# QN_DF FUNCTION TESTS
# =============================================================================


class TestQnDfBasicFunctionality:
    """Test basic qn_df functionality and parameter handling."""

    @pytest.mark.parametrize("axis", AXIS_OPTIONS)
    def test_qn_basic_normalization(self, axis):
        """Test basic quantile normalization for both axes."""
        df = QN_TEST_DF.copy()
        result = qn_df(df, axis=axis)

        # Check basic properties
        assert result.shape == df.shape
        assert list(result.index) == list(df.index)
        assert list(result.columns) == list(df.columns)
        assert isinstance(result, pd.DataFrame)

    def test_qn_with_missing_values_preserved(self):
        """Test quantile normalization preserves missing values."""
        df = NAN_TEST_DF.copy()
        result = qn_df(df, axis="col")

        # Missing values should be preserved as NaN
        assert np.isnan(result.iloc[1, 0])  # A, row2
        assert np.isnan(result.iloc[2, 1])  # B, row3
        assert result.shape == df.shape

    def test_qn_single_column_unchanged(self):
        """Test quantile normalization with single column."""
        df = pd.DataFrame({"A": [1, 2, 3]})
        result = qn_df(df, axis="col")

        assert result.shape == df.shape
        # Single column QN should return the column unchanged
        np.testing.assert_array_equal(result["A"].values, df["A"].values)

    def test_qn_identical_columns_remain_identical(self):
        """Test quantile normalization with identical columns."""
        df = pd.DataFrame({"A": [1, 2, 3], "B": [1, 2, 3]})
        result = qn_df(df, axis="col")

        # Identical columns should remain identical after QN
        np.testing.assert_array_equal(result["A"].values, result["B"].values)

    def test_qn_original_dataframe_unchanged(self):
        """Test that original DataFrame is not modified."""
        df = QN_TEST_DF.copy()
        original_data = df.copy()

        qn_df(df, axis="col")

        assert_dataframe_unchanged(original_data, df)


class TestQnDfEdgeCases:
    """Test qn_df edge cases and boundary conditions."""

    def test_qn_empty_dataframe(self):
        """Test quantile normalization with empty DataFrame."""
        result = qn_df(EMPTY_DF, axis="col")
        assert result.empty

    def test_qn_all_missing_values(self):
        """Test quantile normalization with all missing values."""
        df = pd.DataFrame({"A": [np.nan, np.nan], "B": [np.nan, np.nan]})
        result = qn_df(df, axis="col")

        # All values should remain NaN
        assert result.isna().all().all()

    def test_qn_single_row(self):
        """Test quantile normalization with single row."""
        df = pd.DataFrame({"A": [1], "B": [2]})
        result = qn_df(df, axis="col")

        assert result.shape == df.shape

    def test_qn_with_duplicate_values(self):
        """Test quantile normalization with duplicate values."""
        df = pd.DataFrame({"A": [1, 1, 2], "B": [3, 3, 4]})
        result = qn_df(df, axis="col")

        assert result.shape == df.shape
        assert isinstance(result, pd.DataFrame)


# =============================================================================
# CALC_COMMON_DIST FUNCTION TESTS
# =============================================================================


class TestCalcCommonDist:
    """Test calc_common_dist function with various input scenarios."""

    def test_basic_common_distribution(self):
        """Test basic common distribution calculation."""
        df = pd.DataFrame({"A": [3, 2, 1], "B": [30, 20, 10]})
        result = calc_common_dist(df)

        # Should return mean of sorted columns
        assert len(result) == len(df)
        assert isinstance(result, np.ndarray)

        # Result should be in descending order
        assert np.all(result[:-1] >= result[1:])

    def test_common_dist_single_column(self):
        """Test common distribution with single column."""
        df = pd.DataFrame({"A": [3, 2, 1]})
        result = calc_common_dist(df)

        # With single column, common dist should be the sorted column
        expected = np.array([3, 2, 1], dtype=float)
        np.testing.assert_array_equal(result, expected)

    def test_common_dist_identical_values(self):
        """Test common distribution with identical values."""
        df = pd.DataFrame({"A": [5, 5, 5], "B": [5, 5, 5]})
        result = calc_common_dist(df)

        # All values should be 5
        expected = np.array([5, 5, 5], dtype=float)
        np.testing.assert_array_equal(result, expected)

    def test_common_dist_empty_dataframe(self):
        """Test common distribution with empty DataFrame."""
        result = calc_common_dist(EMPTY_DF)
        assert len(result) == 0

    def test_common_dist_with_nan_values(self):
        """Test common distribution with NaN values."""
        df = pd.DataFrame({"A": [3, np.nan, 1], "B": [30, 20, np.nan]})
        result = calc_common_dist(df)

        # Should handle NaN appropriately
        assert len(result) == len(df)
        assert isinstance(result, np.ndarray)


# =============================================================================
# SWAP_IN_COMMON_DIST FUNCTION TESTS
# =============================================================================


class TestSwapInCommonDist:
    """Test swap_in_common_dist function with various scenarios."""

    def test_basic_swap_operation(self):
        """Test basic swap in common distribution."""
        df = pd.DataFrame({"A": [3, 2, 1], "B": [1, 2, 3]})
        common_dist = np.array([2.0, 2.0, 2.0])  # All same for simplicity

        result = swap_in_common_dist(df, common_dist)

        assert result.shape == df.shape
        assert list(result.index) == list(df.index)
        assert list(result.columns) == list(df.columns)

        # All values should be from common_dist
        assert (result == 2.0).all().all()

    def test_swap_single_column(self):
        """Test swap with single column."""
        df = pd.DataFrame({"A": [3, 2, 1]})
        common_dist = np.array([10.0, 20.0, 30.0])

        result = swap_in_common_dist(df, common_dist)
        assert result.shape == df.shape

    def test_swap_empty_dataframe(self):
        """Test swap with empty DataFrame."""
        result = swap_in_common_dist(EMPTY_DF, np.array([]))
        assert result.empty

    def test_swap_with_tied_values(self):
        """Test swap with tied values in input."""
        df = pd.DataFrame({"A": [3, 2, 2], "B": [1, 1, 3]})
        common_dist = np.array([10.0, 20.0, 30.0])

        result = swap_in_common_dist(df, common_dist)
        assert result.shape == df.shape
        # Result may contain NaN due to tie-handling limitations

    def test_swap_mismatched_lengths(self):
        """Test swap with mismatched common_dist length."""
        df = pd.DataFrame({"A": [1, 2, 3]})
        common_dist = np.array([10.0, 20.0])  # Shorter than df

        result = swap_in_common_dist(df, common_dist)
        assert isinstance(result, pd.DataFrame)
        assert result.shape == df.shape


# =============================================================================
# UMI_NORM FUNCTION TESTS
# =============================================================================


class TestUmiNorm:
    """Test umi_norm function with various input scenarios."""

    def test_basic_umi_normalization(self):
        """Test basic UMI normalization."""
        df = UMI_TEST_DF.copy()
        result = umi_norm(df)

        assert_umi_normalization_correct(df, result)
        assert result.shape == df.shape

    def test_umi_norm_with_zero_column_sums(self):
        """Test UMI normalization with zero column sums."""
        df = pd.DataFrame({"sample1": [0, 0], "sample2": [100, 200]})
        result = umi_norm(df)

        # sample1 should have inf or NaN due to division by zero
        assert np.any(np.isinf(result["sample1"]) | np.isnan(result["sample1"]))

        # sample2 should sum to 1.0
        assert np.allclose(result["sample2"].sum(), 1.0, atol=STATISTICAL_TOLERANCE)

    def test_umi_norm_with_negative_values(self):
        """Test UMI normalization with negative values."""
        df = pd.DataFrame({"sample1": [-50, 100], "sample2": [200, 300]})
        result = umi_norm(df)

        # Should handle negative values (though biologically unusual)
        assert result.shape == df.shape

    def test_umi_norm_single_sample(self):
        """Test UMI normalization with single sample."""
        df = pd.DataFrame({"sample1": [100, 200, 300]})
        result = umi_norm(df)

        assert np.allclose(result.sum().iloc[0], 1.0, atol=STATISTICAL_TOLERANCE)

    def test_umi_norm_original_unchanged(self):
        """Test that original DataFrame is not modified."""
        df = UMI_TEST_DF.copy()
        original_data = df.copy()

        umi_norm(df)

        assert_dataframe_unchanged(original_data, df)

    def test_umi_norm_empty_dataframe(self):
        """Test UMI normalization with empty DataFrame."""
        result = umi_norm(EMPTY_DF)
        assert result.empty


# =============================================================================
# Z_CLIP_FUN FUNCTION TESTS
# =============================================================================


class TestZClipFun:
    """Test z_clip_fun function with various clipping scenarios."""

    @pytest.mark.parametrize("lower,upper", CLIP_BOUNDS_TEST_CASES)
    def test_clipping_bounds_combinations(self, lower, upper):
        """Test various combinations of clipping bounds."""
        df = pd.DataFrame({"A": [-5, 0, 5], "B": [-10, 2, 10]})
        result = z_clip_fun(df, lower=lower, upper=upper)

        assert_values_clipped_correctly(result, lower, upper)
        assert result.shape == df.shape

    def test_clipping_specific_values(self):
        """Test clipping with specific value checks."""
        df = pd.DataFrame({"A": [-5, 0, 5], "B": [-10, 2, 10]})
        result = z_clip_fun(df, lower=-3, upper=3)

        # Check specific clipped values
        assert result.loc[0, "A"] == -3  # Was -5, clipped to -3
        assert result.loc[2, "A"] == 3  # Was 5, clipped to 3
        assert result.loc[1, "A"] == 0  # Was 0, unchanged
        assert result.loc[0, "B"] == -3  # Was -10, clipped to -3
        assert result.loc[2, "B"] == 3  # Was 10, clipped to 3

    def test_clipping_with_nan_values_preserved(self):
        """Test clipping preserves NaN values."""
        df = pd.DataFrame({"A": [-5, np.nan, 5]})
        result = z_clip_fun(df, lower=-2, upper=2)

        # NaN should be preserved
        assert np.isnan(result.iloc[1, 0])
        assert result.iloc[0, 0] == -2
        assert result.iloc[2, 0] == 2

    def test_clipping_no_bounds_unchanged(self):
        """Test clipping with no bounds leaves data unchanged."""
        df = pd.DataFrame({"A": [-5, 0, 5]})
        result = z_clip_fun(df, lower=None, upper=None)

        pd.testing.assert_frame_equal(result, df)

    def test_clipping_original_unchanged(self):
        """Test that original DataFrame is not modified."""
        df = pd.DataFrame({"A": [-5, 0, 5]})
        original_data = df.copy()

        z_clip_fun(df, lower=-2, upper=2)

        assert_dataframe_unchanged(original_data, df)

    def test_clipping_empty_dataframe(self):
        """Test clipping with empty DataFrame."""
        result = z_clip_fun(EMPTY_DF, lower=-1, upper=1)
        assert result.empty


# =============================================================================
# INTEGRATION AND ERROR HANDLING TESTS
# =============================================================================


class TestIntegrationScenarios:
    """Test integration scenarios combining multiple functions."""

    def test_complete_zscore_pipeline(self, standard_mock_net):
        """Test complete z-score normalization pipeline."""
        standard_mock_net.dat_to_df.return_value = ZSCORE_TEST_DF

        run_norm(standard_mock_net, norm_type="zscore", axis="row", z_clip=2.0)

        # Verify complete pipeline execution
        standard_mock_net.df_to_dat.assert_called_once()
        assert "pre_zscore" in standard_mock_net.dat

    def test_quantile_normalization_pipeline(self):
        """Test complete quantile normalization pipeline."""
        df = pd.DataFrame({"A": [1, 2, 3, 4], "B": [10, 20, 30, 40], "C": [100, 200, 300, 400]})

        result = qn_df(df, axis="col")

        assert result.shape == df.shape
        # After QN, columns should have more similar distributions

    @pytest.mark.parametrize("norm_type", NORM_TYPES)
    def test_normalization_with_missing_data(self, norm_type):
        """Test all normalization methods handle missing data appropriately."""
        df = pd.DataFrame({"A": [1, np.nan, 3], "B": [np.nan, 5, 6], "C": [7, 8, np.nan]})

        if norm_type == "zscore":
            result, _, _ = zscore_df(df, axis="col")
        elif norm_type == "qn":
            result = qn_df(df, axis="col")
        elif norm_type == "umi":
            result = umi_norm(df)

        assert result.shape == df.shape
        assert isinstance(result, pd.DataFrame)


class TestErrorHandlingAndBoundaryConditions:
    """Test error handling and boundary conditions across functions."""

    def test_functions_with_non_numeric_data(self):
        """Test functions with non-numeric data raise appropriate errors."""
        df = pd.DataFrame({"A": ["a", "b", "c"], "B": [1, 2, 3]})

        # These should fail with appropriate errors
        with pytest.raises((TypeError, ValueError)):
            zscore_df(df, axis="col")

        with pytest.raises((TypeError, ValueError)):
            umi_norm(df)

    def test_functions_with_extremely_large_values(self):
        """Test functions handle extremely large values gracefully."""
        df = LARGE_VALUES_DF.copy()

        # Should handle large values or fail gracefully
        try:
            result_df, _, _ = zscore_df(df, axis="col")
            assert isinstance(result_df, pd.DataFrame)
        except (OverflowError, ValueError):
            # Acceptable if system can't handle extremely large values
            pass

    def test_functions_with_infinite_values(self):
        """Test functions handle infinite values appropriately."""
        df = INFINITE_VALUES_DF.copy()

        # Should handle infinite values or fail gracefully
        try:
            zscore_result, _, _ = zscore_df(df, axis="col")
            assert isinstance(zscore_result, pd.DataFrame)
        except (ValueError, TypeError):
            # Acceptable if function can't handle inf
            pass

    def test_all_zero_dataframe_behavior(self):
        """Test functions with all-zero DataFrame."""
        df = ZERO_DF.copy()

        # Z-score should produce NaN (std=0)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            zscore_result, _, _ = zscore_df(df, axis="col")
        assert zscore_result.isna().all().all()

        # UMI norm should produce NaN (division by 0)
        umi_result = umi_norm(df)
        assert umi_result.isna().all().all()

    def test_single_value_dataframes(self):
        """Test functions with single-value DataFrames."""
        df = SINGLE_VALUE_DF.copy()

        # Should handle single values gracefully
        zscore_result, _, _ = zscore_df(df, axis="col")
        assert zscore_result.shape == (1, 1)

        qn_result = qn_df(df, axis="col")
        assert qn_result.shape == (1, 1)

        umi_result = umi_norm(df)
        assert umi_result.shape == (1, 1)

    @pytest.mark.parametrize(
        "test_df",
        [
            create_test_data_with_properties(has_nan=True),
            create_test_data_with_properties(has_constant_cols=True),
            create_test_data_with_properties(has_zero_cols=True),
            create_test_data_with_properties(has_negative=True),
            create_test_data_with_properties(single_row=True),
            create_test_data_with_properties(single_col=True),
        ],
    )
    def test_robustness_across_data_types(self, test_df):
        """Test function robustness across various data characteristics."""
        # All functions should handle various data types without crashing
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                zscore_result, _, _ = zscore_df(test_df, axis="col")
            assert isinstance(zscore_result, pd.DataFrame)
        except (ValueError, TypeError):
            pass  # Some data types may legitimately fail

        try:
            qn_result = qn_df(test_df, axis="col")
            assert isinstance(qn_result, pd.DataFrame)
        except (ValueError, TypeError):
            pass

        try:
            umi_result = umi_norm(test_df)
            assert isinstance(umi_result, pd.DataFrame)
        except (ValueError, TypeError):
            pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
