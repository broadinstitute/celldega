"""
Module for pre-processing to generate LandscapeFiles from ST data.
"""

try:
    import pyvips
except ImportError:
    pyvips = None

import base64
import hashlib
import json
from pathlib import Path
import subprocess
import warnings
import xml.etree.ElementTree as ET

from matplotlib.colors import to_hex
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix, issparse
from shapely.geometry import MultiPolygon, Point, Polygon
from skimage.io import imread, imsave
import tifffile
import zarr

from .boundary_tile import (
    _round_nested_coord_list,
    make_cell_boundary_tiles,
    make_cell_boundary_tiles_row_groups,
)
from .image_info import get_image_info
from .landscape import (
    calc_meta_gene_data,
    read_cbg_mtx,
    save_cbg_gene_parquets,
    save_cbg_gene_parquets_row_groups,
)
from .run_pre_processing import main
from .sbg_tile import write_pseudotranscripts_from_sbg
from .trx_tile import make_trx_tiles, make_trx_tiles_row_groups


def _load_xenium_cluster_data(data_dir, meta_cell):
    """
    Load and process Xenium clustering data.

    Parameters:
    - data_dir: Path to data directory
    - meta_cell: Meta cell dataframe

    Returns:
    - Tuple of (default_clustering, clusters)
    """
    # Load the default clustering data
    default_clustering = pd.read_csv(
        Path(data_dir) / "analysis" / "clustering" / "gene_expression_graphclust" / "clusters.csv",
        index_col=0,
    )
    default_clustering.columns = default_clustering.columns.str.lower()

    # Prepare the clustering data
    default_clustering_ini = default_clustering.copy()
    default_clustering_ini["cluster"] = default_clustering_ini["cluster"].astype("string")

    # Align the clustering data with the cell metadata
    default_clustering = pd.DataFrame(index=meta_cell["name"].tolist())
    default_clustering.loc[default_clustering_ini.index.tolist(), "cluster"] = (
        default_clustering_ini["cluster"]
    )

    # Count the number of cells in each cluster
    ser_counts = default_clustering["cluster"].value_counts()
    clusters = ser_counts.index.tolist()

    return default_clustering, clusters, ser_counts


def _create_cluster_colors(clusters):
    """
    Create color mapping for clusters.

    Parameters:
    - clusters: List of cluster names

    Returns:
    - List of colors for clusters
    """
    palettes = [plt.get_cmap(name).colors for name in plt.colormaps() if "tab" in name]
    flat_colors = [color for palette in palettes for color in palette]
    flat_colors_hex = [to_hex(color) for color in flat_colors]

    return [
        (flat_colors_hex[i % len(flat_colors_hex)] if "Blank" not in cluster else "#FFFFFF")
        for i, cluster in enumerate(clusters)
    ]


def _save_cluster_data(cell_clusters_dir, default_clustering, clusters, ser_counts):
    """
    Save cluster and meta cluster data.

    Parameters:
    - cell_clusters_dir: Directory to save cluster data
    - default_clustering: Clustering dataframe
    - clusters: List of cluster names
    - ser_counts: Series with cluster counts
    """
    # Save the clustering data
    default_clustering.to_parquet(Path(cell_clusters_dir) / "cluster.parquet")

    # Assign colors to clusters
    colors = _create_cluster_colors(clusters)

    # Create the meta cluster DataFrame
    ser_color = pd.Series(colors, index=clusters, name="color")
    meta_cluster = pd.DataFrame(ser_color)
    meta_cluster["count"] = ser_counts

    # Save the meta cluster data
    meta_cluster.to_parquet(Path(cell_clusters_dir) / "meta_cluster.parquet")


def cluster_gene_expression(
    technology,
    path_landscape_files,
    cbg,
    data_dir=None,
    segmentation_approach="default",
):
    """
    Calculates cluster-specific gene expression signatures for Xenium data.

    Args:
        technology (str): The technology used (e.g., "Xenium" or "MERSCOPE"). Currently, only "Xenium" is supported.
        data_dir (str): Path to the directory containing the Xenium data.
        path_landscape_files (str): Path to the directory where the gene expression signature file will be saved.
        cbg (pd.DataFrame): A cell-by-gene matrix where rows represent cells and columns represent genes.
                            The index of the DataFrame should match the cell IDs in the Xenium metadata.

    Raises:
        ValueError: If the specified technology is not supported.
        FileNotFoundError: If the required input files are not found.
    """
    print("\n========Create cluster gene expression (df_sig)========")
    if technology not in ["Xenium", "custom"]:
        raise ValueError(
            f"Unsupported technology: {technology}. Currently, only 'Xenium' and 'Custom' is supported."
        )

    if technology == "Xenium":
        cells_csv_path = Path(data_dir) / "cells.csv.gz"
        clusters_csv_path = (
            Path(data_dir)
            / "analysis"
            / "clustering"
            / "gene_expression_graphclust"
            / "clusters.csv"
        )

        # Load the cell metadata
        usecols = ["cell_id", "x_centroid", "y_centroid"]
        meta_cell = pd.read_csv(cells_csv_path, index_col=0, usecols=usecols)
        meta_cell.columns = ["center_x", "center_y"]

        # Load the clustering data
        df_meta = pd.read_csv(clusters_csv_path, index_col=0)
        df_meta["Cluster"] = df_meta["Cluster"].astype("string")
        df_meta.columns = ["cluster"]

        # Add cluster information to the cell metadata
        meta_cell["cluster"] = df_meta["cluster"]
        clusters = meta_cell["cluster"].unique().tolist()

        # Calculate cluster-specific gene expression signatures
        list_ser = []
        for inst_cat in meta_cell["cluster"].unique().tolist():
            if inst_cat is not None:
                inst_cells = meta_cell[meta_cell["cluster"] == inst_cat].index.tolist()
                inst_ser = cbg.loc[inst_cells].sum() / len(inst_cells)
                inst_ser.name = inst_cat
                list_ser.append(inst_ser)

    elif technology == "custom":
        df_cluster = pd.read_parquet(
            Path(path_landscape_files)
            / f"cell_clusters_{segmentation_approach}"
            / "cluster.parquet"
        )
        clusters = df_cluster["cluster"].unique().tolist()

        list_ser = []
        for inst_cat in df_cluster["cluster"].unique():
            if inst_cat is not None:
                inst_cells = df_cluster[df_cluster["cluster"] == inst_cat].index.tolist()

                if set(inst_cells) & set(cbg.index):
                    common_cells = list(set(inst_cells) & set(cbg.index))
                    inst_ser = cbg.loc[common_cells].sum() / len(common_cells)
                else:
                    genes = cbg.columns
                    inst_ser = pd.Series(0.0, index=genes)

                inst_ser.name = inst_cat
                list_ser.append(inst_ser)

    # Combine the signatures into a DataFrame
    df_sig = pd.concat(list_ser, axis=1)

    # Handle potential multiindex issues
    df_sig.columns = df_sig.columns.tolist()
    df_sig.index = df_sig.index.tolist()

    # Filter out unwanted genes
    keep_genes = df_sig.index.tolist()
    keep_genes = [x for x in keep_genes if "Unassigned" not in x]
    keep_genes = [x for x in keep_genes if "NegControl" not in x]
    keep_genes = [x for x in keep_genes if "DeprecatedCodeword" not in x]

    # Subset the DataFrame to keep only relevant genes and clusters
    df_sig = df_sig.loc[keep_genes, clusters]

    # drop columns with Nan values
    df_sig = df_sig.dropna(axis=1, how="all")

    df_sig = df_sig.loc[sorted(df_sig.index), sorted(df_sig.columns)]

    # Save the gene expression signatures
    segmentation_suffix = f"_{segmentation_approach}" if segmentation_approach != "default" else ""
    output_path = Path(path_landscape_files) / f"df_sig{segmentation_suffix}.parquet"

    if any(isinstance(dtype, pd.SparseDtype) for dtype in df_sig.dtypes):
        df_sig.sparse.to_dense().to_parquet(output_path)
    else:
        df_sig.to_parquet(output_path)

    print("Cluster-specific gene expression signatures saved successfully.")

    return df_sig


