import os
import glob
import zarr
import tifffile
import pandas as pd
import numpy as np
import geopandas as gpd
import matplotlib.pyplot as plt
import rasterio
from rasterio.mask import mask
from rasterstats import zonal_stats
from rasterio.io import MemoryFile
from shapely.geometry import Polygon, MultiPolygon
from shapely.affinity import scale
from PIL import Image, ImageEnhance
from ..pre.boundary_tile import numpy_affine_transform, batch_transform_geometries, get_cell_polygons

def open_zarr(path: str) -> zarr.Group:

    """
    Opens a Zarr dataset from a given path.
    
    Args:
        path (str): Path to the Zarr dataset (either .zip or directory store).
    
    Returns:
        zarr.Group: The root group of the opened Zarr dataset.
    """

    store = (zarr.ZipStore(path, mode="r")
    if path.endswith(".zip")
    else zarr.DirectoryStore(path)
    )
    return zarr.group(store=store)

def process_row(row):
    
    """
    Extracts the largest polygon from a MultiPolygon geometry.
    
    Args:
        row (pd.Series): A row containing a geometry column.
    
    Returns:
        pd.Series: The updated row with the largest polygon.
    """

    geometry = row['geometry']

    if geometry.geom_type == "MultiPolygon" and len(geometry.geoms) > 0:
        largest_polygon = max(geometry.geoms, key=lambda p: p.area)
        row['geometry'] = largest_polygon

    return row

def image_contrast_adjustment(base_path, technology_name, contrast_factor=5, intensity_threshold=100):

    """
    Adjusts the contrast of an image and filters bright stain regions.
    
    Args:
        base_path (str): Base directory where images are stored.
        technology_name (str): Imaging technology name (MERSCOPE or Xenium).
        contrast_factor (int, optional): Factor by which contrast is enhanced. Defaults to 5.
        intensity_threshold (int, optional): Threshold for filtering bright stain regions. Defaults to 100.
    
    Returns:
        str: Path to the contrast-adjusted image file.
    """

    if technology_name == 'MERSCOPE':
        image_file = (glob.glob(os.path.join(base_path, "images", "*.tif")) + glob.glob(os.path.join(base_path, "images", "*.tiff")))[0]
        stain_image_array = tifffile.imread(image_file)
        stain_image = Image.fromarray(stain_image_array).convert("L")

    elif technology_name == 'Xenium':
        image_file = (glob.glob(os.path.join(base_path, "morphology_focus", "*.tif")) + glob.glob(os.path.join(base_path, "morphology_focus", "*.tiff")))[0]
        stain_image_array = tifffile.imread(image_file, is_ome=False)
        stain_image = Image.fromarray(stain_image_array).convert("L")

    # Plot the original stain image
    plt.figure(figsize=(10, 10))
    plt.imshow(stain_image, cmap='gray')
    plt.title("Original Stain Image")

    enhancer = ImageEnhance.Contrast(stain_image)
    stain_image_with_contrast = enhancer.enhance(contrast_factor)

    # Plot the stain image after contrast adjustment
    plt.figure(figsize=(10, 10))
    plt.imshow(stain_image_with_contrast, cmap='gray')
    plt.title(f"Stain Image with Contrast Factor {contrast_factor}")

    stain_image_with_contrast = np.array(stain_image_with_contrast)
    stain_bright_regions = np.where(stain_image_with_contrast >= intensity_threshold, stain_image_with_contrast, 0)

    # Plot the filtered bright regions
    plt.figure(figsize=(10, 10))
    plt.imshow(stain_bright_regions, cmap='hot')
    plt.title(f"Filtered Bright Regions (Threshold: {intensity_threshold})")
    plt.show()
    plt.close('all')

    tifffile.imwrite(f"{base_path}/contrast_adjusted_stain_image.tif", stain_bright_regions.astype(np.uint8))
    print("Contrast adjusted image (.tif) saved.")

    return f"{base_path}/contrast_adjusted_stain_image.tif"

