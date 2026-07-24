import numpy as np
import pandas as pd
import pytest


try:
    import anndata as ad

    from celldega.viz import Landscape
except Exception as e:  # pragma: no cover - if deps missing skip
    pytest.skip(f"celldega modules unavailable: {e}", allow_module_level=True)


def test_cluster_colors_built_when_missing_without_mutation() -> None:
    adata = ad.AnnData(np.zeros((3, 3)))
    adata.obs["leiden"] = pd.Categorical(["0", "1", "0"])
    adata.uns.pop("leiden_colors", None)

    adata.obsm["X_umap"] = np.array([[0.0, 0.0], [1.0, 1.0], [2.0, 2.0]])

    widget = Landscape(adata=adata)

    # A color-per-cluster legend is built...
    assert hasattr(widget, "meta_cluster_df")
    assert len(widget.meta_cluster_df) == adata.obs["leiden"].nunique()
    assert widget.meta_cluster_df["color"].notna().all()
    # ...without writing `<attr>_colors` back into the caller's AnnData.
    assert "leiden_colors" not in adata.uns


def test_cluster_attr_colors_by_arbitrary_attribute() -> None:
    # No "leiden" column at all — color the cluster legend by "cell_type".
    adata = ad.AnnData(np.zeros((3, 3)))
    adata.obs["cell_type"] = pd.Categorical(["T", "B", "T"])
    adata.obsm["X_umap"] = np.array([[0.0, 0.0], [1.0, 1.0], [2.0, 2.0]])

    widget = Landscape(adata=adata, cluster_attr="cell_type")

    assert hasattr(widget, "meta_cluster_df")
    # The legend is built from the chosen attribute, not the absent "leiden".
    assert set(widget.meta_cluster_df.index) == {"T", "B"}
    assert widget.meta_cluster_df["color"].notna().all()
    # Non-mutating: no cell_type_colors written into adata.uns.
    assert "cell_type_colors" not in adata.uns


def test_landscape_does_not_mutate_passed_adata() -> None:
    # Regression: Landscape used to `adata.obs.set_index("cell_id", inplace=True)`
    # (swapping the caller's index) and to run sc.pl.umap (writing colors into
    # adata.uns). Neither may touch the passed AnnData.
    adata = ad.AnnData(np.zeros((3, 3)))
    adata.obs_names = ["T10_E14_62_cell1", "T10_E14_62_cell2", "T10_E14_62_cell3"]
    adata.obs["cell_id"] = ["cell1__T10_E14_62", "cell2__T10_E14_62", "cell3__T10_E14_62"]
    adata.obs["leiden"] = pd.Categorical(["0", "1", "0"])
    adata.obsm["X_umap"] = np.array([[0.0, 0.0], [1.0, 1.0], [2.0, 2.0]])

    index_before = list(adata.obs_names)
    columns_before = list(adata.obs.columns)
    uns_keys_before = set(adata.uns.keys())

    Landscape(adata=adata, cluster_attr="leiden")

    assert list(adata.obs_names) == index_before
    assert list(adata.obs.columns) == columns_before  # cell_id not consumed into index
    assert set(adata.uns.keys()) == uns_keys_before
