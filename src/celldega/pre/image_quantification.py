import geopandas as gpd
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import tifffile
from shapely.geometry import Polygon, MultiPolygon
from shapely.affinity import scale
from PIL import Image, ImageEnhance
from rasterio.mask import mask
from pathlib import Path
from rasterstats import zonal_stats
import statistics
from matplotlib.lines import Line2D

from ..pre.boundary_tile import numpy_affine_transform, batch_transform_geometries

def process_row(row):
    geometry = row['Geometry']
    if geometry.geom_type == "MultiPolygon":
        largest_polygon = max(geometry.geoms, key=lambda p: p.area)
        row['Geometry'] = largest_polygon
    return row

def image_flip(image, axis):
    return np.flip(image, axis=axis)

def process_inputs_for_quantification(technology_name, cell_boundary_file, image_file_to_flip, image_file_to_scale, transform_file, output_path, flip_along_axis, contrast_factor=5, intensity_threshold=100, axis=None):

    gdf = gpd.read_parquet(cell_boundary_file)
    transformation_matrix = pd.read_csv(transform_file, header=None, sep=" ").values

    if technology_name == 'MERSCOPE':
        merged_gdf = gdf.dissolve(by='EntityID').reset_index().rename(columns={'EntityID': 'cell_id'})
    elif technology_name == 'Xenium':
        merged_gdf = gdf.dissolve(by='cell_id').reset_index()

    new_df = merged_gdf.apply(process_row, axis=1)
    new_df["transformed_geometry"] = batch_transform_geometries(new_df["Geometry"], transformation_matrix, scale=1)
    new_df["polygons"] = new_df["transformed_geometry"].apply(lambda x: Polygon(x[0]))

    gdf_cells = gpd.GeoDataFrame({'cell_id': new_df['cell_id']}, geometry=new_df['polygons'])
    gdf_cells.to_csv(f"{output_path}/transformed_cell_boundaries.csv")

    resized_tif_path = f"{output_path}/DAPI_reference.tif"

    if flip_along_axis:
        image_to_flip = tifffile.imread(image_file_to_flip)
        moving_image = image_flip(image_to_flip, axis)
        tifffile.imwrite(f"{output_path}/new_moving_image.tif", moving_image.astype(np.float32))
    else:
        moving_image = tifffile.imread(image_file_to_flip)

    tif_image = tifffile.imread(image_file_to_scale).astype(np.float32)
    tif_image = (tif_image - np.min(tif_image)) / (np.max(tif_image) - np.min(tif_image))
    tif_image = (tif_image * 255).astype(np.uint8)

    tif_image_pil = Image.fromarray(tif_image, mode="L")
    tif_image_resized = tif_image_pil.resize((moving_image.shape[1], moving_image.shape[0]), Image.LANCZOS)

    tifffile.imwrite(resized_tif_path, tif_image_resized)

    polygons_df = resize_cell_polygons(polygons_df=gdf_cells, original_tif=tif_image, resized_tif=tif_image_resized, output_path=output_path)

    stain_bright_regions, stain_image_file = image_contrast_adjustment(image_file=image_file_to_scale, output_path=output_path, contrast_factor=contrast_factor, intensity_threshold=intensity_threshold)

    return polygons_df, stain_bright_regions, stain_image_file

def resize_polygon(polygon, scale_x, scale_y):
    return scale(polygon, xfact=scale_x, yfact=scale_y, origin=(0, 0))

def resize_cell_polygons(polygons_df, original_tif, resized_tif, output_path):
    original_height, original_width = original_tif.shape
    resized_height, resized_width = resized_tif.shape

    scale_x = resized_width / original_width
    scale_y = resized_height / original_height

    polygons_df["geometry"] = polygons_df["geometry"].apply(lambda poly: resize_polygon(poly, scale_x, scale_y))
    polygons_df.to_csv(f"{output_path}/resized_cell_polygons.csv")

    return polygons_df

def image_contrast_adjustment(image_file, output_path, contrast_factor=5, intensity_threshold=100):
    stain_image = Image.open(image_file).convert("L")
    enhancer = ImageEnhance.Contrast(stain_image)
    stain_image_with_contrast = enhancer.enhance(contrast_factor)

    stain_image_with_contrast = np.array(stain_image_with_contrast)
    stain_bright_regions = np.where(stain_image_with_contrast >= intensity_threshold, stain_image_with_contrast, 0)

    tifffile.imwrite(f"{output_path}/contrast_adjusted_stain_image.tif", stain_bright_regions.astype(np.uint8))

    return stain_bright_regions, f"{output_path}/contrast_adjusted_stain_image.tif"

def calculate_stain_intensities(stain_image_file, cell_polygons):
    with rasterio.open(stain_image_file) as src:
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
    return cell_polygons

def filtering_stain_positive_cells(highlighted_bins, bin_edges, log_transformed_EdU_intensities, cell_polygons, stain_image, output_path):
    for value in highlighted_bins:
        bin_index = np.where((bin_edges[:-1] <= value) & (bin_edges[1:] > value))[0][0]
        bin_start, bin_end = bin_edges[bin_index], bin_edges[bin_index + 1]
        original_start = np.expm1(bin_start * (log_transformed_EdU_intensities.max() - log_transformed_EdU_intensities.min()) + log_transformed_EdU_intensities.min())

        filtered_cells = cell_polygons[cell_polygons['sum_intensity_EdU'] > original_start]
        filtered_cells.to_csv(f'{output_path}/filtered_cells.csv')

    print("Filtering done.")

def main(technology_name, cell_boundary_file, image_file_to_flip, image_file_to_scale, transform_file, output_path, flip_along_axis, highlighted_bins, axis=None):
    polygons_df, stain_bright_regions, stain_image_file = process_inputs_for_quantification(
        technology_name, cell_boundary_file, image_file_to_flip, image_file_to_scale, transform_file, output_path, flip_along_axis, axis=axis
    )

    log_transformed_EdU_intensities, bin_edges = calculate_stain_intensities(
        stain_image_file=stain_image_file, cell_polygons=polygons_df
    )

    filtering_stain_positive_cells(
        highlighted_bins=highlighted_bins,
        bin_edges=bin_edges,
        log_transformed_EdU_intensities=log_transformed_EdU_intensities,
        cell_polygons=polygons_df,
        stain_image=stain_bright_regions,
        output_path=output_path
    )

    print("Image quantification and filtering done.")