def process_inputs_for_quantification(technology_name, transformation_matrix, base_path, image_contrast_required=False, contrast_factor=5, intensity_threshold=100):

    """
    Processes cell boundary data and applies transformations for quantification.
    
    Args:
        technology_name (str): Imaging technology name (MERSCOPE or Xenium).
        transformation_matrix (np.ndarray): Transformation matrix for coordinate adjustments.
        base_path (str): Base directory for output files.
        image_contrast_required (bool, optional): Whether contrast adjustment is required. Defaults to False.
        contrast_factor (int, optional): Contrast enhancement factor. Defaults to 5.
        intensity_threshold (int, optional): Brightness threshold for filtering. Defaults to 100.
    
    Returns:
        gpd.GeoDataFrame or tuple: Processed cell polygons with or without contrast-adjusted image path.
    """

    cell_boundary_file = os.path.join(base_path, "cell_boundaries.parquet")

    if technology_name == 'MERSCOPE':
        gdf = pd.read_parquet(cell_boundary_file)
        merged_gdf = gdf.dissolve(by='EntityID').reset_index().rename(columns={'EntityID': 'cell_index', 'Geometry': 'geometry'})
      
    elif technology_name == 'Xenium':
        merged_gdf = get_cell_polygons(technology=technology_name, path_cell_boundaries=cell_boundary_file)
        merged_gdf = merged_gdf.reset_index().rename(columns={'cell_id': 'cell_index'})

    merged_gdf = merged_gdf.apply(process_row, axis=1)
    merged_gdf["transformed_geometry"] = batch_transform_geometries(merged_gdf["geometry"], transformation_matrix, scale=1)
    merged_gdf["polygons"] = merged_gdf["transformed_geometry"].apply(lambda x: Polygon(x[0]))

    transformed_cells = gpd.GeoDataFrame({'cell_index': merged_gdf['cell_index']}, geometry=merged_gdf['polygons'])
    transformed_cells.to_parquet(f"{base_path}/transformed_cell_polygons.parquet")

    if image_contrast_required:
        contrast_adjusted_image_file = image_contrast_adjustment(base_path=base_path, technology_name=technology_name, contrast_factor=contrast_factor, intensity_threshold=intensity_threshold)
        return (transformed_cells, contrast_adjusted_image_file)
    else:
        return transformed_cells
    
