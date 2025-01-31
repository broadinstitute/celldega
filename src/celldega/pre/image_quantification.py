import os
import glob
import tifffile
import pandas as pd
import numpy as np
import geopandas as gpd
import matplotlib.pyplot as plt
from rasterio.mask import mask
from rasterstats import zonal_stats
from shapely.geometry import Polygon, MultiPolygon
from shapely.affinity import scale
from PIL import Image, ImageEnhance
from ..pre.boundary_tile import numpy_affine_transform, batch_transform_geometries

def process_row(row):
    geometry = row['Geometry']
    if geometry.geom_type == "MultiPolygon":
        largest_polygon = max(geometry.geoms, key=lambda p: p.area)
        row['Geometry'] = largest_polygon
    return row

def image_contrast_adjustment(image_file, base_path, contrast_factor=5, intensity_threshold=100):
    stain_image = Image.open(image_file).convert("L")

    # Plot the original stain image
    plt.figure(figsize=(10, 10))
    plt.imshow(stain_image, cmap='gray')
    plt.title("Original Stain Image")
    plt.show()

    enhancer = ImageEnhance.Contrast(stain_image)
    stain_image_with_contrast = enhancer.enhance(contrast_factor)

    # Plot the stain image after contrast adjustment
    plt.figure(figsize=(10, 10))
    plt.imshow(stain_image_with_contrast, cmap='gray')
    plt.title(f"Stain Image with Contrast Factor {contrast_factor}")
    plt.show()

    stain_image_with_contrast = np.array(stain_image_with_contrast)
    stain_bright_regions = np.where(stain_image_with_contrast >= intensity_threshold, stain_image_with_contrast, 0)

    # Plot the filtered bright regions
    plt.figure(figsize=(10, 10))
    plt.imshow(stain_bright_regions, cmap='hot')
    plt.title(f"Filtered Bright Regions (Threshold: {intensity_threshold})")
    plt.show()

    tifffile.imwrite(f"{base_path}/contrast_adjusted_stain_image.tif", stain_bright_regions.astype(np.uint8))

    return f"{base_path}/contrast_adjusted_stain_image.tif"

def process_inputs_for_quantification(technology_name, cell_boundary_file, image_file, transform_file, base_path, image_contrast_required=False, contrast_factor=5, intensity_threshold=100):

    gdf = gpd.read_parquet(cell_boundary_file)
    transformation_matrix = pd.read_csv(transform_file, header=None, sep=" ").values

    if technology_name == 'MERSCOPE':
        merged_gdf = gdf.dissolve(by='EntityID').reset_index().rename(columns={'EntityID': 'cell_index'})
   
    # add creation of polygons from vertices for xenium, after segmentation metrics pull request merge
   
    elif technology_name == 'Xenium':
        merged_gdf = gdf.dissolve(by='cell_index').reset_index()

    merged_gdf = merged_gdf.apply(process_row, axis=1)
    merged_gdf["transformed_geometry"] = batch_transform_geometries(merged_gdf["Geometry"], transformation_matrix, scale=1)
    merged_gdf["polygons"] = merged_gdf["transformed_geometry"].apply(lambda x: Polygon(x[0]))

    transformed_cells = gpd.GeoDataFrame({'cell_index': merged_gdf['cell_index']}, geometry=merged_gdf['polygons'])
    transformed_cells.to_csv(f"{base_path}/transformed_cell_polygons.csv")

    if image_contrast_required:
        contrast_adjusted_image_file = image_contrast_adjustment(image_file, base_path, contrast_factor, intensity_threshold)
        return (transformed_cells, contrast_adjusted_image_file)
    else:
        return (transformed_cells)
    
def calculate_stain_intensities(image_file, cell_polygons):
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

    cell_polygons["mean_intensity_EdU"] = intensities
    cell_polygons["sum_intensity_EdU"] = sum_intensities

    log_transformed_EdU_intensities = np.log1p(cell_polygons['sum_intensity_EdU'])

    # Normalize the log-transformed intensities to the range [0, 1]
    log_normalized_EdU_intensities = (log_transformed_EdU_intensities - log_transformed_EdU_intensities.min()) / \
                                     (log_transformed_EdU_intensities.max() - log_transformed_EdU_intensities.min())

    # Plot the histogram of log-normalized EdU intensities
    counts, bin_edges, _ = plt.hist(log_normalized_EdU_intensities, bins=50, edgecolor='black', alpha=0.7)

    plt.title('Distribution of Log-Normalized EdU Intensities')
    plt.xlabel('Log-Normalized Intensity Values')
    plt.ylabel('Frequency of Occurrence')
    plt.show()

    return cell_polygons_with_metadata, log_transformed_EdU_intensities, bin_edges

def filtering_stain_positive_cells(highlighted_bin, bin_edges, log_transformed_EdU_intensities, cell_polygons_with_metadata, base_path, use_contrast_adjusted_image=False):
    
    if use_contrast_adjusted_image:
        stain_image = tifffile.imread(f"{base_path}/contrast_adjusted_stain_image.tif")
    else:
        image_file = glob.glob(os.path.join(base_path, "*.tif")) + glob.glob(os.path.join(base_path, "*.tiff"))[0]
        stain_image = tifffile.imread(image_file)
    
    bin_index = np.where((bin_edges[:-1] <= highlighted_bin) & (bin_edges[1:] > highlighted_bin))[0][0]
    bin_start, bin_end = bin_edges[bin_index], bin_edges[bin_index + 1]
    original_start = np.expm1(bin_start * (log_transformed_EdU_intensities.max() - log_transformed_EdU_intensities.min()) + log_transformed_EdU_intensities.min())

    filtered_cells = cell_polygons_with_metadata[cell_polygons_with_metadata['sum_intensity_EdU'] > original_start]

    fig, ax = plt.subplots(figsize=(40, 40))
    ax.imshow(stain_image)
    filtered_cells.plot(ax=ax, alpha=0.5, linewidth=0.5, facecolor='none', edgecolor='red')
    plt.title("Overlay of filtered stain-positive cells on stain image", fontsize=40)
    plt.xticks(fontsize=40)
    plt.yticks(fontsize=40)
    plt.show()

    filtered_cells.to_csv(f'{base_path}/filtered_stain_positive_cells.csv')

    print("Filtered stain positive cells data (.csv) saved. Filtering done.")

def image_quantification(base_path, technology_name, image_contrast_required=False):
    
    cell_boundary_file = os.path.join(base_path, "cell_boundaries.parquet")
    image_file = glob.glob(os.path.join(base_path, "*.tif")) + glob.glob(os.path.join(base_path, "*.tiff"))[0]
    transform_file = os.path.join(base_path, "transformation_matrix.csv")

    processing_outputs = process_inputs_for_quantification(
        technology_name, cell_boundary_file, image_file, transform_file, base_path, image_contrast_required)

    if len(processing_outputs) == 2:
        cell_polygons_with_metadata, log_transformed_EdU_intensities, bin_edges = calculate_stain_intensities(
                                        image_file=processing_outputs[1], cell_polygons=processing_outputs[0]
                                        )
    else:
        cell_polygons_with_metadata, log_transformed_EdU_intensities, bin_edges = calculate_stain_intensities(
                                        image_file=image_file, cell_polygons=processing_outputs[0]
                                        )
        
    print("Image quantification and filtering done.")
    return cell_polygons_with_metadata, log_transformed_EdU_intensities, bin_edges