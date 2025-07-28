import numpy as np
import pandas as pd
import pytest
import io
import json
from unittest.mock import patch

try:
    import anndata as ad
    from celldega.viz import Landscape
except Exception as e:  # pragma: no cover - if deps missing skip
    pytest.skip(f"celldega modules unavailable: {e}", allow_module_level=True)

def mock_urlopen_success(*args, **kwargs):
    fake_json = json.dumps({"technology": "Xenium"}).encode("utf-8")
    return io.BytesIO(fake_json)

@patch("celldega.viz.widget.urllib.request.urlopen", side_effect=mock_urlopen_success)
def test_leiden_colors_added_if_missing(mock_urlopen) -> None:
    adata = ad.AnnData(np.zeros((3, 3)))
    adata.obs["leiden"] = pd.Categorical(["0", "1", "0"])
    adata.uns.pop("leiden_colors", None)

    adata.obsm["X_umap"] = np.array([
        [0.0, 0.0],
        [1.0, 1.0],
        [2.0, 2.0]
    ])

    widget = Landscape(adata=adata)

    assert hasattr(widget, "meta_cluster_df")
    colors = adata.uns.get("leiden_colors")
    assert colors is not None
    assert len(colors) == adata.obs["leiden"].nunique()
