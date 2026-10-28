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
