"""
Module for zonal stats extraction from imagery data 
using mask (numpy array) or polygons (GeoDataFrame).
"""

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import rasterize
from shapely.geometry import mapping
import pandas as pd

def calc_img_zonal_stats(
    polygon_src, 
    img, 
    unique_polygon_col_name='name', 
    channel_names=None,
    stats_funcs=['mean'],
):
    """
    Calculate zonal statistics for each polygon from a multi-channel image.

    Parameters:
    - polygon_src: Either:
        - GeoDataFrame containing polygon geometries and a unique identifier column
        - 2D NumPy array mask where each unique value represents a different polygon
    - img: 3D NumPy array (H, W, C) representing the multi-channel image.
    - unique_polygon_col_name: Column name in GeoDataFrame containing unique polygon identifiers.
    - channel_names: dict mapping channel indices to channel names.
    - stats_funcs: List of strings/functions specifying statistics to calculate.

    Returns:
    - GeoDataFrame (if input was GeoDataFrame) or DataFrame containing all statistics
      with columns in format: polygon_id, {channel}_{stat}, geometry (if GeoDataFrame)
    """
    # Standard statistics mapping
    STATS_FUNCS = {
        'mean': np.nanmean,
        'median': np.nanmedian,
        'std': np.nanstd,
        'min': np.nanmin,
        'max': np.nanmax,
        'sum': np.nansum,
    }

    # Process stats_funcs argument
    if not isinstance(stats_funcs, list):
        stats_funcs = [stats_funcs]

    # Prepare functions and names
    funcs = []
    metric_names = []
    
    for stat in stats_funcs:
        if isinstance(stat, str):
            if stat.startswith('percentile_'):
                try:
                    q = float(stat.split('_')[1])
                    funcs.append(lambda x, q=q: np.nanpercentile(x, q))
                    metric_names.append(f'p{q}')
                except (IndexError, ValueError):
                    raise ValueError(f"Invalid percentile specification: {stat}")
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

    height, width, num_channels = img.shape
    transform = rasterio.transform.from_origin(0, height, 1, 1)
    
    # Initialize result collection
    all_results = []
    polygon_info = []

    if isinstance(polygon_src, gpd.GeoDataFrame):
        # Process GeoDataFrame
        for idx, row in polygon_src.iterrows():
            polygon = row.geometry
            polygon_name = row[unique_polygon_col_name]
            polygon_info.append({'polygon_id': polygon_name, 'geometry': polygon})

            mask = rasterize(
                [(mapping(polygon), 1)],
                out_shape=(height, width),
                transform=transform,
                fill=0,
                all_touched=True,
                dtype=np.uint8
            )

            # Compute all stats for all channels
            channel_results = {}
            for ch in range(num_channels):
                masked_data = img[:, :, ch][mask == 1]
                ch_name = channel_names.get(ch, f'channel_{ch}') if channel_names else f'channel_{ch}'
                
                for func, name in zip(funcs, metric_names):
                    stat_value = func(masked_data) if masked_data.size > 0 else np.nan
                    col_name = f"{ch_name}_{name}"
                    channel_results[col_name] = stat_value
            
            channel_results['polygon_id'] = polygon_name
            all_results.append(channel_results)
    else:
        # Process numpy array mask
        unique_polygon_ids = np.unique(polygon_src)
        unique_polygon_ids = unique_polygon_ids[unique_polygon_ids != 0]
        
        for polygon_id in unique_polygon_ids:
            polygon_info.append({'polygon_id': polygon_id})
            mask = (polygon_src == polygon_id)

            channel_results = {}
            for ch in range(num_channels):
                masked_data = img[:, :, ch][mask]
                ch_name = channel_names.get(ch, f'channel_{ch}') if channel_names else f'channel_{ch}'
                
                for func, name in zip(funcs, metric_names):
                    stat_value = func(masked_data) if masked_data.size > 0 else np.nan
                    col_name = f"{ch_name}_{name}"
                    channel_results[col_name] = stat_value
            
            channel_results['polygon_id'] = polygon_id
            all_results.append(channel_results)

    return pd.DataFrame(all_results)