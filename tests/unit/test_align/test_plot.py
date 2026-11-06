import matplotlib


matplotlib.use("Agg")

from anndata import AnnData
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest

from celldega.align import calc_alignment_transform, calc_landmarks, plot_alignment


_CENTERS = {"a": (0.0, 0.0), "b": (10.0, 0.0), "c": (0.0, 10.0)}


def _rotation_matrix(angle_deg):
    theta = np.radians(angle_deg)
    return np.array([[np.cos(theta), -np.sin(theta)], [np.sin(theta), np.cos(theta)]])


def _make_slice(rng, rotation_deg=0.0, translation=(0.0, 0.0)):
    rotation = _rotation_matrix(rotation_deg)
    translation = np.asarray(translation)
    labels, coords = [], []
    for label, center in _CENTERS.items():
        pts = np.asarray(center) + rng.normal(scale=1e-6, size=(15, 2))
        pts = pts @ rotation.T + translation
        coords.append(pts)
        labels += [label] * 15
    coords = np.concatenate(coords, axis=0)
    obs = pd.DataFrame({"cluster": labels})
    var = pd.DataFrame(index=["g0", "g1"])
    adata = AnnData(X=rng.poisson(1.0, size=(coords.shape[0], 2)).astype(float), obs=obs, var=var)
    adata.obsm["spatial"] = coords
    return adata


def _make_transform_and_slices():
    rng = np.random.default_rng(0)
    slice0 = _make_slice(rng)
    slice1 = _make_slice(rng, rotation_deg=20, translation=(5.0, -3.0))
    landmarks = calc_landmarks([slice0, slice1], "cluster")
    transform = calc_alignment_transform(landmarks, reference=0)
    return transform, [slice0, slice1]


def _make_transform():
    transform, _ = _make_transform_and_slices()
    return transform


def test_plot_alignment_returns_figure_with_two_axes():
    transform = _make_transform()

    fig, (ax_before, ax_after) = plot_alignment(transform)

    assert isinstance(fig, plt.Figure)
    assert ax_before is not ax_after
    plt.close(fig)


def test_plot_alignment_by_label_uses_one_series_per_landmark():
    transform = _make_transform()

    fig, (_, ax_after) = plot_alignment(transform, color_by="label")

    # One scatter series (PathCollection) per distinct landmark label.
    assert len(ax_after.collections) == len(_CENTERS)
    plt.close(fig)


def test_plot_alignment_rejects_unknown_color_by():
    transform = _make_transform()

    with pytest.raises(ValueError, match="color_by"):
        plot_alignment(transform, color_by="not_a_mode")


def test_transform_plot_method_delegates_to_plot_alignment():
    transform = _make_transform()

    fig, axes = transform.plot()

    assert isinstance(fig, plt.Figure)
    assert len(axes) == 2
    plt.close(fig)


def test_plot_alignment_overlays_cell_centroids_when_adatas_given():
    transform, slices = _make_transform_and_slices()

    # color_by="label" gives one landmark collection per label; cells add one
    # more collection per slice, drawn first (underneath).
    fig, (ax_before, ax_after) = plot_alignment(transform, adatas=slices, color_by="label")

    assert len(ax_after.collections) == len(slices) + len(_CENTERS)
    assert len(ax_before.collections) == len(slices) + len(_CENTERS)
    plt.close(fig)


def test_plot_alignment_landmarks_only_when_no_adatas():
    transform = _make_transform()

    fig, (_, ax_after) = plot_alignment(transform, color_by="label")

    # No adatas -> no cell-centroid collections, only the landmark ones.
    assert len(ax_after.collections) == len(_CENTERS)
    plt.close(fig)


def test_plot_alignment_subsamples_cells():
    transform, slices = _make_transform_and_slices()

    # The cell-centroid collections (drawn first) are capped at
    # max_cells_per_slice.
    fig, (_, ax_after) = plot_alignment(
        transform, adatas=slices, color_by="label", max_cells_per_slice=5
    )

    cell_collections = ax_after.collections[: len(slices)]
    for collection in cell_collections:
        assert collection.get_offsets().shape[0] <= 5
    plt.close(fig)
