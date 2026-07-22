import json
import warnings

import anndata as ad
from anndata import AnnData
import numpy as np
import pandas as pd
import pytest

from celldega.align import (
    SerialAlignmentTransform,
    align_serial_slices,
    calc_alignment_transform,
    calc_landmarks,
)


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


def _centroid(adata, slice_attr, slice_id, label):
    mask = (adata.obs[slice_attr] == slice_id).to_numpy() & (
        adata.obs["cluster"] == label
    ).to_numpy()
    return np.asarray(adata.obsm["spatial"])[mask].mean(axis=0)


def _landmark_xy(landmarks, slice_attr, slice_id, label):
    row = landmarks.loc[(landmarks[slice_attr] == slice_id) & (landmarks["label"] == label)].iloc[0]
    return np.array([row["x"], row["y"]])


# ---------------------------------------------------------------------------
# calc_alignment_transform: fitting only, never touches an AnnData's cells.
# ---------------------------------------------------------------------------


def test_calc_alignment_transform_recovers_known_transform():
    rng = np.random.default_rng(0)
    slice0 = _make_slice(rng)
    slice1 = _make_slice(rng, rotation_deg=25, translation=(8.0, -6.0))
    landmarks = calc_landmarks([slice0, slice1], "cluster")

    transform = calc_alignment_transform(landmarks, reference=0)

    for label in _TRUE_CENTERS:
        ref_xy = _landmark_xy(landmarks, "slice", 0, label)
        aligned_xy = _landmark_xy(transform.landmarks_aligned, "slice", 1, label)
        assert np.allclose(ref_xy, aligned_xy, atol=1e-3)


def test_calc_alignment_transform_reference_is_identity():
    rng = np.random.default_rng(1)
    slice0 = _make_slice(rng)
    slice1 = _make_slice(rng, rotation_deg=-40, translation=(-3.0, 4.0))
    landmarks = calc_landmarks([slice0, slice1], "cluster")

    transform = calc_alignment_transform(landmarks, reference=0)

    identity = transform.transforms[0]
    assert np.allclose(identity.rotation, np.eye(2))
    assert identity.scale == 1.0
    assert np.allclose(identity.translation, np.zeros(2))


def test_calc_alignment_transform_never_rescales():
    rng = np.random.default_rng(26)
    slice0 = _make_slice(rng)
    slice1 = _make_slice(rng, scale=1.4, translation=(3.0, -2.0))
    landmarks = calc_landmarks([slice0, slice1], "cluster")

    transform = calc_alignment_transform(landmarks)

    assert transform.transforms[1].scale == 1.0


def test_z_coord_sets_explicit_absolute_values_per_slice():
    rng = np.random.default_rng(2)
    slices = [
        _make_slice(rng),
        _make_slice(rng, rotation_deg=10, translation=(1.0, 1.0)),
        _make_slice(rng, rotation_deg=-15, translation=(-2.0, 3.0)),
    ]
    landmarks = calc_landmarks(slices, "cluster")
    transform = calc_alignment_transform(landmarks, reference=1)

    combined = align_serial_slices(slices, transform, z_coord=[-2.0, 0.0, 5.0])

    z_by_slice = combined.obs.groupby("slice")["Z"].first()
    assert z_by_slice.loc[0] == pytest.approx(-2.0)
    assert z_by_slice.loc[1] == pytest.approx(0.0)
    assert z_by_slice.loc[2] == pytest.approx(5.0)


def test_z_coord_wrong_length_raises():
    rng = np.random.default_rng(2)
    slices = [_make_slice(rng), _make_slice(rng), _make_slice(rng)]
    landmarks = calc_landmarks(slices, "cluster")
    transform = calc_alignment_transform(landmarks)

    with pytest.raises(ValueError, match="length 3"):
        align_serial_slices(slices, transform, z_coord=[0.0, 1.0])


