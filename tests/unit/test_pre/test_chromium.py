import json
import numpy as np
import pandas as pd
import pytest
from anndata import AnnData

from celldega.pre import make_chromium_from_anndata


def test_make_chromium_from_anndata(tmp_path):
    X = np.array([[1, 2], [3, 0]])
    adata = AnnData(
        X,
        obs=pd.DataFrame(index=["c1", "c2"]),
        var=pd.DataFrame(index=["g1", "g2"]),
    )
    adata.layers["counts"] = adata.X.copy()

    make_chromium_from_anndata(adata, tmp_path)

    assert (tmp_path / "cbg" / "g1.parquet").exists()

    cell_meta = pd.read_parquet(tmp_path / "cell_metadata.parquet")
    assert cell_meta["name"].tolist() == ["c1", "c2"]
    assert list(cell_meta["geometry"].iloc[0]) == [0.0, 0.0]

    with open(tmp_path / "landscape_parameters.json") as fh:
        params = json.load(fh)
    assert params["technology"] == "Chromium"


def test_make_chromium_requires_integer(tmp_path):
    X = np.array([[1.5]])
    adata = AnnData(X, obs=pd.DataFrame(index=["c1"]), var=pd.DataFrame(index=["g1"]))
    with pytest.raises(ValueError):
        make_chromium_from_anndata(adata, tmp_path)
