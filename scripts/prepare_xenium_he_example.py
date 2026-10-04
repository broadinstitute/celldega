"""Download the SpatialData Xenium example and build DegaFiles for its tutorial ROI.

Run from the repository root with celldega[pre] installed:
    python scripts/prepare_xenium_he_example.py --download

Source: 10x Genomics, FFPE Human Lung Cancer, Xenium 2.0.0 (CC BY 4.0).
See docs/python/aligned_he.md for attribution and coordinate conventions.
The crop matches SpatialData's global pixel ROI [20000, 8000]-[22000, 8500].
"""

import argparse
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET
import zipfile

import fsspec
import h5py
import numpy as np
import pandas as pd
import pyvips
import requests
from scipy.sparse import csc_matrix
import tifffile
import zarr

from celldega import pre
from celldega.pre.run_pre_processing import create_dummy_clusters


SAMPLE = "Xenium_V1_humanLung_Cancer_FFPE"
BASE = f"https://cf.10xgenomics.com/samples/xenium/2.0.0/{SAMPLE}/{SAMPLE}"
FILES = [
    "experiment.xenium",
    "cells.parquet",
    "cell_boundaries.parquet",
    "cell_feature_matrix.h5",
    "transcripts.parquet",
    "morphology_focus/morphology_focus_0000.ome.tif",
]


def download(destination):
    destination.mkdir(parents=True, exist_ok=True)
    for suffix in ["he_image.ome.tif", "he_imagealignment.csv"]:
        target = destination / f"{SAMPLE}_{suffix}"
        if target.exists():
            continue
        print(f"Downloading {target.name}", flush=True)
        with requests.get(f"{BASE}_{suffix}", stream=True, timeout=120) as response:
            response.raise_for_status()
            partial = target.with_suffix(target.suffix + ".part")
            with partial.open("wb") as handle:
                for chunk in response.iter_content(8 * 1024 * 1024):
                    handle.write(chunk)
            partial.replace(target)
    # HTTP byte ranges avoid downloading the 4.8 GB morphology z-stack and masks.
    with (
        fsspec.open(f"{BASE}_outs.zip", block_size=8 * 1024 * 1024).open() as remote,
        zipfile.ZipFile(remote) as archive,
    ):
        for name in FILES:
            target = destination / name
            if target.exists() and target.stat().st_size == archive.getinfo(name).file_size:
                continue
            print(f"Downloading {name}", flush=True)
            target.parent.mkdir(parents=True, exist_ok=True)
            partial = target.with_suffix(target.suffix + ".part")
            with archive.open(name) as source, partial.open("wb") as handle:
                shutil.copyfileobj(source, handle)
            partial.replace(target)


