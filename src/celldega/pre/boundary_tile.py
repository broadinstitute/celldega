import concurrent.futures
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import MultiPolygon, Point, Polygon
from tqdm import tqdm


def _get_name_mapping(path_landscape_files, layer, segmentation="default"):
    """
    Generates mappings from gene and cell names to unique integer identifiers.

    Args:
        path_landscape_files (str): Path to the directory containing the metadata files.
            Expected files:
            - `meta_gene.parquet`: Contains gene metadata with gene names as the index.
            - `cell_metadata.parquet`: Contains cell metadata with a 'name' column.
            - `layer`: 'boundary' or 'transcript'
            - `segmentation`: 'default' or 'cellpose2', etc.

    Returns:
        dict: Maps gene names (str) to integer ranks (int).
    """

    if layer == "transcript":
        # Load gene metadata
        df_meta_gene = pd.read_parquet(f"{path_landscape_files}/meta_gene.parquet")
        if segmentation != "default":
            df_meta_gene = pd.read_parquet(
                f"{path_landscape_files}/meta_gene_{segmentation}.parquet"
            )
        df_meta_gene["name"] = df_meta_gene.index
        df_meta_gene = df_meta_gene.reset_index(drop=True)
        return {str(name): idx for idx, name in df_meta_gene["name"].items()}

    if layer == "boundary":
        # Load cell metadata
        df_meta_cell = pd.read_parquet(f"{path_landscape_files}/cell_metadata.parquet")
        if segmentation != "default":
            df_meta_cell = pd.read_parquet(
                f"{path_landscape_files}/cell_metadata_{segmentation}.parquet"
            )
        df_meta_cell = df_meta_cell.reset_index(drop=True)
        return {str(name): idx for idx, name in df_meta_cell["name"].items()}

    raise ValueError(
        f"Unsupported layer: {layer}. Supported technologies are 'boundary' and 'transcript'."
    )


def _round_nested_coord_list(value, decimals=2):
    """Rounds numeric values in nested lists or arrays to a specified number of decimal places.

    Args:
        value (list, np.ndarray, float, int): The input value, which can be a nested list, array, or numeric value.
        decimals (int, optional): The number of decimal places to round to. Defaults to 2.

    Returns:
        list, float: The rounded value. If the input is a nested list or array, returns a nested list with rounded values.
    """
    if isinstance(value, (list | np.ndarray)):
        return [_round_nested_coord_list(item, decimals) for item in value]

    return round(value, decimals) if isinstance(value, (float | int)) else value


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
    affine_matrix = np.array(
        [
            [
                transformation_matrix[0, 0],
                transformation_matrix[0, 1],
                transformation_matrix[0, 2],
            ],
            [
                transformation_matrix[1, 0],
                transformation_matrix[1, 1],
                transformation_matrix[1, 2],
            ],
            [0, 0, 1],
        ]
    )

    transformed_geometries = []

    for geom in geometries:
        if isinstance(geom, Point):
            # Transform a single Point geometry
            point_coords = np.array([[geom.x, geom.y]])
            transformed_coords = numpy_affine_transform(point_coords, affine_matrix) / scale
            transformed_geometries.append(Point(transformed_coords[0]))

        elif isinstance(geom, Polygon):
            # Transform a Polygon geometry
            exterior_coords = np.array(geom.exterior.coords)

            # Apply the affine transformation and scale
            transformed_coords = numpy_affine_transform(exterior_coords, affine_matrix) / scale

            # Append the result to the transformed_geometries list
            transformed_geometries.append([transformed_coords.tolist()])

        elif isinstance(geom, MultiPolygon):
            geom = max(geom.geoms, key=lambda g: g.area)

            # Transform the exterior of the polygon
            exterior_coords = np.array(geom.exterior.coords)

            # Apply the affine transformation and scale
            transformed_coords = numpy_affine_transform(exterior_coords, affine_matrix) / scale

            # Append the result to the transformed_geometries list
            transformed_geometries.append([transformed_coords.tolist()])

    return transformed_geometries


