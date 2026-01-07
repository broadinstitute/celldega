"""
Transcript tile processing module for spatial transcriptomics data.
"""

import concurrent.futures
from pathlib import Path

import numpy as np
import polars as pl
from scipy.sparse import csr_matrix
from tqdm import tqdm

from .boundary_tile import _get_name_mapping


def _process_coarse_tile_transcripts(
    trx,
    i,
    j,
    coarse_tile_x_min,
    coarse_tile_x_max,
    coarse_tile_y_min,
    coarse_tile_y_max,
    tile_size,
    path_trx_tiles,
    x_min,
    y_min,
    n_fine_tiles_x,
    n_fine_tiles_y,
    max_workers=1,
):
    """
    Process a single coarse tile for transcript data.

    Parameters:
    - trx: Transcript data
    - i, j: Coarse tile indices
    - coarse_tile_x_min, coarse_tile_x_max: X bounds for coarse tile
    - coarse_tile_y_min, coarse_tile_y_max: Y bounds for coarse tile
    - tile_size: Size of each tile
    - path_trx_tiles: Path to transcript tiles
    - x_min, y_min: Minimum coordinates
    - n_fine_tiles_x, n_fine_tiles_y: Number of fine tiles
    - max_workers: Maximum number of workers
    """
    # Filter the entire dataset for the current coarse tile
    coarse_tile = trx.filter(
        (pl.col("transformed_x") >= coarse_tile_x_min)
        & (pl.col("transformed_x") < coarse_tile_x_max)
        & (pl.col("transformed_y") >= coarse_tile_y_min)
        & (pl.col("transformed_y") < coarse_tile_y_max)
    )

    if not coarse_tile.is_empty():
        # Now process fine tiles using global fine tile indices
        _process_fine_tiles_transcripts(
            coarse_tile,
            i,
            j,
            coarse_tile_x_min,
            coarse_tile_x_max,
            coarse_tile_y_min,
            coarse_tile_y_max,
            tile_size,
            path_trx_tiles,
            x_min,
            y_min,
            n_fine_tiles_x,
            n_fine_tiles_y,
            max_workers,
        )


def _process_fine_tiles_transcripts(
    coarse_tile,
    coarse_i,
    coarse_j,
    coarse_tile_x_min,
    coarse_tile_x_max,
    coarse_tile_y_min,
    coarse_tile_y_max,
    tile_size,
    path_trx_tiles,
    x_min,
    y_min,
    n_fine_tiles_x,
    n_fine_tiles_y,
    max_workers=1,
):
    """
    Process fine tiles within a coarse tile for transcript data.

    Parameters:
    - coarse_tile: Coarse tile data
    - coarse_i, coarse_j: Coarse tile indices
    - coarse_tile_x_min, coarse_tile_x_max: X bounds for coarse tile
    - coarse_tile_y_min, coarse_tile_y_max: Y bounds for coarse tile
    - tile_size: Size of each tile
    - path_trx_tiles: Path to transcript tiles
    - x_min, y_min: Minimum coordinates
    - n_fine_tiles_x, n_fine_tiles_y: Number of fine tiles
    - max_workers: Maximum number of workers
    """
    # Use ThreadPoolExecutor for parallel processing of fine-grain tiles within the coarse tile
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []

        # Iterate over fine-grain tiles within the global bounds
        for fine_i in range(n_fine_tiles_x):
            fine_tile_x_min = x_min + fine_i * tile_size
            fine_tile_x_max = fine_tile_x_min + tile_size

            # Process only if the fine tile falls within the current coarse tile's bounds
            if fine_tile_x_min < coarse_tile_x_min or fine_tile_x_max > coarse_tile_x_max:
                continue

            for fine_j in range(n_fine_tiles_y):
                fine_tile_y_min = y_min + fine_j * tile_size
                fine_tile_y_max = fine_tile_y_min + tile_size

                # Process only if the fine tile falls within the current coarse tile's bounds
                if not (
                    fine_tile_y_min >= coarse_tile_y_min and fine_tile_y_max <= coarse_tile_y_max
                ):
                    continue

                # Submit the task for each fine tile to process in parallel
                futures.append(
                    executor.submit(
                        _filter_and_save_fine_tile,
                        coarse_tile,
                        coarse_i,
                        coarse_j,
                        fine_i,
                        fine_j,
                        fine_tile_x_min,
                        fine_tile_x_max,
                        fine_tile_y_min,
                        fine_tile_y_max,
                        path_trx_tiles,
                    )
                )

        # Wait for all futures to complete
        for future in concurrent.futures.as_completed(futures):
            future.result()  # Raise exceptions if any occurred during execution