def _convert_long_id_to_short(df):
    """Converts a column of long integer cell IDs in a DataFrame to a shorter, hash-based representation.

    Args:
        df (pd.DataFrame): The DataFrame containing the `EntityID` column.

    Returns:
        pd.DataFrame: The original DataFrame with an additional column named `cell_id`
                      containing the shortened cell IDs.

    The function applies a SHA-256 hash to each cell ID, encodes the hash using base64, and truncates
    it to create a shorter identifier that is added as a new column to the DataFrame.
    """

    def hash_and_shorten_id(cell_id):
        # Create a hash of the cell ID
        cell_id_bytes = str(cell_id).encode("utf-8")
        hash_object = hashlib.sha256(cell_id_bytes)
        hash_digest = hash_object.digest()

        # Encode the hash to a base64 string to mix letters and numbers, truncate to 9 characters
        return base64.urlsafe_b64encode(hash_digest).decode("utf-8")[:9]

    # Apply the hash_and_shorten_id function to each cell ID in the specified column
    df["cell_id"] = df["EntityID"].apply(hash_and_shorten_id)

    return df


def create_cluster_and_meta_cluster(
    technology, path_landscape_files, data_dir=None, segmentation_approach="default"
):
    """
    Creates cell clusters and meta cluster files for visualization.
    Currently supports only Xenium.

    Args:
        technology (str): The technology used (e.g., "Xenium" or "MERSCOPE"). Currently, only "Xenium" is supported.
        data_dir (str): Path to the directory containing the Xenium data.
        path_landscape_files (str): Path to the directory where the cluster and meta cluster files will be saved.

    Raises:
        ValueError: If the specified technology is not supported.
        FileNotFoundError: If the required input files are not found.
    """
    print("\n========Create clusters and meta clusters files========")

    if technology not in ["Xenium", "custom"]:
        raise ValueError(
            f"Unsupported technology: {technology}. Currently, only 'Xenium' and 'Custom' is supported."
        )

    # Check if the cell metadata file exists
    segmentation_suffix = f"_{segmentation_approach}" if segmentation_approach != "default" else ""
    cell_metadata_path = Path(path_landscape_files) / f"cell_metadata{segmentation_suffix}.parquet"

    if not cell_metadata_path.exists():
        raise FileNotFoundError(
            f"The file '{cell_metadata_path.name}' does not exist in directory '{path_landscape_files}'."
        )

    # Create the cell_clusters directory if it doesn't exist
    cell_clusters_dir = Path(path_landscape_files) / f"cell_clusters{segmentation_suffix}"
    cell_clusters_dir.mkdir(exist_ok=True)

    # Load the cell metadata
    meta_cell = pd.read_parquet(cell_metadata_path)

    if technology == "Xenium":
        default_clustering, clusters, ser_counts = _load_xenium_cluster_data(data_dir, meta_cell)
        _save_cluster_data(cell_clusters_dir, default_clustering, clusters, ser_counts)

    elif technology == "custom":
        df_cluster = pd.DataFrame(index=meta_cell["name"].tolist())
        df_cluster["cluster"] = "0"
        df_cluster["cluster"] = df_cluster["cluster"].astype("string")
        df_cluster.to_parquet(cell_clusters_dir / "cluster.parquet")

        meta_cluster = pd.DataFrame(index=["0"])
        meta_cluster.loc["0", "color"] = "#1f77b4"
        meta_cluster.loc["0", "count"] = len(meta_cell["name"].tolist())
        meta_cluster.to_parquet(cell_clusters_dir / "meta_cluster.parquet")

        ser_counts = df_cluster["cluster"].value_counts()
        clusters = ser_counts.index.tolist()

    print("Cell clusters and meta cluster files created successfully.")

    return clusters


