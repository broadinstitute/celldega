"""
Main preprocessing script for Xenium data processing.
"""

import argparse
from collections import defaultdict
from pathlib import Path
import shutil

import pandas as pd
import spatialdata as sd
from spatialdata_io import xenium

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


def _output_exists(path):
    """Check if a file or non-empty directory already exists."""
    p = Path(path)
    return p.exists() and (p.is_file() or any(p.iterdir()))


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
    raise ValueError(
        "Unsupported technology. Only Xenium and MERSCOPE are supported in this script."
    )


def _setup_preprocessing_paths(technology, path_landscape_files, data_dir, sample=None):
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

    raise ValueError(
        "Unsupported technology. Only Xenium and MERSCOPE are supported in this script."
    )


def _make_xenium_anndata(data_dir, path_landscape_files, write=True):
    path_landscape_files = Path(path_landscape_files)
    sample = path_landscape_files.name

    zarr_path = path_landscape_files / f"{sample}.zarr"

    # check if the zarr file already exists
    if zarr_path.exists():
        print(f"The file {zarr_path} already exists.")
        sdata = sd.read_zarr(zarr_path)
    else:
        # ingest xenium data raw output folder using spatialdata-io
        sdata = xenium(data_dir)
        sdata.write(zarr_path)
        print(f"Data written to {zarr_path} successfully.")

    # create anndata from sdata.tables["table"]
    adata = sdata.tables["table"]

    if write:
        h5ad_path = path_landscape_files / f"{sample}.h5ad"
        adata.write_h5ad(h5ad_path)
        print(f"AnnData written to {h5ad_path}")

    return adata


