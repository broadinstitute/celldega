"""Packing a built DeepZoom pyramid into chunked parquet row groups.

Operates purely on files already on disk, so unlike :mod:`celldega.pre.image_tiles` this
module needs neither pyvips nor scikit-image.
"""

import json
from pathlib import Path


def pack_image_tiles_to_parquet(
    pyramid_dir,
    channel_name,
    output_path,
    image_format=".webp",
    delete_source_tiles=True,
    max_row_groups_per_file=2000,
):
    """
    Pack all image tiles from a DeepZoom pyramid into chunked parquet files with row groups.

    Each zoom level's tiles are stored as row groups, allowing efficient range-based access.
    The formula for row group index is:
        row_group_index = sum of tiles in previous zoom levels + tile_x * num_tiles_y + tile_y

    For large datasets, tiles are split across multiple parquet files, each containing
    at most `max_row_groups_per_file` row groups.

    Args:
        pyramid_dir (str): Path to the pyramid_images directory.
        channel_name (str): Name of the image channel (e.g., "dapi").
        output_path (str): Path to the output directory (will contain chunk_X.parquet files).
        image_format (str): Image file extension (default ".webp").
        delete_source_tiles (bool): If True, delete the original tile files after packing.
        max_row_groups_per_file (int): Maximum row groups per file (default 400).

    Returns:
        dict: Image tile metadata including grid info per zoom level and image dimensions.
    """
    import xml.etree.ElementTree as ET

    import pyarrow as pa
    import pyarrow.parquet as pq

    tiles_dir = Path(pyramid_dir) / f"{channel_name}_files"

    if not tiles_dir.exists():
        raise FileNotFoundError(f"Tiles directory not found: {tiles_dir}")

    # Read image dimensions from .dzi file before potentially deleting it
    dzi_file = Path(pyramid_dir) / f"{channel_name}.dzi"
    image_width = None
    image_height = None
    tile_size = 512  # Default tile size

    if dzi_file.exists():
        try:
            # Read raw content to check format
            dzi_content = dzi_file.read_text()
            print(f"DZI file content preview: {dzi_content[:200]}")

            tree = ET.parse(dzi_file)
            root = tree.getroot()

            # Try different ways to find the Size element
            # Method 1: With namespace
            ns = {"dzi": "http://schemas.microsoft.com/deepzoom/2008"}
            size_elem = root.find(".//dzi:Size", ns)

            # Method 2: Without namespace (pyvips may not include namespace)
            if size_elem is None:
                size_elem = root.find(".//Size")

            # Method 3: Direct child of root
            if size_elem is None:
                size_elem = root.find("Size")

            # Method 4: root might be Image element itself
            if size_elem is None:
                for child in root:
                    if "Size" in child.tag:
                        size_elem = child
                        break

            if size_elem is not None:
                image_width = int(size_elem.get("Width"))
                image_height = int(size_elem.get("Height"))
            else:
                print(
                    f"Warning: Could not find Size element in DZI. Root tag: {root.tag}, children: {[c.tag for c in root]}"
                )

            # Get tile size from Image element
            if root.get("TileSize"):
                tile_size = int(root.get("TileSize"))

            print(
                f"Read image dimensions from DZI: {image_width}x{image_height}, tile_size={tile_size}"
            )
        except Exception as e:
            print(f"Warning: Could not parse DZI file: {e}")
            import traceback

            traceback.print_exc()

    # Discover zoom levels and tiles
    zoom_levels = sorted([int(d.name) for d in tiles_dir.iterdir() if d.is_dir()])

    if not zoom_levels:
        raise ValueError(f"No zoom levels found in {tiles_dir}")

    print(f"Found {len(zoom_levels)} zoom levels: {zoom_levels[0]} to {zoom_levels[-1]}")

    # Collect all tiles with their metadata
    all_tiles = []
    zoom_info = {}

    for zoom in zoom_levels:
        zoom_dir = tiles_dir / str(zoom)
        tile_files = list(zoom_dir.glob(f"*{image_format}"))

        # Parse tile coordinates from filenames (format: x_y.webp)
        tiles_in_zoom = []
        for tile_file in tile_files:
            parts = tile_file.stem.split("_")
            if len(parts) == 2:
                tile_x, tile_y = int(parts[0]), int(parts[1])
                image_bytes = tile_file.read_bytes()
                tiles_in_zoom.append((tile_x, tile_y, image_bytes))

        # Sort tiles in column-major order for consistent indexing
        tiles_in_zoom.sort(key=lambda t: (t[0], t[1]))

        # Calculate grid dimensions
        if tiles_in_zoom:
            max_x = max(t[0] for t in tiles_in_zoom)
            max_y = max(t[1] for t in tiles_in_zoom)
            num_tiles_x = max_x + 1
            num_tiles_y = max_y + 1
        else:
            num_tiles_x = 0
            num_tiles_y = 0

        zoom_info[zoom] = {
            "num_tiles_x": num_tiles_x,
            "num_tiles_y": num_tiles_y,
            "num_tiles": len(tiles_in_zoom),
            "row_group_offset": len(all_tiles),
        }

        all_tiles.extend([(zoom, tx, ty, data) for tx, ty, data in tiles_in_zoom])

    if not all_tiles:
        raise ValueError("No tiles found to pack")

    total_tiles = len(all_tiles)
    num_files = (total_tiles + max_row_groups_per_file - 1) // max_row_groups_per_file
    print(
        f"Packing {total_tiles} tiles into {num_files} parquet files "
        f"(max {max_row_groups_per_file} per file)..."
    )

    # Create output directory
    output_dir = Path(output_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create schema
    schema = pa.schema(
        [
            pa.field("zoom", pa.int32()),
            pa.field("tile_x", pa.int32()),
            pa.field("tile_y", pa.int32()),
            pa.field("image_data", pa.binary()),
        ]
    )

    # Add metadata
    metadata = {
        b"storage_mode": b"row_groups_image_chunked",
        b"zoom_info": json.dumps(zoom_info).encode("utf-8"),
        b"channel_name": channel_name.encode("utf-8"),
        b"image_format": image_format.encode("utf-8"),
    }
    schema = schema.with_metadata(metadata)

    # Write tiles to chunked parquet files
    file_list = []
    current_file_idx = 0
    current_row_in_file = 0
    writer = None

    for _tile_idx, (zoom, tile_x, tile_y, image_bytes) in enumerate(all_tiles):
        # Start a new file if needed
        if current_row_in_file == 0 or current_row_in_file >= max_row_groups_per_file:
            if writer is not None:
                writer.close()
            file_name = f"chunk_{current_file_idx}.parquet"
            file_path = output_dir / file_name
            file_list.append(file_name)
            writer = pq.ParquetWriter(str(file_path), schema, write_statistics=False)
            current_file_idx += 1
            current_row_in_file = 0

        # Write this tile as a row group
        tile_table = pa.table(
            {
                "zoom": [zoom],
                "tile_x": [tile_x],
                "tile_y": [tile_y],
                "image_data": [image_bytes],
            },
            schema=schema,
        )
        writer.write_table(tile_table)
        current_row_in_file += 1

    if writer is not None:
        writer.close()

    print(f"Wrote {total_tiles} image tiles across {len(file_list)} files to {output_dir}")

    # Delete source tile images if requested (but keep .dzi files for dimension info)
    if delete_source_tiles:
        import shutil

        print(f"Deleting source tile images from {tiles_dir}...")
        try:
            shutil.rmtree(tiles_dir)
            # Keep the .dzi file - it's tiny and provides image dimensions
            print(f"Deleted source tile images for {channel_name} (kept .dzi file)")
        except Exception as e:
            print(f"Warning: Could not delete source tiles: {e}")

    return {
        "channel_name": channel_name,
        "num_tiles": total_tiles,
        "zoom_levels": zoom_levels,
        "zoom_info": zoom_info,
        "image_width": image_width,
        "image_height": image_height,
        "tile_size": tile_size,
        # Chunk info for frontend
        "directory": channel_name,
        "files": file_list,
        "max_row_groups_per_file": max_row_groups_per_file,
        "total_row_groups": total_tiles,
    }
