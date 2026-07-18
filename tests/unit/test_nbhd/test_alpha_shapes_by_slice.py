import anndata as ad
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import Polygon

from celldega.nbhd import alpha_shape_cell_clusters_by_slice
from celldega.nbhd.utils import _stamp_z


def _synthetic_multi_slice_adata(seed=0, n_slices=2, n_clusters=2, n_per_cluster=30):
    rng = np.random.RandomState(seed)
    rows = []
    xy = []
    for slice_idx in range(n_slices):
        for cluster_idx in range(n_clusters):
            center = np.array([cluster_idx * 200.0, slice_idx * 200.0])
            pts = rng.normal(loc=center, scale=5.0, size=(n_per_cluster, 2))
            xy.append(pts)
            rows.extend(
                [
                    {
                        "cluster": str(cluster_idx),
                        "slice_id": f"s{slice_idx}",
                        "z": float(slice_idx) * 100.0,
                    }
                ]
                * n_per_cluster
            )

    obs = pd.DataFrame(rows)
    obs.index = [f"cell_{i}" for i in range(len(obs))]
    adata = ad.AnnData(obs=obs)
    adata.obsm["spatial"] = np.vstack(xy)
    return adata


def test_alpha_shape_cell_clusters_by_slice_builds_one_neighborhood_per_slice_cluster():
    adata = _synthetic_multi_slice_adata(n_slices=2, n_clusters=2)

    gdf = alpha_shape_cell_clusters_by_slice(
        adata, cluster_attr="cluster", slice_attr="slice_id", z_attr="z", alphas=(150,)
    )

    assert set(gdf["slice_id"]) == {"s0", "s1"}
    assert set(gdf["cluster_id"]) == {"0", "1"}
    assert len(gdf) == 4
    assert list(gdf["name"]) == [
        f"{s}__{c}" for s, c in zip(gdf["slice_id"], gdf["cluster_id"], strict=True)
    ]
    assert (gdf["cell_count"] == 30).all()


def test_alpha_shape_cell_clusters_by_slice_stamps_each_slices_z():
    adata = _synthetic_multi_slice_adata(n_slices=2, n_clusters=1)

    gdf = alpha_shape_cell_clusters_by_slice(
        adata, cluster_attr="cluster", slice_attr="slice_id", z_attr="z", alphas=(150,)
    )

    assert gdf.geometry.apply(lambda g: g.has_z).all()
    z_by_slice = {
        slice_id: {round(coord[2], 3) for poly in row.geoms for coord in poly.exterior.coords}
        for slice_id, row in zip(gdf["slice_id"], gdf.geometry, strict=True)
    }
    assert z_by_slice["s0"] == {0.0}
    assert z_by_slice["s1"] == {100.0}


def test_alpha_shape_cell_clusters_by_slice_jitters_coplanar_clusters_within_a_slice():
    adata = _synthetic_multi_slice_adata(n_slices=1, n_clusters=3)

    gdf = alpha_shape_cell_clusters_by_slice(
        adata,
        cluster_attr="cluster",
        slice_attr="slice_id",
        z_attr="z",
        alphas=(150,),
        z_jitter=2.0,
    )

    z_values = sorted(
        {
            round(coord[2], 3)
            for poly in gdf.geometry
            for g in poly.geoms
            for coord in g.exterior.coords
        }
    )
    # 3 clusters at the same slice Z=0 should be jittered apart: 0.0, 2.0, 4.0
    assert z_values == [0.0, 2.0, 4.0]


def test_alpha_shape_cell_clusters_by_slice_defaults_to_z_zero_without_z_attr():
    adata = _synthetic_multi_slice_adata(n_slices=2, n_clusters=1)

    gdf = alpha_shape_cell_clusters_by_slice(
        adata, cluster_attr="cluster", slice_attr="slice_id", z_attr=None, alphas=(150,)
    )

    z_values = {
        round(coord[2], 3)
        for poly in gdf.geometry
        for g in poly.geoms
        for coord in g.exterior.coords
    }
    assert z_values == {0.0}


def test_alpha_shape_cell_clusters_by_slice_rejects_multiple_alphas():
    adata = _synthetic_multi_slice_adata(n_slices=1, n_clusters=1)

    with pytest.raises(ValueError, match="single alpha-shape"):
        alpha_shape_cell_clusters_by_slice(adata, alphas=(100, 150))


def test_stamp_z_sets_constant_z_on_every_vertex():
    poly = Polygon([(0, 0), (0, 10), (10, 10), (10, 0)])
    stamped = _stamp_z(poly, 42.0)

    assert stamped.has_z
    assert {round(z, 3) for _x, _y, z in stamped.exterior.coords} == {42.0}


def test_stamp_z_passes_through_none():
    assert _stamp_z(None, 5.0) is None