def test_scalar_z_space_is_uniform_offset_from_reference():
    rng = np.random.default_rng(3)
    slices = [_make_slice(rng) for _ in range(3)]
    landmarks = calc_landmarks(slices, "cluster")
    transform = calc_alignment_transform(landmarks, reference=0)

    combined = align_serial_slices(slices, transform, z_space=2.5)

    z_by_slice = combined.obs.groupby("slice")["Z"].first()
    assert z_by_slice.loc[0] == pytest.approx(0.0)
    assert z_by_slice.loc[1] == pytest.approx(2.5)
    assert z_by_slice.loc[2] == pytest.approx(5.0)


def test_same_transform_reused_with_different_z_schemes():
    """Z assignment is decided at apply time, so the identical fitted transform
    can be applied twice with different z_space/z_coord, without refitting."""
    rng = np.random.default_rng(42)
    slices = [_make_slice(rng) for _ in range(3)]
    landmarks = calc_landmarks(slices, "cluster")
    transform = calc_alignment_transform(landmarks, reference=1)

    uniform = (
        align_serial_slices([s.copy() for s in slices], transform, z_space=5.0)
        .obs.groupby("slice")["Z"]
        .first()
    )
    explicit = (
        align_serial_slices([s.copy() for s in slices], transform, z_coord=[0.0, 10.0, 20.0])
        .obs.groupby("slice")["Z"]
        .first()
    )

    assert uniform.loc[0] == pytest.approx(-5.0)
    assert uniform.loc[1] == pytest.approx(0.0)
    assert uniform.loc[2] == pytest.approx(5.0)
    assert explicit.loc[0] == pytest.approx(0.0)
    assert explicit.loc[1] == pytest.approx(10.0)
    assert explicit.loc[2] == pytest.approx(20.0)


def test_calc_alignment_transform_requires_at_least_two_slices():
    rng = np.random.default_rng(35)
    slice0 = _make_slice(rng)
    landmarks = calc_landmarks([slice0], "cluster")

    with pytest.raises(ValueError, match="at least 2 slices"):
        calc_alignment_transform(landmarks)


def test_insufficient_shared_landmarks_raises():
    rng = np.random.default_rng(4)
    slice0 = _make_slice(rng)
    slice1 = _make_slice(rng)
    slice1.obs["cluster"] = slice1.obs["cluster"].map(lambda c: f"other_{c}")
    landmarks = calc_landmarks([slice0, slice1], "cluster")

    with pytest.raises(ValueError, match="shares only 0 landmark"):
        calc_alignment_transform(landmarks)


def test_method_tps_recovers_non_affine_warp_that_procrustes_cannot():
    rng = np.random.default_rng(6)
    slice0 = _make_slice(rng)

    def bend(pts):
        # A local, non-affine bend: no single rotation/translation undoes this.
        return pts + np.column_stack([0.08 * pts[:, 1] ** 2, np.zeros(len(pts))])

    slice1 = _make_warped_slice(rng, bend)
    landmarks = calc_landmarks([slice0, slice1], "cluster")

    rigid = calc_alignment_transform(landmarks)
    tps = calc_alignment_transform(landmarks, method="tps")

    def total_residual(transform):
        return sum(
            np.linalg.norm(
                _landmark_xy(landmarks, "slice", 0, label)
                - _landmark_xy(transform.landmarks_aligned, "slice", 1, label)
            )
            for label in _TRUE_CENTERS
        )

    rigid_residual = total_residual(rigid)
    tps_residual = total_residual(tps)

    assert rigid_residual > 0.5  # a global rigid fit leaves visible residual on a local bend
    assert tps_residual < 1e-3  # TPS interpolates exactly through the landmark centroids
    assert tps_residual < rigid_residual


def test_invalid_method_raises():
    rng = np.random.default_rng(28)
    slice0 = _make_slice(rng)
    slice1 = _make_slice(rng)
    landmarks = calc_landmarks([slice0, slice1], "cluster")

    with pytest.raises(ValueError, match="method"):
        calc_alignment_transform(landmarks, method="bogus")


