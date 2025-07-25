"""
Main preprocessing script for Xenium data processing.
"""

import argparse
from pathlib import Path
import shutil

import pandas as pd

import celldega as dega


def _create_directories(directories):
    """
    Create directories if they don't exist.

    Parameters:
    - directories: List of directory paths to create
    """
    for folder in directories:
        folder_path = Path(folder)
        if not folder_path.exists():
            folder_path.mkdir(parents=True, exist_ok=True)
            print(f"Created directory: {folder}")


def create_dummy_clusters(path_landscape_files, cbg):
    _create_directories([f"{path_landscape_files}/cell_clusters"])

    inst_index = [str(x) for x in cbg.index.tolist()]
    meta_cell = pd.DataFrame(index=inst_index)
    meta_cell["cluster"] = "0"
    meta_cell.index = meta_cell.index.astype(str)
    meta_cell.to_parquet(f"{path_landscape_files}/cell_clusters/cluster.parquet")

    meta_cluster = pd.DataFrame(index=["0"], columns=["color", "count"])
    meta_cluster.loc["0", "color"] = "#1f77b4"
    meta_cluster.loc["0", "count"] = len(meta_cell)
    meta_cluster.to_parquet(f"{path_landscape_files}/cell_clusters/meta_cluster.parquet")


def _determine_technology(data_dir):
    """
    Determine technology based on files present in data directory.

    Parameters:
    - data_dir: Path to data directory

    Returns:
    - Technology type string

    Raises:
    - ValueError: If technology cannot be determined
    """
    data_path = Path(data_dir)

    # Determine technology based on characteristic files
    if (data_path / "experiment.xenium").exists():
        return "Xenium"
    if (data_path / "detected_transcripts.csv").exists():
        return "MERSCOPE"
    if (data_path / "registered_images").exists():
        return "IST"
    raise ValueError("Unsupported technology. Only Xenium, MERSCOPE and IST are supported in this script.")


def _setup_preprocessing_paths(technology, path_landscape_files, data_dir):
    """
    Setup preprocessing file paths.

    Parameters:
    - technology: Technology type (e.g., 'Xenium', 'MERSCOPE')
    - path_landscape_files: Base landscape files path
    - data_dir: Data directory path

    Returns:
    - Dictionary of file paths
    """
    landscape_path = Path(path_landscape_files)
    data_path = Path(data_dir)
    if technology == "Xenium":
        return {
            "transformation_matrix": landscape_path / "micron_to_image_transform.csv",
            "meta_cell_micron": data_path / "cells.csv.gz",
            "meta_cell_image": landscape_path / "cell_metadata.parquet",
            "meta_gene": landscape_path / "meta_gene.parquet",
            "transcripts": data_path / "transcripts.parquet",
            "transcript_tiles": landscape_path / "transcript_tiles",
            "cell_boundaries": data_path / "cell_boundaries.parquet",
            "cell_segmentation": landscape_path / "cell_segmentation",
            "cbg_matrix": data_path / "cell_feature_matrix",
        }
    if technology == "MERSCOPE":
        return {
            "transformation_matrix": data_path / "images/micron_to_mosaic_pixel_transform.csv",
            "meta_cell_micron": data_path / "cell_metadata.csv",
            "meta_cell_image": landscape_path / "cell_metadata.parquet",
            "meta_gene": landscape_path / "meta_gene.parquet",
            "transcripts": data_path / "detected_transcripts.csv",
            "transcript_tiles": landscape_path / "transcript_tiles",
            "cell_boundaries": data_path / "cell_boundaries.parquet",
            "cell_segmentation": landscape_path / "cell_segmentation",
            "cbg_csv": data_path / "cell_by_gene.csv",
        }
    if technology == "IST":
        dataset, inst_slice = dega.pre._parse_ist_names(str(data_path))
        return {
            "transformation_matrix": landscape_path / "micron_to_image_transform.csv",
            "meta_cell_image": landscape_path / "cell_metadata.parquet",
            "meta_gene": landscape_path / "meta_gene.parquet",
            "transcript_tiles": landscape_path / "transcript_tiles",
            "cell_boundaries": landscape_path / "cell_boundaries.parquet",
            "cell_segmentation": landscape_path / "cell_segmentation",
            "cbg_matrix": data_path / "matrix_files" / f"{inst_slice}_{dataset}" / f"{inst_slice}_{dataset}_raw",
            "image_file": data_path / "registered_images" / f"{inst_slice}_{dataset}.ome.tiff",
        }
    raise ValueError(
        "Unsupported technology. Only Xenium, MERSCOPE and IST are supported in this script."
    )


