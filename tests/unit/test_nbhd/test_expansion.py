import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import Polygon

from celldega.nbhd import NeighborhoodCollection
from celldega.nbhd.expansion import _calc_expansion


def _synthetic_nucleus_cell_inputs():
    # cell 1: 10x10 square at origin; nucleus 1: centered 2x2 square (area 4)
    # cell 2: 10x10 square offset far away; nucleus 2: centered 2x2 square (area 4)
    gdf_nuclei = gpd.GeoDataFrame(
        {
            "cell_id": ["c1", "c2"],
            "geometry": [
                Polygon([(4, 4), (6, 4), (6, 6), (4, 6)]),
                Polygon([(24, 24), (26, 24), (26, 26), (24, 26)]),
            ],
        }
    )
    gdf_cells = gpd.GeoDataFrame(
        {
            "cell_id": ["c1", "c2"],
            "geometry": [
                Polygon([(0, 0), (10, 0), (10, 10), (0, 10)]),
                Polygon([(20, 20), (30, 20), (30, 30), (20, 30)]),
            ],
        }
    )
    return gdf_nuclei, gdf_cells


def test_calc_expansion_grows_and_clips_to_bound():
    gdf_nuclei, gdf_cells = _synthetic_nucleus_cell_inputs()

    series = _calc_expansion(gdf_nuclei, gdf_cells, radii_um=[0, 1, 5], id_col="cell_id")

    assert list(series.keys()) == [0.0, 1.0, 5.0]

    # radius 0: original 2x2 source polygon, area 4
    gdf_0 = series[0.0]
    assert set(gdf_0["cell_id"]) == {"c1", "c2"}
    np.testing.assert_allclose(sorted(gdf_0["area_um2"]), [4.0, 4.0])

    # radius 1: buffered 1 unit on each side -> 4x4 square, area 16, still inside the bound
    gdf_1 = series[1.0]
    np.testing.assert_allclose(sorted(gdf_1["area_um2"]), [16.0, 16.0])

    # radius 5: buffer would overshoot the bound -> clipped to the full 10x10 bound
    gdf_5 = series[5.0]
    np.testing.assert_allclose(sorted(gdf_5["area_um2"]), [100.0, 100.0])


def test_calc_expansion_scale_um_per_pixel_converts_pixel_space_geometry():
    gdf_nuclei, gdf_cells = _synthetic_nucleus_cell_inputs()
    high_res_scale = 2.0  # pixels per micron, e.g. a notebook's own scale variable
    scale_um_per_pixel = 1.0 / high_res_scale  # microns per pixel -- what calc_expansion wants

    result = _calc_expansion(
        gdf_nuclei,
        gdf_cells,
        radii_um=[1],
        id_col="cell_id",
        scale_um_per_pixel=scale_um_per_pixel,
    )

    # matches `buffer_dist = expand_um * high_res_scale`: a 2x2 nucleus buffered by
    # 1um * 2px/um = 2px on each side -> 6x6 = 36 px^2, well inside the 10x10 bound
    gdf_1 = result[1.0]
    np.testing.assert_allclose(sorted(gdf_1["area_px2"]), [36.0, 36.0])
    # area_um2 = area_px2 * scale_um_per_pixel**2 = 36 * 0.25 = 9
    np.testing.assert_allclose(sorted(gdf_1["area_um2"]), [9.0, 9.0])


def test_calc_expansion_default_scale_treats_geometry_as_microns():
    gdf_nuclei, gdf_cells = _synthetic_nucleus_cell_inputs()

    result = _calc_expansion(gdf_nuclei, gdf_cells, radii_um=[1], id_col="cell_id")

    # no conversion: a 2x2 nucleus buffered by 1um -> 4x4 = 16 um^2
    gdf_1 = result[1.0]
    np.testing.assert_allclose(sorted(gdf_1["area_um2"]), [16.0, 16.0])


def test_calc_expansion_resolves_scale_from_technology():
    gdf_nuclei, gdf_cells = _synthetic_nucleus_cell_inputs()

    result = _calc_expansion(
        gdf_nuclei, gdf_cells, radii_um=[1], id_col="cell_id", technology="Xenium"
    )
    expected = _calc_expansion(
        gdf_nuclei, gdf_cells, radii_um=[1], id_col="cell_id", scale_um_per_pixel=0.2125
    )
    pd.testing.assert_frame_equal(
        result[1.0].drop(columns="color"), expected[1.0].drop(columns="color")
    )


def test_neighborhood_collection_calc_expansion_accepts_scale_um_per_pixel():
    gdf_nuclei, gdf_cells = _synthetic_nucleus_cell_inputs()
    nbhd_nuclei = NeighborhoodCollection(gdf=gdf_nuclei, nbhd_type="nucleus", nbhd_col="cell_id")

    series = nbhd_nuclei.calc_expansion(gdf_cells, radii_um=[1], scale_um_per_pixel=0.5)

    np.testing.assert_allclose(sorted(series[1.0].gdf["area_px2"]), [36.0, 36.0])