def test_weight_by_adjacent_counts_downweights_small_mislabeled_cluster():
    rng = np.random.default_rng(20)
    counts = {"0": 50, "1": 50, "2": 50, "3": 50, "4": 2}
    slice0 = _make_slice_with_counts(rng, counts)
    slice1 = _make_slice_with_counts(rng, counts, rotation_deg=15, translation=(3.0, -2.0))

    # Corrupt the small cluster's landmark in slice1 (e.g. a mislabeled/noisy small population).
    mask4 = (slice1.obs["cluster"] == "4").to_numpy()
    spatial = np.asarray(slice1.obsm["spatial"]).copy()
    spatial[mask4] += np.array([15.0, 15.0])
    slice1.obsm["spatial"] = spatial
    landmarks = calc_landmarks([slice0, slice1], "cluster")

    def large_cluster_residual(transform):
        return sum(
            np.linalg.norm(
                _landmark_xy(landmarks, "slice", 0, label)
                - _landmark_xy(transform.landmarks_aligned, "slice", 1, label)
            )
            for label in ["0", "1", "2", "3"]
        )

    unweighted = calc_alignment_transform(landmarks, weight_by_adjacent_counts=False)
    weighted = calc_alignment_transform(landmarks)  # default: True

    assert large_cluster_residual(unweighted) > 10.0
    assert large_cluster_residual(weighted) < 5.0
    assert large_cluster_residual(weighted) < large_cluster_residual(unweighted)


def test_alignment_window_reduces_sensitivity_to_one_noisy_neighbor():
    rng = np.random.default_rng(0)
    slice0 = _make_slice(rng)
    slice1 = _make_slice(rng, rotation_deg=10, translation=(1.0, 1.0))
    slice2 = _make_slice(rng, rotation_deg=20, translation=(2.0, -1.0), noise=1.5)
    slice3 = _make_slice(rng, rotation_deg=30, translation=(-1.0, 2.0))
    landmarks = calc_landmarks([slice0, slice1, slice2, slice3], "cluster")

    def residual_vs_reference(transform):
        return sum(
            np.linalg.norm(
                _landmark_xy(landmarks, "slice", 0, label)
                - _landmark_xy(transform.landmarks_aligned, "slice", 3, label)
            )
            for label in _TRUE_CENTERS
        )

    window1 = calc_alignment_transform(landmarks, alignment_window=1)
    window2 = calc_alignment_transform(landmarks, alignment_window=2)

    assert residual_vs_reference(window2) < residual_vs_reference(window1)


def test_alignment_window_must_be_at_least_one():
    rng = np.random.default_rng(23)
    slice0 = _make_slice(rng)
    slice1 = _make_slice(rng)
    landmarks = calc_landmarks([slice0, slice1], "cluster")

    with pytest.raises(ValueError, match="alignment_window"):
        calc_alignment_transform(landmarks, alignment_window=0)


def test_leave_one_out_residual_recorded_by_default():
    rng = np.random.default_rng(24)
    slice0 = _make_slice(rng)
    slice1 = _make_slice(rng, rotation_deg=10, translation=(1.0, 1.0))
    landmarks = calc_landmarks([slice0, slice1], "cluster")

    transform = calc_alignment_transform(landmarks)

    entry = transform.transform_log["1"]
    assert "leave_one_out_residual" in entry
    assert set(entry["leave_one_out_residual"]["per_landmark"]) == set(_TRUE_CENTERS)
    assert entry["leave_one_out_residual"]["mean"] < 1e-2


def test_compute_residuals_false_skips_leave_one_out_residual():
    rng = np.random.default_rng(25)
    slice0 = _make_slice(rng)
    slice1 = _make_slice(rng, rotation_deg=10, translation=(1.0, 1.0))
    landmarks = calc_landmarks([slice0, slice1], "cluster")

    transform = calc_alignment_transform(landmarks, compute_residuals=False)

    assert "leave_one_out_residual" not in transform.transform_log["1"]


