"""Per-cell and per-gene metadata tables.

Builds the two DegaFiles metadata artefacts: ``cell_metadata.parquet`` (centroid in image
coordinates, plus whatever the technology's own metadata file carries) and
``meta_gene.parquet``.

Giving ``make_meta_gene`` a real submodule home is what lets ``nbhd_cloud`` and
``celldega.align.point_cloud`` stop reaching into the package facade for it.
"""

import base64
import hashlib
import warnings

import pandas as pd
from scipy.sparse import csr_matrix

from .boundary_tile import _round_nested_coord_list
from .colors import _create_cluster_colors
from .landscape import calc_meta_gene_data


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

    colors = _create_cluster_colors(genes)

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