def _filter_and_save_fine_tile(
    coarse_tile,
    coarse_i,
    coarse_j,
    fine_i,
    fine_j,
    fine_tile_x_min,
    fine_tile_x_max,
    fine_tile_y_min,
    fine_tile_y_max,
    path_trx_tiles,
):
    """
    Filter and save a fine tile for transcript data.

    Parameters:
    - coarse_tile: Coarse tile data
    - coarse_i, coarse_j: Coarse tile indices
    - fine_i, fine_j: Fine tile indices
    - fine_tile_x_min, fine_tile_x_max: X bounds for fine tile
    - fine_tile_y_min, fine_tile_y_max: Y bounds for fine tile
    - path_trx_tiles: Path to transcript tiles
    """
    # Filter the coarse tile for the current fine tile's boundaries
    fine_tile_trx = coarse_tile.filter(
        (pl.col("transformed_x") >= fine_tile_x_min)
        & (pl.col("transformed_x") < fine_tile_x_max)
        & (pl.col("transformed_y") >= fine_tile_y_min)
        & (pl.col("transformed_y") < fine_tile_y_max)
    )

    if not fine_tile_trx.is_empty():
        # Add geometry column as a list of [x, y] pairs
        fine_tile_trx = fine_tile_trx.with_columns(
            pl.concat_list([pl.col("transformed_x"), pl.col("transformed_y")]).alias("geometry")
        )

        # Drop columns if they exist
        columns_to_drop = [
            col
            for col in ["transformed_x", "transformed_y", "cell_id", "transcript_id"]
            if col in fine_tile_trx.columns
        ]
        fine_tile_trx = fine_tile_trx.drop(columns_to_drop)

        # Define the filename based on fine tile coordinates
        filename = Path(path_trx_tiles) / f"transcripts_tile_{fine_i}_{fine_j}.parquet"

        # Save the filtered DataFrame to a Parquet file
        fine_tile_trx.to_pandas().to_parquet(filename, index=False)


def _load_transcript_data_by_technology(technology, path_trx):
    """
    Load transcript data based on technology.

    Parameters:
    - technology: Technology type
    - path_trx: Path to transcript data

    Returns:
    - Polars DataFrame with transcript data
    """
    if technology == "MERSCOPE":
        # Define both potential file paths
        path_trx = Path(path_trx)  # if it's a string, convert to Path
        parquet_path = path_trx.with_suffix(".parquet")

        # Prefer Parquet if it exists
        if parquet_path.exists():
            trx_ini = pl.read_parquet(
                parquet_path,
                columns=["gene", "global_x", "global_y", "cell_id", "transcript_id"],
            )
        # Fallback to CSV if Parquet does not exist, to be backward compatible
        else:
            trx_ini = pl.read_csv(
                path_trx, columns=["gene", "global_x", "global_y", "cell_id", "transcript_id"]
            )

        return trx_ini.with_columns(
            [
                pl.col("cell_id"),
                pl.col("transcript_id"),
                pl.col("global_x").alias("x"),
                pl.col("global_y").alias("y"),
                pl.col("gene").alias("name"),
            ]
        ).select(["name", "x", "y"])

    if technology == "Xenium":
        return pl.read_parquet(path_trx).select(
            [
                pl.col("cell_id"),
                pl.col("transcript_id"),
                pl.col("feature_name").alias("name"),
                pl.col("x_location").alias("x"),
                pl.col("y_location").alias("y"),
            ]
        )

    raise ValueError(f"Unsupported technology: {technology}")