def calculate_stain_intensities(image_file, cell_polygons, technology_name):

    """
    Computes the mean and sum intensity values of a stain image within segmented cell polygons.
    
    Args:
        image_file (str): Path to the stain image file (original image file or a contrast-adjusted image file).
        cell_polygons (gpd.GeoDataFrame): GeoDataFrame containing segmented cell polygons.
        technology_name (str): Imaging technology (MERSCOPE or Xenium).
    
    Returns:
        - gpd.GeoDataFrame: Updated cell polygons with computed stain intensity values.
        - np.ndarray: Log-transformed sum intensities of the stain.
        - np.ndarray: Bin edges for histogram plotting of log-normalized intensities.
    """

    if technology_name == 'Xenium':

        image_array = tifffile.imread(image_file, is_ome=False)

        meta = {
            "driver": "GTiff",
            "dtype": image_array.dtype,
            "count": 1 if image_array.ndim == 2 else image_array.shape[0],  # Handle single/multi-channel
            "height": image_array.shape[-2],
            "width": image_array.shape[-1],
            "nodata": None,
        }

        with MemoryFile() as memfile:
            with memfile.open(**meta) as src:
                src.write(image_array if image_array.ndim == 2 else image_array[0], 1)

                image_crs = src.crs

                if cell_polygons.crs and cell_polygons.crs != image_crs:
                    cell_polygons = cell_polygons.to_crs(image_crs)
                
                intensities, sum_intensities = [], []
                for polygon in cell_polygons.geometry:
                    try:
                        out_image, _ = mask(src, [polygon], crop=True)
                        pixel_values = out_image[0].flatten()
                        pixel_values = pixel_values[pixel_values != src.nodata]
                
                        mean_intensity = pixel_values.mean() if len(pixel_values) > 0 else 0
                        sum_intensity = np.sum(pixel_values) if len(pixel_values) > 0 else 0
                    except ValueError:
                        mean_intensity, sum_intensity = 0, 0
                    
                    intensities.append(mean_intensity)
                    sum_intensities.append(sum_intensity)

    elif technology_name == 'MERSCOPE':

        with rasterio.open(image_file) as src:
            image_crs = src.crs

            if cell_polygons.crs != image_crs:
                cell_polygons = cell_polygons.to_crs(image_crs)

            intensities, sum_intensities = [], []
            for polygon in cell_polygons.geometry:
                try:
                    out_image, _ = mask(src, [polygon], crop=True)
                    pixel_values = out_image[0].flatten()
                    pixel_values = pixel_values[pixel_values != src.nodata]

                    mean_intensity = pixel_values.mean() if len(pixel_values) > 0 else 0
                    sum_intensity = np.sum(pixel_values) if len(pixel_values) > 0 else 0
                except ValueError:
                    mean_intensity, sum_intensity = 0, 0

                intensities.append(mean_intensity)
                sum_intensities.append(sum_intensity)

    cell_polygons["mean_stain_intensity"] = intensities
    cell_polygons["sum_stain_intensity"] = sum_intensities

    log_transformed_stain_intensities = np.log1p(cell_polygons['sum_stain_intensity'])

    # Normalize the log-transformed intensities to the range [0, 1]
    log_normalized_stain_intensities = (log_transformed_stain_intensities - log_transformed_stain_intensities.min()) / \
                                     (log_transformed_stain_intensities.max() - log_transformed_stain_intensities.min())

    # Plot the histogram of log-normalized stain intensities

    stain_image = tifffile.imread(image_file, is_ome=False)
    fig, ax = plt.subplots(figsize=(40, 40))
    ax.imshow(stain_image)
    cell_polygons.plot(ax=ax, alpha=1, linewidth=1, facecolor='none', edgecolor='red')
    plt.title("Overlay of all stain-positive cells on stain image", fontsize=40)
    plt.xticks(fontsize=40)
    plt.yticks(fontsize=40)

    fig, ax = plt.subplots(figsize=(15, 9))
    counts, bin_edges, _ = plt.hist(log_normalized_stain_intensities, bins=50, edgecolor='black', alpha=0.7)
    plt.title('Distribution of Log-Normalized Stain Intensities')
    plt.xlabel('Log-Normalized Intensity Values')
    plt.ylabel('Frequency of Occurrence')
    plt.show()
    plt.close('all')

    return cell_polygons, log_transformed_stain_intensities, bin_edges

