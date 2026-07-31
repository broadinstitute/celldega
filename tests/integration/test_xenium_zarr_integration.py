"""Integration test for tiling transcripts from a real Xenium ``transcripts.zarr.zip``.

This test is skipped unless a real Xenium output bundle is available locally. Point the
``CELLDEGA_XENIUM_PANCREAS_DIR`` environment variable at an extracted Xenium ``outs``
directory that contains ``transcripts.zarr.zip``, for example::

    # Download + extract the 10x Xenium Human Pancreas FFPE dataset (~9 GB):
    #   https://www.10xgenomics.com/datasets/ffpe-human-pancreas-with-xenium-multimodal-cell-segmentation-1-standard
    curl -O https://cf.10xgenomics.com/samples/xenium/2.0.0/Xenium_V1_human_Pancreas_FFPE/Xenium_V1_human_Pancreas_FFPE_outs.zip
    unzip Xenium_V1_human_Pancreas_FFPE_outs.zip -d Xenium_V1_human_Pancreas_FFPE_outs

    export CELLDEGA_XENIUM_PANCREAS_DIR="$PWD/Xenium_V1_human_Pancreas_FFPE_outs"
    pytest tests/integration/test_xenium_zarr_integration.py -q
"""

import os
from pathlib import Path

import numpy as np
import pytest


DATA_DIR = os.environ.get("CELLDEGA_XENIUM_PANCREAS_DIR")


def _zarr_bundle() -> Path | None:
    if not DATA_DIR:
        return None
    candidate = Path(DATA_DIR) / "transcripts.zarr.zip"
    return candidate if candidate.exists() else None


pytestmark = pytest.mark.skipif(
    _zarr_bundle() is None,
    reason=(
        "Set CELLDEGA_XENIUM_PANCREAS_DIR to an extracted Xenium outs directory "
        "containing transcripts.zarr.zip to run the integration test."
    ),
)


def test_zarr_metadata_and_tiling(tmp_path):
    from celldega.pre import trx_zarr

    bundle = _zarr_bundle()

    meta = trx_zarr.read_zarr_transcript_metadata(bundle)
    assert meta["gene_names"], "expected a non-empty gene panel"
    assert meta["number_rnas"] and meta["number_rnas"] > 0
    assert meta["position_keys"], "expected at least one level-0 grid position"

    # First batch should look like transcripts.
    first_batch = next(trx_zarr.iter_zarr_transcript_batches(bundle))
    assert first_batch.columns == ["name", "x", "y"]
    assert first_batch.height > 0

    # Identity transform keeps coordinates in micron space for a self-contained test.
    transform = tmp_path / "identity.csv"
    np.savetxt(transform, np.eye(3))

    gene_map = {name: idx for idx, name in enumerate(meta["gene_names"])}
    out_dir = tmp_path / "transcripts"

    _tile_bounds, tile_grid_info, chunk_info = trx_zarr.make_trx_tiles_from_zarr(
        bundle,
        transform,
        out_dir,
        tile_size=200,
        use_row_groups=True,
        gene_str_to_int_mapping=gene_map,
    )

    assert tile_grid_info["num_tiles_x"] > 0
    assert tile_grid_info["num_tiles_y"] > 0
    assert chunk_info["total_row_groups"] == (
        tile_grid_info["num_tiles_x"] * tile_grid_info["num_tiles_y"]
    )

    # Total tiled transcripts should be positive and not exceed the raw count
    # (no-call / low-quality transcripts are filtered out).
    import pyarrow.parquet as pq

    total = 0
    for chunk_path in out_dir.glob("chunk_*.parquet"):
        pf = pq.ParquetFile(chunk_path)
        for rg in range(pf.metadata.num_row_groups):
            total += pf.read_row_group(rg).num_rows

    assert 0 < total <= meta["number_rnas"]