def main(
    sample,
    data_root_dir,
    tile_size,
    image_tile_layer,
    path_landscape_files,
    use_int_index=True,
    max_workers=1,
):
    """
    Main function to preprocess Xenium or MERSCOPE data and generate landscape files.

    Args:
        sample (str): Name of the sample (e.g., 'Xenium_V1_human_Pancreas_FFPE_outs').
        data_root_dir (str): Root directory containing all sample data. The
            ``sample`` name will be appended to this path to locate the
            specific dataset.
        tile_size (int): Size of the tiles for transcript and boundary tiles.
        image_tile_layer (str): Image layers to be tiled. 'dapi' or 'all'.
        path_landscape_files (str): Directory to save the landscape files.
        use_int_index (bool): Use integer index for smaller files and faster rendering.

    Example:
        change directory to celldega, and run:

        python run_pre_processing.py \
            --sample Xenium_V1_human_Pancreas_FFPE_outs \
            --data_root_dir data \
            --tile_size 250 \
            --image_tile_layer 'dapi' \
            --path_landscape_files notebooks/Xenium_V1_human_Pancreas_FFPE_outs

    """
    print(f"Starting preprocessing for sample: {sample}")

    # Construct data directory
    data_dir = Path(data_root_dir) / sample

    # Create necessary directories if they don't exist
    _create_directories([data_dir, path_landscape_files])

    # Determine technology
    technology = _determine_technology(data_dir)

    # Setup file paths
    paths = _setup_preprocessing_paths(technology, path_landscape_files, data_dir)

    # Save transformation matrices

    if technology == "Xenium":
        dega.pre._xenium_unzipper(str(data_dir))
        dega.pre.write_xenium_transform(str(data_dir), path_landscape_files)

    elif technology == "MERSCOPE":
        source_path = Path(paths["transformation_matrix"])
        shutil.copy(source_path, Path(path_landscape_files) / "micron_to_image_transform.csv")

    elif technology == "IST":
        dega.pre.write_identity_transform(path_landscape_files)

    # Check required files for preprocessing
    dega.pre._check_required_files(technology, str(data_dir))

    if technology in ["Xenium", "MERSCOPE"]:
        dega.pre.make_meta_cell_image_coord(
            technology,
            str(paths["transformation_matrix"]),
            str(paths["meta_cell_micron"]),
            str(paths["meta_cell_image"]),
            image_scale=1,
        )
    elif technology == "IST":
        dega.pre.make_meta_cell_ist(str(data_dir), path_landscape_files)

    # Calculate CBG
    if technology in ["Xenium", "IST"]:
        cbg = dega.pre.read_cbg_mtx(str(paths["cbg_matrix"]))
    elif technology == "MERSCOPE":
        cbg = pd.read_csv(str(paths["cbg_csv"]), index_col=0)

    if technology == "Xenium":
        dega.pre.cluster_gene_expression(technology, path_landscape_files, cbg, str(data_dir))
    else:
        create_dummy_clusters(path_landscape_files, cbg)

    # Make meta gene files
    dega.pre.make_meta_gene(cbg, str(paths["meta_gene"]))

    # Save CBG gene parquet files
    dega.pre.save_cbg_gene_parquets(path_landscape_files, cbg, verbose=True)

    if technology == "Xenium":
        # Create cluster and meta cluster files
        dega.pre.create_cluster_and_meta_cluster(technology, path_landscape_files, str(data_dir))

    if technology == "IST":

        print("\n======== Image tiles ========")
        dega.pre.create_image_tiles_ist(str(data_dir), path_landscape_files)

        tile_bounds = dega.pre.get_ist_image_bounds(str(paths["image_file"]))
        bound_path = dega.pre.make_cell_boundaries_ist(str(data_dir), path_landscape_files)

        print("\n======== Cell Boundary Tiles ========")
        dega.pre.make_cell_boundary_tiles(
            "custom",
            str(bound_path),
            str(paths["cell_segmentation"]),
            coarse_tile_factor=10,
            tile_size=tile_size,
            tile_bounds=tile_bounds,
            image_scale=1,
            max_workers=max_workers,
        )

    else:

        print("\n======== Image Tiles========")
        dega.pre.create_image_tiles(
            technology, str(data_dir), path_landscape_files, image_tile_layer=image_tile_layer
        )

        print("\n======== Transcript Tiles========")
        tile_bounds = dega.pre.make_trx_tiles(
            technology,
            str(paths["transcripts"]),
            str(paths["transformation_matrix"]),
            str(paths["transcript_tiles"]),
            coarse_tile_factor=10,
            tile_size=tile_size,
            chunk_size=100000,
            verbose=False,
            image_scale=1,
            max_workers=max_workers,
        )
        print(f"tile bounds: {tile_bounds}")

        print("\n======== Cell Boundary Tiles ========")
        dega.pre.make_cell_boundary_tiles(
            technology,
            str(paths["cell_boundaries"]),
            str(paths["cell_segmentation"]),
            str(paths.get("meta_cell_micron", "")),
            str(paths["transformation_matrix"]),
            coarse_tile_factor=10,
            tile_size=tile_size,
            tile_bounds=tile_bounds,
            max_workers=max_workers,
        )

    # Force name to be str for MERSCOPE
    if technology == "MERSCOPE":
        cell_meta = pd.read_parquet(str(paths["meta_cell_image"]))
        cell_meta["name"] = cell_meta["name"].astype(str)
        cell_meta.to_parquet(str(paths["meta_cell_image"]))

    # Save landscape parameters
    dega.pre.save_landscape_parameters(
        technology,
        path_landscape_files,
        "dapi_files",
        tile_size=tile_size,
        image_info=dega.pre.get_image_info(technology, image_tile_layer),
        image_format=".webp",
        use_int_index=use_int_index,
    )

    print("Preprocessing completed successfully.")