def _process_image_channel(path_landscape_files, channel_info, img):
    """
    Process a single image channel for tiling.

    Parameters:
    - path_landscape_files: Landscape files path
    - channel_info: Dictionary with channel information (name, index)
    - img: Optional pre-loaded image array

    Returns:
    - None
    """
    channel_name = channel_info["name"]
    channel_index = channel_info.get("index", 0)

    print(f"generating {channel_name} image tiles ...")

    pyramid_path = Path(path_landscape_files) / "pyramid_images" / f"{channel_name}_files"
    if pyramid_path.exists():
        return

    # Extract and process the channel
    scale = 1 if channel_name.lower() == "dapi" else 2  # Adjust intensity for better visualization
    if img.ndim == 3:
        image_data = img[..., channel_index] * scale
    elif img.ndim == 2:
        image_data = img * scale
    else:
        raise ValueError(f"Unsupported image dimensions: {img.ndim}. Expected 2D or 3D image.")

    output_path = Path(path_landscape_files) / f"{channel_name}_output_regular.tif"
    imsave(output_path, image_data)

    # Convert the image to PNG format
    image_png = _convert_to_png(str(output_path))

    # Create a DeepZoom pyramid for the channel
    make_deepzoom_pyramid(
        image_png,
        str(Path(path_landscape_files) / "pyramid_images"),
        channel_name,
        suffix=".webp[Q=100]",
    )


def create_image_tiles(technology, data_dir, path_landscape_files, image_tile_layer="dapi"):
    """
    Creates image tiles for visualization from the Xenium morphology image.

    Args:
        technology (str): The technology used (e.g., "Xenium", "MERSCOPE", "VisiumHD", "H&E").
        data_dir (str): Path to the directory containing the data (e.g., morphology_focus_0000.ome.tif).
        path_landscape_files (str): Path to the directory where the image tiles and pyramid will be saved.
        image_tile_layer (str, optional): Specifies which image layers to process. Options for Xenium are
        'dapi' (default) or 'all'. Use the filename of the .scn file for h&e Landscapes.

    Raises:
        ValueError: If the specified technology is not supported or if the image_tile_layer is invalid.
        FileNotFoundError: If the required input image file is not found.
    """
    print("\n========Generating image tiles========")
    if technology == "Xenium":
        print("------ xenium")
        create_image_tiles_xenium(data_dir, path_landscape_files, image_tile_layer=image_tile_layer)
    elif technology == "MERSCOPE":
        print("------ merscope")
        create_image_tiles_merscope(
            data_dir, path_landscape_files, image_tile_layer=image_tile_layer
        )
    elif technology == "h&e":
        print("------ h&e")
        create_image_tiles_h_and_e(
            data_dir, path_landscape_files, image_tile_layer=image_tile_layer
        )

    print("Image tiles created successfully.")


def create_image_tiles_h_and_e(data_dir, path_landscape_files, image_tile_layer):
    """
    Creates image tiles for visualization from the H&E image.

    Args:
        data_dir (str): Path to the directory containing the data (e.g., morphology_focus_0000.ome.tif).
        path_landscape_files (str): Path to the directory where the image tiles and pyramid will be saved.
        image_tile_layer (str, optional): Specifies the name of the h&e image to process.
    Raises:
        FileNotFoundError: If the required input image file is not found.
    """
    with tifffile.TiffFile(Path(data_dir) / image_tile_layer) as tif:
        print(tif.pages)  # Show available pages
        image = tif.pages[0].asarray()

        # make this directory, path_landscape_files, if it does not exist
        landscape_path = Path(path_landscape_files)
        landscape_path.mkdir(exist_ok=True)

        temp_tiff_path = landscape_path / image_tile_layer.replace(".scn", "_output_regular.tif")
        tifffile.imwrite(temp_tiff_path, image)

        # Convert the image to PNG format
        image_png = _convert_to_png(str(temp_tiff_path))

        # Create a DeepZoom pyramid for the DAPI channel
        make_deepzoom_pyramid(
            image_png,
            str(landscape_path / "pyramid_images"),
            "h_and_e",
            suffix=".webp[Q=100]",
        )

        remove_intermediate_files(path_landscape_files)


def remove_intermediate_files(path_landscape_files):
    """
    Remove intermediate image files.

    Parameters:
    - path_landscape_files: Path to landscape files directory
    """
    # Remove intermediate files
    intermediate_image_files = list(Path(path_landscape_files).glob("*output_regular*"))
    for file in intermediate_image_files:
        file.unlink()


def create_image_tiles_xenium(data_dir, path_landscape_files, image_tile_layer="dapi"):
    """
    Creates image tiles for visualization from the Xenium morphology image.

    Args:
        data_dir (str): Path to the directory containing the data (e.g., morphology_focus_0000.ome.tif).
        path_landscape_files (str): Path to the directory where the image tiles and pyramid will be saved.
        image_tile_layer (str, optional): Specifies which image layers to process. Options are 'dapi' (default) or 'all'.
    Raises:
        FileNotFoundError: If the required input image file is not found.
    """
    if image_tile_layer not in ["dapi", "all"]:
        raise ValueError(f"Invalid image_tile_layer: {image_tile_layer}. Must be 'dapi' or 'all'.")

    # Define the path to the morphology image
    file_path = Path(data_dir) / "morphology_focus" / "morphology_focus_0000.ome.tif"

    # Check if the morphology image exists
    if not file_path.exists():
        raise FileNotFoundError(
            f"The file 'morphology_focus_0000.ome.tif' does not exist in directory '{data_dir}'."
        )

    # Load the morphology image once if processing multiple channels
    img = imread(file_path)

    # Process the DAPI channel
    if image_tile_layer in ["dapi", "all"]:
        _process_image_channel(path_landscape_files, {"name": "dapi", "index": 0}, img)

    # Process additional channels if image_tile_layer is 'all'
    if image_tile_layer == "all":
        for idx, channel in enumerate(["bound", "rna", "prot"]):
            _process_image_channel(path_landscape_files, {"name": channel, "index": idx + 1}, img)

    remove_intermediate_files(path_landscape_files)