def _apply_gene_mapping(trx_ini, gene_str_to_int_mapping):
    """
    Apply gene name mapping to transcript data.

    Parameters:
    - trx_ini: Initial transcript data
    - gene_str_to_int_mapping: Mapping dictionary for gene names

    Returns:
    - Transcript data with mapped gene names
    """
    # Create a list with the mapped names; if a name isn't in gene_map, keep the original.
    mapped_names = [gene_str_to_int_mapping.get(name, name) for name in trx_ini["name"]]

    # Replace the "name" column using with_columns.
    return trx_ini.with_columns([pl.Series("name", mapped_names)])


def _transform_coordinates_in_chunks(trx_ini, chunk_size, transformation_matrix, image_scale):
    """
    Transform coordinates in chunks for memory efficiency.

    Parameters:
    - trx_ini: Initial transcript data
    - chunk_size: Size of chunks to process
    - transformation_matrix: Transformation matrix
    - image_scale: Image scale factor

    Returns:
    - Concatenated transformed data
    """
    all_chunks = []
    sparse_matrix = csr_matrix(transformation_matrix)

    for start_row in tqdm(range(0, trx_ini.height, chunk_size), desc="Processing chunks"):
        chunk = trx_ini.slice(start_row, chunk_size)

        points = np.hstack([chunk.select(["x", "y"]).to_numpy(), np.ones((chunk.height, 1))])
        transformed_points = sparse_matrix.dot(points.T).T[:, :2]

        # Create new transformed columns and drop original x, y columns
        transformed_chunk = chunk.with_columns(
            [
                (pl.Series(transformed_points[:, 0]) * image_scale).round(2).alias("transformed_x"),
                (pl.Series(transformed_points[:, 1]) * image_scale).round(2).alias("transformed_y"),
            ]
        ).drop(["x", "y"])
        all_chunks.append(transformed_chunk)

    # Concatenate all chunks after processing
    return pl.concat(all_chunks)


def transform_transcript_coordinates(
    technology,
    path_trx,
    chunk_size,
    transformation_matrix,
    image_scale=1,
    gene_str_to_int_mapping=None,
):
    """
    Transform transcript coordinates from microns to image space.

    Parameters:
    - technology: Technology type
    - path_trx: Path to transcript data
    - chunk_size: Chunk size for processing
    - transformation_matrix: Transformation matrix
    - image_scale: Image scale factor
    - gene_str_to_int_mapping: Gene name mapping dictionary

    Returns:
    - Transformed transcript data
    """
    if gene_str_to_int_mapping is None:
        gene_str_to_int_mapping = {}

    # Load the transcript data based on the technology using Polars
    trx_ini = _load_transcript_data_by_technology(technology, path_trx)

    # Apply gene mapping
    trx_ini = _apply_gene_mapping(trx_ini, gene_str_to_int_mapping)

    # Process the data in chunks and apply transformations
    return _transform_coordinates_in_chunks(trx_ini, chunk_size, transformation_matrix, image_scale)


def _get_custom_tile_bounds(path_trx):
    """
    Get tile bounds for custom technology.

    Parameters:
    - path_trx: Path to transcript data

    Returns:
    - Tuple of (x_min, y_min, x_max, y_max)
    """
    x_min, y_min = 0, 0
    x_max, y_max = (
        pl.read_parquet(path_trx)
        .select(
            [
                pl.col("x_image_coords").max().alias("x_max"),
                pl.col("y_image_coords").max().alias("y_max"),
            ]
        )
        .row(0)
    )
    return x_min, y_min, x_max, y_max