def prepare(source, output, *, include_he=True):
    """Build the tutorial ROI; omit H&E to demonstrate its import separately."""
    if output.exists():
        raise FileExistsError(f"Choose a new output directory: {output}")
    output.mkdir(parents=True)
    (output / "pyramid_images").mkdir()
    x0, y0, width, height = 20000, 8000, 2000, 500
    morphology = source / "morphology_focus/morphology_focus_0000.ome.tif"
    with tifffile.TiffFile(morphology) as tif:
        pixels = ET.fromstring(tif.ome_metadata).find(".//{*}Pixels")
        sx, sy = float(pixels.attrib["PhysicalSizeX"]), float(pixels.attrib["PhysicalSizeY"])
    transform = np.array([[1 / sx, 0, -x0], [0, 1 / sy, -y0], [0, 0, 1]])
    transform_path = output / "micron_to_image_transform.csv"
    np.savetxt(transform_path, transform)
    # imagecodecs decodes Xenium's JPEG2000 TIFF tiles even when libvips lacks it.
    with tifffile.TiffFile(morphology) as tif, tif.pages[0].aszarr() as store:
        image = zarr.open(store, mode="r")
        pixels = np.asarray(image[y0 : y0 + height, x0 : x0 + width])
    pixels = (pixels / max(1, pixels.max()) * 255).astype(np.uint8)
    crop = pyvips.Image.new_from_memory(pixels.tobytes(), width, height, 1, "uchar")
    crop.dzsave(str(output / "pyramid_images/dapi"), tile_size=512, overlap=0, suffix=".webp[Q=95]")

    cells = pd.read_parquet(source / "cells.parquet")
    cells = cells[
        cells.x_centroid.between(x0 * sx, (x0 + width) * sx, inclusive="left")
        & cells.y_centroid.between(y0 * sy, (y0 + height) * sy, inclusive="left")
    ].sort_values("cell_id")
    names = cells.cell_id.tolist()
    pd.DataFrame(
        {
            "name": names,
            "geometry": np.column_stack(
                [
                    cells.x_centroid / sx - x0,
                    cells.y_centroid / sy - y0,
                ]
            ).tolist(),
        }
    ).to_parquet(output / "cell_metadata.parquet", index=False)
    with h5py.File(source / "cell_feature_matrix.h5") as handle:
        group = handle["matrix"]
        counts = csc_matrix(
            (group["data"][:], group["indices"][:], group["indptr"][:]), shape=group["shape"][:]
        )
        barcodes = pd.Index(group["barcodes"][:].astype(str))
        genes = group["features/name"][:].astype(str)
        cbg = pd.DataFrame(
            counts[:, barcodes.get_indexer(names)].T.toarray(), index=names, columns=genes
        )
    # Retain biological genes; control probes do not belong in the demo gene menu.
    cbg = cbg.loc[:, ~cbg.columns.str.contains("Control|Codeword|Unassigned")]
    pre.make_meta_gene(cbg, output / "meta_gene.parquet")
    create_dummy_clusters(str(output), cbg)
    pre.save_cbg_gene_parquets("Xenium", str(output), cbg.copy())

    boundary = pd.read_parquet(source / "cell_boundaries.parquet")
    boundary = boundary[boundary.cell_id.isin(names)]
    boundary_path = output / "roi_boundaries.parquet"
    boundary.to_parquet(boundary_path)
    pre.make_cell_boundary_tiles(
        "Xenium",
        boundary_path,
        str(output / "cell_segmentation"),
        path_transformation_matrix=transform_path,
        tile_bounds={"x_min": 0, "x_max": width, "y_min": 0, "y_max": height},
        tile_size=250,
    )
    trx = pd.read_parquet(
        source / "transcripts.parquet",
        filters=[
            ("x_location", ">=", x0 * sx),
            ("x_location", "<", (x0 + width) * sx),
            ("y_location", ">=", y0 * sy),
            ("y_location", "<", (y0 + height) * sy),
            ("qv", ">=", 20),
        ],
    )
    trx = trx[trx.feature_name.isin(cbg.columns)]
    trx_path = output / "roi_transcripts.parquet"
    trx.to_parquet(trx_path)
    pre.make_trx_tiles(
        "Xenium", trx_path, transform_path, str(output / "transcript_tiles"), tile_size=250
    )
    pre.save_landscape_parameters(
        "Xenium",
        str(output),
        tile_size=250,
        image_info=pre.get_image_info("Xenium", "dapi"),
        image_format=".webp",
    )
    if include_he:
        matrix = np.loadtxt(source / f"{SAMPLE}_he_imagealignment.csv", delimiter=",")
        translate_crop = np.array([[1, 0, -x0], [0, 1, -y0], [0, 0, 1]])
        pre.add_aligned_he(
            output, source / f"{SAMPLE}_he_image.ome.tif", alignment=translate_crop @ matrix
        )
    (output / "example.json").write_text(
        json.dumps(
            {
                "cells": names,
                "crop_pixels": [x0, y0, width, height],
                "cell_count": len(cells),
                "transcript_count": len(trx),
                "source": "https://www.10xgenomics.com/datasets/preview-data-ffpe-human-lung-cancer-with-xenium-multimodal-cell-segmentation-1-standard",
                "license": "CC BY 4.0",
                "clusters": "Single display group; no inferred cell types",
            },
            indent=2,
        )
    )
    print(f"Wrote {output}: {len(cells)} cells and {len(trx)} transcripts", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--source", type=Path, default=Path("data/xenium_h_and_e"))
    parser.add_argument("--output", type=Path, default=Path("data/xenium_he_dega"))
    args = parser.parse_args()
    if args.download:
        download(args.source)
    prepare(args.source, args.output)
