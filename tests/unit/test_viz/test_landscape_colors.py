import numpy as np
import pandas as pd
import pytest


try:
    import anndata as ad

    from celldega.viz import Landscape
except Exception as e:  # pragma: no cover - if deps missing skip
    pytest.skip(f"celldega modules unavailable: {e}", allow_module_level=True)


def test_leiden_colors_added_if_missing() -> None:
    adata = ad.AnnData(np.zeros((3, 3)))
    adata.obs["leiden"] = pd.Categorical(["0", "1", "0"])
    adata.uns.pop("leiden_colors", None)

    adata.obsm["X_umap"] = np.array([[0.0, 0.0], [1.0, 1.0], [2.0, 2.0]])

    widget = Landscape(adata=adata)

    assert hasattr(widget, "meta_cluster_df")
    colors = adata.uns.get("leiden_colors")
    assert colors is not None
    assert len(colors) == adata.obs["leiden"].nunique()


def test_cluster_attr_colors_by_arbitrary_attribute() -> None:
    # No "leiden" column at all — color the cluster legend by "cell_type".
    adata = ad.AnnData(np.zeros((3, 3)))
    adata.obs["cell_type"] = pd.Categorical(["T", "B", "T"])
    adata.obsm["X_umap"] = np.array([[0.0, 0.0], [1.0, 1.0], [2.0, 2.0]])

    widget = Landscape(adata=adata, cluster_attr="cell_type")

    assert hasattr(widget, "meta_cluster_df")
    # The legend is built from the chosen attribute, not the absent "leiden".
    assert set(widget.meta_cluster_df.index) == {"T", "B"}
    assert adata.uns.get("cell_type_colors") is not None
