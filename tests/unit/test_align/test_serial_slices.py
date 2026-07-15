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


def _make_slice_with_counts(rng, counts, rotation_deg=0.0, translation=(0.0, 0.0), noise=1e-6):
    """Like _make_slice, but with an explicit per-cluster cell count."""
    rotation = _rotation_matrix(rotation_deg)
    translation = np.asarray(translation)
    labels, coords = [], []
    for label, center in _TRUE_CENTERS.items():
        n = counts[label]
        pts = np.asarray(center) + rng.normal(scale=noise, size=(n, 2))
        pts = pts @ rotation.T + translation
        coords.append(pts)
        labels += [label] * n
    coords = np.concatenate(coords, axis=0)
    n_total = coords.shape[0]
    obs = pd.DataFrame({"cluster": labels})
    var = pd.DataFrame(index=[f"gene{i}" for i in range(5)])
    adata = AnnData(X=rng.poisson(1.0, size=(n_total, 5)).astype(float), obs=obs, var=var)
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


def test_z_coord_sets_explicit_absolute_values_per_slice():
    rng = np.random.default_rng(2)
    slices = [
        _make_slice(rng),
        _make_slice(rng, rotation_deg=10, translation=(1.0, 1.0)),
        _make_slice(rng, rotation_deg=-15, translation=(-2.0, 3.0)),
    ]

    combined = align_serial_slices(
        slices, cluster_key="cluster", reference=1, z_coord=[-2.0, 0.0, 5.0]
    )

    z_by_slice = combined.obs.groupby("slice")["Z"].first()
    assert z_by_slice.loc[0] == pytest.approx(-2.0)
    assert z_by_slice.loc[1] == pytest.approx(0.0)
    assert z_by_slice.loc[2] == pytest.approx(5.0)


def test_z_coord_wrong_length_raises():
    rng = np.random.default_rng(2)
    slices = [_make_slice(rng), _make_slice(rng), _make_slice(rng)]

    with pytest.raises(ValueError, match="length 3"):
        align_serial_slices(slices, cluster_key="cluster", z_coord=[0.0, 1.0])


def test_scalar_z_space_is_uniform_offset_from_reference():
    rng = np.random.default_rng(3)
    slices = [_make_slice(rng) for _ in range(3)]

    combined = align_serial_slices(slices, cluster_key="cluster", reference=0, z_space=2.5)

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
    tps = align_serial_slices(
        [slice0, slice1], cluster_key="cluster", fit_transform=fit_thin_plate_spline
    )

    def total_residual(combined):
        return sum(
            np.linalg.norm(
                _centroid(combined, "slice", 0, label) - _centroid(combined, "slice", 1, label)
            )
            for label in _TRUE_CENTERS
        )

    rigid_residual = total_residual(rigid)
    tps_residual = total_residual(tps)

    assert rigid_residual > 0.5  # a global rigid fit leaves visible residual on a local bend
    assert tps_residual < 1e-3  # TPS interpolates exactly through the landmark centroids
    assert tps_residual < rigid_residual


def test_cluster_weight_cell_count_downweights_small_mislabeled_cluster():
    rng = np.random.default_rng(20)
    counts = {"0": 50, "1": 50, "2": 50, "3": 50, "4": 2}
    slice0 = _make_slice_with_counts(rng, counts)
    slice1 = _make_slice_with_counts(rng, counts, rotation_deg=15, translation=(3.0, -2.0))

    # Corrupt the small cluster's landmark in slice1 (e.g. a mislabeled/noisy small population).
    mask4 = (slice1.obs["cluster"] == "4").to_numpy()
    spatial = np.asarray(slice1.obsm["spatial"]).copy()
    spatial[mask4] += np.array([15.0, 15.0])
    slice1.obsm["spatial"] = spatial

    def large_cluster_residual(combined):
        return sum(
            np.linalg.norm(
                _centroid(combined, "slice", 0, label) - _centroid(combined, "slice", 1, label)
            )
            for label in ["0", "1", "2", "3"]
        )

    unweighted = align_serial_slices([slice0, slice1], cluster_key="cluster")
    weighted = align_serial_slices(
        [slice0, slice1], cluster_key="cluster", cluster_weight="cell_count"
    )

    assert large_cluster_residual(unweighted) > 10.0
    assert large_cluster_residual(weighted) < 5.0
    assert large_cluster_residual(weighted) < large_cluster_residual(unweighted)


def test_cluster_weight_presence_and_combined_presets_run():
    rng = np.random.default_rng(21)
    slice0 = _make_slice(rng)
    slice1 = _make_slice(rng, rotation_deg=10, translation=(1.0, 1.0))

    for preset in ["presence", "cell_count_and_presence"]:
        combined = align_serial_slices(
            [slice0, slice1], cluster_key="cluster", cluster_weight=preset
        )
        assert combined.uns["align_serial_slices"]["cluster_weight"] == preset


def test_cluster_weight_invalid_preset_raises():
    rng = np.random.default_rng(22)
    slice0 = _make_slice(rng)
    slice1 = _make_slice(rng)

    with pytest.raises(ValueError, match="cluster_weight"):
        align_serial_slices([slice0, slice1], cluster_key="cluster", cluster_weight="bogus")


def test_alignment_window_reduces_sensitivity_to_one_noisy_neighbor():
    rng = np.random.default_rng(0)
    slice0 = _make_slice(rng)
    slice1 = _make_slice(rng, rotation_deg=10, translation=(1.0, 1.0))
    slice2 = _make_slice(rng, rotation_deg=20, translation=(2.0, -1.0), noise=1.5)
    slice3 = _make_slice(rng, rotation_deg=30, translation=(-1.0, 2.0))
    slices = [slice0, slice1, slice2, slice3]

    def residual_vs_reference(combined):
        return sum(
            np.linalg.norm(
                _centroid(combined, "slice", 0, label) - _centroid(combined, "slice", 3, label)
            )
            for label in _TRUE_CENTERS
        )

    window1 = align_serial_slices(
        [s.copy() for s in slices], cluster_key="cluster", alignment_window=1
    )
    window2 = align_serial_slices(
        [s.copy() for s in slices], cluster_key="cluster", alignment_window=2
    )

    assert residual_vs_reference(window2) < residual_vs_reference(window1)


def test_alignment_window_must_be_at_least_one():
    rng = np.random.default_rng(23)
    slice0 = _make_slice(rng)
    slice1 = _make_slice(rng)

    with pytest.raises(ValueError, match="alignment_window"):
        align_serial_slices([slice0, slice1], cluster_key="cluster", alignment_window=0)


def test_leave_one_out_residual_recorded_in_uns_by_default():
    rng = np.random.default_rng(24)
    slice0 = _make_slice(rng)
    slice1 = _make_slice(rng, rotation_deg=10, translation=(1.0, 1.0))

    combined = align_serial_slices([slice0, slice1], cluster_key="cluster")

    entry = combined.uns["align_serial_slices"]["transforms"]["1"]
    assert "leave_one_out_residual" in entry
    assert set(entry["leave_one_out_residual"]["per_cluster"]) == set(_TRUE_CENTERS)
    assert entry["leave_one_out_residual"]["mean"] < 1e-2


def test_compute_residuals_false_skips_leave_one_out_residual():
    rng = np.random.default_rng(25)
    slice0 = _make_slice(rng)
    slice1 = _make_slice(rng, rotation_deg=10, translation=(1.0, 1.0))

    combined = align_serial_slices([slice0, slice1], cluster_key="cluster", compute_residuals=False)

    entry = combined.uns["align_serial_slices"]["transforms"]["1"]
    assert "leave_one_out_residual" not in entry