def filtering_stain_positive_cells(highlighted_bin, bin_edges, log_transformed_stain_intensities, cell_polygons_with_metadata, base_path, technology_name, use_contrast_adjusted_image=False):
    
    """
    Filters stain-positive cells based on stain intensity thresholds and overlays them on the stain image.
    
    Args:
        highlighted_bin (float): The bin (according to the x-axis) representing the threshold for filtering stain-positive cells.
        bin_edges (np.ndarray): Bin edges used for histogram binning of intensities.
        log_transformed_stain_intensities (np.ndarray): Log-transformed stain intensities.
        cell_polygons_with_metadata (gpd.GeoDataFrame): GeoDataFrame containing cell polygon geometries and stain intensity metadata.
        base_path (str): Base directory where images and results are stored.
        technology_name (str): Imaging technology used (MERSCOPE or Xenium).
        use_contrast_adjusted_image (bool, optional): Whether to use the contrast-adjusted image for visualization. Defaults to False.
    
    Returns:
        None: Saves the filtered stain-positive cells data to a CSV file and displays an overlay plot.
    """

    if use_contrast_adjusted_image:
        stain_image = tifffile.imread(f"{base_path}/contrast_adjusted_stain_image.tif")
    else:
        if technology_name == 'MERSCOPE':
            image_file = (glob.glob(os.path.join(base_path, "images", "*.tif")) + glob.glob(os.path.join(base_path, "images", "*.tiff")))[0]
            stain_image = tifffile.imread(image_file)
        elif technology_name == 'Xenium':
            image_file = (glob.glob(os.path.join(base_path, "morphology_focus", "*.tif")) + glob.glob(os.path.join(base_path, "morphology_focus", "*.tiff")))[0]
            stain_image = tifffile.imread(image_file, is_ome=False)
    
    bin_index = np.where((bin_edges[:-1] <= highlighted_bin) & (bin_edges[1:] > highlighted_bin))[0][0]
    bin_start, bin_end = bin_edges[bin_index], bin_edges[bin_index + 1]
    original_start = np.expm1(bin_start * (log_transformed_stain_intensities.max() - log_transformed_stain_intensities.min()) + log_transformed_stain_intensities.min())

    filtered_cells = cell_polygons_with_metadata[cell_polygons_with_metadata['sum_stain_intensity'] > original_start]

    fig, ax = plt.subplots(figsize=(40, 40))
    ax.imshow(stain_image)
    filtered_cells.plot(ax=ax, alpha=1, linewidth=1, facecolor='none', edgecolor='red')
    plt.title("Overlay of filtered stain-positive cells on stain image", fontsize=40)
    plt.xticks(fontsize=40)
    plt.yticks(fontsize=40)
    plt.show()
    plt.close('all')

    filtered_cells.to_csv(f'{base_path}/filtered_stain_positive_cells.csv')

    print("Filtered stain positive cells data (.csv) saved. Filtering done.")

def image_quantification(base_path, technology_name, image_contrast_required=False, contrast_factor=5, intensity_threshold=100):
    
    """
    Performs image quantification by extracting stain intensities and processing cell boundaries.
    
    Args:
        base_path (str): The base directory containing input images and metadata.
        technology_name (str): The imaging technology used (MERSCOPE or Xenium).
        image_contrast_required (bool, optional): Whether contrast adjustment is needed. Defaults to False.
        contrast_factor (int, optional): Factor by which contrast is enhanced if required. Defaults to 5.
        intensity_threshold (int, optional): Intensity threshold for filtering bright stain regions. Defaults to 100.
    
    Returns:
        - gpd.GeoDataFrame: Processed cell polygons with stain intensity metadata.
        - np.ndarray: Log-transformed sum intensities of the stain.
        - np.ndarray: Bin edges for histogram visualization of intensity distribution.
    """

    if technology_name == 'MERSCOPE':
        image_file = (glob.glob(os.path.join(base_path, "images", "*.tif")) + glob.glob(os.path.join(base_path, "images", "*.tiff")))[0]
        transformation_matrix = pd.read_csv(os.path.join(base_path, "images", "micron_to_mosaic_pixel_transform.csv")).values

    elif technology_name == 'Xenium':
        image_file = (glob.glob(os.path.join(base_path, "morphology_focus", "*.tif")) + glob.glob(os.path.join(base_path, "morphology_focus", "*.tiff")))[0]
        root = open_zarr(base_path + "cells.zarr.zip")
        transformation_matrix = root['masks']['homogeneous_transform'][:]

    processing_outputs = process_inputs_for_quantification(
        technology_name, transformation_matrix, base_path, image_contrast_required, contrast_factor, intensity_threshold)

    if type(processing_outputs) == tuple:
        cell_polygons_with_metadata, log_transformed_stain_intensities, bin_edges = calculate_stain_intensities(
                                        image_file=processing_outputs[1], cell_polygons=processing_outputs[0], technology_name=technology_name)
    else:
        cell_polygons_with_metadata, log_transformed_stain_intensities, bin_edges = calculate_stain_intensities(
                                        image_file=image_file, cell_polygons=processing_outputs, technology_name=technology_name)
        
    print("Image quantification and filtering done.")
    return cell_polygons_with_metadata, log_transformed_stain_intensities, bin_edges