def _setup_argument_parser():
    """
    Setup and return argument parser.

    Returns:
    - Configured ArgumentParser instance
    """
    parser = argparse.ArgumentParser(
        description="Preprocess Xenium data and generate landscape files."
    )
    parser.add_argument(
        "--sample",
        required=True,
        help="Name of the sample (e.g., 'Xenium_V1_human_Pancreas_FFPE_outs').",
    )
    parser.add_argument(
        "--data_root_dir",
        required=True,
        help="Root directory containing all samples. The value will be joined with"
        " the provided sample name to locate the dataset.",
    )
    parser.add_argument(
        "--tile_size",
        type=int,
        required=True,
        help="Size of the tiles for transcript and boundary tiles.",
    )
    parser.add_argument(
        "--image_tile_layer", type=str, required=True, help="Image layers for tiling."
    )
    parser.add_argument(
        "--path_landscape_files", required=True, help="Directory to save the landscape files."
    )
    parser.add_argument(
        "--use_int_index",
        type=bool,
        required=False,
        default=True,
        help="Use integer index for smaller files and faster rendering at front end",
    )

    return parser


if __name__ == "__main__":
    # Set up argument parser
    parser = _setup_argument_parser()

    # Parse arguments
    args = parser.parse_args()

    # Run the main function
    main(
        args.sample,
        args.data_root_dir,
        args.tile_size,
        args.image_tile_layer,
        args.path_landscape_files,
        args.use_int_index,
    )