def create_image_tiles_merscope(data_dir, path_landscape_files, image_tile_layer="dapi"):
    """
    Creates image tiles for visualization from the Xenium morphology image.

    Args:
        data_dir (str): Path to the directory containing the data (e.g., morphology_focus_0000.ome.tif).
        path_landscape_files (str): Path to the directory where the image tiles and pyramid will be saved.
        image_tile_layer (str, optional): Specifies which image layers to process. Options are 'dapi' (default) or 'all'.
    Raises:
        FileNotFoundError: If the required input image file is not found.
    """
    if image_tile_layer not in ["dapi", "all"]:
        raise ValueError(f"Invalid image_tile_layer: {image_tile_layer}. Must be 'dapi' or 'all'.")

    # Define the path to the DAPI image
    dapi_file_path = Path(data_dir) / "images" / "mosaic_DAPI_z3.tif"

    # Check if the DAPI image exists
    if not dapi_file_path.exists():
        raise FileNotFoundError(
            f"The file 'mosaic_DAPI_z3.tif' does not exist in directory '{data_dir}'."
        )

    # Load the DAPI image once if processing multiple channels
    img_dapi = imread(dapi_file_path)

    # Process the DAPI channel
    _process_image_channel(path_landscape_files, {"name": "dapi", "index": 0}, img_dapi)

    # Process additional channels if image_tile_layer is 'all'
    if image_tile_layer == "all":
        # Define the path to the boundary image
        bounda_file_path = Path(data_dir) / "images" / "mosaic_Cellbound1_z3.tif"

        # Check if the boundary image exists
        if not bounda_file_path.exists():
            raise FileNotFoundError(
                f"The file 'mosaic_Cellbound1_z3.tif' does not exist in directory '{data_dir}'."
            )

        # Load the boundary image once if processing multiple channels
        img_bound = imread(bounda_file_path)

        # Process the boundary channel
        _process_image_channel(path_landscape_files, {"name": "bound", "index": 0}, img_bound)

    remove_intermediate_files(path_landscape_files)


def _reduce_image_size(image_path, scale_image=0.5, path_landscape_files=""):
    """Reduces the size of an image by a specified scale factor.

    Args:
        image_path (str): Path to the image file.
        scale_image (float, optional): Scale factor for the image resize. Defaults to 0.5.
        path_landscape_files (str, optional): Directory to save the resized image. Defaults to "".

    Returns:
        str: Path to the resized image file.
    """
    image = pyvips.Image.new_from_file(image_path, access="sequential")
    resized_image = image.resize(scale_image)

    new_image_name = Path(image_path).name.replace(".tif", "_downsize.tif")
    new_image_path = Path(path_landscape_files) / new_image_name
    resized_image.write_to_file(str(new_image_path))

    return str(new_image_path)


def _convert_to_jpeg(image_path, quality=80):
    """Converts a TIFF image to a JPEG image with a specified quality score.

    Args:
        image_path (str): Path to the image file.
        quality (int, optional): Quality score for the JPEG image. Defaults to 80.

    Returns:
        str: Path to the JPEG image file.
    """
    image = pyvips.Image.new_from_file(image_path, access="sequential")
    new_image_path = str(Path(image_path).with_suffix(".jpeg"))
    image.jpegsave(new_image_path, Q=quality)

    return new_image_path


def _convert_to_png(image_path):
    """Converts a TIFF image to a PNG image.

    Args:
        image_path (str): Path to the image file.

    Returns:
        str: Path to the PNG image file.
    """
    image = pyvips.Image.new_from_file(image_path, access="sequential")
    new_image_path = str(Path(image_path).with_suffix(".png"))
    image.pngsave(new_image_path)

    return new_image_path


def _convert_to_webp(image_path, quality=100):
    """Converts a TIFF image to a WEBP image with a specified quality score.

    Args:
        image_path (str): Path to the image file.
        quality (int, optional): Quality score for the WEBP image. Defaults to 100.

    Returns:
        str: Path to the WEBP image file.
    """
    image = pyvips.Image.new_from_file(image_path, access="sequential")
    new_image_path = str(Path(image_path).with_suffix(".webp"))
    image.webpsave(new_image_path, Q=quality)

    return new_image_path


def make_deepzoom_pyramid(
    image_path, output_path, pyramid_name, tile_size=512, overlap=0, suffix=".jpeg"
):
    """Creates a DeepZoom image pyramid from a JPEG image.

    Args:
        image_path (str): Path to the JPEG image file.
        output_path (str): Directory to save the DeepZoom pyramid.
        pyramid_name (str): Name of the pyramid directory.
        tile_size (int, optional): Tile size for the DeepZoom pyramid. Defaults to 512.
        overlap (int, optional): Overlap size for the DeepZoom pyramid. Defaults to 0.
        suffix (str, optional): Suffix for the DeepZoom pyramid tiles. Defaults to ".jpeg".

    Returns:
        None
    """
    output_path = Path(output_path)
    image = pyvips.Image.new_from_file(image_path, access="sequential")
    output_path.mkdir(parents=True, exist_ok=True)
    output_path = output_path / pyramid_name
    image.dzsave(str(output_path), tile_size=tile_size, overlap=overlap, suffix=suffix)


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