def filter_and_save_fine_boundary(
    coarse_tile,
    fine_i,
    fine_j,
    fine_tile_x_min,
    fine_tile_x_max,
    fine_tile_y_min,
    fine_tile_y_max,
    path_output,
):
    cell_ids = coarse_tile.index.values

    tile_filter = (
        (coarse_tile["center_x"] >= fine_tile_x_min)
        & (coarse_tile["center_x"] < fine_tile_x_max)
        & (coarse_tile["center_y"] >= fine_tile_y_min)
        & (coarse_tile["center_y"] < fine_tile_y_max)
    )
    filtered_indices = np.where(tile_filter)[0]

    keep_cells = cell_ids[filtered_indices]
    fine_tile_cells = coarse_tile.loc[keep_cells, ["GEOMETRY"]]

    fine_tile_cells["name"] = fine_tile_cells.index

    # Apply rounding to the GEOMETRY column
    fine_tile_cells["GEOMETRY"] = fine_tile_cells["GEOMETRY"].apply(_round_nested_coord_list)

    if not fine_tile_cells.empty:
        filename = f"{path_output}/cell_tile_{fine_i}_{fine_j}.parquet"
        fine_tile_cells.to_parquet(filename, index=False)


def process_fine_boundaries(
    coarse_tile,
    i,
    j,
    coarse_tile_x_min,
    coarse_tile_x_max,
    coarse_tile_y_min,
    coarse_tile_y_max,
    tile_size,
    path_output,
    x_min,
    y_min,
    n_fine_tiles_x,
    n_fine_tiles_y,
    max_workers,
):
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for fine_i in range(n_fine_tiles_x):
            fine_tile_x_min = x_min + fine_i * tile_size
            fine_tile_x_max = fine_tile_x_min + tile_size

            if not (fine_tile_x_min >= coarse_tile_x_min and fine_tile_x_max <= coarse_tile_x_max):
                continue

            for fine_j in range(n_fine_tiles_y):
                fine_tile_y_min = y_min + fine_j * tile_size
                fine_tile_y_max = fine_tile_y_min + tile_size

                if not (
                    fine_tile_y_min >= coarse_tile_y_min and fine_tile_y_max <= coarse_tile_y_max
                ):
                    continue

                futures.append(
                    executor.submit(
                        filter_and_save_fine_boundary,
                        coarse_tile,
                        fine_i,
                        fine_j,
                        fine_tile_x_min,
                        fine_tile_x_max,
                        fine_tile_y_min,
                        fine_tile_y_max,
                        path_output,
                    )
                )

        for future in futures:
            future.result()


def get_cell_polygons(
    technology,
    path_cell_boundaries,
    transformation_matrix,
    path_output=None,
    image_scale=1,
    path_meta_cell_micron=None,
):
    # Load cell boundary data based on the technology
    if technology == "MERSCOPE":
        cells_orig = gpd.read_parquet(path_cell_boundaries)
        cells_orig["cell_id"] = cells_orig["EntityID"]
        cells_orig = cells_orig[cells_orig["ZIndex"] == 1]

        # Correct cell_id issues with meta_cell
        meta_cell = pd.read_csv(path_meta_cell_micron)
        meta_cell["cell_id"] = meta_cell["EntityID"]
        cells_orig.index = meta_cell[meta_cell["cell_id"].isin(cells_orig["cell_id"])].index

        # Correct 'MultiPolygon' to 'Polygon'

        # Remove rows where geometry is empty (None, MultiPolygon with no geoms, or generic empty)
        cells_orig = cells_orig[
            ~(
                cells_orig["Geometry"].isna()  # None values
                | cells_orig["Geometry"].apply(lambda g: g.is_empty)  # Generic empty
                | cells_orig["Geometry"].apply(  # Empty MultiPolygons
                    lambda g: isinstance(g, MultiPolygon) and len(g.geoms) == 0
                )
            )
        ].copy()

        cells_orig["geometry"] = cells_orig["Geometry"].apply(
            lambda x: next(iter(x.geoms)) if isinstance(x, MultiPolygon) else x
        )

        cells_orig.set_index("cell_id", inplace=True)

        cells_orig.rename(columns={"geometry": "geometry_micron"}, inplace=True)

    elif technology == "Xenium":
        xenium_cells = pd.read_parquet(path_cell_boundaries)
        grouped = xenium_cells.groupby("cell_id")[["vertex_x", "vertex_y"]].agg(
            lambda x: x.tolist()
        )
        grouped["geometry"] = grouped.apply(
            lambda row: Polygon(zip(row["vertex_x"], row["vertex_y"], strict=False)),
            axis=1,
        )
        cells_orig = gpd.GeoDataFrame(grouped, geometry="geometry")[["geometry"]]

        cells_orig.rename(columns={"geometry": "geometry_micron"}, inplace=True)

    # Transform geometries
    cells_orig["GEOMETRY"] = batch_transform_geometries(
        cells_orig["geometry_micron"], transformation_matrix, image_scale
    )

    # Convert transformed geometries to polygons and calculate centroids
    cells_orig["polygon"] = cells_orig["GEOMETRY"].apply(lambda x: Polygon(x[0]))

    # Specify the columns to include
    columns_to_include = ["geometry_micron", "GEOMETRY"]

    return gpd.GeoDataFrame(cells_orig[columns_to_include], geometry=cells_orig["polygon"])