def test_appending_manual_landmark_satisfies_min_shared_landmarks():
    rng = np.random.default_rng(30)
    slice0 = _make_slice(rng)
    slice1 = _make_slice(rng, rotation_deg=15, translation=(2.0, -1.0))

    # Only 2 of the 5 clusters remain shared -- below the default min_shared_landmarks=3.
    slice1.obs["cluster"] = slice1.obs["cluster"].map(
        lambda c: c if c in ("0", "1") else f"other_{c}"
    )
    landmarks = calc_landmarks([slice0, slice1], "cluster")

    with pytest.raises(ValueError, match="shares only 2 landmark"):
        calc_alignment_transform(landmarks)

    # The caller appends one manually-matched landmark (true center of cluster "4" in both
    # slices), tipping the shared count to 3 -- exactly the workflow a semi-manual mix expects.
    rotation = _rotation_matrix(15)
    manual_xy = np.array([5.0, 5.0]) @ rotation.T + np.array([2.0, -1.0])
    manual_landmark = pd.DataFrame(
        {
            "label": ["manual_extra", "manual_extra"],
            "slice": [0, 1],
            "x": [5.0, manual_xy[0]],
            "y": [5.0, manual_xy[1]],
        }
    )
    landmarks_plus_manual = pd.concat([landmarks, manual_landmark], ignore_index=True)

    transform = calc_alignment_transform(landmarks_plus_manual)
    assert transform.transform_log["1"]["n_shared_landmarks"] == 3


def test_landmarks_missing_required_column_raises():
    landmarks = pd.DataFrame({"slice": [0]})

    with pytest.raises(ValueError, match="missing required column"):
        calc_alignment_transform(landmarks)


def test_duplicate_landmark_label_raises():
    rng = np.random.default_rng(32)
    slice0 = _make_slice(rng)
    slice1 = _make_slice(rng)
    landmarks = calc_landmarks([slice0, slice1], "cluster")
    duplicate_row = landmarks[(landmarks["slice"] == 0) & (landmarks["label"] == "0")]
    landmarks = pd.concat([landmarks, duplicate_row], ignore_index=True)

    with pytest.raises(ValueError, match="duplicate landmark label"):
        calc_alignment_transform(landmarks)


# ---------------------------------------------------------------------------
# align_serial_slices: applies a fitted SerialAlignmentTransform to AnnData.
# ---------------------------------------------------------------------------


def test_align_serial_slices_applies_transform_to_cell_coordinates():
    rng = np.random.default_rng(0)
    slice0 = _make_slice(rng)
    slice1 = _make_slice(rng, rotation_deg=25, translation=(8.0, -6.0))
    landmarks = calc_landmarks([slice0, slice1], "cluster")
    transform = calc_alignment_transform(landmarks, reference=0)

    combined = align_serial_slices([slice0, slice1], transform)

    assert combined.n_obs == slice0.n_obs + slice1.n_obs
    assert list(combined.obs["Z"].unique()) == [0.0, 1.0]
    for label in _TRUE_CENTERS:
        c_ref = _centroid(combined, "slice", 0, label)
        c_aligned = _centroid(combined, "slice", 1, label)
        assert np.allclose(c_ref, c_aligned, atol=1e-3)


def test_align_from_single_combined_anndata_matches_list_input():
    rng = np.random.default_rng(1)
    slice0 = _make_slice(rng)
    slice1 = _make_slice(rng, rotation_deg=-40, translation=(-3.0, 4.0))
    slice0.obs["batch"] = "a"
    slice1.obs["batch"] = "b"

    manual = ad.concat([slice0, slice1], join="outer")
    landmarks = calc_landmarks(manual, "cluster", slice_attr="batch")
    transform = calc_alignment_transform(landmarks, slice_attr="batch", reference=0)

    combined = align_serial_slices(manual, transform)

    for label in _TRUE_CENTERS:
        c_ref = _centroid(combined, "batch", "a", label)
        c_aligned = _centroid(combined, "batch", "b", label)
        assert np.allclose(c_ref, c_aligned, atol=1e-3)