def _load_meta_cell_by_technology(technology, path_meta_cell_micron, paths=None, dataset=None):
    """
    Load meta cell data based on technology.

    Parameters:
    - technology: Technology type
    - path_meta_cell_micron: Path to meta cell micron data

    Returns:
    - Meta cell dataframe
    """
    if technology == "MERSCOPE":
        meta_cell = pd.read_csv(path_meta_cell_micron, usecols=["EntityID", "center_x", "center_y"])
        # meta_cell = _convert_long_id_to_short(meta_cell)
        meta_cell["cell_id"] = meta_cell["EntityID"]
        meta_cell["name"] = meta_cell["cell_id"]
        meta_cell = meta_cell.set_index("cell_id")
    elif technology == "Xenium":
        usecols = ["cell_id", "x_centroid", "y_centroid"]
        meta_cell = pd.read_csv(path_meta_cell_micron, index_col=0, usecols=usecols)
        meta_cell.columns = ["center_x", "center_y"]
        meta_cell["name"] = pd.Series(meta_cell.index, index=meta_cell.index)

    elif technology == "custom":
        import geopandas as gpd

        meta_cell = gpd.read_parquet(path_meta_cell_micron)
        meta_cell["center_x"] = meta_cell.centroid.x
        meta_cell["center_y"] = meta_cell.centroid.y
        meta_cell["name"] = pd.Series(meta_cell.index, index=meta_cell.index).astype("str")
        cols_to_drop = [c for c in ["area", "centroid"] if c in meta_cell.columns]
        if cols_to_drop:
            meta_cell.drop(columns=cols_to_drop, inplace=True)
    else:
        raise ValueError(f"Unsupported technology: {technology}")
    return meta_cell


def make_meta_cell_image_coord(
    technology,
    path_transformation_matrix,
    path_meta_cell_micron,
    path_meta_cell_image,
    image_scale=1,
    sample=None,
    paths=None,
    dataset=None,
):
    """Applies an affine transformation to cell coordinates in microns and saves the transformed coordinates in pixels.

    Parameters
    ----------
    technology : str
        The technology used to generate the data, Xenium and MERSCOPE are supported.
    path_transformation_matrix : str
        Path to the transformation matrix file
    path_meta_cell_micron : str
        Path to the meta cell file with coordinates in microns
    path_meta_cell_image : str
        Path to save the meta cell file with coordinates in pixels

    Returns
    -------
    None

    Examples
    --------
    >>> make_meta_cell_image_coord(
    ...     technology='Xenium',
    ...     path_transformation_matrix='data/transformation_matrix.csv',
    ...     path_meta_cell_micron='data/meta_cell_micron.csv',
    ...     path_meta_cell_image='data/meta_cell_image.parquet'
    ... )
    Args:
        technology (str): The technology used to generate the data (e.g., "Xenium" or "MERSCOPE").
        path_transformation_matrix (str): Path to the transformation matrix file.
        path_meta_cell_micron (str): Path to the meta cell file with coordinates in microns.
        path_meta_cell_image (str): Path to save the meta cell file with coordinates in pixels.
        image_scale (float): Scaling factor to convert micron coordinates to pixel coordinates.

    Returns:
        None
    """
    print("\n========Make meta cells in pixel space========")
    transformation_matrix = pd.read_csv(path_transformation_matrix, header=None, sep=" ").values
    sparse_matrix = csr_matrix(transformation_matrix)

    meta_cell = _load_meta_cell_by_technology(
        technology,
        path_meta_cell_micron,
        paths=paths,
        dataset=dataset,
    )

    print("meta_cell after _load_meta_cell_by_technology")
    print(meta_cell.head())

    # Adding a ones column to accommodate for affine transformation
    meta_cell["ones"] = 1
    points = meta_cell[["center_x", "center_y", "ones"]].values

    # Applying the transformation matrix
    transformed_points = sparse_matrix.dot(points.T).T[:, :2]

    meta_cell["center_x"] = transformed_points[:, 0]
    meta_cell["center_y"] = transformed_points[:, 1]
    meta_cell.drop(columns=["ones"], inplace=True)

    meta_cell["center_x"] = meta_cell["center_x"] / image_scale
    meta_cell["center_y"] = meta_cell["center_y"] / image_scale

    meta_cell["geometry"] = meta_cell.apply(lambda row: [row["center_x"], row["center_y"]], axis=1)

    if technology == "MERSCOPE":
        meta_cell = meta_cell[["name", "geometry", "EntityID"]]
    else:
        meta_cell = meta_cell[["name", "geometry"]]

    # Check if the 'name' column is unique
    if not meta_cell["name"].is_unique:
        warnings.warn("Duplicate cell names found in meta_cell!", UserWarning, stacklevel=2)

    # Apply rounding to the GEOMETRY column
    meta_cell["geometry"] = meta_cell["geometry"].apply(_round_nested_coord_list)

    # Force alphabetically sort by 'name'
    meta_cell = meta_cell.sort_values(by=["name"]).reset_index(drop=True)
    meta_cell.to_parquet(path_meta_cell_image, index=False)
    print("Done.")


def make_meta_gene(cbg, path_output):
    """Creates a DataFrame with genes and their assigned colors.

    Args:
        cbg (pandas.DataFrame): A sparse DataFrame with genes as columns and barcodes as rows..
        path_output (str): Path to save the meta gene file.

    Returns:
        None
    """
    print("\n========Write meta gene files========")
    genes = cbg.columns.tolist()

    palettes = [plt.get_cmap(name).colors for name in plt.colormaps() if "tab" in name]
    flat_colors = [color for palette in palettes for color in palette]
    flat_colors_hex = [to_hex(color) for color in flat_colors]

    colors = [
        flat_colors_hex[i % len(flat_colors_hex)] if "Blank" not in gene else "#FFFFFF"
        for i, gene in enumerate(genes)
    ]

    ser_color = pd.Series(colors, index=genes)
    meta_gene = calc_meta_gene_data(cbg)
    meta_gene["color"] = ser_color

    sparse_cols = [col for col in meta_gene.columns if pd.api.types.is_sparse(meta_gene[col])]
    for col in sparse_cols:
        meta_gene[col] = meta_gene[col].sparse.to_dense()

    # Force alphabetically sort by index
    meta_gene.sort_index(inplace=True)
    meta_gene.to_parquet(path_output)
    print("All meta gene files are succesfully saved.")