def make_cell_boundary_tiles(
    technology,
    path_cell_boundaries,
    path_output,
    path_meta_cell_micron=None,
    path_transformation_matrix=None,
    coarse_tile_factor=20,
    tile_size=250,
    tile_bounds=None,
    image_scale=1,
    max_workers=1,
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
    coarse_tile_factor  : int, optional, default=20.
        scaling factor of each coarse-grain tile comparing to the fine tile size.
    tile_size : int, optional, default=500
        Size of each fine-grain tile in microns.
    tile_bounds : dict, optional
        Dictionary containing the minimum and maximum bounds for x and y coordinates.
    image_scale : float, optional, default=1
        Scale factor to apply to the geometry data.
    max_workers : int, optional, default=1
        Maximum number of parallel workers for processing tiles.

    Returns
    -------
    None
    """

    print("\n========Create cell boundary spatial tiles========")

    # Ensure the output directory exists
    Path(path_output).mkdir(parents=True, exist_ok=True)

    if technology == "custom":
        print("custom technology")
        gdf_cells = gpd.read_parquet(path_cell_boundaries)

        # Convert string index to integer index
        cell_str_to_int_mapping = _get_name_mapping(
            str(Path(path_output).parent),  # get the path of landscape files
            layer="boundary",
            segmentation=path_output.split("cell_segmentation_")[
                1
            ],  # get the cell segmentation method, such as cellpose2.
        )

        gdf_cells.index = gdf_cells.index.astype(str).map(cell_str_to_int_mapping)

        gdf_cells.rename(columns={"geometry_image_space": "GEOMETRY"}, inplace=True)

        gdf_cells["center_x"] = gdf_cells["GEOMETRY"].apply(lambda geom: geom.centroid.x)
        gdf_cells["center_y"] = gdf_cells["GEOMETRY"].apply(lambda geom: geom.centroid.y)

        transformed_geometries = []

        for geom in gdf_cells["GEOMETRY"]:
            if isinstance(geom, Polygon):
                exterior_coords = np.array(geom.exterior.coords)
                transformed_geometries.append([exterior_coords.tolist()])

        gdf_cells["GEOMETRY"] = transformed_geometries

    # MERSCOPE and Xenium
    elif technology in ["MERSCOPE", "Xenium"]:
        print("technology", technology)
        transformation_matrix = pd.read_csv(path_transformation_matrix, header=None, sep=" ").values

        gdf_cells = get_cell_polygons(
            technology,
            path_cell_boundaries,
            transformation_matrix,
            path_output,
            image_scale,
            path_meta_cell_micron,
        )

        # Convert string index to integer index
        cell_str_to_int_mapping = _get_name_mapping(
            path_output.replace("/cell_segmentation", ""),
            layer="boundary",
        )

        gdf_cells.index = gdf_cells.index.astype(str).map(cell_str_to_int_mapping)

        gdf_cells["center_x"] = gdf_cells.geometry.centroid.x
        gdf_cells["center_y"] = gdf_cells.geometry.centroid.y
    else:
        raise ValueError(
            f"Unsupported technology: {technology}. Supported technologies are 'MERSCOPE' and 'Xenium'."
        )

    # Calculate tile bounds and fine/coarse tiles
    x_min, x_max = tile_bounds["x_min"], tile_bounds["x_max"]
    y_min, y_max = tile_bounds["y_min"], tile_bounds["y_max"]
    n_fine_tiles_x = int(np.ceil((x_max - x_min) / tile_size))
    n_fine_tiles_y = int(np.ceil((y_max - y_min) / tile_size))
    n_coarse_tiles_x = int(np.ceil((x_max - x_min) / (coarse_tile_factor * tile_size)))
    n_coarse_tiles_y = int(np.ceil((y_max - y_min) / (coarse_tile_factor * tile_size)))

    # Process coarse tiles in parallel
    for i in tqdm(range(n_coarse_tiles_x), desc="Processing coarse tiles"):
        coarse_tile_x_min = x_min + i * (coarse_tile_factor * tile_size)
        coarse_tile_x_max = coarse_tile_x_min + (coarse_tile_factor * tile_size)

        for j in range(n_coarse_tiles_y):
            coarse_tile_y_min = y_min + j * (coarse_tile_factor * tile_size)
            coarse_tile_y_max = coarse_tile_y_min + (coarse_tile_factor * tile_size)

            coarse_tile = gdf_cells[
                (gdf_cells["center_x"] >= coarse_tile_x_min)
                & (gdf_cells["center_x"] < coarse_tile_x_max)
                & (gdf_cells["center_y"] >= coarse_tile_y_min)
                & (gdf_cells["center_y"] < coarse_tile_y_max)
            ]
            if not coarse_tile.empty:
                process_fine_boundaries(
                    coarse_tile,
                    i,
                    j,
                    coarse_tile_x_min,
                    coarse_tile_x_max,
                    coarse_tile_y_min,
                    coarse_tile_y_max,
                    tile_size,
                    path_output,
                    x_min,
                    y_min,
                    n_fine_tiles_x,
                    n_fine_tiles_y,
                    max_workers,
                )

    print("Done.")


def _collect_boundary_tile_data_for_row_groups(
    gdf_cells,
    x_min,
    y_min,
    x_max,
    y_max,
    tile_size,
):
    """
    Collect all boundary tile data for row group output in deterministic order.

    ALL tiles are included (even empty ones) so that the formula works:
        row_group_index = tile_x * num_tiles_y + tile_y

    Parameters:
    - gdf_cells: GeoDataFrame with cell boundaries
    - x_min, y_min, x_max, y_max: Coordinate bounds
    - tile_size: Size of each tile

    Returns:
    - List of (tile_x, tile_y, DataFrame) tuples (including empty DataFrames)
    """
    n_tiles_x = int(np.ceil((x_max - x_min) / tile_size))
    n_tiles_y = int(np.ceil((y_max - y_min) / tile_size))

    tile_data_list = []

    # Column-major order: tile_x varies slowest
    # row_group_index = tile_x * num_tiles_y + tile_y
    for tile_i in tqdm(range(n_tiles_x), desc="Collecting boundary tiles (X)"):
        tile_x_min = x_min + tile_i * tile_size
        tile_x_max = tile_x_min + tile_size

        for tile_j in range(n_tiles_y):
            tile_y_min = y_min + tile_j * tile_size
            tile_y_max = tile_y_min + tile_size

            # Filter cells for this tile based on centroid
            tile_filter = (
                (gdf_cells["center_x"] >= tile_x_min)
                & (gdf_cells["center_x"] < tile_x_max)
                & (gdf_cells["center_y"] >= tile_y_min)
                & (gdf_cells["center_y"] < tile_y_max)
            )

            tile_cells = gdf_cells[tile_filter].copy()

            if not tile_cells.empty:
                # Prepare data for output
                tile_df = tile_cells[["GEOMETRY"]].copy()
                tile_df["name"] = tile_df.index

                # Apply rounding to the GEOMETRY column
                tile_df["GEOMETRY"] = tile_df["GEOMETRY"].apply(_round_nested_coord_list)

                # Add tile metadata columns
                tile_df["tile_x"] = tile_i
                tile_df["tile_y"] = tile_j

                tile_data_list.append((tile_i, tile_j, tile_df))
            else:
                # Mark as empty - write function will create empty table with correct schema
                tile_data_list.append((tile_i, tile_j, None))

    return tile_data_list


def _write_boundary_tiles_as_row_groups(tile_data_list, output_path, tile_grid_info):
    """
    Write boundary tile data as row groups in a single parquet file.

    Each tile becomes one row group in deterministic order:
        row_group_index = tile_x * num_tiles_y + tile_y

    Empty tiles are written as empty row groups to maintain index alignment.

    Parameters:
    - tile_data_list: List of (tile_x, tile_y, DataFrame) tuples
    - output_path: Path to output parquet file
    - tile_grid_info: Dictionary with grid dimensions
    """
    import json

    import pyarrow as pa
    import pyarrow.parquet as pq

    if not tile_data_list:
        print("Warning: No boundary tile data to write")
        return

    # Create metadata with tile grid info
    metadata = {
        b"tile_grid_info": json.dumps(tile_grid_info).encode("utf-8"),
        b"storage_mode": b"row_groups_formula",
    }

    # Get schema from first non-empty tile
    schema = None
    for _, _, tile_df in tile_data_list:
        if tile_df is not None:
            first_table = pa.Table.from_pandas(tile_df.reset_index(drop=True), preserve_index=False)
            schema = first_table.schema.with_metadata(metadata)
            break

    if schema is None:
        print("Warning: All tiles are empty, cannot determine schema")
        return

    # Write with one row group per tile in order
    # Disable statistics to reduce footer size for large datasets
    writer = pq.ParquetWriter(output_path, schema, write_statistics=False)

    non_empty_count = 0
    for tile_x, tile_y, tile_df in tile_data_list:
        if tile_df is not None:
            # Non-empty tile: convert and write
            tile_table = pa.Table.from_pandas(tile_df.reset_index(drop=True), preserve_index=False)
            writer.write_table(tile_table)
            non_empty_count += 1
        else:
            # Empty tile: create empty table with correct schema
            empty_table = schema.empty_table()
            writer.write_table(empty_table)

    writer.close()

    total_tiles = tile_grid_info["num_tiles_x"] * tile_grid_info["num_tiles_y"]
    print(f"Wrote {len(tile_data_list)} row groups ({non_empty_count} non-empty) to {output_path}")
    print(
        f"Tile grid: {tile_grid_info['num_tiles_x']}x{tile_grid_info['num_tiles_y']} = {total_tiles} tiles"
    )


def make_cell_boundary_tiles_row_groups(
    technology,
    path_cell_boundaries,
    path_output,
    path_meta_cell_micron=None,
    path_transformation_matrix=None,
    coarse_tile_factor=20,
    tile_size=250,
    tile_bounds=None,
    image_scale=1,
    max_workers=1,
    path_landscape_files=None,
):
    """
    Processes cell boundary data and saves all tiles as row groups in a single parquet file.

    This is an alternative to make_cell_boundary_tiles that creates a single file with row groups
    instead of many individual tile files.

    Parameters
    ----------
    technology : str
        The technology used to generate the cell boundary data, e.g., "MERSCOPE", "Xenium".
    path_cell_boundaries : str
        Path to the file containing the cell boundaries (Parquet format).
    path_output : str
        Path to the output parquet file (single file with row groups).
    path_meta_cell_micron : str, optional
        Path to the file containing cell metadata (CSV format).
    path_transformation_matrix : str, optional
        Path to the file containing the transformation matrix (CSV format).
    coarse_tile_factor : int, optional
        Not used in row group mode, kept for API compatibility.
    tile_size : int, optional
        Size of each tile in pixels (default is 250).
    tile_bounds : dict, optional
        Dictionary containing the minimum and maximum bounds for x and y coordinates.
    image_scale : float, optional
        Scale factor to apply to the geometry data (default is 1).
    max_workers : int, optional
        Not used in row group mode, kept for API compatibility.
    path_landscape_files : str, optional
        Path to landscape files directory for loading cell mapping.

    Returns
    -------
    None
    """
    print("\n======== Create cell boundary spatial tiles (Row Groups) ========")

    if technology == "custom":
        raise NotImplementedError("Row group mode not yet supported for custom technology")

    if technology not in ["MERSCOPE", "Xenium"]:
        raise ValueError(
            f"Unsupported technology: {technology}. Supported technologies are 'MERSCOPE' and 'Xenium'."
        )

    transformation_matrix = pd.read_csv(path_transformation_matrix, header=None, sep=" ").values

    gdf_cells = get_cell_polygons(
        technology,
        path_cell_boundaries,
        transformation_matrix,
        path_output,
        image_scale,
        path_meta_cell_micron,
    )

    # Convert string index to integer index
    if path_landscape_files:
        cell_str_to_int_mapping = _get_name_mapping(
            path_landscape_files,
            layer="boundary",
        )
    else:
        # Fallback to path-based resolution
        cell_str_to_int_mapping = _get_name_mapping(
            str(Path(path_output).parent),
            layer="boundary",
        )

    gdf_cells.index = gdf_cells.index.astype(str).map(cell_str_to_int_mapping)

    gdf_cells["center_x"] = gdf_cells.geometry.centroid.x
    gdf_cells["center_y"] = gdf_cells.geometry.centroid.y

    # Get tile bounds
    x_min, x_max = tile_bounds["x_min"], tile_bounds["x_max"]
    y_min, y_max = tile_bounds["y_min"], tile_bounds["y_max"]

    n_tiles_x = int(np.ceil((x_max - x_min) / tile_size))
    n_tiles_y = int(np.ceil((y_max - y_min) / tile_size))

    # Collect all tile data (including empty tiles for formula-based indexing)
    tile_data_list = _collect_boundary_tile_data_for_row_groups(
        gdf_cells,
        x_min,
        y_min,
        x_max,
        y_max,
        tile_size,
    )

    tile_grid_info = {
        "tile_size": tile_size,
        "num_tiles_x": n_tiles_x,
        "num_tiles_y": n_tiles_y,
        "x_min": float(x_min),
        "x_max": float(x_max),
        "y_min": float(y_min),
        "y_max": float(y_max),
    }

    # Write as row groups
    _write_boundary_tiles_as_row_groups(tile_data_list, path_output, tile_grid_info)

    print("Done.")
