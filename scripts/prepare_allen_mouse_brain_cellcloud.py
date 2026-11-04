"""Create new, compact CellCloud artifacts; never upload or modify hosted data.

Run from the checkout with its Python environment::

    python scripts/prepare_allen_mouse_brain_cellcloud.py --download

Inputs are pinned published AnnData and alignment files. Outputs go into a new
versioned directory, with a size report and checksums. Existing output is refused.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import gc
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time
from urllib.request import urlopen

import anndata as ad
import h5py
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from scipy.sparse import csr_matrix

import celldega as dega


HF_REPO = "broadinstitute/Celldega_Supporting_Data"
HF_REVISION = "df537e04ad0e51a91f3d68a53b788efb61552913"
H5AD = "Allen-Broad_Dev-Mouse-Brain/E15.5/xenium_E15.5_clustered.h5ad"
GH_REPO = "broadinstitute/celldega_xenium_E15.5_cell_cloud"
GH_REVISION = "e8d0d6fb17109333e982497fca1c526e5e457747"
GH_DIR = "xenium_E15.5_cell_cloud"
CLUSTER_KEY = "leiden_1.0"
VERSION = "cellcloud_v2_1um"


def log(message):
    print(message, flush=True)


def download_file(url: str, path: Path):
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(path.suffix + ".part")
    with urlopen(url) as response, partial.open("wb") as output:
        shutil.copyfileobj(response, output, length=8 * 1024 * 1024)
    partial.replace(path)


def download_sources(source: Path):
    h5ad = source / H5AD
    if not h5ad.exists():
        subprocess.run(
            [
                "hf",
                "download",
                HF_REPO,
                H5AD,
                "--type",
                "dataset",
                "--revision",
                HF_REVISION,
                "--local-dir",
                str(source),
                "--quiet",
            ],
            check=True,
        )
    base = f"https://raw.githubusercontent.com/{GH_REPO}/{GH_REVISION}/{GH_DIR}"
    files = [
        "cell_cloud.json",
        "cell_metadata_neighborhood.parquet",
        "cell_metadata_centroids.parquet",
        "cell_clusters/cluster.parquet",
        "cell_clusters/meta_cluster.parquet",
        "meta_gene.parquet",
    ]
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(
            pool.map(lambda name: download_file(f"{base}/{name}", source / "github" / name), files)
        )
    # Repository tree metadata records sizes without downloading 4.6 GB of legacy files.
    download_file(
        f"https://api.github.com/repos/{GH_REPO}/git/trees/{GH_REVISION}?recursive=1",
        source / "github-tree.json",
    )


def load_cloud(source: Path):
    """Read just raw counts and the metadata this visualization uses."""
    table = pq.read_table(source / "github/cell_metadata_neighborhood.parquet")
    names = pd.Index(table["name"].to_pylist())
    if not names.is_unique:
        raise ValueError("Published alignment contains duplicate cell IDs")
    alignments = {}
    rounding = {}
    for alignment in ["neighborhood", "centroids"]:
        positions = pq.read_table(source / f"github/cell_metadata_{alignment}.parquet")
        if positions["name"].to_pylist() != names.tolist():
            raise ValueError(f"{alignment}: published cell order differs")
        xyz = positions["geometry"].combine_chunks().values.to_numpy().reshape(-1, 3)
        rounded = np.rint(xyz).astype(np.int32)
        delta = rounded.astype(float) - xyz
        rounding[alignment] = {
            "max_axis_error_um": float(np.abs(delta).max()),
            "max_distance_error_um": float(np.linalg.norm(delta, axis=1).max()),
        }
        alignments[alignment] = rounded
    del table, positions, xyz, rounded, delta
    gc.collect()

    log("Reading pinned H5AD raw counts and cell annotations")
    with h5py.File(source / H5AD) as f:
        original_names = pd.Index(f["obs/_index"].asstr()[:])
        if not original_names.is_unique:
            raise ValueError("Source AnnData contains duplicate cell IDs")
        order = original_names.get_indexer(names)
        if (order < 0).any():
            raise ValueError("Alignment cell IDs are absent from the source AnnData")
        categories = f[f"obs/{CLUSTER_KEY}/categories"].asstr()[:]
        codes = f[f"obs/{CLUSTER_KEY}/codes"][:][order]
        slices = f["obs/slice"][:][order]
        extra = f["obs/extra_tissue_piece"][:][order]
        if (slices == 44).any() or extra.any():
            raise ValueError("The stack unexpectedly includes excluded cells")
        colors = f[f"uns/{CLUSTER_KEY}_colors"].asstr()[:]
        var_group = f["var"]
        var_index = var_group.attrs["_index"]
        genes = var_group[var_index].asstr()[:]
        x = f["X"]
        if x.attrs["encoding-type"] != "csr_matrix":
            raise ValueError("Source X is no longer CSR; inspect it before converting")
        values = x["data"][:]
        if values.dtype.kind not in "iu" and (
            not np.isfinite(values).all() or not np.equal(values, np.rint(values)).all()
        ):
            raise ValueError("Source X must contain finite integral raw counts")
        if values.min(initial=0) < 0:
            raise ValueError("Expected nonnegative raw counts")
        max_count = int(values.max(initial=0))
        if max_count > np.iinfo(np.uint32).max:
            raise ValueError("Raw counts exceed uint32; retain their original dtype")
        count_dtype = np.uint16 if max_count <= np.iinfo(np.uint16).max else np.uint32
        values = values.astype(count_dtype)
        raw = csr_matrix((values, x["indices"][:], x["indptr"][:]), shape=tuple(x.attrs["shape"]))
    log(f"Reordering {len(names):,} cells and converting counts to CSC ({np.dtype(count_dtype)})")
    counts = raw[order].tocsc()
    del raw, values, original_names, order
    gc.collect()
    obs = pd.DataFrame(
        {
            CLUSTER_KEY: pd.Categorical.from_codes(codes, categories=categories),
            "slice": slices.astype(np.uint8),
        },
        index=names,
    )
    cloud = ad.AnnData(X=counts, obs=obs, var=pd.DataFrame(index=genes))
    cloud.uns[f"{CLUSTER_KEY}_colors"] = colors
    cloud.obsm["spatial"] = alignments["neighborhood"]
    cloud.uns["provenance"] = {
        "source_h5ad": f"https://huggingface.co/datasets/{HF_REPO}/resolve/{HF_REVISION}/{H5AD}",
        "alignment_source": f"https://github.com/{GH_REPO}/tree/{GH_REVISION}/{GH_DIR}",
        "note": "Original cell order, alignments, raw counts, cluster labels, and colors retained; coordinates rounded to nearest 1 um.",
    }
    log(f"Prepared {cloud.n_obs:,} cells, {cloud.n_vars} genes, {counts.nnz:,} nonzero counts")
    return cloud, alignments, rounding, max_count


def inventory(path: Path):
    return {
        str(p.relative_to(path)): p.stat().st_size for p in sorted(path.rglob("*")) if p.is_file()
    }


def legacy_inventory(source: Path):
    path = source / "github-tree.json"
    if path.exists():
        tree = json.loads(path.read_text())["tree"]
        return {
            p["path"].removeprefix(f"{GH_DIR}/"): p["size"]
            for p in tree
            if p["type"] == "blob" and p["path"].startswith(f"{GH_DIR}/")
        }
    # Also accept an earlier local audit of the same pinned tree.
    tree = json.loads((source / "github-tree-sizes.json").read_text())["files"]
    return {p["path"].removeprefix(f"{GH_DIR}/"): p["size"] for p in tree}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--work-dir", type=Path, default=Path("data/allen_mouse_brain_cellcloud_v2")
    )
    parser.add_argument(
        "--download", action="store_true", help="Download pinned inputs if missing; never uploads"
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reuse completed compact DegaFiles after an interrupted Zarr export",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify completed artifacts against pinned inputs and refresh the report/checksums",
    )
    args = parser.parse_args()
    source = args.work_dir / "source"
    output = args.work_dir / "artifacts"
    if output.exists() and not (args.resume or args.verify):
        raise FileExistsError(f"Refusing to overwrite {output}; choose another --work-dir")
    if (output / "size-report.json").exists() and not args.verify:
        raise FileExistsError(f"{output} already contains a completed export")
    if args.download:
        download_sources(source)
    started = time.perf_counter()
    cloud, alignments, rounding, max_count = load_cloud(source)
    output.mkdir(parents=True, exist_ok=args.resume or args.verify)
    degafiles = output / "github/xenium_E15.5_cell_cloud_v2_1um"
    completed_dega = (degafiles / "cell_cloud.json").exists()
    if completed_dega:
        params = json.loads((degafiles / "cell_cloud.json").read_text())
        if not (
            (args.resume or args.verify)
            and params.get("use_int_index")
            and params.get("coordinate_resolution") == 1.0
            and set(params.get("alignments", [])) == set(alignments)
            and len(list((degafiles / "cbg").glob("*.parquet"))) == cloud.n_vars
        ):
            raise ValueError(
                "Existing DegaFiles do not match this export; choose a new work directory"
            )
        log("Reusing completed compact DegaFiles; all values will be verified below")
    for alignment, xyz in [] if completed_dega else alignments.items():
        cloud.obsm["spatial"] = xyz
        log(f"Writing compact DegaFiles: {alignment}")
        dega.pre.write_point_cloud_dataset(
            cloud,
            degafiles,
            name=alignment,
            z_key=None,
            cluster_key=CLUSTER_KEY,
            use_int_index=True,
            coordinate_resolution=1.0,
            compression="zstd",
            compression_level=6,
            write_base_metadata=(alignment == "neighborhood"),
        )
    cloud.obsm["spatial"] = alignments["neighborhood"]
    zarr = output / f"huggingface/Allen-Broad_Dev-Mouse-Brain/E15.5/{VERSION}.zarr"
    log("Writing AnnData Zarr with CSC counts and both alignments")
    if not args.verify:
        dega.pre.write_point_cloud_zarr(
            cloud,
            zarr,
            z_key=None,
            cluster_key=CLUSTER_KEY,
            alignments=alignments,
            coordinate_resolution=1.0,
            obs_columns=[CLUSTER_KEY, "slice"],
        )
    log("Checking complete round trips")
    saved = ad.read_zarr(zarr)
    assert saved.obs_names.equals(cloud.obs_names)
    assert saved.var_names.equals(cloud.var_names)
    assert (saved.X != cloud.X).nnz == 0
    for alignment, xyz in alignments.items():
        np.testing.assert_array_equal(saved.obsm[f"spatial_{alignment}"], xyz)
        table = pq.read_table(degafiles / f"cell_metadata_{alignment}.parquet")
        np.testing.assert_array_equal(
            table["name"].to_numpy(), np.arange(cloud.n_obs, dtype=np.uint32)
        )
        np.testing.assert_array_equal(
            table["geometry"].combine_chunks().values.to_numpy().reshape(-1, 3), xyz
        )
    assert (
        pq.read_table(degafiles / "cell_ids.parquet")["name"].to_pylist()
        == cloud.obs_names.tolist()
    )
    np.testing.assert_array_equal(
        saved.obs[CLUSTER_KEY].astype(str), cloud.obs[CLUSTER_KEY].astype(str)
    )
    np.testing.assert_array_equal(
        saved.uns[f"{CLUSTER_KEY}_colors"], cloud.uns[f"{CLUSTER_KEY}_colors"]
    )
    clusters = pq.read_table(degafiles / "cell_clusters/cluster.parquet")
    np.testing.assert_array_equal(
        clusters["name"].to_numpy(), np.arange(cloud.n_obs, dtype=np.uint32)
    )
    np.testing.assert_array_equal(
        clusters["cluster"].to_pylist(), cloud.obs[CLUSTER_KEY].astype(str)
    )
    for name in ["cell_clusters/meta_cluster.parquet", "meta_gene.parquet"]:
        assert "__index_level_0__" in pq.read_schema(degafiles / name).names
        pd.testing.assert_frame_equal(
            pd.read_parquet(degafiles / name),
            pd.read_parquet(source / "github" / name),
            check_dtype=False,
            check_index_type=False,
        )
    for g, gene in enumerate(cloud.var_names):
        start, stop = cloud.X.indptr[g : g + 2]
        table = pq.read_table(degafiles / "cbg" / f"{gene}.parquet")
        np.testing.assert_array_equal(
            table["__index_level_0__"].to_numpy(), cloud.X.indices[start:stop]
        )
        np.testing.assert_array_equal(table[str(gene)].to_numpy(), cloud.X.data[start:stop])
    old_files = legacy_inventory(source)
    report = {
        "version": VERSION,
        "n_cells": cloud.n_obs,
        "n_genes": cloud.n_vars,
        "n_slices": int(cloud.obs["slice"].nunique()),
        "nnz": int(cloud.X.nnz),
        "counts_dtype": str(cloud.X.dtype),
        "maximum_raw_count": max_count,
        "rounding": rounding,
        "github_revision": GH_REVISION,
        "hf_revision": HF_REVISION,
        "legacy_files": old_files,
        "degafiles": inventory(degafiles),
        "zarr": inventory(zarr),
        "verified": [
            "all cell IDs",
            "all gene IDs",
            "all raw expression values (Zarr)",
            "all raw expression values (DegaFiles)",
            "both alignment coordinate arrays",
            "cluster labels and palette",
        ],
        "generation_seconds": round(time.perf_counter() - started, 2),
    }
    report["total_bytes"] = {
        "legacy_degafiles": sum(old_files.values()),
        "compact_degafiles": sum(report["degafiles"].values()),
        "anndata_zarr": sum(report["zarr"].values()),
    }
    (output / "size-report.json").write_text(json.dumps(report, indent=2) + "\n")
    comparison = Path(__file__).resolve().parents[1] / ".github/CELLCLOUD_STORAGE.md"
    if comparison.exists():
        shutil.copyfile(comparison, output / "README.md")
    checksums = []
    for p in sorted(output.rglob("*")):
        if p.is_file() and p.name != "SHA256SUMS":
            with p.open("rb") as f:
                digest = hashlib.file_digest(f, "sha256").hexdigest()
            checksums.append(f"{digest}  {p.relative_to(output)}")
    (output / "SHA256SUMS").write_text("\n".join(checksums) + "\n")
    log(json.dumps(report["total_bytes"], indent=2))
    log(f"Artifacts and validation report: {output.resolve()}")


if __name__ == "__main__":
    main()
