import warnings

import pytest

from celldega.viz import Landscape, widget as widget_module


def test_zarr_url_defaults_to_chromium_without_a_transform_warning():
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        landscape = Landscape(
            zarr_url="https://huggingface.co/datasets/org/repo/resolve/main/pbmc.zarr/",
            zarr_layer="counts_csc",
        )

    assert landscape.technology == "Chromium"
    assert landscape.zarr_url == "https://huggingface.co/datasets/org/repo/resolve/main/pbmc.zarr"
    assert landscape.zarr_layer == "counts_csc"
    assert landscape.base_url == ""


def test_zarr_url_rejects_dega_files_and_spatial_technologies():
    with pytest.raises(ValueError, match="not both"):
        Landscape(zarr_url="https://example.org/pbmc.zarr", base_url="https://example.org/dega")
    with pytest.raises(ValueError, match="Chromium"):
        Landscape(zarr_url="https://example.org/pbmc.zarr", technology="Xenium")


def test_local_zarr_path_is_served_by_one_shared_local_server(tmp_path, monkeypatch):
    store = tmp_path / "data dir" / "pbmc.zarr"
    store.mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(widget_module, "_SHARED_LOCAL_SERVER_PORT", None)
    ports = iter([8123, 9999])
    monkeypatch.setattr("celldega.viz.local_server.get_local_server", lambda: next(ports))

    first = Landscape(zarr_url="data dir/pbmc.zarr")
    second = Landscape(zarr_url=store)

    assert first.zarr_url == "http://localhost:8123/data%20dir/pbmc.zarr"
    assert second.zarr_url == first.zarr_url


def test_local_zarr_path_must_exist_under_the_working_directory(tmp_path, monkeypatch):
    outside = tmp_path / "outside.zarr"
    outside.mkdir()
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)

    with pytest.raises(FileNotFoundError):
        Landscape(zarr_url="missing.zarr")
    with pytest.raises(ValueError, match="outside the working directory"):
        Landscape(zarr_url=outside)


def test_gene_signatures_use_the_shared_store_server(tmp_path, monkeypatch):
    cells = tmp_path / "cells.zarr"
    signatures = tmp_path / "cell type signatures.zarr"
    cells.mkdir()
    signatures.mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(widget_module, "_SHARED_LOCAL_SERVER_PORT", 8123)
    landscape = Landscape(zarr_url=cells, gene_signature_url=signatures)
    assert landscape.gene_signature_url == "http://localhost:8123/cell%20type%20signatures.zarr"
    assert landscape.traits()["gene_signature_url"].metadata["sync"]
    landscape.close()


def test_remote_gene_signature_url_and_missing_local_store(tmp_path, monkeypatch):
    landscape = Landscape(
        gene_signature_url="https://example.org/signatures.zarr/",
        transform=[[1, 0, 0], [0, 1, 0], [0, 0, 1]],
    )
    assert landscape.gene_signature_url == "https://example.org/signatures.zarr"
    landscape.close()
    monkeypatch.chdir(tmp_path)
    with pytest.raises(FileNotFoundError):
        Landscape(gene_signature_url="missing.zarr")


def _signatures(**uns):
    """Cell-type means shaped like sc.get.aggregate(..., func="mean") output."""
    import anndata as ad
    import numpy as np
    import pandas as pd

    sig = ad.AnnData(
        obs=pd.DataFrame(index=["T", "B"]),
        var=pd.DataFrame(index=["CD3D", "MS4A1", "unused"]),
        layers={"mean": np.array([[2.0, 0.0, 0.0], [0.0, 3.0, 0.0]], dtype=np.float32)},
        uns=uns,
    )
    sig.X = None
    return sig


def test_adata_sig_is_sent_as_gene_by_cell_type_parquet():
    import io
    import json

    import pyarrow.parquet as pq

    landscape = Landscape(
        adata_sig=_signatures(),
        cluster_attr="cell_type",
        transform=[[1, 0, 0], [0, 1, 0], [0, 0, 1]],
    )
    table = pq.read_table(io.BytesIO(landscape.gene_signature_parquet))
    assert table.column_names == ["gene", "T", "B"]
    # Genes no cell type expresses can't rank in the estimate.
    assert table.column("gene").to_pylist() == ["CD3D", "MS4A1"]
    assert table.column("B").to_pylist() == [0.0, 3.0]
    assert json.loads(table.schema.metadata[b"viewport_signature"]) == {
        "groupby": "cell_type",
        "units": "mean expression per cell",
    }
    assert landscape.traits()["gene_signature_parquet"].metadata["sync"]
    landscape.close()

    stored = {"groupby": "leiden", "units": "mean counts per cell"}
    landscape = Landscape(
        adata_sig=_signatures(viewport_signature=json.dumps(stored)),
        transform=[[1, 0, 0], [0, 1, 0], [0, 0, 1]],
    )
    table = pq.read_table(io.BytesIO(landscape.gene_signature_parquet))
    assert json.loads(table.schema.metadata[b"viewport_signature"]) == stored
    landscape.close()


def test_adata_sig_rejects_signature_urls_and_z_scores():
    with pytest.raises(ValueError, match="not both"):
        Landscape(adata_sig=_signatures(), gene_signature_url="https://example.org/s.zarr")
    z_scored = _signatures()
    z_scored.X = z_scored.layers["mean"] - 1
    with pytest.raises(ValueError, match="nonnegative"):
        Landscape(adata_sig=z_scored)


def test_adata_sig_reads_the_counts_layer_or_the_named_layer():
    import io
    import json

    import numpy as np
    import pyarrow.parquet as pq

    sig = _signatures()
    means = sig.layers.pop("mean")
    sig.layers["counts"] = means
    sig.layers["log1p"] = np.log1p(means)
    units = {"counts": "mean counts per cell", "log1p": "mean log1p counts per 10,000"}
    sig.uns["viewport_signature"] = {"groupby": "cell_type", "layers": units}
    identity = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]

    landscape = Landscape(adata_sig=sig, transform=identity)
    table = pq.read_table(io.BytesIO(landscape.gene_signature_parquet))
    assert table.column("B").to_pylist() == [0.0, 3.0]
    assert json.loads(table.schema.metadata[b"viewport_signature"])["units"] == units["counts"]
    landscape.close()

    sig.uns["viewport_signature"]["layer"] = "log1p"
    landscape = Landscape(adata_sig=sig, transform=identity)
    table = pq.read_table(io.BytesIO(landscape.gene_signature_parquet))
    assert table.column("B").to_pylist() == pytest.approx([0.0, float(np.log1p(3.0))])
    assert json.loads(table.schema.metadata[b"viewport_signature"])["units"] == units["log1p"]
    landscape.close()

    sig.uns["viewport_signature"]["layer"] = "scaled"
    with pytest.raises(ValueError, match="no layer 'scaled'"):
        Landscape(adata_sig=sig, transform=identity)
