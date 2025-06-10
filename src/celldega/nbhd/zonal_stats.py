from collections.abc import Callable, Sequence
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize
from shapely.geometry import mapping
from shapely.geometry.base import BaseGeometry


def _prepare_statistics_functions(
    stats_funcs: str | Callable | list[str | Callable],
) -> tuple[list[Callable], list[str]]:
    """Parse stat specs into callables and names."""
    STATS_FUNCS = {
        "mean": np.nanmean,
        "median": np.nanmedian,
        "std": np.nanstd,
        "min": np.nanmin,
        "max": np.nanmax,
        "sum": np.nansum,
    }

    if not isinstance(stats_funcs, list):
        stats_funcs = [stats_funcs]

    funcs = []
    metric_names = []

    for stat in stats_funcs:
        if isinstance(stat, str):
            if stat.startswith("percentile_"):
                try:
                    q = float(stat.split("_")[1])
                    funcs.append(lambda x, q=q: np.nanpercentile(x, q))
                    metric_names.append(f"p{q}")
                except (IndexError, ValueError) as err:
                    raise ValueError(f"Invalid percentile specification: {stat}") from err
            else:
                if stat not in STATS_FUNCS:
                    raise ValueError(f"Unknown statistic: {stat}")
                funcs.append(STATS_FUNCS[stat])
                metric_names.append(stat)
        elif callable(stat):
            funcs.append(stat)
            metric_names.append(stat.__name__)
        else:
            raise ValueError("stats_funcs must contain strings or callables")
    return funcs, metric_names


def _create_polygon_mask(
    polygon: BaseGeometry, height: int, width: int, transform: Any
) -> np.ndarray:
    """Convert geometry to binary mask."""
    return rasterize(
        [(mapping(polygon), 1)],
        out_shape=(height, width),
        transform=transform,
        fill=0,
        all_touched=True,
        dtype=np.uint8,
    )


def _calculate_channel_stats(
    img: np.ndarray,
    mask: np.ndarray,
    funcs: Sequence[Callable],
    metric_names: Sequence[str],
    channel_names: dict[int, str] | None,
) -> dict[str, float]:
    """Compute stats for all channels given a binary mask."""
    num_channels = img.shape[2]
    channel_results = {}
    for ch in range(num_channels):
        masked_data = img[:, :, ch][mask == 1]
        ch_name = channel_names.get(ch, f"channel_{ch}") if channel_names else f"channel_{ch}"
        for func, name in zip(funcs, metric_names, strict=False):
            stat_value = func(masked_data) if masked_data.size > 0 else np.nan
            col_name = f"{ch_name}_{name}"
            channel_results[col_name] = stat_value
    return channel_results


def _process_geodataframe_polygons(
    polygon_src: gpd.GeoDataFrame,
    img: np.ndarray,
    unique_polygon_col_name: str,
    funcs: Sequence[Callable],
    metric_names: Sequence[str],
    channel_names: dict[int, str] | None,
    transform: Any,
) -> list[dict[str, Any]]:
    """Handle GeoDataFrame workflow."""
    height, width, _ = img.shape
    all_results = []
    for _, row in polygon_src.iterrows():
        polygon = row.geometry
        polygon_name = row[unique_polygon_col_name]
        mask = _create_polygon_mask(polygon, height, width, transform)
        channel_stats = _calculate_channel_stats(img, mask, funcs, metric_names, channel_names)
        channel_stats["polygon_id"] = polygon_name
        all_results.append(channel_stats)
    return all_results


def _process_mask_array_polygons(
    polygon_src: np.ndarray,
    img: np.ndarray,
    funcs: Sequence[Callable],
    metric_names: Sequence[str],
    channel_names: dict[int, str] | None,
) -> list[dict[str, Any]]:
    """Handle mask array workflow."""
    _, _, num_channels = img.shape
    unique_polygon_ids = np.unique(polygon_src)
    unique_polygon_ids = unique_polygon_ids[unique_polygon_ids != 0]
    all_results = []
    for polygon_id in unique_polygon_ids:
        mask = polygon_src == polygon_id
        channel_stats = {}
        for ch in range(num_channels):
            masked_data = img[:, :, ch][mask]
            ch_name = channel_names.get(ch, f"channel_{ch}") if channel_names else f"channel_{ch}"
            for func, name in zip(funcs, metric_names, strict=False):
                stat_value = func(masked_data) if masked_data.size > 0 else np.nan
                col_name = f"{ch_name}_{name}"
                channel_stats[col_name] = stat_value
        channel_stats["polygon_id"] = polygon_id
        all_results.append(channel_stats)
    return all_results


def calc_img_zonal_stats(
    polygon_src: gpd.GeoDataFrame | np.ndarray,
    img: np.ndarray,
    unique_polygon_col_name: str = "name",
    channel_names: dict[int, str] | None = None,
    stats_funcs: str | Callable | list[str | Callable] | None = None,
) -> pd.DataFrame:
    """
    Calculate zonal statistics for each polygon from a multi-channel image.
    Returns a DataFrame with columns: polygon_id, {channel}_{stat}, geometry (if GeoDataFrame).
    """
    if stats_funcs is None:
        stats_funcs = ["mean"]

    funcs, metric_names = _prepare_statistics_functions(stats_funcs)
    height, width, _ = img.shape
    transform = rasterio.transform.from_origin(0, height, 1, 1)

    if isinstance(polygon_src, gpd.GeoDataFrame):
        results = _process_geodataframe_polygons(
            polygon_src,
            img,
            unique_polygon_col_name,
            funcs,
            metric_names,
            channel_names,
            transform,
        )
    else:
        results = _process_mask_array_polygons(
            polygon_src,
            img,
            funcs,
            metric_names,
            channel_names,
        )

    return pd.DataFrame(results)