def test_align_serial_slices_missing_spatial_raises():
    rng = np.random.default_rng(36)
    slice0 = _make_slice(rng)
    slice1 = _make_slice(rng)
    landmarks = calc_landmarks([slice0, slice1], "cluster")
    transform = calc_alignment_transform(landmarks)
    del slice1.obsm["spatial"]

    with pytest.raises(ValueError, match="obsm\\['spatial'\\]"):
        align_serial_slices([slice0, slice1], transform)


def test_align_serial_slices_single_anndata_missing_slice_attr_column_raises():
    rng = np.random.default_rng(5)
    slice0 = _make_slice(rng)
    slice1 = _make_slice(rng)
    landmarks = calc_landmarks([slice0, slice1], "cluster")
    transform = calc_alignment_transform(landmarks)  # slice_attr defaults to "slice"

    lone_slice = _make_slice(rng)  # has no "slice" obs column

    with pytest.raises(ValueError, match="not a column"):
        align_serial_slices(lone_slice, transform)


def test_align_serial_slices_slice_order_mismatch_raises():
    rng = np.random.default_rng(37)
    slice0 = _make_slice(rng)
    slice1 = _make_slice(rng, rotation_deg=10, translation=(1.0, 1.0))
    slice0.obs["batch"] = "a"
    slice1.obs["batch"] = "b"
    manual = ad.concat([slice0, slice1], join="outer")
    landmarks = calc_landmarks(manual, "cluster", slice_attr="batch")
    transform = calc_alignment_transform(landmarks, slice_attr="batch")

    other = manual.copy()
    other.obs["batch"] = other.obs["batch"].map({"a": "a", "b": "c"})  # "b" -> "c"

    with pytest.raises(ValueError, match="doesn't match the slices"):
        align_serial_slices(other, transform)


def test_align_serial_slices_uns_provenance_matches_transform():
    rng = np.random.default_rng(34)
    slice0 = _make_slice(rng)
    slice1 = _make_slice(rng, rotation_deg=10, translation=(1.0, 1.0))
    landmarks = calc_landmarks([slice0, slice1], "cluster")
    transform = calc_alignment_transform(landmarks)

    combined = align_serial_slices([slice0, slice1], transform)

    uns = combined.uns["align_serial_slices"]
    assert uns["landmarks_initial"].equals(transform.landmarks_initial)
    assert uns["landmarks_aligned"].equals(transform.landmarks_aligned)
    assert uns["transforms"] == transform.transform_log
    assert uns["method"] == transform.method


def test_align_serial_slices_warns_on_duplicate_obs_names():
    """Slices commonly reuse the same per-slice barcode convention (e.g. every
    sample starts at "0", "1", ...) -- align_serial_slices should flag that
    rather than silently producing an AnnData with duplicate obs_names."""
    rng = np.random.default_rng(42)
    slice0 = _make_slice(rng)
    slice1 = _make_slice(rng, rotation_deg=10, translation=(1.0, 1.0))
    landmarks = calc_landmarks([slice0, slice1], "cluster")
    transform = calc_alignment_transform(landmarks)

    with pytest.warns(UserWarning, match="obs_names are not unique"):
        combined = align_serial_slices([slice0, slice1], transform)

    assert not combined.obs_names.is_unique


def test_align_serial_slices_cell_name_prefix_keeps_names_unique_and_silences_warning():
    rng = np.random.default_rng(43)
    slice0 = _make_slice(rng)
    slice1 = _make_slice(rng, rotation_deg=10, translation=(1.0, 1.0))
    landmarks = calc_landmarks([slice0, slice1], "cluster")
    transform = calc_alignment_transform(landmarks)

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        combined = align_serial_slices([slice0, slice1], transform, cell_name_prefix=True)

    assert combined.obs_names.is_unique
    assert combined.obs_names[0].startswith("0_")
    assert combined.obs_names[slice0.n_obs].startswith("1_")


