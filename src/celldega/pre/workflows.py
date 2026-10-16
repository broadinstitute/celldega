"""End-to-end entry points that sequence the other modules into a DegaFiles directory.

These sit at the same altitude as :func:`celldega.pre.run_pre_processing.main` -- they
orchestrate rather than being orchestrated. ``make_chromium_from_anndata`` builds a
Chromium landscape from scratch; ``add_custom_segmentation`` extends an existing one.
"""

import json
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd
from scipy.sparse import issparse

from .boundary_tile import make_cell_boundary_tiles
from .cell_clusters import cluster_gene_expression, create_cluster_and_meta_cluster
from .landscape import save_cbg_gene_parquets
from .landscape_parameters import save_landscape_parameters
from .meta_cell import make_meta_cell_image_coord, make_meta_gene


def make_chromium_from_anndata(adata, path_dega_files):
    """Generate minimal LandscapeFiles from a Chromium AnnData object.

    Parameters
    ----------
    adata : anndata.AnnData
        AnnData object containing scRNA-seq count data.
    path_dega_files : str or Path
        Directory where LandscapeFiles will be written.

    Raises
    ------
    ValueError
        If the expression matrix contains non-integer values.
    """

    print("\n========Process Chromium AnnData========")
    path_dega_files = Path(path_dega_files)
    path_dega_files.mkdir(parents=True, exist_ok=True)

    X = adata.layers.get("counts", adata.X)

    data = X.data if issparse(X) else np.asarray(X)

    if not np.all(np.equal(np.mod(data, 1), 0)):
        raise ValueError("Chromium processing requires integer counts")

    if issparse(X):
        cbg = pd.DataFrame.sparse.from_spmatrix(X, index=adata.obs_names, columns=adata.var_names)
    else:
        cbg = pd.DataFrame(X, index=adata.obs_names, columns=adata.var_names)

    cell_meta = pd.DataFrame({"name": adata.obs_names, "geometry": [[0.0, 0.0]] * adata.n_obs})
    cell_meta.to_parquet(path_dega_files / "cell_metadata.parquet", index=False)

    save_cbg_gene_parquets("Chromium", path_dega_files, cbg)

    make_meta_gene(cbg, path_dega_files / "meta_gene.parquet")

    (path_dega_files / "pyramid_images").mkdir(exist_ok=True)

    save_landscape_parameters(
        technology="Chromium",
        path_dega_files=path_dega_files,
        image_name="",
        tile_size=1,
        image_info=[],
    )


def add_custom_segmentation(
    technology, path_dega_files, path_segmentation_files, image_scale=1, tile_size=250
):
    """
    Add custom segmentation to existing landscape files.

    Parameters:
    - technology: Technology type (e.g., "Xenium", "MERSCOPE", "custom")
    - path_dega_files: Path to landscape files
    - path_segmentation_files: Path to segmentation files
    - image_scale: Image scale factor
    - tile_size: Tile size for processing
    """
    with (Path(path_segmentation_files) / "segmentation_parameters.json").open() as file:
        segmentation_parameters = json.load(file)

    cbg_custom = pd.read_parquet(Path(path_segmentation_files) / "cell_by_gene_matrix.parquet")

    # make sure all genes are present in cbg_custom
    meta_gene = pd.read_parquet(Path(path_dega_files) / "meta_gene.parquet")
    missing_cols = meta_gene.index.difference(cbg_custom.columns)
    for col in missing_cols:
        cbg_custom[col] = 0

    make_meta_gene(
        cbg=cbg_custom,
        path_output=Path(path_dega_files)
        / f"meta_gene_{segmentation_parameters['segmentation_approach']}.parquet",
    )

    make_meta_cell_image_coord(
        technology=segmentation_parameters["technology"],
        path_transformation_matrix=str(Path(path_dega_files) / "micron_to_image_transform.csv"),
        path_meta_cell_micron=str(
            Path(path_segmentation_files) / "cell_metadata_micron_space.parquet"
        ),
        path_meta_cell_image=str(
            Path(path_dega_files)
            / f"cell_metadata_{segmentation_parameters['segmentation_approach']}.parquet"
        ),
        image_scale=image_scale,
    )

    save_cbg_gene_parquets(
        technology=technology,
        base_path=path_dega_files,
        cbg=cbg_custom,
        verbose=True,
        segmentation_approach=segmentation_parameters["segmentation_approach"],
    )

    create_cluster_and_meta_cluster(
        technology=segmentation_parameters["technology"],
        path_dega_files=path_dega_files,
        segmentation_approach=segmentation_parameters["segmentation_approach"],
    )

    # Get the first .dzi file in sorted order
    dzi_files = sorted((Path(path_dega_files) / "pyramid_images").glob("*.dzi"))
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
            Path(path_dega_files)
            / f"cell_segmentation_{segmentation_parameters['segmentation_approach']}"
        ),
        tile_size=tile_size,
        tile_bounds=tile_bounds,
        image_scale=image_scale,
    )

    cluster_gene_expression(
        technology=segmentation_parameters["technology"],
        path_dega_files=path_dega_files,
        cbg=cbg_custom,
        segmentation_approach=segmentation_parameters["segmentation_approach"],
    )

    save_landscape_parameters(
        technology=segmentation_parameters["technology"],
        path_dega_files=path_dega_files,
        image_name="dapi_files",
        tile_size=tile_size,
        image_format=".webp",
        segmentation_approach=segmentation_parameters["segmentation_approach"],
    )
