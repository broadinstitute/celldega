"""Reading and validating a raw vendor output bundle before processing starts.

Covers the steps that run against the vendor's own directory rather than against
DegaFiles: extracting the micron-to-image transform from the Xenium OME-Zarr, unpacking a
.zip/.tar bundle, and the pre-flight check that the files a technology needs are present.

``_xenium_unzipper`` and ``_check_required_files`` are reached as
``dega.pre._xenium_unzipper`` / ``dega.pre._check_required_files`` from
``run_pre_processing`` (lines 207 and 216), so both stay re-exported from the facade.
"""

from pathlib import Path
import subprocess

import numpy as np
import pandas as pd
import zarr

from .image_info import resolve_xenium_morphology_ome_path


def write_xenium_transform(
    data_dir, path_dega_files, transform_fname="micron_to_image_transform.csv"
):
    """
    Extracts the transformation matrix from the Xenium cells.zarr.zip file and saves it as a CSV file.

    Args:
        data_dir (str): Path to the directory containing the Xenium data (e.g., cells.zarr.zip).
        path_dega_files (str): Path to the directory where the transformation matrix CSV will be saved.
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
            zarr.storage.ZipStore(path, mode="r")
            if path.endswith(".zip")
            else zarr.storage.LocalStore(path, read_only=True)
        )
        return zarr.open_group(store=store, mode="r")

    try:
        # Open the cells Zarr file
        root = open_zarr(str(cells_zarr_path))

        # Extract the transformation matrix
        transformation_matrix = root["masks"]["homogeneous_transform"][:]

        # Save the transformation matrix as a CSV file
        output_path = Path(path_dega_files) / transform_fname
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

    missing_files_or_dir = [
        file for file in required_files_or_dir if not (data_path / file).exists()
    ]
    if technology == "Xenium":
        try:
            resolve_xenium_morphology_ome_path(data_path)
        except FileNotFoundError:
            missing_files_or_dir.append(
                "morphology OME-TIFF (morphology_focus/… or morphology.ome.tif)"
            )

    if missing_files_or_dir:
        raise FileNotFoundError(
            f"The following required files or directories are missing in directory '{data_dir}' "
            f"for technology '{technology}': {', '.join(missing_files_or_dir)}"
        )
    print(
        f"All required files or directories for technology '{technology}' are present in '{data_dir}'."
    )


def write_identity_transform(path_dega_files: str) -> None:
    """Write an identity transform matrix for IST data."""
    path = Path(path_dega_files) / "micron_to_image_transform.csv"
    if not path.exists():
        pd.DataFrame(np.eye(3)).to_csv(path, sep=" ", header=False, index=False)