# ---------------------------------------------------------------------------
# Reuse on arbitrary point data, and save/load persistence.
# ---------------------------------------------------------------------------


def test_apply_to_points_reused_on_arbitrary_points():
    """The same fitted transform applies to any (n, 2) array -- e.g. standing in
    for segmentation-polygon vertices or transcript coordinates, not just cells."""
    rng = np.random.default_rng(38)
    slice0 = _make_slice(rng)
    slice1 = _make_slice(rng, rotation_deg=25, translation=(8.0, -6.0))
    landmarks = calc_landmarks([slice0, slice1], "cluster")
    transform = calc_alignment_transform(landmarks, reference=0)

    fake_polygon_vertices = np.array([[1.0, 1.0], [2.0, 1.0], [2.0, 2.0], [1.0, 2.0]])
    aligned_vertices = transform.apply_to_points(1, fake_polygon_vertices)

    # Applying the identical transform directly should match.
    expected = transform.transforms[1].apply(fake_polygon_vertices)
    assert np.allclose(aligned_vertices, expected)


@pytest.mark.parametrize("method", ["procrustes", "tps"])
def test_serial_alignment_transform_save_load_round_trip(tmp_path, method):
    rng = np.random.default_rng(39)
    slice0 = _make_slice(rng)
    slice1 = _make_slice(rng, rotation_deg=15, translation=(4.0, -3.0))
    landmarks = calc_landmarks([slice0, slice1], "cluster")
    transform = calc_alignment_transform(landmarks, method=method)

    save_dir = tmp_path / "transform"
    transform.save(save_dir)
    reloaded = SerialAlignmentTransform.load(save_dir)

    fake_points = np.array([[1.0, 1.0], [2.0, 3.0], [-1.0, 4.0]])
    assert np.allclose(
        transform.apply_to_points(1, fake_points), reloaded.apply_to_points(1, fake_points)
    )
    assert reloaded.slice_attr == transform.slice_attr
    assert reloaded.slice_ids == transform.slice_ids
    assert reloaded.reference == transform.reference
    assert reloaded.landmarks_initial.equals(transform.landmarks_initial)
    assert reloaded.landmarks_aligned.equals(transform.landmarks_aligned)
    assert reloaded.degree == transform.degree


def test_serial_alignment_transform_load_defaults_degree_for_older_saves(tmp_path):
    rng = np.random.default_rng(40)
    slice0 = _make_slice(rng)
    slice1 = _make_slice(rng, rotation_deg=10, translation=(2.0, -1.0))
    landmarks = calc_landmarks([slice0, slice1], "cluster")
    transform = calc_alignment_transform(landmarks, method="tps")

    save_dir = tmp_path / "transform"
    transform.save(save_dir)
    # Simulate a transform saved before `degree` existed.
    metadata_path = save_dir / "metadata.json"
    metadata = json.loads(metadata_path.read_text())
    del metadata["degree"]
    metadata_path.write_text(json.dumps(metadata))

    reloaded = SerialAlignmentTransform.load(save_dir)
    assert reloaded.degree == 1


def test_calc_alignment_transform_degree_changes_the_tps_fit():
    rng = np.random.default_rng(41)
    slice0 = _make_slice(rng)
    slice1 = _make_slice(rng, rotation_deg=15, translation=(4.0, -3.0))
    landmarks = calc_landmarks([slice0, slice1], "cluster")

    transform_degree_1 = calc_alignment_transform(landmarks, method="tps", degree=1)
    transform_degree_0 = calc_alignment_transform(landmarks, method="tps", degree=0)

    assert transform_degree_1.degree == 1
    assert transform_degree_0.degree == 0
    far_point = np.array([[500.0, 500.0]])
    assert not np.allclose(
        transform_degree_1.apply_to_points(1, far_point),
        transform_degree_0.apply_to_points(1, far_point),
    )