def make_chromium_from_anndata(adata, path_landscape_files):
    """Generate minimal LandscapeFiles from a Chromium AnnData object.

    Parameters
    ----------
    adata : anndata.AnnData
        AnnData object containing scRNA-seq count data.
    path_landscape_files : str or Path
        Directory where LandscapeFiles will be written.

    Raises
    ------
    ValueError
        If the expression matrix contains non-integer values.
    """

    print("\n========Process Chromium AnnData========")
    path_landscape_files = Path(path_landscape_files)
    path_landscape_files.mkdir(parents=True, exist_ok=True)

    X = adata.layers.get("counts", adata.X)

    data = X.data if issparse(X) else np.asarray(X)

    if not np.all(np.equal(np.mod(data, 1), 0)):
        raise ValueError("Chromium processing requires integer counts")

    if issparse(X):
        cbg = pd.DataFrame.sparse.from_spmatrix(X, index=adata.obs_names, columns=adata.var_names)
    else:
        cbg = pd.DataFrame(X, index=adata.obs_names, columns=adata.var_names)

    cell_meta = pd.DataFrame({"name": adata.obs_names, "geometry": [[0.0, 0.0]] * adata.n_obs})
    cell_meta.to_parquet(path_landscape_files / "cell_metadata.parquet", index=False)

    save_cbg_gene_parquets("Chromium", path_landscape_files, cbg)

    make_meta_gene(cbg, path_landscape_files / "meta_gene.parquet")

    (path_landscape_files / "pyramid_images").mkdir(exist_ok=True)

    save_landscape_parameters(
        technology="Chromium",
        path_landscape_files=path_landscape_files,
        image_name="",
        tile_size=1,
        image_info=[],
    )


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
    path_landscape_files,
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
        path_landscape_files (str): Path to the directory where landscape files are stored.
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
        path_image_pyramid = Path(path_landscape_files) / "pyramid_images" / image_name
        max_pyramid_zoom = get_max_zoom_level(path_image_pyramid)

    path_landscape_parameters = Path(path_landscape_files) / "landscape_parameters.json"

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
            pyramid_images_dir = Path(path_landscape_files) / "pyramid_images"
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


def add_custom_segmentation(
    technology, path_landscape_files, path_segmentation_files, image_scale=1, tile_size=250
):
    """
    Add custom segmentation to existing landscape files.

    Parameters:
    - technology: Technology type (e.g., "Xenium", "MERSCOPE", "custom")
    - path_landscape_files: Path to landscape files
    - path_segmentation_files: Path to segmentation files
    - image_scale: Image scale factor
    - tile_size: Tile size for processing
    """
    with (Path(path_segmentation_files) / "segmentation_parameters.json").open() as file:
        segmentation_parameters = json.load(file)

    cbg_custom = pd.read_parquet(Path(path_segmentation_files) / "cell_by_gene_matrix.parquet")

    # make sure all genes are present in cbg_custom
    meta_gene = pd.read_parquet(Path(path_landscape_files) / "meta_gene.parquet")
    missing_cols = meta_gene.index.difference(cbg_custom.columns)
    for col in missing_cols:
        cbg_custom[col] = 0

    make_meta_gene(
        cbg=cbg_custom,
        path_output=Path(path_landscape_files)
        / f"meta_gene_{segmentation_parameters['segmentation_approach']}.parquet",
    )

    make_meta_cell_image_coord(
        technology=segmentation_parameters["technology"],
        path_transformation_matrix=str(
            Path(path_landscape_files) / "micron_to_image_transform.csv"
        ),
        path_meta_cell_micron=str(
            Path(path_segmentation_files) / "cell_metadata_micron_space.parquet"
        ),
        path_meta_cell_image=str(
            Path(path_landscape_files)
            / f"cell_metadata_{segmentation_parameters['segmentation_approach']}.parquet"
        ),
        image_scale=image_scale,
    )

    save_cbg_gene_parquets(
        technology=technology,
        base_path=path_landscape_files,
        cbg=cbg_custom,
        verbose=True,
        segmentation_approach=segmentation_parameters["segmentation_approach"],
    )

    create_cluster_and_meta_cluster(
        technology=segmentation_parameters["technology"],
        path_landscape_files=path_landscape_files,
        segmentation_approach=segmentation_parameters["segmentation_approach"],
    )

    # Get the first .dzi file in sorted order
    dzi_files = sorted((Path(path_landscape_files) / "pyramid_images").glob("*.dzi"))
    if not dzi_files:
        raise FileNotFoundError("No .dzi files found in pyramid_images.")

    # Use the first .dzi file
    tree = ET.parse(dzi_files[0])
    root = tree.getroot()
    width = int(root[0].attrib["Width"])
    height = int(root[0].attrib["Height"])

    tile_bounds = {"x_min": 0, "x_max": width, "y_min": 0, "y_max": height}

    make_cell_boundary_tiles(
        technology=segmentation_parameters["technology"],
        path_cell_boundaries=str(Path(path_segmentation_files) / "cell_polygons.parquet"),
        path_output=str(
            Path(path_landscape_files)
            / f"cell_segmentation_{segmentation_parameters['segmentation_approach']}"
        ),
        tile_size=tile_size,
        tile_bounds=tile_bounds,
        image_scale=image_scale,
    )

    cluster_gene_expression(
        technology=segmentation_parameters["technology"],
        path_landscape_files=path_landscape_files,
        cbg=cbg_custom,
        segmentation_approach=segmentation_parameters["segmentation_approach"],
    )

    save_landscape_parameters(
        technology=segmentation_parameters["technology"],
        path_landscape_files=path_landscape_files,
        image_name="dapi_files",
        tile_size=tile_size,
        image_format=".webp",
        segmentation_approach=segmentation_parameters["segmentation_approach"],
    )