def test_calc_expansion_works_for_non_nucleus_entities():
    # Demonstrates this isn't nucleus/cell-specific: any pair of per-entity
    # source/bound geometries with a shared id column works, e.g. a small "core"
    # region expanding into a larger parent "zone".
    gdf_core = gpd.GeoDataFrame(
        {
            "region_id": ["r1", "r2"],
            "geometry": [
                Polygon([(1, 1), (2, 1), (2, 2), (1, 2)]),
                Polygon([(11, 1), (12, 1), (12, 2), (11, 2)]),
            ],
        }
    )
    gdf_zone = gpd.GeoDataFrame(
        {
            "region_id": ["r1", "r2"],
            "geometry": [
                Polygon([(0, 0), (5, 0), (5, 5), (0, 5)]),
                Polygon([(10, 0), (15, 0), (15, 5), (10, 5)]),
            ],
        }
    )

    series = _calc_expansion(gdf_core, gdf_zone, radii_um=[0, 10], id_col="region_id")

    assert list(series.keys()) == [0.0, 10.0]
    assert set(series[0.0]["region_id"]) == {"r1", "r2"}
    # radius 10 overshoots every zone -> clipped to each 5x5 zone, area 25
    np.testing.assert_allclose(sorted(series[10.0]["area_um2"]), [25.0, 25.0])


def test_calc_expansion_add_colors():
    gdf_nuclei, gdf_cells = _synthetic_nucleus_cell_inputs()

    with_colors = _calc_expansion(gdf_nuclei, gdf_cells, radii_um=[0, 1, 2], id_col="cell_id")
    assert all("color" in gdf.columns for gdf in with_colors.values())
    # one shade per radius, shared across entities within that radius
    assert with_colors[0.0]["color"].nunique() == 1
    assert len({gdf["color"].iloc[0] for gdf in with_colors.values()}) == 3

    without_colors = _calc_expansion(
        gdf_nuclei, gdf_cells, radii_um=[0, 1], id_col="cell_id", add_colors=False
    )
    assert all("color" not in gdf.columns for gdf in without_colors.values())


def test_calc_expansion_raises_on_duplicate_ids():
    gdf_nuclei, gdf_cells = _synthetic_nucleus_cell_inputs()
    gdf_cells_dup = pd.concat([gdf_cells, gdf_cells.iloc[[0]]], ignore_index=True)
    gdf_cells_dup = gpd.GeoDataFrame(gdf_cells_dup, geometry="geometry")

    with pytest.raises(ValueError, match="duplicate"):
        _calc_expansion(gdf_nuclei, gdf_cells_dup, radii_um=[0, 1], id_col="cell_id")


def test_calc_expansion_raises_on_missing_bound_match():
    gdf_nuclei, gdf_cells = _synthetic_nucleus_cell_inputs()
    gdf_cells_missing = gdf_cells.iloc[[0]].reset_index(drop=True)

    with pytest.raises(ValueError, match="no matching row"):
        _calc_expansion(gdf_nuclei, gdf_cells_missing, radii_um=[0, 1], id_col="cell_id")


def test_neighborhood_collection_calc_expansion_returns_series():
    gdf_nuclei, gdf_cells = _synthetic_nucleus_cell_inputs()
    nbhd_nuclei = NeighborhoodCollection(gdf=gdf_nuclei, nbhd_type="nucleus", nbhd_col="cell_id")

    series = nbhd_nuclei.calc_expansion(gdf_cells, radii_um=[0, 1, 5])

    assert list(series.keys()) == [0.0, 1.0, 5.0]
    for nbhd in series.values():
        assert isinstance(nbhd, NeighborhoodCollection)
        assert nbhd.nbhd_col == "cell_id"
        assert set(nbhd.obs.index) == {"c1", "c2"}
        assert nbhd.nbhd_type == "expansion"


