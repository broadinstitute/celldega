"""Tests for Landscape widget initialization with AnnData."""

import io
import numpy as np
import pandas as pd
import pytest
from anndata import AnnData

try:
    from celldega.viz import Landscape
except Exception as e:  # pragma: no cover - skip if deps missing
    pytest.skip(f"celldega modules unavailable: {e}", allow_module_level=True)


def make_simple_anndata() -> AnnData:
    """Create a small AnnData object for testing."""
    np.random.seed(0)
    X = np.random.rand(5, 3)
    obs = pd.DataFrame({"leiden": pd.Categorical(["0", "1", "0", "1", "0"])})
    obs.index = [f"cell{i}" for i in range(5)]
    var = pd.DataFrame(index=[f"gene{i}" for i in range(3)])
    adata = AnnData(X=X, obs=obs, var=var)
    adata.obsm["X_umap"] = np.random.rand(5, 2)
    adata.uns["leiden_colors"] = ["#ff0000", "#00ff00"]
    return adata


def test_landscape_initializes_with_anndata() -> None:
    """Landscape should accept AnnData and expose parquet traitlets."""
    adata = make_simple_anndata()
    widget = Landscape(base_url="https://example.com", AnnData=adata)

    assert hasattr(widget, "meta_cell_parquet")
    assert hasattr(widget, "meta_cluster_parquet")
    assert hasattr(widget, "umap_parquet")

    meta_cell = pd.read_parquet(io.BytesIO(widget.meta_cell_parquet))
    meta_cluster = pd.read_parquet(io.BytesIO(widget.meta_cluster_parquet))
    umap_df = pd.read_parquet(io.BytesIO(widget.umap_parquet))

    pd.testing.assert_frame_equal(
        meta_cell,
        adata.obs[["leiden"]].reset_index(),
    )

    cluster_counts = adata.obs["leiden"].value_counts().sort_index()
    expected_cluster = pd.DataFrame(
        {
            "color": adata.uns["leiden_colors"][: len(cluster_counts)],
            "count": cluster_counts.values,
        },
        index=cluster_counts.index,
    ).reset_index()
    pd.testing.assert_frame_equal(meta_cluster, expected_cluster)

    pd.testing.assert_frame_equal(
        umap_df,
        pd.DataFrame(adata.obsm["X_umap"], index=adata.obs.index).reset_index(),
    )