def main(
    sample,
    data_root_dir,
    tile_size,
    image_tile_layer="all",
    path_landscape_files="",
    use_int_index=True,
    max_workers=1,
    use_row_groups=False,
    max_row_groups_per_file=400,
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
        use_row_groups (bool): If True, save tiles as row groups in chunked parquet files
            instead of individual tile files. Defaults to False.
        max_row_groups_per_file (int): Maximum row groups per parquet file when using
            row groups mode. Lower values create more files but avoid parquet-wasm memory
            issues with dense datasets. Defaults to 400.

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
    paths = _setup_preprocessing_paths(technology, path_landscape_files, data_dir, sample=sample)

    # Transformation matrix
    transform_out = Path(path_landscape_files) / "micron_to_image_transform.csv"

    if not transform_out.exists():
        if technology == "Xenium":
            dega.pre._xenium_unzipper(str(data_dir))
            dega.pre.write_xenium_transform(str(data_dir), path_landscape_files)
        elif technology == "MERSCOPE":
            source_path = Path(paths["transformation_matrix"])
            shutil.copy(source_path, transform_out)
    else:
        print(f"Skipping transform step, using existing {transform_out}")

    # Check required files for preprocessing
    dega.pre._check_required_files(technology, str(data_dir))

    # Make meta_cell with image coordinates
    if not Path(paths["meta_cell_image"]).exists():
        if technology in ["Xenium", "MERSCOPE"]:
            dega.pre.make_meta_cell_image_coord(
                technology,
                str(transform_out),
                str(paths.get("meta_cell_micron", "")),
                str(paths["meta_cell_image"]),
                image_scale=1,
            )
    else:
        print(f"Skipping meta cell generation, found {paths['meta_cell_image']}")

    # Load CBG matrix
    if technology == "Xenium":
        cbg = dega.pre.read_cbg_mtx(str(paths["cbg_matrix"]), technology=technology)
    elif technology == "MERSCOPE":
        cbg = pd.read_csv(str(paths["cbg_csv"]), index_col=0)

    def make_column_names_unique_fast(df):
        counts = defaultdict(int)
        used = set()
        new_cols = []

        for col in df.columns:
            if col not in used:
                new_cols.append(col)
                used.add(col)
                counts[col] += 1
            else:
                while True:
                    new_name = f"{col}_{counts[col]}"
                    counts[col] += 1
                    if new_name not in used:
                        new_cols.append(new_name)
                        used.add(new_name)
                        break

        df.columns = new_cols
        return df

    if cbg.columns.duplicated().any():
        print("Duplicate columns found in CBG matrix. Making column names unique.")
        cbg = make_column_names_unique_fast(cbg)

    # Cell and Cluster Metadata
    cluster_file = Path(path_landscape_files) / "cell_clusters/cluster.parquet"
    df_sig_file = Path(path_landscape_files) / "df_sig.parquet"

    if technology == "Xenium":
        if not df_sig_file.exists():
            dega.pre.cluster_gene_expression(technology, path_landscape_files, cbg, str(data_dir))
        else:
            print(f"Skipping cluster gene expression, found {df_sig_file}")
    else:
        if not cluster_file.exists():
            create_dummy_clusters(path_landscape_files, cbg)

    # Make meta gene files
    if not Path(paths["meta_gene"]).exists():
        dega.pre.make_meta_gene(cbg, str(paths["meta_gene"]))
    else:
        print(f"Skipping meta gene file creation, found {paths['meta_gene']}")

    # Save CBG gene parquet files
    cbg_chunk_info = None
    if use_row_groups:
        # Row group mode: chunked parquet files with one row group per gene
        cbg_dir = Path(path_landscape_files) / "cbg"
        if not cbg_dir.exists() or not any(cbg_dir.glob("*.parquet")):
            cbg_chunk_info = dega.pre.save_cbg_gene_parquets_row_groups(
                technology,
                path_landscape_files,
                cbg,
                verbose=True,
                max_row_groups_per_file=max_row_groups_per_file,
            )
        else:
            print(f"Skipping CBG row groups, directory {cbg_dir} already exists")
    else:
        # Traditional mode: one parquet file per gene
        cbg_dir = Path(path_landscape_files) / "cbg"
        if not cbg_dir.exists() or not any(cbg_dir.glob("*.parquet")):
            dega.pre.save_cbg_gene_parquets(technology, path_landscape_files, cbg, verbose=True)
        else:
            print(f"Skipping CBG gene parquets, directory {cbg_dir} already populated")

    if technology == "Xenium" and not cluster_file.exists():
        # Create cluster and meta cluster files
        dega.pre.create_cluster_and_meta_cluster(technology, path_landscape_files, str(data_dir))

    # Image, Cell Boundary, and Transcript Tiles
    # Xenium and MERSCOPE
    if technology in ["MERSCOPE", "Xenium"]:
        print("\n======== Image Tiles========")
        dega.pre.create_image_tiles(
            technology, str(data_dir), path_landscape_files, image_tile_layer=image_tile_layer
        )

        # Optionally pack image tiles into parquet row groups
        # Store max_pyramid_zoom before deleting tiles
        image_tile_info = {}
        if use_row_groups:
            print("\n======== Packing Image Tiles to Parquet ========")
            pyramid_dir = Path(path_landscape_files) / "pyramid_images"

            # Determine which channels were created
            image_info = dega.pre.get_image_info(technology, image_tile_layer)
            for channel_info in image_info:
                channel_name = channel_info["name"]
                # Put chunked parquet files in pyramid_images/{channel_name}/ directory
                output_dir = pyramid_dir / channel_name

                # Check if already processed (directory with chunk files exists)
                if not output_dir.exists() or not list(output_dir.glob("chunk_*.parquet")):
                    try:
                        # Use default max_row_groups_per_file=2000 for images
                        # (higher than tiles since image tiles are smaller)
                        tile_info = dega.pre.pack_image_tiles_to_parquet(
                            str(pyramid_dir),
                            channel_name,
                            str(output_dir),
                            image_format=".webp",
                            delete_source_tiles=True,
                        )
                        image_tile_info[channel_name] = tile_info
                    except FileNotFoundError as e:
                        print(f"Warning: Could not pack {channel_name} tiles: {e}")
                else:
                    print(f"Skipping {channel_name} parquet, directory already exists")

        tile_bounds = None
        tile_grid_info = None

        # Chunk info for landscape_parameters.json
        trx_chunk_info = None
        cell_chunk_info = None

        if use_row_groups:
            # Row group mode: save tiles as row groups in chunked parquet files
            trx_output_dir = Path(path_landscape_files) / "transcripts"
            cell_output_dir = Path(path_landscape_files) / "cell_segmentation"

            need_trx_tiles = not trx_output_dir.exists()
            need_boundaries = not cell_output_dir.exists()

            if need_trx_tiles:
                print("\n======== Transcript Tiles (Row Groups) ========")
                tile_bounds, tile_grid_info, trx_chunk_info = dega.pre.make_trx_tiles_row_groups(
                    technology,
                    str(paths["transcripts"]),
                    str(transform_out),
                    str(trx_output_dir),
                    coarse_tile_factor=10,
                    tile_size=tile_size,
                    chunk_size=100000,
                    verbose=False,
                    image_scale=1,
                    max_workers=max_workers,
                    path_landscape_files=path_landscape_files,
                    max_row_groups_per_file=max_row_groups_per_file,
                )
                print(f"tile bounds: {tile_bounds}")
            else:
                print("Skipping transcript tiles, output already exists")

            if need_boundaries:
                print("\n======== Cell Boundary Tiles (Row Groups) ========")
                cell_chunk_info = dega.pre.make_cell_boundary_tiles_row_groups(
                    technology,
                    str(paths["cell_boundaries"]),
                    str(cell_output_dir),
                    str(paths.get("meta_cell_micron", "")),
                    str(transform_out),
                    coarse_tile_factor=10,
                    tile_size=tile_size,
                    tile_bounds=tile_bounds,
                    max_workers=max_workers,
                    path_landscape_files=path_landscape_files,
                    max_row_groups_per_file=max_row_groups_per_file,
                )
            else:
                print("Skipping cell boundary tiles, output already exists")
        else:
            # Traditional mode: save individual tile files
            need_trx_tiles = not _output_exists(paths["transcript_tiles"])
            need_boundaries = not _output_exists(paths["cell_segmentation"])

            if need_trx_tiles or need_boundaries:
                print("\n======== Transcript Tiles========")
                tile_bounds = dega.pre.make_trx_tiles(
                    technology,
                    str(paths["transcripts"]),
                    str(transform_out),
                    str(paths["transcript_tiles"]),
                    coarse_tile_factor=10,
                    tile_size=tile_size,
                    chunk_size=100000,
                    verbose=False,
                    image_scale=1,
                    max_workers=max_workers,
                )
                print(f"tile bounds: {tile_bounds}")
            else:
                print("Skipping transcript tiles, output already exists")

            if need_boundaries:
                print("\n======== Cell Boundary Tiles ========")
                dega.pre.make_cell_boundary_tiles(
                    technology,
                    str(paths["cell_boundaries"]),
                    str(paths["cell_segmentation"]),
                    str(paths.get("meta_cell_micron", "")),
                    str(transform_out),
                    coarse_tile_factor=10,
                    tile_size=tile_size,
                    tile_bounds=tile_bounds,
                    max_workers=max_workers,
                )
            else:
                print("Skipping cell boundary tiles, output already exists")
    else:
        raise ValueError(
            f"Unsupported technology: {technology}. Supported technologies are 'MERSCOPE' and 'Xenium'."
        )

    # Force name to be str for MERSCOPE
    if technology == "MERSCOPE":
        cell_meta = pd.read_parquet(str(paths["meta_cell_image"]))
        cell_meta["name"] = cell_meta["name"].astype(str)
        cell_meta.to_parquet(str(paths["meta_cell_image"]))

    check_img_directory = "dapi_files" if image_tile_layer == "all" else f"{image_tile_layer}_files"

    # Save landscape parameters
    dega.pre.save_landscape_parameters(
        technology,
        path_landscape_files,
        check_img_directory,
        tile_size=tile_size,
        image_info=dega.pre.get_image_info(technology, image_tile_layer),
        image_format=".webp",
        use_int_index=use_int_index,
        use_row_groups=use_row_groups,
        tile_grid_info=tile_grid_info,
        image_tile_info=image_tile_info if use_row_groups else None,
        trx_chunk_info=trx_chunk_info,
        cell_chunk_info=cell_chunk_info,
        cbg_chunk_info=cbg_chunk_info,
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
    parser.add_argument(
        "--use_row_groups",
        type=bool,
        required=False,
        default=False,
        help="Use row groups in a single parquet file instead of individual tile files",
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
        use_row_groups=args.use_row_groups,
    )