def test_calc_alignment_transform_area_regularization_preserves_slice_area(tmp_path):
    rng = np.random.default_rng(42)
    slice0 = _make_slice(rng)
    # slice1 is genuinely ~0.6x the size of slice0 (a real area difference).
    slice1 = _make_slice(rng, scale=0.6, rotation_deg=10, translation=(3.0, -2.0))
    landmarks = calc_landmarks([slice0, slice1], "cluster")

    def area_factor(transform, slice_id):
        # aligned landmark cloud area vs source (slice1's own coords)
        src = np.array([_TRUE_CENTERS[k] for k in _TRUE_CENTERS])
        out = transform.apply_to_points(slice_id, src * 0.6)
        cov_out = np.linalg.det(np.cov(out, rowvar=False))
        cov_src = np.linalg.det(np.cov(src * 0.6, rowvar=False))
        return float(np.sqrt(cov_out / cov_src))

    plain = calc_alignment_transform(landmarks, method="tps")
    pinned = calc_alignment_transform(landmarks, method="tps", area_regularization=1.0)

    assert plain.area_regularization == 0.0
    assert pinned.area_regularization == 1.0
    # Plain TPS blows slice1 up ~1/0.6 to match slice0; the penalty keeps its area.
    assert area_factor(plain, 1) > 1.3
    assert np.isclose(area_factor(pinned, 1), 1.0, atol=1e-6)

    # area_regularization survives save/load.
    save_dir = tmp_path / "t"
    pinned.save(save_dir)
    reloaded = SerialAlignmentTransform.load(save_dir)
    assert reloaded.area_regularization == 1.0
    fake = np.array([[1.0, 1.0], [2.0, 3.0]])
    assert np.allclose(pinned.apply_to_points(1, fake), reloaded.apply_to_points(1, fake))


def test_serial_alignment_transform_tps_save_load_preserves_exact_interpolation(tmp_path):
    """Before this split, a TPS transform's spline was discarded entirely -- this
    is the concrete fix: it survives a save/load round trip and still
    interpolates its own landmarks exactly."""
    rng = np.random.default_rng(40)
    slice0 = _make_slice(rng)
    slice1 = _make_slice(rng, rotation_deg=15, translation=(4.0, -3.0))
    landmarks = calc_landmarks([slice0, slice1], "cluster")
    transform = calc_alignment_transform(landmarks, method="tps")

    transform.save(tmp_path / "transform")
    reloaded = SerialAlignmentTransform.load(tmp_path / "transform")

    source = landmarks.loc[landmarks["slice"] == 1, ["x", "y"]].to_numpy()
    target = transform.landmarks_aligned.loc[
        transform.landmarks_aligned["slice"] == 1, ["x", "y"]
    ].to_numpy()

    assert np.allclose(reloaded.apply_to_points(1, source), target, atol=1e-6)


def test_align_serial_slices_works_with_reloaded_transform(tmp_path):
    rng = np.random.default_rng(41)
    slice0 = _make_slice(rng)
    slice1 = _make_slice(rng, rotation_deg=25, translation=(8.0, -6.0))
    landmarks = calc_landmarks([slice0, slice1], "cluster")
    transform = calc_alignment_transform(landmarks, reference=0)

    transform.save(tmp_path / "transform")
    reloaded = SerialAlignmentTransform.load(tmp_path / "transform")

    expected = align_serial_slices([slice0.copy(), slice1.copy()], transform)
    actual = align_serial_slices([slice0.copy(), slice1.copy()], reloaded)

    assert np.allclose(np.asarray(expected.obsm["spatial"]), np.asarray(actual.obsm["spatial"]))
    assert (expected.obs["Z"].to_numpy() == actual.obs["Z"].to_numpy()).all()
