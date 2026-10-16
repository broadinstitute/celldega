"""
Readers for 10x Atera output bundles.

Atera bundles are Xenium-class: same micron coordinate system, same cell-id encoding, and the
same ``cells.zarr`` / ``transcripts.zarr`` / ``cell_feature_matrix.zarr`` stores that Xenium
Explorer reads. They do not ship the flat Xenium files (``cells.csv.gz``,
``transcripts.parquet``, ``cell_boundaries.parquet``, ``cell_feature_matrix/*.mtx.gz``,
``analysis/``), so these readers load the zarr stores directly and return the same shapes the
Xenium loaders return. Pre-processing treats an Atera bundle as technology ``"Xenium"``.
"""

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import polars as pl
from scipy.sparse import csr_matrix
from shapely.geometry import Polygon
import zarr

ATERA_EXPERIMENT_FILE = "experiment.spatial"
ATERA_CELLS = "cells.zarr.zip"
ATERA_TRANSCRIPTS = "transcripts.zarr.zip"
ATERA_CBG = "cell_feature_matrix.zarr.zip"
ATERA_MORPHOLOGY_DIR = "morphology_2d"

# Polygon set index for cell (vs nucleus) boundaries in cells.zarr
CELL_POLYGON_SET = "1"

# Xenium's default "high quality" transcript threshold
DEFAULT_MIN_QV = 20


def is_atera_bundle(data_dir):
    """Return True if ``data_dir`` is an Atera output bundle."""
    return (Path(data_dir) / ATERA_EXPERIMENT_FILE).exists()


def is_atera_store(path):
    """Return True if ``path`` points at an Atera zarr store rather than a Xenium flat file."""
    return str(path).endswith(".zarr.zip")


def _open_zarr_zip(path):
    return zarr.open_group(store=zarr.storage.ZipStore(str(path), mode="r"), mode="r")


def _encode_cell_ids(cell_id):
    """
    Convert ``(prefix, dataset_suffix)`` uint32 pairs to Xenium cell-id strings
    (e.g. ``[7790, 1] -> "aaaabogo-1"``): each hex digit of the prefix is shifted to a-p.
    """
    cell_id = np.asarray(cell_id)
    hex_digits = np.char.zfill(np.char.mod("%x", cell_id[:, 0]), 8)
    shifted = np.char.translate(hex_digits, str.maketrans("0123456789abcdef", "abcdefghijklmnop"))
    return np.char.add(np.char.add(shifted, "-"), cell_id[:, 1].astype(str))


def _decode_categorical(group):
    codes = group["codes"][:]
    categories = np.asarray(group["categories"][:]).astype(str)
    values = np.where(codes >= 0, categories[np.clip(codes, 0, None)], None)
    return pd.Series(values, dtype="string")


def atera_paths(data_dir):
    """Map Xenium input roles to the corresponding Atera store paths."""
    data_path = Path(data_dir)
    return {
        "meta_cell_micron": data_path / ATERA_CELLS,
        "transcripts": data_path / ATERA_TRANSCRIPTS,
        "cell_boundaries": data_path / ATERA_CELLS,
        "cbg_matrix": data_path / ATERA_CBG,
    }


def check_atera_files(data_dir):
    """Return the list of required Atera files missing from ``data_dir``."""
    data_path = Path(data_dir)
    required = [ATERA_CELLS, ATERA_TRANSCRIPTS, ATERA_CBG]
    missing = [f for f in required if not (data_path / f).exists()]
    if not resolve_atera_morphology_paths(data_dir):
        missing.append(f"{ATERA_MORPHOLOGY_DIR}/*.ome.tif")
    return missing


def read_atera_meta_cell(path_cells):
    """
    Load cell centroids (microns) from ``cells.zarr.zip``.

    Returns a DataFrame indexed by cell id with ``center_x``, ``center_y`` and ``name``,
    matching the Xenium branch of ``_load_meta_cell_by_technology``.
    """
    root = _open_zarr_zip(path_cells)
    cell_ids = _encode_cell_ids(root["cell_id"][:])
    summary = root["cell_summary"]
    column_names = list(summary.attrs["column_names"])
    values = summary[:]
    meta_cell = pd.DataFrame(
        {
            "center_x": values[:, column_names.index("cell_centroid_x")],
            "center_y": values[:, column_names.index("cell_centroid_y")],
        },
        index=pd.Index(cell_ids, name="cell_id"),
    )
    meta_cell["name"] = meta_cell.index
    return meta_cell


