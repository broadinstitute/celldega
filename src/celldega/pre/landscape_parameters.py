"""Assembly of ``landscape_parameters.json``.

This file is the contract between Python pre-processing and the JavaScript viewer, so its
key set and nesting are load-bearing.

``get_max_zoom_level`` lives here rather than with the pyramid packer because
``save_landscape_parameters`` is its only caller.
"""

import json
from pathlib import Path


def get_max_zoom_level(path_image_pyramid):
    """Returns the maximum zoom level based on the highest-numbered directory in the specified path.

    Args:
        path_image_pyramid (str): Path to the directory containing zoom level directories.

    Returns:
        int: The maximum zoom level.
    """
    path_pyramid = Path(path_image_pyramid)
    zoom_levels = [
        entry.name for entry in path_pyramid.iterdir() if entry.is_dir() and entry.name.isdigit()
    ]
    return max(map(int, zoom_levels)) if zoom_levels else None


def save_landscape_parameters(
    technology,
    path_dega_files,
    image_name="dapi_files",
    tile_size=1000,
    image_info=None,
    image_format=".webp",
    use_int_index=True,
    segmentation_approach="default",
    use_row_groups=False,
    tile_grid_info=None,
    image_tile_info=None,
    trx_chunk_info=None,
    cell_chunk_info=None,
    cbg_chunk_info=None,
):
    """Saves the landscape parameters to a JSON file.

    Args:
        technology (str): The technology used to generate the data.
        path_dega_files (str): Path to the directory where landscape files are stored.
        image_name (str, optional): Name of the image directory. Defaults to "dapi_files".
        tile_size (int, optional): Tile size for the image pyramid. Defaults to 1000.
        image_info (dict, optional): Additional image metadata. Defaults to None.
        image_format (str, optional): Format of the image files. Defaults to ".webp".
        use_int_index (bool, optional): Use integer name for cell_tile and trx_tile.
        use_row_groups (bool, optional): If True, tiles are stored as row groups. Defaults to False.
        tile_grid_info (dict, optional): Tile grid metadata when using row groups.
        image_tile_info (dict, optional): Image tile metadata from pack_image_tiles_to_parquet.
        trx_chunk_info (dict, optional): Chunk info for transcript parquet files.
        cell_chunk_info (dict, optional): Chunk info for cell segmentation parquet files.
        cbg_chunk_info (dict, optional): Chunk info for CBG parquet files.

    Returns:
        None
    """
    print("\n========Save landscape parameters========")

    if image_info is None:
        image_info = {}

    if technology == "h&e":
        image_name = "h_and_e_files"
        image_info = [{"name": "h&e", "button_name": "H&E", "color": [0, 0, 255]}]

    # Get max pyramid zoom - use from image_tile_info if available (row groups mode)
    # since the tile files may have been deleted
    if image_tile_info and use_row_groups:
        # Get max zoom from the first channel's info
        first_channel_info = next(iter(image_tile_info.values()), None)
        if first_channel_info and "zoom_levels" in first_channel_info:
            max_pyramid_zoom = max(first_channel_info["zoom_levels"])
        else:
            max_pyramid_zoom = None
    else:
        path_image_pyramid = Path(path_dega_files) / "pyramid_images" / image_name
        max_pyramid_zoom = get_max_zoom_level(path_image_pyramid)

    path_landscape_parameters = Path(path_dega_files) / "landscape_parameters.json"

    # if technology is 'h&e' set parameters
    if technology == "h&e":
        landscape_parameters = {
            "technology": technology,
            "segmentation_approach": ["N.A."],
            "max_pyramid_zoom": max_pyramid_zoom,
            "tile_size": "N.A.",
            "image_info": image_info,
            "image_format": image_format,
            "use_int_index": "N.A.",
        }
    elif technology != "custom":
        landscape_parameters = {
            "technology": technology,
            "segmentation_approach": [segmentation_approach],
            "max_pyramid_zoom": max_pyramid_zoom,
            "tile_size": tile_size,
            "image_info": image_info,
            "image_format": image_format,
            "use_int_index": use_int_index,
            "use_row_groups": use_row_groups,
        }

        # Add row group specific metadata
        if use_row_groups and tile_grid_info:
            landscape_parameters["row_group_files"] = {}

            # Add chunked CBG files
            if cbg_chunk_info:
                landscape_parameters["row_group_files"]["cbg"] = {
                    "directory": cbg_chunk_info.get("directory", "cbg"),
                    "files": cbg_chunk_info.get("files", []),
                    "max_row_groups_per_file": cbg_chunk_info.get("max_row_groups_per_file", 2000),
                    "total_row_groups": cbg_chunk_info.get("total_row_groups", 0),
                    "gene_to_row_group": cbg_chunk_info.get("gene_to_row_group", {}),
                }
            else:
                # Legacy single file mode (backwards compatibility)
                landscape_parameters["row_group_files"]["cbg"] = "cbg.parquet"

            # Add chunked transcript files
            if trx_chunk_info:
                landscape_parameters["row_group_files"]["transcripts"] = {
                    "directory": "transcripts",
                    "files": trx_chunk_info.get("files", []),
                    "max_row_groups_per_file": trx_chunk_info.get("max_row_groups_per_file", 10000),
                    "total_row_groups": trx_chunk_info.get("total_row_groups", 0),
                }
            else:
                # Legacy single file mode (backwards compatibility)
                landscape_parameters["row_group_files"]["transcripts"] = "transcripts.parquet"

            # Add chunked cell segmentation files
            if cell_chunk_info:
                landscape_parameters["row_group_files"]["cell_segmentation"] = {
                    "directory": "cell_segmentation",
                    "files": cell_chunk_info.get("files", []),
                    "max_row_groups_per_file": cell_chunk_info.get(
                        "max_row_groups_per_file", 10000
                    ),
                    "total_row_groups": cell_chunk_info.get("total_row_groups", 0),
                }
            else:
                # Legacy single file mode (backwards compatibility)
                landscape_parameters["row_group_files"]["cell_segmentation"] = (
                    "cell_segmentation.parquet"
                )

            # Add image parquet files for each channel with zoom info
            # Parquet files are now in pyramid_images/{channel_name}/ directories (chunked)
            pyramid_images_dir = Path(path_dega_files) / "pyramid_images"
            if pyramid_images_dir.exists():
                image_parquets = {}

                # Check for chunked directories (new format)
                for channel_dir in pyramid_images_dir.iterdir():
                    if channel_dir.is_dir():
                        # Sort numerically, not alphabetically (chunk_10 should come after chunk_9)
                        chunk_files = sorted(
                            channel_dir.glob("chunk_*.parquet"),
                            key=lambda f: int(f.stem.split("_")[1]),
                        )
                        if chunk_files:
                            channel_name = channel_dir.name
                            image_entry = {
                                "directory": f"pyramid_images/{channel_name}",
                                "files": [f.name for f in chunk_files],
                            }
                            # Add chunk info and zoom_info if available from image_tile_info
                            if image_tile_info and channel_name in image_tile_info:
                                channel_info = image_tile_info[channel_name]
                                image_entry["zoom_info"] = channel_info.get("zoom_info", {})
                                image_entry["zoom_levels"] = channel_info.get("zoom_levels", [])
                                image_entry["max_row_groups_per_file"] = channel_info.get(
                                    "max_row_groups_per_file", 2000
                                )
                                image_entry["total_row_groups"] = channel_info.get(
                                    "total_row_groups", 0
                                )
                            image_parquets[channel_name] = image_entry

                # Also check for legacy single parquet files (backwards compatibility)
                for pq_file in pyramid_images_dir.glob("*.parquet"):
                    channel_name = pq_file.stem
                    if channel_name not in image_parquets:
                        image_entry = {
                            "path": f"pyramid_images/{pq_file.name}",
                        }
                        # Add zoom_info if available from image_tile_info
                        if image_tile_info and channel_name in image_tile_info:
                            channel_info = image_tile_info[channel_name]
                            image_entry["zoom_info"] = channel_info.get("zoom_info", {})
                            image_entry["zoom_levels"] = channel_info.get("zoom_levels", [])
                        image_parquets[channel_name] = image_entry

                if image_parquets:
                    landscape_parameters["row_group_files"]["images"] = image_parquets

            # Store image dimensions from first channel (all channels have same dimensions)
            if image_tile_info:
                first_channel_info = next(iter(image_tile_info.values()), None)
                if first_channel_info:
                    landscape_parameters["image_dimensions"] = {
                        "width": first_channel_info.get("image_width"),
                        "height": first_channel_info.get("image_height"),
                        "tile_size": first_channel_info.get("tile_size", 512),
                    }

            # Store grid dimensions - frontend computes row group index using:
            # row_group_index = tile_x * num_tiles_y + tile_y
            landscape_parameters["tile_grid"] = {
                "tile_size": tile_grid_info.get("tile_size", tile_size),
                "num_tiles_x": tile_grid_info.get("num_tiles_x"),
                "num_tiles_y": tile_grid_info.get("num_tiles_y"),
                "x_min": tile_grid_info.get("x_min"),
                "x_max": tile_grid_info.get("x_max"),
                "y_min": tile_grid_info.get("y_min"),
                "y_max": tile_grid_info.get("y_max"),
            }
    else:
        with path_landscape_parameters.open() as file:
            landscape_parameters = json.load(file)
        landscape_parameters["segmentation_approach"].append(segmentation_approach)

    with path_landscape_parameters.open("w") as file:
        json.dump(landscape_parameters, file, indent=4)

    print("Done.")
