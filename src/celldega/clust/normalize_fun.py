from typing import Literal
import warnings

import numpy as np
import pandas as pd


def run_norm(
    net,
    df: pd.DataFrame | None = None,
    norm_type: Literal["zscore", "qn", "umi"] = "zscore",
    axis: Literal["row", "col"] = "row",
    z_clip: float | None = None,
) -> None:
    """Apply normalization to DataFrame and update network object.

    Args:
        net: Network object with dat_to_df, df_to_dat methods and dat dictionary
        df: DataFrame to normalize. If None, uses net.dat_to_df()
        norm_type: Normalization type - "zscore", "qn", or "umi"
        axis: Normalization axis - "row" or "col"
        z_clip: Optional positive clipping threshold for z-scores

    Raises:
        ValueError: If parameters are invalid
    """
    if norm_type not in {"zscore", "qn", "umi"}:
        raise ValueError(f"Invalid norm_type '{norm_type}'. Must be 'zscore', 'qn', or 'umi'")

    if axis not in {"row", "col"}:
        raise ValueError(f"Invalid axis '{axis}'. Must be 'row' or 'col'")

    if z_clip is not None and z_clip <= 0:
        raise ValueError(f"z_clip must be positive, got {z_clip}")

    if df is None:
        df = net.dat_to_df()

    if norm_type == "zscore":
        df, ser_mean, ser_std = zscore_df(df, axis, z_clip=z_clip)
        net.dat["pre_zscore"] = {
            "mean": ser_mean.values.tolist(),
            "std": ser_std.values.tolist(),
        }
    elif norm_type == "qn":
        df = qn_df(df, axis)
    elif norm_type == "umi":
        df = umi_norm(df)

    net.df_to_dat(df)


def qn_df(df: pd.DataFrame, axis: Literal["row", "col"] = "row") -> pd.DataFrame:
    """Apply quantile normalization to DataFrame.

    Quantile normalization ensures all samples have the same distribution
    by replacing values with the mean of values at the same quantile.

    Args:
        df: Input DataFrame
        axis: Normalization axis - "col" normalizes columns, "row" normalizes rows

    Returns:
        Quantile normalized DataFrame with same shape as input
    """
    if df.empty:
        return df

    work_df = df.T if axis == "row" else df

    # Optimized null checking - single scan
    has_nulls = work_df.isnull()
    missing_mask = has_nulls if has_nulls.any().any() else None

    if missing_mask is not None:
        work_df = work_df.fillna(0)

    # Calculate common distribution and apply
    common_dist = calc_common_dist(work_df)
    work_df = swap_in_common_dist(work_df, common_dist)

    if missing_mask is not None:
        work_df = work_df.mask(missing_mask, np.nan)

    return work_df.T if axis == "row" else work_df


def zscore_df(
    df: pd.DataFrame, axis: Literal["row", "col"] = "row", z_clip: float | None = None
) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    """Apply z-score normalization to DataFrame.

    Args:
        df: Input DataFrame
        axis: Normalization axis - "row" or "col"
        z_clip: Optional clipping threshold

    Returns:
        Tuple of (normalized_df, means, stds)

    Warns:
        UserWarning: If constant columns are detected (std=0)
    """
    if df.empty:
        return df, pd.Series(dtype=float), pd.Series(dtype=float)

    work_df = df.T if axis == "row" else df
    means, stds = work_df.mean(), work_df.std()

    # Warn about constant columns
    if (stds == 0).any():
        warnings.warn(
            "Constant columns detected in z-score normalization. "
            "These will produce inf/NaN values.",
            UserWarning,
            stacklevel=2,
        )

    normalized = (work_df - means) / stds

    if z_clip is not None:
        normalized = normalized.clip(lower=-z_clip, upper=z_clip)

    result = normalized.T if axis == "row" else normalized
    return result, means, stds


def umi_norm(df: pd.DataFrame) -> pd.DataFrame:
    """Apply UMI normalization - divide each column by its sum.

    Each column is normalized by its total count to account for
    library size differences in sequencing data.

    Args:
        df: Input DataFrame with samples as columns

    Returns:
        UMI normalized DataFrame
    """
    return df if df.empty else df.div(df.sum(axis=0), axis=1)


def z_clip_fun(
    df: pd.DataFrame, lower: float | None = None, upper: float | None = None
) -> pd.DataFrame:
    """Clip DataFrame values to specified thresholds.

    Args:
        df: Input DataFrame
        lower: Lower clipping threshold
        upper: Upper clipping threshold

    Returns:
        Clipped DataFrame
    """
    return df.clip(lower=lower, upper=upper)


def calc_common_dist(df: pd.DataFrame) -> np.ndarray:
    """Calculate common distribution for quantile normalization.

    Computes the mean of sorted values across all columns to create
    a common distribution for quantile normalization.

    Args:
        df: Input DataFrame with columns to normalize

    Returns:
        Common distribution array
    """
    if df.empty:
        return np.array([])

    # Optimized: collect all sorted arrays first
    sorted_arrays = [df[col].sort_values(ascending=False).values for col in df.columns]

    # Handle single column case
    if len(sorted_arrays) == 1:
        return sorted_arrays[0]

    # Stack vertically then transpose (matches original)
    stacked = np.vstack(sorted_arrays).T
    return stacked.mean(axis=1)


def swap_in_common_dist(df: pd.DataFrame, common_dist: np.ndarray) -> pd.DataFrame:
    """Apply common distribution values based on ranking.

    Maps each value to its corresponding position in the common distribution
    based on the value's rank within its column.

    Args:
        df: Input DataFrame
        common_dist: Common distribution values to apply

    Returns:
        DataFrame with common distribution applied
    """
    if df.empty or len(common_dist) == 0:
        return df

    result_data = {}

    for col in df.columns:
        # Replicate original algorithm: sort descending, get positional indices
        sorted_series = df[col].sort_values(ascending=False)
        position_map = {idx: pos for pos, idx in enumerate(sorted_series.index)}

        # Pre-allocate result array for performance
        col_result = np.full(len(df), np.nan)

        for i, idx in enumerate(df.index):
            try:
                position = position_map[idx]
                if position < len(common_dist):
                    col_result[i] = common_dist[position]
            except KeyError:
                pass  # col_result[i] already set to NaN

        result_data[col] = col_result

    return pd.DataFrame(result_data, index=df.index)