def test_calc_signature_cell_free_accepts_custom_columns_across_radii(tmp_path):
    gdf_nuclei, gdf_cells = _synthetic_nucleus_cell_inputs()
    nbhd_nuclei = NeighborhoodCollection(gdf=gdf_nuclei, nbhd_type="nucleus", nbhd_col="cell_id")
    series = nbhd_nuclei.calc_expansion(gdf_cells, radii_um=[0, 5])

    # Custom transcript format: "name" for gene, arbitrary x/y columns --
    # exercises the feature_col/x_col/y_col overrides end to end.
    pd.DataFrame(
        {
            "name": ["GeneA", "GeneB", "GeneA"],
            "x": [5, 1, 25],
            "y": [5, 1, 25],
        }
    ).to_parquet(tmp_path / "transcripts.parquet")

    nbhd_r0 = series[0.0]
    nbhd_r0.calc_signature(
        by="cell-free",
        data_dir=str(tmp_path),
        feature_col="name",
        x_col="x",
        y_col="y",
        drop_missing=False,
    )
    modality_r0 = nbhd_r0.mod["gene_cell_free"]
    df_r0 = pd.DataFrame(modality_r0.X, index=modality_r0.obs_names, columns=modality_r0.var_names)
    # at radius 0 the source polygon doesn't reach (1, 1); only the point inside it counts
    # ("GeneB" never falls inside any neighborhood at this radius, so it has no column)
    assert df_r0.loc["c1", "GeneA"] == 1
    assert "GeneB" not in df_r0.columns
    assert df_r0.loc["c2", "GeneA"] == 1

    nbhd_r5 = series[5.0]
    nbhd_r5.calc_signature(
        by="cell-free",
        data_dir=str(tmp_path),
        feature_col="name",
        x_col="x",
        y_col="y",
        drop_missing=False,
    )
    modality_r5 = nbhd_r5.mod["gene_cell_free"]
    df_r5 = pd.DataFrame(modality_r5.X, index=modality_r5.obs_names, columns=modality_r5.var_names)
    # at radius 5 the source polygon has expanded to the full bound, now capturing (1, 1) too
    assert df_r5.loc["c1", "GeneA"] == 1
    assert df_r5.loc["c1", "GeneB"] == 1


def test_calc_signature_cell_free_requires_data_dir():
    gdf_nuclei, _gdf_cells = _synthetic_nucleus_cell_inputs()
    nbhd = NeighborhoodCollection(gdf=gdf_nuclei, nbhd_type="nucleus", nbhd_col="cell_id")

    with pytest.raises(ValueError, match="data_dir is required"):
        nbhd.calc_signature(by="cell-free")


def test_calc_signature_cell_free_streams_from_data_dir_across_radii(tmp_path):
    gdf_nuclei, gdf_cells = _synthetic_nucleus_cell_inputs()
    nbhd_nuclei = NeighborhoodCollection(gdf=gdf_nuclei, nbhd_type="nucleus", nbhd_col="cell_id")
    series = nbhd_nuclei.calc_expansion(gdf_cells, radii_um=[0, 5])

    # data_dir's cell-free path is now backed by the streaming engine internally,
    # using the Xenium transcripts.parquet convention.
    pd.DataFrame(
        {
            "feature_name": ["GeneA", "GeneB", "GeneA"],
            "x_location": [5, 1, 25],
            "y_location": [5, 1, 25],
        }
    ).to_parquet(tmp_path / "transcripts.parquet")

    nbhd_r0 = series[0.0]
    nbhd_r0.calc_signature(by="cell-free", data_dir=str(tmp_path), drop_missing=False)
    df_r0 = pd.DataFrame(
        nbhd_r0.mod["gene_cell_free"].X,
        index=nbhd_r0.mod["gene_cell_free"].obs_names,
        columns=nbhd_r0.mod["gene_cell_free"].var_names,
    )
    assert df_r0.loc["c1", "GeneA"] == 1
    assert "GeneB" not in df_r0.columns

    nbhd_r5 = series[5.0]
    nbhd_r5.calc_signature(by="cell-free", data_dir=str(tmp_path), drop_missing=False)
    df_r5 = pd.DataFrame(
        nbhd_r5.mod["gene_cell_free"].X,
        index=nbhd_r5.mod["gene_cell_free"].obs_names,
        columns=nbhd_r5.mod["gene_cell_free"].var_names,
    )
    assert df_r5.loc["c1", "GeneA"] == 1
    assert df_r5.loc["c1", "GeneB"] == 1


def test_calc_signature_cell_free_data_dir_accepts_custom_columns(tmp_path):
    gdf_nuclei, gdf_cells = _synthetic_nucleus_cell_inputs()
    nbhd_nuclei = NeighborhoodCollection(gdf=gdf_nuclei, nbhd_type="nucleus", nbhd_col="cell_id")
    series = nbhd_nuclei.calc_expansion(gdf_cells, radii_um=[5])

    # non-Xenium transcripts.parquet: "name"/"x"/"y" instead of
    # "feature_name"/"x_location"/"y_location"
    pd.DataFrame(
        {
            "name": ["GeneA", "GeneB", "GeneA"],
            "x": [5, 1, 25],
            "y": [5, 1, 25],
        }
    ).to_parquet(tmp_path / "transcripts.parquet")

    nbhd_r5 = series[5.0]
    nbhd_r5.calc_signature(
        by="cell-free",
        data_dir=str(tmp_path),
        feature_col="name",
        x_col="x",
        y_col="y",
        drop_missing=False,
    )
    df_r5_custom = pd.DataFrame(
        nbhd_r5.mod["gene_cell_free"].X,
        index=nbhd_r5.mod["gene_cell_free"].obs_names,
        columns=nbhd_r5.mod["gene_cell_free"].var_names,
    )
    assert df_r5_custom.loc["c1", "GeneA"] == 1
    assert df_r5_custom.loc["c1", "GeneB"] == 1
    assert df_r5_custom.loc["c2", "GeneA"] == 1
