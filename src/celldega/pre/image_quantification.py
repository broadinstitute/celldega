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
from rasterio.io import MemoryFile
from shapely.geometry import Polygon, box
from shapely import bounds
from shapely.affinity import translate
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

def load_stain_img(image_file, technology_name):

    """
    Load a subset of a TIFF image based on the specified coordinates.

    Parameters:
    -----------
    image_file : str
        Path to the TIFF image file.
    technology_name : str
        Name of the technology.

    Returns:
    --------
    numpy.ndarray
        A 2D array or a list containing 2D arrays representing the extracted region of the image.

    """

    if technology_name == 'MERSCOPE':

        with tifffile.TiffFile(image_file, is_ome=False) as image_file:

            series = image_file.series[0]
            plane = series.pages[0]

            subset_image = plane.asarray()

        return subset_image

    elif technology_name == 'Xenium':

        subset_image = []
        with tifffile.TiffFile(image_file, is_ome=True) as image_file:

            series = image_file.series[0]
            plane = series.pages

        for index in range(4):
            subset_image.append(plane[index].asarray())

        return subset_image

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
    Adjusts the contrast of a stain image and filters bright regions based on an intensity threshold.

    Parameters:
    -----------
    base_path : str
        Base directory where images are stored.
    technology_name : str
        Name of the imaging technology used. Supported values:
        - 'MERSCOPE': Looks for images in the 'images' directory.
        - 'Xenium': Looks for images in the 'morphology_focus' directory.
    contrast_factor : int, optional
        Factor by which the image contrast is enhanced. Higher values increase contrast more. Defaults to 5.
    intensity_threshold : int, optional
        Pixel intensity threshold for filtering bright regions. Pixels above this threshold are retained;
        others are set to zero. Defaults to 100.

    Returns:
    --------
    numpy.ndarray
        A 2D array representing the contrast-adjusted image with bright regions filtered.

    Outputs:
    --------
    - Displays three plots:
        1. The original stain image.
        2. The contrast-enhanced stain image.
        3. The filtered bright regions based on the intensity threshold.
    - Saves the contrast-adjusted image as a TIFF file named 'contrast_adjusted_stain_image.tif' in `base_path`.

    """

    if technology_name == 'MERSCOPE':
        image_file = (glob.glob(os.path.join(base_path, "images", "*.tif")) + glob.glob(os.path.join(base_path, "images", "*.tiff")))[0]
        stain_image_array = load_stain_img(image_file, technology_name)
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

        return stain_bright_regions

    elif technology_name == 'Xenium':
        image_file = (glob.glob(os.path.join(base_path, "morphology_focus", "*.tif")) + glob.glob(os.path.join(base_path, "morphology_focus", "*.tiff")))[0]
        stain_image_array = load_stain_img(image_file, technology_name)

        stain_bright_regions_list = []

        for index in range(4):
            stain_image = Image.fromarray(stain_image_array[index]).convert("L")

            # Plot the original stain image
            plt.figure(figsize=(10, 10))
            plt.imshow(stain_image, cmap='gray')
            plt.title(f"Original Stain Image - Index {index}")

            enhancer = ImageEnhance.Contrast(stain_image)
            stain_image_with_contrast = enhancer.enhance(contrast_factor)

            # Plot the stain image after contrast adjustment
            plt.figure(figsize=(10, 10))
            plt.imshow(stain_image_with_contrast, cmap='gray')
            plt.title(f"Stain Image with Contrast Factor {contrast_factor} - Index {index}")

            stain_image_with_contrast = np.array(stain_image_with_contrast)
            stain_bright_regions = np.where(stain_image_with_contrast >= intensity_threshold, stain_image_with_contrast, 0)

            # Plot the filtered bright regions
            plt.figure(figsize=(10, 10))
            plt.imshow(stain_bright_regions, cmap='hot')
            plt.title(f"Filtered Bright Regions (Threshold: {intensity_threshold}) - Index {index}")
            plt.show()
            plt.close('all')

            tifffile.imwrite(f"{base_path}/contrast_adjusted_stain_image_{index}.tif", stain_bright_regions.astype(np.uint8))
            print(f"Contrast adjusted image (.tif) saved - Index {index}")

            stain_bright_regions_list.append(stain_bright_regions)

        return stain_bright_regions_list

def process_inputs_for_quantification(technology_name, transformation_matrix, base_path, image_contrast_required=False, contrast_factor=5, intensity_threshold=100):

    """
    Processes cell boundary data, applies geometric transformations, and extracts image data for quantification.

    Parameters:
    -----------
    technology_name : str
        Name of the imaging technology used. Supported values:
        - 'MERSCOPE': Uses cell boundary data from 'cell_boundaries.parquet' and extracts images from the 'images' directory.
        - 'Xenium': Uses `get_cell_polygons()` to retrieve cell boundaries and extracts images from the 'morphology_focus' directory.
    transformation_matrix : np.ndarray
        Transformation matrix used to adjust the coordinates of cell boundaries.
    base_path : str
        Base directory where cell boundary and image files are stored.
    image_contrast_required : bool, optional
        If True, applies contrast enhancement to the extracted image. Defaults to False.
    contrast_factor : int, optional
        Factor by which the image contrast is enhanced. Higher values increase contrast more. Defaults to 5.
    intensity_threshold : int, optional
        Pixel intensity threshold for filtering bright regions. Pixels above this threshold are retained; others are set to zero. Defaults to 100.

    Returns:
    --------
    tuple:
        - gpd.GeoDataFrame: Processed cell polygons with transformed coordinates, saved as 'transformed_cell_polygons.parquet'.
        - numpy.ndarray: If `image_contrast_required` is False, returns the extracted stain image as an array.
        - numpy.ndarray: If `image_contrast_required` is True, returns the contrast-adjusted stain image as an array.

    Outputs:
    --------
    - Saves the transformed cell polygons as 'transformed_cell_polygons.parquet' in `base_path`.
    - If `image_contrast_required` is True, the contrast-adjusted stain image is saved as 'contrast_adjusted_stain_image.tif' in `base_path`.

    """

    cell_boundary_file = os.path.join(base_path, "cell_boundaries.parquet")

    if technology_name == 'MERSCOPE':
        image_file = (glob.glob(os.path.join(base_path, "images", "*.tif")) + glob.glob(os.path.join(base_path, "images", "*.tiff")))[0]
        gdf = pd.read_parquet(cell_boundary_file)
        merged_gdf = gdf.dissolve(by='EntityID').reset_index().rename(columns={'EntityID': 'cell_index', 'Geometry': 'geometry'})

    elif technology_name == 'Xenium':
        image_file = (glob.glob(os.path.join(base_path, "morphology_focus", "*.tif")) + glob.glob(os.path.join(base_path, "morphology_focus", "*.tiff")))[0]
        merged_gdf = get_cell_polygons(technology=technology_name, path_cell_boundaries=cell_boundary_file)
        merged_gdf = merged_gdf.reset_index().rename(columns={'cell_id': 'cell_index'})

    merged_gdf = merged_gdf.apply(process_row, axis=1)
    merged_gdf["polygons"] = batch_transform_geometries(merged_gdf["geometry"], transformation_matrix, scale=1)

    transformed_cells = gpd.GeoDataFrame({'cell_index': merged_gdf['cell_index']}, geometry=merged_gdf['polygons'])

    transformed_cells.to_parquet(f"{base_path}/transformed_cell_polygons.parquet")

    if image_contrast_required:
        contrast_adjusted_image = image_contrast_adjustment(base_path=base_path, technology_name=technology_name, contrast_factor=contrast_factor, intensity_threshold=intensity_threshold)
        return (transformed_cells, contrast_adjusted_image)
    else:
        image_array = load_stain_img(image_file, technology_name)
        return (transformed_cells, image_array)

def calc_img_region_stats(image_array, cell_polygons, technology_name):

    """
    Computes zonal statistics (mean and sum intensity) for each cell polygon based on the provided stain image.

    Parameters:
    -----------
    image_array : numpy.ndarray or str
        - For 'Xenium': A NumPy array representing the stain image.
        - For 'MERSCOPE': A file path to the TIFF image.
    cell_polygons : gpd.GeoDataFrame
        A GeoDataFrame containing cell polygon geometries. It should have a valid coordinate reference system (CRS).
    technology_name : str
        Name of the imaging technology used. Supported values:
        - 'Xenium': The image is provided as a NumPy array and is processed using `rasterio.MemoryFile`.
        - 'MERSCOPE': The image is read from a file using `rasterio.open()`.

    Returns:
    --------
    tuple:
        - gpd.GeoDataFrame: Updated GeoDataFrame with two new columns:
            - "mean_stain_intensity": Mean pixel intensity within each cell polygon.
            - "sum_stain_intensity": Sum of pixel intensities within each cell polygon.
        - numpy.ndarray or str: The input image array (for 'Xenium') or file path (for 'MERSCOPE').

    """

    if technology_name == 'Xenium':

        for index in range(4):

            meta = {
                    "driver": "GTiff",
                    "dtype": image_array[index].dtype,
                    "count": 1 if image_array[index].ndim == 2 else image_array[index].shape[0],  # Handle single/multi-channel
                    "height": image_array[index].shape[-2],
                    "width": image_array[index].shape[-1],
                    "nodata": None,
            }

            with MemoryFile() as memfile:
                with memfile.open(**meta) as src:
                    src.write(image_array[index] if image_array[index].ndim == 2 else image_array[index][0], 1)

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

                    cell_polygons[f"{index} image mean_stain_intensity"] = intensities
                    cell_polygons[f"{index} image sum_stain_intensity"] = sum_intensities

    elif technology_name == 'MERSCOPE':

        with rasterio.open(image_array) as src:
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

    return cell_polygons, image_array

def plot_region_stats(image_array, cell_polygons, technology_name):

    """
    Plots spatial and statistical distributions of stain intensities across cell polygons.

    Parameters:
    -----------
    image_array : numpy.ndarray
        A 2D or 3D array representing the stain image on which the cell polygons will be overlaid.
    cell_polygons : gpd.GeoDataFrame
        A GeoDataFrame containing cell polygon geometries and their corresponding "sum_stain_intensity" values.

    Returns:
    --------
    tuple:
        - numpy.ndarray: Log-transformed sum stain intensities for each cell polygon.
        - numpy.ndarray: Bin edges of the histogram for log-normalized stain intensities.

    Plots:
    ------
    1. An overlay of cell polygons with stain-positive intensities on the stain image.
    2. A histogram of log-normalized stain intensities, showing their distribution.

    """

    if technology_name == 'Xenium':

        log_transformed_stain_intensities_dict = {}
        bin_edges_dict = {}

        for index in range(4):
            log_transformed_stain_intensities = np.log1p(cell_polygons[f"{index} image sum_stain_intensity"])

            log_transformed_stain_intensities_dict[index] = log_transformed_stain_intensities

            # Normalize the log-transformed intensities to the range [0, 1]
            log_normalized_stain_intensities = (log_transformed_stain_intensities - log_transformed_stain_intensities.min()) / \
                                            (log_transformed_stain_intensities.max() - log_transformed_stain_intensities.min())

            print(f"Plotting cells with total stain intensity (for Image Index {index}) greater than zero:")

            fig, ax = plt.subplots(figsize=(40, 40))
            ax.imshow(image_array[index])
            cell_polygons.plot(ax=ax, alpha=1, linewidth=1, facecolor='none', edgecolor='red')
            plt.title(f"Overlay of all stain-positive cells on stain image - index {index}", fontsize=40)
            plt.xticks(fontsize=40)
            plt.yticks(fontsize=40)

            fig, ax = plt.subplots(figsize=(15, 9))
            counts, bin_edges, _ = plt.hist(log_normalized_stain_intensities, bins=50, edgecolor='black', alpha=0.7)
            plt.title(f'Distribution of Log-Normalized Stain Intensities of Image Index {index}')
            plt.xlabel('Log-Normalized Intensity Values')
            plt.ylabel('Frequency of Occurrence')
            plt.xticks([min_bin_edge for min_bin_edge in bin_edges], fontsize=10, rotation=45)
            plt.yticks(fontsize=10)
            plt.show()
            plt.close('all')

            bin_edges_dict[index] = bin_edges

        return log_transformed_stain_intensities_dict, bin_edges_dict

    elif technology_name == 'MERSCOPE':

        log_transformed_stain_intensities = np.log1p(cell_polygons["sum_stain_intensity"])

        # Normalize the log-transformed intensities to the range [0, 1]
        log_normalized_stain_intensities = (log_transformed_stain_intensities - log_transformed_stain_intensities.min()) / \
                                        (log_transformed_stain_intensities.max() - log_transformed_stain_intensities.min())

        print("Plotting cells with total stain intensity greater than zero:")

        fig, ax = plt.subplots(figsize=(40, 40))
        ax.imshow(image_array)
        cell_polygons.plot(ax=ax, alpha=1, linewidth=1, facecolor='none', edgecolor='red')
        plt.title("Overlay of all stain-positive cells on stain image", fontsize=40)
        plt.xticks(fontsize=40)
        plt.yticks(fontsize=40)

        fig, ax = plt.subplots(figsize=(15, 9))
        counts, bin_edges, _ = plt.hist(log_normalized_stain_intensities, bins=50, edgecolor='black', alpha=0.7)
        plt.title('Distribution of Log-Normalized Stain Intensities}')
        plt.xlabel('Log-Normalized Intensity Values')
        plt.ylabel('Frequency of Occurrence')
        plt.xticks([min_bin_edge for min_bin_edge in bin_edges], fontsize=10, rotation=45)
        plt.yticks(fontsize=10)
        plt.show()
        plt.close('all')

        return log_transformed_stain_intensities, bin_edges

def calculate_stain_intensities(image_file, cell_polygons, technology_name):

    """
    Computes stain intensity values within segmented cell polygons and visualizes their distribution.

    Parameters:
    -----------
    image_file : str
        Path to the stain image file. This can be the original image or a contrast-adjusted version.
    cell_polygons : gpd.GeoDataFrame
        A GeoDataFrame containing segmented cell polygons.
    technology_name : str
        Name of the imaging technology used. Supported values:
        - 'MERSCOPE': Processes the image from file using raster-based methods.
        - 'Xenium': Uses a NumPy array for in-memory processing.

    Returns:
    --------
    tuple:
        - gpd.GeoDataFrame: Updated cell polygons with two new columns:
            - "mean_stain_intensity": Mean pixel intensity within each cell polygon.
            - "sum_stain_intensity": Sum of pixel intensities within each cell polygon.
        - numpy.ndarray: The processed stain image as an array.
        - numpy.ndarray: Log-transformed sum intensities for each cell polygon.
        - numpy.ndarray: Bin edges of the histogram for log-normalized stain intensities.

    Workflow:
    ---------
    1. Calls `calc_img_region_stats()` to compute mean and sum stain intensities for each polygon.
    2. Calls `plot_region_stats()` to generate:
        - An overlay of segmented cells on the stain image.
        - A histogram of log-normalized stain intensities.
    3. Returns updated cell polygons, the processed stain image, and intensity distribution statistics.

    """

    cell_polygons, image_array = calc_img_region_stats(image_array=image_file,
                                                 cell_polygons=cell_polygons,
                                                 technology_name=technology_name)

    log_transformed_stain_intensities, bin_edges = plot_region_stats(image_array, cell_polygons, technology_name)

    return cell_polygons, image_array, log_transformed_stain_intensities, bin_edges

def filtering_stain_positive_cells(filtering_positive_cells_threshold, bin_edges, log_transformed_stain_intensities, cell_polygons_with_metadata, base_path, image_array, subset_bounds, technology_name, contrast_limits=None):

    """
    Filters stain-positive cells based on a user-defined stain intensity threshold and overlays them on the stain image.

    Parameters:
    -----------
    filtering_positive_cells_threshold : array
        The log-normalized intensity thresholds used to filter stain-positive cells.
    bin_edges : np.ndarray
        Bin edges from the histogram binning of log-transformed stain intensities.
    log_transformed_stain_intensities : np.ndarray
        Log-transformed sum stain intensities of cells.
    cell_polygons_with_metadata : gpd.GeoDataFrame
        GeoDataFrame containing segmented cell polygons with stain intensity metadata.
    base_path : str
        Base directory where output images and results will be stored.
    image_array : np.ndarray
        The original stain image array used for visualization.
    subset_bounds : tuple or list of four elements (start_y, end_y, start_x, end_x)
        The coordinates specifying the region of interest (ROI) to extract.
        - start_y: Starting y-coordinate.
        - end_y: Ending y-coordinate.
        - start_x: Starting x-coordinate.
        - end_x: Ending x-coordinate.
    use_contrast_adjusted_image : bool, optional
        If True, uses the contrast-adjusted stain image for visualization. Defaults to False.
    contrast_limits : tuple (vmin, vmax), optional
        If provided, sets the contrast range for displaying the stain image. If None, it is automatically set using the 1st and 99th percentile of the image intensity.

    Returns:
    --------
    None
        - Saves a CSV file containing the filtered stain-positive cells: `filtered_stain_positive_cells.csv`.
        - Displays an overlay plot of the filtered stain-positive cells on the stain image.

    Workflow:
    ---------
    1. If `use_contrast_adjusted_image` is True, loads the contrast-adjusted image.
    2. Determines the bin corresponding to the threshold intensity.
    3. Converts the log-normalized threshold back to the original stain intensity scale.
    4. Filters cells whose sum stain intensity exceeds the threshold.
    5. Plots the filtered stain-positive cells over the stain image.
    6. Saves the filtered cell data as a CSV file.

    """

    if technology_name == 'MERSCOPE':

        subset_image_array = image_array[subset_bounds[0]:subset_bounds[1], subset_bounds[2]:subset_bounds[3]]

        if contrast_limits is None:
            vmin = np.quantile(subset_image_array, 0.01)  # 1st percentile (low-intensity cutoff)
            vmax = np.quantile(subset_image_array, 0.99)  # 99th percentile (high-intensity cutoff)
        else:
            vmin, vmax = contrast_limits

        bin_index = np.where((bin_edges[:-1] <= filtering_positive_cells_threshold[0]) & (bin_edges[1:] > filtering_positive_cells_threshold[0]))[0][0]
        bin_start, bin_end = bin_edges[bin_index], bin_edges[bin_index + 1]
        original_start = np.expm1(bin_start * (log_transformed_stain_intensities.max() - log_transformed_stain_intensities.min()) + log_transformed_stain_intensities.min())

        bbox = box(subset_bounds[2], subset_bounds[0], subset_bounds[3], subset_bounds[1])

        subset_cells = cell_polygons_with_metadata[cell_polygons_with_metadata.geometry.within(bbox)]
        filtered_cells = subset_cells[subset_cells['sum_stain_intensity'] > original_start]

        print(f"Plotting cells with total stain intensity greater than the selected threshold of {filtering_positive_cells_threshold[0]}:")
        fig, ax = plt.subplots(figsize=(40, 40))
        ax.imshow(subset_image_array, vmin=vmin, vmax=vmax, extent=[subset_bounds[2], subset_bounds[3], subset_bounds[1], subset_bounds[0]])
        filtered_cells.plot(ax=ax, alpha=1, linewidth=1, facecolor='none', edgecolor='red')
        plt.title("Overlay of filtered stain-positive cells on stain image", fontsize=35)
        plt.xticks(fontsize=35)
        plt.yticks(fontsize=35)
        plt.show()
        plt.close('all')

        filtered_cells.to_csv(f'{base_path}/filtered_stain_positive_cells.csv')

    elif technology_name == 'Xenium':

        bbox = box(subset_bounds[2], subset_bounds[0], subset_bounds[3], subset_bounds[1])
        subset_cells = cell_polygons_with_metadata[cell_polygons_with_metadata.geometry.within(bbox)]

        for index in range(4):

            subset_image_array = image_array[index][subset_bounds[0]:subset_bounds[1], subset_bounds[2]:subset_bounds[3]]

            bin_index = np.where((bin_edges[index][:-1] <= filtering_positive_cells_threshold[index]) & (bin_edges[index][1:] > filtering_positive_cells_threshold[index]))[0][0]
            bin_start, bin_end = bin_edges[index][bin_index], bin_edges[index][bin_index + 1]
            original_start = np.expm1(bin_start * (log_transformed_stain_intensities[index].max() - log_transformed_stain_intensities[index].min()) + log_transformed_stain_intensities[index].min())

            filtered_cells = subset_cells[subset_cells[f"{index} image sum_stain_intensity"] > original_start]

            if contrast_limits is None:
                vmin = np.quantile(subset_image_array, 0.01)  # 1st percentile (low-intensity cutoff)
                vmax = np.quantile(subset_image_array, 0.99)  # 99th percentile (high-intensity cutoff)
            else:
                vmin, vmax = contrast_limits

            print(f"Plotting cells with total stain intensity in Image index {index} greater than the selected threshold of {filtering_positive_cells_threshold[index]}:")
            fig, ax = plt.subplots(figsize=(40, 40))
            ax.imshow(subset_image_array, vmin=vmin, vmax=vmax, extent=[subset_bounds[2], subset_bounds[3], subset_bounds[1], subset_bounds[0]])
            filtered_cells.plot(ax=ax, alpha=1, linewidth=1, facecolor='none', edgecolor='red')
            plt.title(f"Overlay of filtered stain-positive cells on stain image - index {index}", fontsize=35)
            plt.xticks(fontsize=35)
            plt.yticks(fontsize=35)
            plt.show()
            plt.close('all')

            filtered_cells.to_csv(f'{base_path}/filtered_stain_{index}_positive_cells.csv')

    print("Filtered stain positive cells data (.csv) saved. Filtering done.")

def image_quantification(base_path, technology_name, image_contrast_required=False, contrast_factor=5, intensity_threshold=100):

    """
    Performs image quantification by extracting stain intensities and processing cell boundaries.

    Parameters:
    -----------
    base_path : str
        The base directory containing input images, metadata, and transformation matrices.
    technology_name : str
        The imaging technology used. Supported values:
        - 'MERSCOPE': Uses a transformation matrix from "micron_to_mosaic_pixel_transform.csv".
        - 'Xenium': Extracts a transformation matrix from a Zarr archive ("cells.zarr.zip").
    image_contrast_required : bool, optional
        If True, applies contrast enhancement to the extracted image. Defaults to False.
    contrast_factor : int, optional
        Factor by which contrast is enhanced if `image_contrast_required` is True. Defaults to 5.
    intensity_threshold : int, optional
        Pixel intensity threshold for filtering bright stain regions. Pixels above this threshold are retained;
        others are set to zero. Defaults to 100.

    Returns:
    --------
    tuple:
        - gpd.GeoDataFrame: Processed cell polygons with computed stain intensity metadata.
        - numpy.ndarray: The processed stain image as an array.
        - numpy.ndarray: Log-transformed sum stain intensities for each cell polygon.
        - numpy.ndarray: Bin edges of the histogram for log-normalized stain intensities.

    Workflow:
    ---------
    1. Loads the transformation matrix based on `technology_name`:
        - 'MERSCOPE': Reads from a CSV file.
        - 'Xenium': Extracts from a Zarr archive.
    2. Calls `process_inputs_for_quantification()` to:
        - Extract cell boundaries and transform them.
        - Load the appropriate stain image (original or contrast-adjusted).
    3. Calls `calculate_stain_intensities()` to:
        - Compute stain intensity statistics (mean and sum intensity).
        - Generate log-transformed intensity values.
        - Extract bin edges for histogram visualization.
    4. Returns processed cell polygons, the stain image array, and intensity distribution statistics.

    """

    if technology_name == 'MERSCOPE':
        transformation_matrix = pd.read_csv(os.path.join(base_path, "images", "micron_to_mosaic_pixel_transform.csv")).values

    elif technology_name == 'Xenium':
        root = open_zarr(base_path + "cells.zarr.zip")
        transformation_matrix = root['masks']['homogeneous_transform'][:]

    processing_outputs = process_inputs_for_quantification(
        technology_name, transformation_matrix, base_path, image_contrast_required, contrast_factor, intensity_threshold)

    cell_polygons_with_metadata, image_array, log_transformed_stain_intensities, bin_edges = calculate_stain_intensities(
                                        image_file=processing_outputs[1], cell_polygons=processing_outputs[0],
                                        technology_name=technology_name)

    print("Image quantification and filtering done.")

    return cell_polygons_with_metadata, image_array, log_transformed_stain_intensities, bin_edges