def _get_transformed_tile_bounds(trx):
    """
    Get tile bounds for transformed transcript data.

    Parameters:
    - trx: Transformed transcript data

    Returns:
    - Tuple of (x_min, y_min, x_max, y_max)
    """
    x_min, y_min = 0, 0
    x_max, y_max = trx.select(
        [
            pl.col("transformed_x").max().alias("x_max"),
            pl.col("transformed_y").max().alias("y_max"),
        ]
    ).row(0)
    return x_min, y_min, x_max, y_max


def _process_transcript_tiles_parallel(
    trx, x_min, y_min, x_max, y_max, tile_size, coarse_tile_factor, path_trx_tiles, max_workers
):
    """
    Process transcript tiles in parallel.

    Parameters:
    - trx: Transcript data
    - x_min, y_min, x_max, y_max: Coordinate bounds
    - tile_size: Size of each tile
    - coarse_tile_factor: Coarse tile scaling factor
    - path_trx_tiles: Path to transcript tiles
    - max_workers: Maximum number of workers
    """
    # Calculate the number of fine-grain tiles globally
    n_fine_tiles_x = int(np.ceil((x_max - x_min) / tile_size))
    n_fine_tiles_y = int(np.ceil((y_max - y_min) / tile_size))

    # Calculate the number of coarse-grain tiles
    n_coarse_tiles_x = int(np.ceil((x_max - x_min) / (coarse_tile_factor * tile_size)))
    n_coarse_tiles_y = int(np.ceil((y_max - y_min) / (coarse_tile_factor * tile_size)))

    # Use ThreadPoolExecutor for parallel processing of coarse-grain tiles
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for i in range(n_coarse_tiles_x):
            coarse_tile_x_min = x_min + i * (coarse_tile_factor * tile_size)
            coarse_tile_x_max = coarse_tile_x_min + (coarse_tile_factor * tile_size)

            for j in range(n_coarse_tiles_y):
                coarse_tile_y_min = y_min + j * (coarse_tile_factor * tile_size)
                coarse_tile_y_max = coarse_tile_y_min + (coarse_tile_factor * tile_size)

                # Submit each coarse tile for parallel processing
                futures.append(
                    executor.submit(
                        _process_coarse_tile_transcripts,
                        trx,
                        i,
                        j,
                        coarse_tile_x_min,
                        coarse_tile_x_max,
                        coarse_tile_y_min,
                        coarse_tile_y_max,
                        tile_size,
                        path_trx_tiles,
                        x_min,
                        y_min,
                        n_fine_tiles_x,
                        n_fine_tiles_y,
                        max_workers,
                    )
                )

        # Wait for all coarse tiles to complete
        for future in tqdm(
            concurrent.futures.as_completed(futures),
            desc="Processing coarse tiles",
            unit="tile",
        ):
            future.result()  # Raise exceptions if any occurred during execution