def read_atera_cbg(path_cbg):
    """
    Load the cell-by-gene matrix from ``cell_feature_matrix.zarr.zip``.

    Returns a sparse DataFrame (cells x features), matching ``read_cbg_mtx``.
    """
    root = _open_zarr_zip(path_cbg)
    x = root["X"]
    shape = tuple(x.attrs["shape"])
    matrix = csr_matrix(
        (x["data"][:], x["indices"][:].astype(np.int32), x["indptr"][:]), shape=shape
    ).tocsc()
    barcodes = np.asarray(root["obs"]["barcode"][:]).astype(str)
    features = np.asarray(root["var"]["feature_name"][:]).astype(str)
    cbg = pd.DataFrame.sparse.from_spmatrix(matrix, index=barcodes, columns=features)
    return cbg.rename_axis("__index_level_0__", axis="columns")


def read_atera_clusters(path_cbg, clustering="leiden_res_1.0"):
    """Load the default graph-based clustering from ``cell_feature_matrix.zarr.zip``."""
    obs = _open_zarr_zip(path_cbg)["obs"]
    clusters = _decode_categorical(obs[clustering])
    clusters.index = np.asarray(obs["barcode"][:]).astype(str)
    return clusters


def read_atera_cell_polygons(path_cells):
    """
    Load cell boundary polygons (microns) from ``cells.zarr.zip``.

    Returns a GeoDataFrame indexed by cell id with a ``geometry`` column, matching the
    Xenium branch of ``get_cell_polygons`` before the micron-to-pixel transform.
    """
    root = _open_zarr_zip(path_cells)
    cell_ids = _encode_cell_ids(root["cell_id"][:])
    polygon_set = root["polygon_sets"][CELL_POLYGON_SET]
    vertices = polygon_set["vertices"][:]
    num_vertices = polygon_set["num_vertices"][:]
    cell_index = polygon_set["cell_index"][:]

    polygons = [
        Polygon(vertices[i, : 2 * n].reshape(-1, 2)) if n >= 3 else None
        for i, n in enumerate(num_vertices)
    ]
    gdf = gpd.GeoDataFrame(
        {"geometry": polygons}, index=pd.Index(cell_ids[cell_index], name="cell_id")
    )
    gdf = gdf[gdf.geometry.notna()]
    return gdf[~gdf.index.duplicated(keep="first")]


def iter_atera_transcript_chunks(path_trx, gene_str_to_int_mapping, min_qv=DEFAULT_MIN_QV):
    """
    Stream transcripts from ``transcripts.zarr.zip`` one spatial grid chunk at a time.

    Each ``grid/<x>,<y>`` chunk stores transcripts sorted by gene, with
    ``gene_offset[g] = [start, end)`` giving the rows of gene ``g`` in ``attrs["gene_names"]``.

    Yields polars DataFrames with ``name`` (integer gene id from ``gene_str_to_int_mapping``),
    ``x`` and ``y`` (microns), the columns the transcript tiler uses. Transcripts below
    ``min_qv`` or whose gene is not in the mapping are dropped.
    """
    root = _open_zarr_zip(path_trx)
    gene_names = list(root.attrs["gene_names"])
    gene_lut = np.array([gene_str_to_int_mapping.get(g, -1) for g in gene_names], dtype=np.int64)
    grid = root["grid"]
    for key in sorted(grid.group_keys()):
        chunk = grid[key]
        gene_offset = chunk["gene_offset"][:]
        n_rows = int(gene_offset[-1, 1]) if len(gene_offset) else 0
        if n_rows == 0:
            continue
        gene_index = np.repeat(
            np.arange(len(gene_offset)), (gene_offset[:, 1] - gene_offset[:, 0]).astype(np.int64)
        )
        name = gene_lut[gene_index]
        keep = name >= 0
        if min_qv is not None:
            keep &= chunk["quality_score"][:].reshape(-1) >= min_qv
        location = chunk["location"][:, :2]
        yield pl.DataFrame({"name": name[keep], "x": location[keep, 0], "y": location[keep, 1]})


def resolve_atera_morphology_paths(data_dir):
    """Return the per-channel 2D morphology OME-TIFFs in channel order (ch0000 = DAPI)."""
    return sorted((Path(data_dir) / ATERA_MORPHOLOGY_DIR).glob("ch*.ome.tif"))


def atera_cluster_signatures(cbg, clusters):
    """
    Mean expression per cluster, computed with one sparse matrix product.

    Returns a DataFrame (features x clusters), matching the per-cluster signatures that
    ``cluster_gene_expression`` builds for Xenium.
    """
    clusters = clusters.reindex(cbg.index)
    valid = clusters.notna().to_numpy()
    cluster_names = sorted(clusters[valid].unique().tolist())
    codes = pd.Categorical(clusters[valid], categories=cluster_names).codes
    indicator = csr_matrix(
        (np.ones(valid.sum()), (codes, np.flatnonzero(valid))),
        shape=(len(cluster_names), len(cbg.index)),
    )
    sums = np.asarray((indicator @ cbg.sparse.to_coo().tocsr()).todense())
    counts = np.asarray(indicator.sum(axis=1)).reshape(-1, 1)
    return pd.DataFrame((sums / counts).T, index=cbg.columns.tolist(), columns=cluster_names)
