
import numpy as np
import pandas as pd
import os
from tqdm import tqdm
import concurrent.futures
import geopandas as gpd
from shapely.geometry import Polygon, MultiPolygon


def make_cell_boundary_tiles(
    technology,
    path_cell_boundaries,
    path_meta_cell_micron,
    path_transformation_matrix,
    path_output,
    coarse_tile_size=5000,
    fine_tile_size=250,
    tile_bounds=None,
    image_scale=1,
    max_workers=8
):
    

    """
    Processes cell boundary data and divides it into spatial tiles based on the provided technology.
    Reads cell boundary data, applies affine transformations, and divides the data into coarse and fine tiles.
    The resulting tiles are saved as Parquet files, each containing the geometries of cells in that tile.

    Parameters
    ----------
    technology : str
        The technology used to generate the cell boundary data, e.g., "MERSCOPE", "Xenium", or "custom".
    path_cell_boundaries : str
        Path to the file containing the cell boundaries (Parquet format).
    path_meta_cell_micron : str
        Path to the file containing cell metadata (CSV format).
    path_transformation_matrix : str
        Path to the file containing the transformation matrix (CSV format).
    path_output : str
        Directory path where the output files (Parquet files) for each tile will be saved.
    coarse_tile_size : int, optional, default=5000
        Size of each coarse-grain tile in microns.
    fine_tile_size : int, optional, default=500
        Size of each fine-grain tile in microns.
    tile_bounds : dict, optional
        Dictionary containing the minimum and maximum bounds for x and y coordinates.
    image_scale : float, optional, default=1
        Scale factor to apply to the geometry data.
    max_workers : int, optional, default=8
        Maximum number of parallel workers for processing tiles.

    Returns
    -------
    None
    """

    def numpy_affine_transform(coords, matrix):
        """Apply affine transformation to numpy coordinates."""
        # Homogeneous coordinates for affine transformation
        coords = np.hstack([coords, np.ones((coords.shape[0], 1))])
        transformed_coords = coords @ matrix.T
        return transformed_coords[:, :2]  # Drop the homogeneous coordinate
    
    def batch_transform_geometries(geometries, transformation_matrix, scale):
        """
        Batch transform geometries using numpy for optimized performance.
        """
        # Extract affine transformation parameters into a 3x3 matrix for numpy
        affine_matrix = np.array([
            [transformation_matrix[0, 0], transformation_matrix[0, 1], transformation_matrix[0, 2]],
            [transformation_matrix[1, 0], transformation_matrix[1, 1], transformation_matrix[1, 2]],
            [0, 0, 1]
        ])
        
        transformed_geometries = []
        
        for polygon in geometries:
            # Extract coordinates and transform them
            if isinstance(polygon, MultiPolygon):
                polygon = next(polygon.geoms)  # Use the first geometry
            
            # Transform the exterior of the polygon
            exterior_coords = np.array(polygon.exterior.coords)
            
            # Apply the affine transformation and scale
            transformed_coords = numpy_affine_transform(exterior_coords, affine_matrix) / scale
            
            # Append the result to the transformed_geometries list
            transformed_geometries.append([transformed_coords.tolist()])
        
        return transformed_geometries


    def filter_and_save_fine_boundary(coarse_tile, fine_i, fine_j, fine_tile_x_min, fine_tile_x_max, fine_tile_y_min, fine_tile_y_max, path_output):
        cell_ids = coarse_tile.index.values
        
        tile_filter = (
            (coarse_tile["center_x"] >= fine_tile_x_min) & (coarse_tile["center_x"] < fine_tile_x_max) &
            (coarse_tile["center_y"] >= fine_tile_y_min) & (coarse_tile["center_y"] < fine_tile_y_max)
        )
        filtered_indices = np.where(tile_filter)[0]

        keep_cells = cell_ids[filtered_indices]
        fine_tile_cells = coarse_tile.loc[keep_cells, ["GEOMETRY"]]
        fine_tile_cells = fine_tile_cells.assign(name=fine_tile_cells.index)
  
        if not fine_tile_cells.empty:
            filename = f"{path_output}/cell_tile_{fine_i}_{fine_j}.parquet"
            fine_tile_cells.to_parquet(filename)

    def process_fine_boundaries(coarse_tile, i, j, coarse_tile_x_min, coarse_tile_x_max, coarse_tile_y_min, coarse_tile_y_max, fine_tile_size, path_output, x_min, y_min, n_fine_tiles_x, n_fine_tiles_y):
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            for fine_i in range(n_fine_tiles_x):
                fine_tile_x_min = x_min + fine_i * fine_tile_size
                fine_tile_x_max = fine_tile_x_min + fine_tile_size

                if not (fine_tile_x_min >= coarse_tile_x_min and fine_tile_x_max <= coarse_tile_x_max):
                    continue

                for fine_j in range(n_fine_tiles_y):
                    fine_tile_y_min = y_min + fine_j * fine_tile_size
                    fine_tile_y_max = fine_tile_y_min + fine_tile_size

                    if not (fine_tile_y_min >= coarse_tile_y_min and fine_tile_y_max <= coarse_tile_y_max):
                        continue

                    futures.append(executor.submit(
                        filter_and_save_fine_boundary, coarse_tile, fine_i, fine_j, fine_tile_x_min, fine_tile_x_max, fine_tile_y_min, fine_tile_y_max, path_output
                    ))

            for future in futures:
                future.result()

    tile_size_x = fine_tile_size
    tile_size_y = fine_tile_size

    transformation_matrix = pd.read_csv(path_transformation_matrix, header=None, sep=" ").values

    # Load cell boundary data based on the technology
    if technology == "MERSCOPE":
        df_meta = pd.read_parquet(f"{path_output.replace('cell_segmentation','cell_metadata.parquet')}")
        entity_to_cell_id_dict = pd.Series(df_meta.index.values, index=df_meta.EntityID).to_dict()
        cells_orig = gpd.read_parquet(path_cell_boundaries)
        cells_orig['cell_id'] = cells_orig['EntityID'].map(entity_to_cell_id_dict)
        cells_orig = cells_orig[cells_orig["ZIndex"] == 1]

        # Correct cell_id issues with meta_cell
        meta_cell = pd.read_csv(path_meta_cell_micron)
        meta_cell['cell_id'] = meta_cell['EntityID'].map(entity_to_cell_id_dict)
        cells_orig.index = meta_cell[meta_cell["cell_id"].isin(cells_orig['cell_id'])].index

        # Correct 'MultiPolygon' to 'Polygon'
        cells_orig["geometry"] = cells_orig["Geometry"].apply(
            lambda x: list(x.geoms)[0] if isinstance(x, MultiPolygon) else x
        )

        cells_orig.set_index('cell_id', inplace=True)

    elif technology == "Xenium":
        xenium_cells = pd.read_parquet(path_cell_boundaries)
        grouped = xenium_cells.groupby("cell_id")[["vertex_x", "vertex_y"]].agg(lambda x: x.tolist())
        grouped["geometry"] = grouped.apply(lambda row: Polygon(zip(row["vertex_x"], row["vertex_y"])), axis=1)
        cells_orig = gpd.GeoDataFrame(grouped, geometry="geometry")[["geometry"]]

    elif technology == "custom":
        cells_orig = gpd.read_parquet(path_cell_boundaries)

    # Transform geometries
    cells_orig["GEOMETRY"] = batch_transform_geometries(cells_orig["geometry"], transformation_matrix, image_scale)

    # Convert transformed geometries to polygons and calculate centroids
    cells_orig["polygon"] = cells_orig["GEOMETRY"].apply(lambda x: Polygon(x[0]))
    gdf_cells = gpd.GeoDataFrame(geometry=cells_orig["polygon"])
    gdf_cells["center_x"] = gdf_cells.geometry.centroid.x
    gdf_cells["center_y"] = gdf_cells.geometry.centroid.y
    gdf_cells["GEOMETRY"] = cells_orig["GEOMETRY"]

    # Ensure the output directory exists
    if not os.path.exists(path_output):
        os.makedirs(path_output)

    # Calculate tile bounds and fine/coarse tiles
    x_min, x_max = tile_bounds["x_min"], tile_bounds["x_max"]
    y_min, y_max = tile_bounds["y_min"], tile_bounds["y_max"]
    n_fine_tiles_x = int(np.ceil((x_max - x_min) / fine_tile_size))
    n_fine_tiles_y = int(np.ceil((y_max - y_min) / fine_tile_size))
    n_coarse_tiles_x = int(np.ceil((x_max - x_min) / coarse_tile_size))
    n_coarse_tiles_y = int(np.ceil((y_max - y_min) / coarse_tile_size))

    # Process coarse tiles in parallel
    for i in tqdm(range(n_coarse_tiles_x), desc="Processing coarse tiles"):
        coarse_tile_x_min = x_min + i * coarse_tile_size
        coarse_tile_x_max = coarse_tile_x_min + coarse_tile_size

        for j in range(n_coarse_tiles_y):
            coarse_tile_y_min = y_min + j * coarse_tile_size
            coarse_tile_y_max = coarse_tile_y_min + coarse_tile_size

            coarse_tile = gdf_cells[
                (gdf_cells["center_x"] >= coarse_tile_x_min) & (gdf_cells["center_x"] < coarse_tile_x_max) &
                (gdf_cells["center_y"] >= coarse_tile_y_min) & (gdf_cells["center_y"] < coarse_tile_y_max)
            ]
            if not coarse_tile.empty:
                process_fine_boundaries(coarse_tile, i, j, coarse_tile_x_min, coarse_tile_x_max, coarse_tile_y_min, coarse_tile_y_max, fine_tile_size, path_output, x_min, y_min, n_fine_tiles_x, n_fine_tiles_y)