def make_trx_tiles(
    technology,
    path_trx,
    path_transformation_matrix=None,
    path_trx_tiles=None,
    coarse_tile_factor=10,
    tile_size=250,
    chunk_size=1000000,
    verbose=False,
    image_scale=1,
    max_workers=1,
):
    """
    Processes transcript data by dividing it into coarse-grain and fine-grain tiles,
    applying transformations, and saving the results in a parallelized manner.

    Parameters
    ----------
    technology : str
        The technology used for generating the transcript data (e.g., "MERSCOPE" or "Xenium").
    path_trx : str
        Path to the file containing the transcript data.
    path_transformation_matrix : str
        Path to the file containing the transformation matrix (CSV file).
    path_trx_tiles : str
        Directory path where the output files (Parquet files) for each tile will be saved.
    coarse_tile_factor : int, optional
        Scaling factor of each coarse-grain tile comparing to the fine tile size.
    tile_size : int, optional
        Size of each fine-grain tile in microns (default is 250).
    chunk_size : int, optional
        Number of rows to process per chunk for memory efficiency (default is 1000000).
    verbose : bool, optional
        Flag to enable verbose output (default is False).
    image_scale : float, optional
        Scale factor to apply to the transcript coordinates (default is 0.5).
    max_workers : int, optional
        Maximum number of parallel workers for processing tiles (default is 1).

    Returns
    -------
    dict
        A dictionary containing the bounds of the processed data in both x and y directions.
    """
    if technology == "custom":
        x_min, y_min, x_max, y_max = _get_custom_tile_bounds(path_trx)
    else:
        # Create output directory
        tiles_path = Path(path_trx_tiles)
        tiles_path.mkdir(exist_ok=True)

        transformation_matrix = np.loadtxt(path_transformation_matrix)

        gene_str_to_int_mapping = _get_name_mapping(
            path_trx_tiles.replace("/transcript_tiles", ""),
            layer="transcript",
        )

        trx = transform_transcript_coordinates(
            technology,
            path_trx,
            chunk_size,
            transformation_matrix,
            image_scale,
            gene_str_to_int_mapping=gene_str_to_int_mapping,
        )

        # Get min and max x, y values
        x_min, y_min, x_max, y_max = _get_transformed_tile_bounds(trx)

        # Process tiles in parallel
        _process_transcript_tiles_parallel(
            trx,
            x_min,
            y_min,
            x_max,
            y_max,
            tile_size,
            coarse_tile_factor,
            path_trx_tiles,
            max_workers,
        )

    # Return the tile bounds
    return {
        "x_min": x_min,
        "x_max": x_max,
        "y_min": y_min,
        "y_max": y_max,
    }


# Legacy function names for backward compatibility
process_coarse_tile = _process_coarse_tile_transcripts
process_fine_tiles = _process_fine_tiles_transcripts
filter_and_save_fine_tile = _filter_and_save_fine_tile


def _collect_tile_data_for_row_groups(
    trx,
    x_min,
    y_min,
    x_max,
    y_max,
    tile_size,
):
    """
    Collect all tile data for row group output in deterministic order.

    ALL tiles are included (even empty ones) so that the formula works:
        row_group_index = tile_x * num_tiles_y + tile_y

    This allows the frontend to calculate row group indices directly from
    tile coordinates using just the grid dimensions.

    OPTIMIZED: Calculates tile indices once for all transcripts, then groups.
    This is O(n) instead of O(tiles x n).

    Parameters:
    - trx: Transcript data
    - x_min, y_min, x_max, y_max: Coordinate bounds
    - tile_size: Size of each tile

    Returns:
    - List of (tile_x, tile_y, DataFrame or None) tuples
    - tile_grid_info: Dictionary with grid dimensions
    """
    # Calculate the number of tiles
    n_tiles_x = int(np.ceil((x_max - x_min) / tile_size))
    n_tiles_y = int(np.ceil((y_max - y_min) / tile_size))

    print(f"Grid: {n_tiles_x} x {n_tiles_y} = {n_tiles_x * n_tiles_y} tiles")
    print("Calculating tile indices for all transcripts...")

    # OPTIMIZED: Calculate tile indices for ALL transcripts at once (O(n))
    trx = trx.with_columns(
        [
            ((pl.col("transformed_x") - x_min) / tile_size).floor().cast(pl.Int32).alias("tile_x"),
            ((pl.col("transformed_y") - y_min) / tile_size).floor().cast(pl.Int32).alias("tile_y"),
        ]
    )

    # Clamp to valid range (edge cases)
    trx = trx.with_columns(
        [
            pl.col("tile_x").clip(0, n_tiles_x - 1).alias("tile_x"),
            pl.col("tile_y").clip(0, n_tiles_y - 1).alias("tile_y"),
        ]
    )

    # Add geometry column
    trx = trx.with_columns(
        pl.concat_list([pl.col("transformed_x"), pl.col("transformed_y")]).alias("geometry")
    )

    # Drop original coordinate columns
    columns_to_drop = [
        col
        for col in ["transformed_x", "transformed_y", "cell_id", "transcript_id"]
        if col in trx.columns
    ]
    trx = trx.drop(columns_to_drop)

    print("Grouping transcripts by tile...")

    # Group by tile using partition_by which returns list of DataFrames
    grouped_dfs = trx.partition_by(["tile_x", "tile_y"], as_dict=True)

    # Convert to dictionary with (tile_x, tile_y) tuple keys
    # key is a tuple of (tile_x, tile_y)
    tile_dict = {
        key: tile_df
        for key, tile_df in tqdm(grouped_dfs.items(), desc="Building tile index")
        if len(tile_df) > 0
    }

    print(f"Found {len(tile_dict)} non-empty tiles")

    # Build ordered list with empty tiles included
    tile_data_list = []
    for tile_i in tqdm(range(n_tiles_x), desc="Ordering tiles"):
        for tile_j in range(n_tiles_y):
            tile_df = tile_dict.get((tile_i, tile_j), None)
            tile_data_list.append((tile_i, tile_j, tile_df))

    tile_grid_info = {
        "tile_size": tile_size,
        "num_tiles_x": n_tiles_x,
        "num_tiles_y": n_tiles_y,
        "x_min": float(x_min),
        "x_max": float(x_max),
        "y_min": float(y_min),
        "y_max": float(y_max),
    }

    return tile_data_list, tile_grid_info