def _to_geometry(coord_data):
    """
    Converts a coordinate structure back to a Shapely geometry object.

    Accepts:
      - [x, y] → Point
      - {"exterior": [...], "interiors": [...]} → Polygon
      - list of {"exterior": [...], "interiors": [...]} → MultiPolygon

    Args:
        coord_data (list or dict): Coordinate list or structured dict.

    Returns:
        shapely.geometry.Point, Polygon, or MultiPolygon

    Raises:
        TypeError: If the input structure is not recognized.
    """

    if isinstance(coord_data, Point | Polygon | MultiPolygon):
        return coord_data

    if (
        isinstance(coord_data, list | tuple)
        and all(isinstance(x, int | float) for x in coord_data)
        and len(coord_data) == 2
    ):
        return Point(coord_data)

    if isinstance(coord_data, dict) and "exterior" in coord_data:
        exterior = coord_data["exterior"]
        interiors = coord_data.get("interiors", [])
        return Polygon(exterior, interiors)

    if isinstance(coord_data, list) and all(
        isinstance(poly, dict) and "exterior" in poly for poly in coord_data
    ):
        return MultiPolygon(
            [Polygon(poly["exterior"], poly.get("interiors", [])) for poly in coord_data]
        )

    raise TypeError(f"Cannot convert {coord_data} to a Shapely geometry. Unexpected structure.")


def _to_coords(geom):
    """
    Converts a Shapely geometry object to a serializable coordinate structure.

    Supports:
      - Point → [x, y]
      - Polygon → {"exterior": [...], "interiors": [...]}
      - MultiPolygon → list of {"exterior": [...], "interiors": [...]}

    Args:
        geom (shapely.geometry): A Shapely Point, Polygon, or MultiPolygon.

    Returns:
        list or dict: Coordinate representation suitable for serialization.

    Raises:
        TypeError: If the geometry type is unsupported.
    """
    if isinstance(geom, Point):
        return list(geom.coords[0])
    if isinstance(geom, Polygon):
        return {
            "exterior": [list(coord) for coord in geom.exterior.coords],
            "interiors": [
                [list(coord) for coord in interior.coords] for interior in geom.interiors
            ],
        }
    if isinstance(geom, MultiPolygon):
        return [
            {
                "exterior": [list(coord) for coord in polygon.exterior.coords],
                "interiors": [
                    [list(coord) for coord in interior.coords] for interior in polygon.interiors
                ],
            }
            for polygon in geom.geoms
        ]
    raise TypeError(f"Unsupported geometry type: {type(geom)}")


def write_xenium_transform(
    data_dir, path_landscape_files, transform_fname="micron_to_image_transform.csv"
):
    """
    Extracts the transformation matrix from the Xenium cells.zarr.zip file and saves it as a CSV file.

    Args:
        data_dir (str): Path to the directory containing the Xenium data (e.g., cells.zarr.zip).
        path_landscape_files (str): Path to the directory where the transformation matrix CSV will be saved.
        transform_fname (str, optional): Name of the output CSV file. Defaults to "micron_to_image_transform.csv".

    Returns:
        numpy.ndarray: The full transformation matrix extracted from the Xenium cells.zarr.zip file.

    Raises:
        FileNotFoundError: If the cells.zarr.zip file does not exist in the specified `data_dir`.
        KeyError: If the transformation matrix is not found in the Zarr file under the expected path.
        Exception: If an unexpected error occurs while processing the Zarr file.
    """
    print("\n========Write xenium transform file from the Zarr folder========")
    # Path to the cells.zarr.zip file
    cells_zarr_path = Path(data_dir) / "cells.zarr.zip"

    # Check if the cells.zarr.zip file exists
    if not cells_zarr_path.exists():
        raise FileNotFoundError(
            f"The file 'cells.zarr.zip' does not exist in directory '{data_dir}'."
        )

    # Function to open a Zarr file
    def open_zarr(path: str) -> zarr.Group:
        store = (
            zarr.ZipStore(path, mode="r") if path.endswith(".zip") else zarr.DirectoryStore(path)
        )
        return zarr.group(store=store)

    try:
        # Open the cells Zarr file
        root = open_zarr(str(cells_zarr_path))

        # Extract the transformation matrix
        transformation_matrix = root["masks"]["homogeneous_transform"][:]

        # Save the transformation matrix as a CSV file
        output_path = Path(path_landscape_files) / transform_fname
        pd.DataFrame(transformation_matrix[:3, :3]).to_csv(
            output_path, sep=" ", header=False, index=False
        )

        print(f"Transformation matrix saved to '{output_path}'.")
    except KeyError as e:
        raise KeyError(f"Could not find the transformation matrix in the Zarr file: {e}") from e
    except Exception as e:
        raise Exception(f"An error occurred while processing the Zarr file: {e}") from e

    return transformation_matrix


