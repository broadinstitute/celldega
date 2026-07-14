from anndata import AnnData
import numpy as np
import pandas as pd
import pytest

from celldega.align import align_serial_slices, fit_thin_plate_spline


_TRUE_CENTERS = {
    "0": (0.0, 0.0),
    "1": (10.0, 0.0),
    "2": (0.0, 10.0),
    "3": (10.0, 10.0),
    "4": (5.0, 5.0),
}


def _rotation_matrix(angle_deg):
    theta = np.radians(angle_deg)
    return np.array([[np.cos(theta), -np.sin(theta)], [np.sin(theta), np.cos(theta)]])


def _make_slice(
    rng, rotation_deg=0.0, scale=1.0, translation=(0.0, 0.0), n_per_cluster=20, noise=1e-6
):
    rotation = _rotation_matrix(rotation_deg)
    translation = np.asarray(translation)
    labels, coords = [], []
    for label, center in _TRUE_CENTERS.items():
        pts = np.asarray(center) + rng.normal(scale=noise, size=(n_per_cluster, 2))
        pts = scale * pts @ rotation.T + translation
        coords.append(pts)
        labels += [label] * n_per_cluster
    coords = np.concatenate(coords, axis=0)
    n = coords.shape[0]
    obs = pd.DataFrame({"cluster": labels})
    var = pd.DataFrame(index=[f"gene{i}" for i in range(5)])
    adata = AnnData(X=rng.poisson(1.0, size=(n, 5)).astype(float), obs=obs, var=var)
    adata.obsm["spatial"] = coords
    return adata


def _make_warped_slice(rng, warp, n_per_cluster=20, noise=1e-6):
    """Like _make_slice, but apply an arbitrary (possibly non-affine) warp."""
    labels, coords = [], []
    for label, center in _TRUE_CENTERS.items():
        pts = np.asarray(center) + rng.normal(scale=noise, size=(n_per_cluster, 2))
        coords.append(warp(pts))
        labels += [label] * n_per_cluster
    coords = np.concatenate(coords, axis=0)
    n = coords.shape[0]
    obs = pd.DataFrame({"cluster": labels})
    var = pd.DataFrame(index=[f"gene{i}" for i in range(5)])
    adata = AnnData(X=rng.poisson(1.0, size=(n, 5)).astype(float), obs=obs, var=var)
    adata.obsm["spatial"] = coords
    return adata


def _centroid(adata, slice_key, slice_id, label):
    mask = (adata.obs[slice_key] == slice_id).to_numpy() & (
        adata.obs["cluster"] == label
    ).to_numpy()
    return np.asarray(adata.obsm["spatial"])[mask].mean(axis=0)


def test_align_recovers_known_transform_from_list_input():
    rng = np.random.default_rng(0)
    slice0 = _make_slice(rng)
    slice1 = _make_slice(rng, rotation_deg=25, scale=1.4, translation=(8.0, -6.0))

    combined = align_serial_slices([slice0, slice1], cluster_key="cluster", reference=0)

    assert combined.n_obs == slice0.n_obs + slice1.n_obs
    assert list(combined.obs["Z"].unique()) == [0.0, 1.0]

    for label in _TRUE_CENTERS:
        c_ref = _centroid(combined, "slice", 0, label)
        c_aligned = _centroid(combined, "slice", 1, label)
        assert np.allclose(c_ref, c_aligned, atol=1e-3)


def test_align_from_single_combined_anndata_matches_list_input():
    rng = np.random.default_rng(1)
    slice0 = _make_slice(rng)
    slice1 = _make_slice(rng, rotation_deg=-40, scale=0.7, translation=(-3.0, 4.0))

    slice0.obs["batch"] = "a"
    slice1.obs["batch"] = "b"
    import anndata as ad

    manual = ad.concat([slice0, slice1], join="outer")

    combined = align_serial_slices(manual, cluster_key="cluster", slice_key="batch", reference=0)

    for label in _TRUE_CENTERS:
        c_ref = _centroid(combined, "batch", "a", label)
        c_aligned = _centroid(combined, "batch", "b", label)
        assert np.allclose(c_ref, c_aligned, atol=1e-3)


def test_z_spacing_list_with_middle_reference():
    rng = np.random.default_rng(2)
    slices = [
        _make_slice(rng),
        _make_slice(rng, rotation_deg=10, translation=(1.0, 1.0)),
        _make_slice(rng, rotation_deg=-15, translation=(-2.0, 3.0)),
    ]

    combined = align_serial_slices(slices, cluster_key="cluster", reference=1, z_spacing=[2.0, 5.0])

    z_by_slice = combined.obs.groupby("slice")["Z"].first()
    assert z_by_slice.loc[0] == pytest.approx(-2.0)
    assert z_by_slice.loc[1] == pytest.approx(0.0)
    assert z_by_slice.loc[2] == pytest.approx(5.0)


def test_scalar_z_spacing_is_uniform_offset_from_reference():
    rng = np.random.default_rng(3)
    slices = [_make_slice(rng) for _ in range(3)]

    combined = align_serial_slices(slices, cluster_key="cluster", reference=0, z_spacing=2.5)

    z_by_slice = combined.obs.groupby("slice")["Z"].first()
    assert z_by_slice.loc[0] == pytest.approx(0.0)
    assert z_by_slice.loc[1] == pytest.approx(2.5)
    assert z_by_slice.loc[2] == pytest.approx(5.0)


def test_insufficient_shared_clusters_raises():
    rng = np.random.default_rng(4)
    slice0 = _make_slice(rng)
    slice1 = _make_slice(rng)
    slice1.obs["cluster"] = slice1.obs["cluster"].map(lambda c: f"other_{c}")

    with pytest.raises(ValueError, match="shares only 0 cluster"):
        align_serial_slices([slice0, slice1], cluster_key="cluster")


def test_single_anndata_without_slice_key_raises():
    rng = np.random.default_rng(5)
    slice0 = _make_slice(rng)

    with pytest.raises(ValueError, match="slice_key is required"):
        align_serial_slices(slice0, cluster_key="cluster")


def test_fit_transform_tps_recovers_non_affine_warp_that_rigid_cannot():
    rng = np.random.default_rng(6)
    slice0 = _make_slice(rng)

    def bend(pts):
        # A local, non-affine bend: no single rotation/scale/translation undoes this.
        return pts + np.column_stack([0.08 * pts[:, 1] ** 2, np.zeros(len(pts))])

    slice1 = _make_warped_slice(rng, bend)

    rigid = align_serial_slices([slice0, slice1], cluster_key="cluster")
    tps = align_serial_slices([slice0, slice1], cluster_key="cluster", fit_transform=fit_thin_plate_spline)

    def total_residual(combined):
        return sum(
            np.linalg.norm(_centroid(combined, "slice", 0, label) - _centroid(combined, "slice", 1, label))
            for label in _TRUE_CENTERS
        )

    rigid_residual = total_residual(rigid)
    tps_residual = total_residual(tps)

    assert rigid_residual > 0.5  # a global rigid fit leaves visible residual on a local bend
    assert tps_residual < 1e-3  # TPS interpolates exactly through the landmark centroids
    assert tps_residual < rigid_residual