def _write_tiles_as_row_groups(
    tile_data_list, output_dir, tile_grid_info, max_row_groups_per_file=400
):
    """
    Write tile data as row groups in chunked parquet files.

    Each tile becomes one row group in deterministic order:
        row_group_index = tile_x * num_tiles_y + tile_y

    Files are chunked to avoid parquet-wasm issues with large footers:
        file_index = row_group_index // max_row_groups_per_file
        local_row_group_index = row_group_index % max_row_groups_per_file

    Empty tiles are written as empty row groups to maintain index alignment.

    Parameters:
    - tile_data_list: List of (tile_x, tile_y, DataFrame) tuples
    - output_dir: Path to output directory (will contain transcripts_0.parquet, etc.)
    - tile_grid_info: Dictionary with grid dimensions
    - max_row_groups_per_file: Maximum row groups per parquet file (default 10000)

    Returns:
    - dict: Chunk info with file list and metadata
    """
    import json

    import pyarrow as pa
    import pyarrow.parquet as pq

    if not tile_data_list:
        print("Warning: No tile data to write")
        return {}

    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Calculate number of files needed
    total_tiles = len(tile_data_list)
    num_files = (total_tiles + max_row_groups_per_file - 1) // max_row_groups_per_file

    print(
        f"Chunking {total_tiles} tiles into {num_files} files (max {max_row_groups_per_file} per file)"
    )

    # Get schema from first non-empty tile
    schema = None
    for _, _, tile_df in tile_data_list:
        if tile_df is not None:
            first_table = pa.Table.from_pandas(tile_df.to_pandas(), preserve_index=False)
            # Add metadata to schema
            metadata = {
                b"tile_grid_info": json.dumps(tile_grid_info).encode("utf-8"),
                b"storage_mode": b"row_groups_chunked",
                b"max_row_groups_per_file": str(max_row_groups_per_file).encode("utf-8"),
            }
            schema = first_table.schema.with_metadata(metadata)
            break

    if schema is None:
        print("Warning: All tiles are empty, cannot determine schema")
        return {}

    # Write tiles to chunked files
    file_list = []
    non_empty_count = 0
    current_file_index = -1
    writer = None

    for i, (_tile_x, _tile_y, tile_df) in enumerate(tile_data_list):
        file_index = i // max_row_groups_per_file

        # Start new file if needed
        if file_index != current_file_index:
            if writer is not None:
                writer.close()

            current_file_index = file_index
            file_name = f"chunk_{file_index}.parquet"
            file_path = output_path / file_name
            file_list.append(file_name)

            # Disable statistics to reduce footer size
            writer = pq.ParquetWriter(file_path, schema, write_statistics=False)

        # Write tile
        if tile_df is not None:
            tile_table = pa.Table.from_pandas(tile_df.to_pandas(), preserve_index=False)
            writer.write_table(tile_table)
            non_empty_count += 1
        else:
            empty_table = schema.empty_table()
            writer.write_table(empty_table)

    # Close last file
    if writer is not None:
        writer.close()

    print(
        f"Wrote {total_tiles} row groups ({non_empty_count} non-empty) across {len(file_list)} files"
    )
    print(
        f"Tile grid: {tile_grid_info['num_tiles_x']}x{tile_grid_info['num_tiles_y']} = {total_tiles} tiles"
    )

    # Return chunk info for landscape_parameters.json
    return {
        "files": file_list,
        "max_row_groups_per_file": max_row_groups_per_file,
        "total_row_groups": total_tiles,
    }