def _xenium_unzipper(target_dir):
    """
    Unzips and extracts Xenium-related files in the specified directory.
    If the unzipped files already exist, the function skips those steps.

    Args:
        target_dir (str): Path to the directory containing the compressed files.

    Raises:
        subprocess.CalledProcessError: If any of the commands fail to execute.
        FileNotFoundError: If the target directory does not exist.
    """
    print("\n========Unzip and extract Xenium-related files========")
    target_path = Path(target_dir)

    # Check if the target directory exists
    if not target_path.exists():
        raise FileNotFoundError(f"The directory '{target_dir}' does not exist.")

    # Save the current working directory
    original_dir = Path.cwd()

    try:
        # Change to the target directory
        import os

        os.chdir(target_path)

        extraction_tasks = [
            ("cells.csv", ["gzip", "-dk", "cells.csv.gz"]),
            ("cells.zarr", ["unzip", "cells.zarr.zip", "-d", "cells.zarr"]),
            ("analysis", ["tar", "-xvzf", "analysis.tar.gz"]),
            ("cell_feature_matrix", ["tar", "-xvzf", "cell_feature_matrix.tar.gz"]),
        ]

        for target_file, command in extraction_tasks:
            if not Path(target_file).exists():
                subprocess.run(
                    command,
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

        print("All files have been successfully extracted or skipped.")
    except subprocess.CalledProcessError as e:
        print(f"An error occurred while executing a command: {e}")
        raise
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        raise
    finally:
        # Restore the original working directory
        os.chdir(original_dir)


def _check_required_files(technology, data_dir):
    """
    Checks if all required files or directories exist for the specified technology.

    Args:
        technology (str): The technology to check files for (e.g., "Xenium" or "MERSCOPE").
        data_dir (str): Path to the directory containing the required files or directories.

    Raises:
        FileNotFoundError: If any required file or directory is missing.
        ValueError: If the specified technology is not supported.
    """
    print("\n========Check if all required files or directories exist========")

    # Define required files or directories for each technology
    required_files_mapping = {
        "Xenium": [
            "morphology_focus/morphology_focus_0000.ome.tif",
            "cells.zarr",
            "cells.csv",
            "cells.csv.gz",
            "cells.parquet",
            "transcripts.parquet",
            "cell_boundaries.parquet",
            "cell_feature_matrix",  # directory
            "analysis",  # directory
        ],
        "MERSCOPE": [
            "images/mosaic_DAPI_z3.tif",
            # "images/mosaic_Cellbound1_z3.tif",
            "images/micron_to_mosaic_pixel_transform.csv",
            "cell_metadata.csv",
            "detected_transcripts.csv",
            "cell_boundaries.parquet",
            "cell_by_gene.csv",
        ],
    }

    if technology not in required_files_mapping:
        raise ValueError(
            f"Unsupported technology: {technology}. Supported technologies are {list(required_files_mapping.keys())}."
        )

    required_files_or_dir = required_files_mapping[technology]
    data_path = Path(data_dir)

    # Raise an error if any files or directories are missing
    if missing_files_or_dir := [
        file for file in required_files_or_dir if not (data_path / file).exists()
    ]:
        raise FileNotFoundError(
            f"The following required files or directories are missing in directory '{data_dir}' "
            f"for technology '{technology}': {', '.join(missing_files_or_dir)}"
        )
    print(
        f"All required files or directories for technology '{technology}' are present in '{data_dir}'."
    )


def write_identity_transform(path_landscape_files: str) -> None:
    """Write an identity transform matrix for IST data."""
    path = Path(path_landscape_files) / "micron_to_image_transform.csv"
    if not path.exists():
        pd.DataFrame(np.eye(3)).to_csv(path, sep=" ", header=False, index=False)


def add_clustering_from_adata(
    adata,
    path_landscape_files: str,
    cluster_key: str = "leiden",
    segmentation_name: str | None = None,
) -> None:
    """
    Add cell clustering data from an AnnData object to LandscapeFiles.

    This function exports clustering assignments and associated colors from an
    AnnData object to the LandscapeFiles format, enabling the Landscape and
    Yearbook widgets to use custom clustering results.

    Parameters
    ----------
    adata : AnnData
        AnnData object containing clustering results in `obs[cluster_key]`.
        Colors can be provided in `uns[f"{cluster_key}_colors"]`.
    path_landscape_files : str or Path
        Path to the LandscapeFiles directory.
    cluster_key : str, default "leiden"
        Column name in `adata.obs` containing cluster assignments.
    segmentation_name : str, optional
        Name for this segmentation/clustering result. If provided, files will be
        saved as `cell_clusters_{segmentation_name}/`. If None, files are saved
        to the default `cell_clusters/` directory.

    Returns
    -------
    None

    Examples
    --------
    >>> import scanpy as sc
    >>> import celldega as dega
    >>>
    >>> # Load and cluster your data
    >>> adata = sc.read_h5ad("my_data.h5ad")
    >>> sc.tl.leiden(adata, resolution=0.5)
    >>>
    >>> # Add clustering to LandscapeFiles
    >>> dega.pre.add_clustering_from_adata(
    ...     adata,
    ...     path_landscape_files="./my_landscape_files",
    ...     cluster_key="leiden"
    ... )
    >>>
    >>> # For a custom segmentation with a specific name
    >>> dega.pre.add_clustering_from_adata(
    ...     adata,
    ...     path_landscape_files="./my_landscape_files",
    ...     cluster_key="leiden",
    ...     segmentation_name="cellpose2"
    ... )

    Notes
    -----
    The Landscape widget can use the custom clustering by setting the
    `segmentation` parameter to match the `segmentation_name`.
    """
    from contextlib import suppress

    import scanpy as sc

    path_lf = Path(path_landscape_files)

    # Determine output directory
    if segmentation_name:
        cluster_dir = path_lf / f"cell_clusters_{segmentation_name}"
    else:
        cluster_dir = path_lf / "cell_clusters"
    cluster_dir.mkdir(exist_ok=True)

    # Get cluster assignments
    if cluster_key not in adata.obs.columns:
        raise ValueError(f"Cluster key '{cluster_key}' not found in adata.obs")

    # Create cluster DataFrame
    df_cluster = pd.DataFrame(index=adata.obs.index)
    df_cluster["cluster"] = adata.obs[cluster_key].astype("string")
    df_cluster.to_parquet(cluster_dir / "cluster.parquet")

    # Get or generate colors
    cluster_counts = df_cluster["cluster"].value_counts().sort_index()
    clusters = cluster_counts.index.tolist()

    color_key = f"{cluster_key}_colors"
    colors = None
    if color_key in adata.uns:
        colors = adata.uns[color_key]
    else:
        # Try to generate colors using scanpy
        with suppress(Exception):
            sc.pl.umap(adata, color=cluster_key, show=False)
            plt.close()
            colors = adata.uns.get(color_key)

    # Fallback to generated colors
    if colors is None:
        colors = _create_cluster_colors(clusters)

    # Ensure we have enough colors
    if len(colors) < len(clusters):
        extra_colors = _create_cluster_colors(clusters[len(colors) :])
        colors = list(colors) + extra_colors

    # Create meta_cluster DataFrame
    meta_cluster = pd.DataFrame(index=clusters)
    meta_cluster["color"] = [
        colors[i] if i < len(colors) else "#808080" for i in range(len(clusters))
    ]
    meta_cluster["count"] = cluster_counts.values
    meta_cluster.to_parquet(cluster_dir / "meta_cluster.parquet")

    print(f"Clustering data saved to {cluster_dir}")


__all__ = [
    "_to_geometry",
    "add_clustering_from_adata",
    "boundary_tile",
    "get_image_info",
    "landscape",
    "main",
    "make_trx_tiles",
    "read_cbg_mtx",
    "trx_tile",
    "write_identity_transform",
]