def make_trx_tiles_row_groups(
    technology,
    path_trx,
    path_transformation_matrix=None,
    path_output_dir=None,
    coarse_tile_factor=10,
    tile_size=250,
    chunk_size=1000000,
    verbose=False,
    image_scale=1,
    max_workers=1,
    path_landscape_files=None,
    max_row_groups_per_file=400,
):
    """
    Processes transcript data and saves all tiles as row groups in chunked parquet files.

    This is an alternative to make_trx_tiles that creates chunked parquet files with row groups
    instead of many individual tile files. Each file contains up to max_row_groups_per_file
    row groups to avoid parquet-wasm memory issues with large footers.

    Parameters
    ----------
    technology : str
        The technology used for generating the transcript data (e.g., "MERSCOPE" or "Xenium").
    path_trx : str
        Path to the file containing the transcript data.
    path_transformation_matrix : str
        Path to the file containing the transformation matrix (CSV file).
    path_output_dir : str
        Path to the output directory (will contain chunk_0.parquet, chunk_1.parquet, etc.).
    coarse_tile_factor : int, optional
        Not used in row group mode, kept for API compatibility.
    tile_size : int, optional
        Size of each tile in pixels (default is 250).
    chunk_size : int, optional
        Number of rows to process per chunk for memory efficiency (default is 1000000).
    verbose : bool, optional
        Flag to enable verbose output (default is False).
    image_scale : float, optional
        Scale factor to apply to the transcript coordinates (default is 1).
    max_workers : int, optional
        Not used in row group mode, kept for API compatibility.
    path_landscape_files : str, optional
        Path to landscape files directory for loading gene mapping.
    max_row_groups_per_file : int, optional
        Maximum row groups per parquet file (default 10000).

    Returns
    -------
    tuple
        (tile_bounds dict, tile_grid_info dict, chunk_info dict)
    """
    if technology == "custom":
        raise NotImplementedError("Row group mode not yet supported for custom technology")

    transformation_matrix = np.loadtxt(path_transformation_matrix)

    # Get gene mapping from landscape files
    if path_landscape_files:
        gene_str_to_int_mapping = _get_name_mapping(
            path_landscape_files,
            layer="transcript",
        )
    else:
        gene_str_to_int_mapping = {}

    # Transform coordinates
    trx = transform_transcript_coordinates(
        technology,
        path_trx,
        chunk_size,
        transformation_matrix,
        image_scale,
        gene_str_to_int_mapping=gene_str_to_int_mapping,
    )

    # Get bounds
    x_min, y_min, x_max, y_max = _get_transformed_tile_bounds(trx)

    # Collect all tile data
    tile_data_list, tile_grid_info = _collect_tile_data_for_row_groups(
        trx,
        x_min,
        y_min,
        x_max,
        y_max,
        tile_size,
    )

    # Write as chunked row groups
    chunk_info = _write_tiles_as_row_groups(
        tile_data_list, path_output_dir, tile_grid_info, max_row_groups_per_file
    )

    tile_bounds = {
        "x_min": x_min,
        "x_max": x_max,
        "y_min": y_min,
        "y_max": y_max,
    }

    return tile_bounds, tile_grid_info, chunk_info
