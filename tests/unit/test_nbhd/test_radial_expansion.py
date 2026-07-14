import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import Point, Polygon

from celldega.nbhd import NeighborhoodCollection
from celldega.nbhd.radial_expansion import _calc_radial_expansion


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


def test_calc_radial_expansion_grows_and_clips_to_bound():
    gdf_nuclei, gdf_cells = _synthetic_nucleus_cell_inputs()

    series = _calc_radial_expansion(gdf_nuclei, gdf_cells, radii_um=[0, 1, 5], id_col="cell_id")

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


def test_calc_radial_expansion_pixels_per_micron_matches_scale_um_per_pixel():
    gdf_nuclei, gdf_cells = _synthetic_nucleus_cell_inputs()
    high_res_scale = 2.0  # pixels per micron, e.g. a notebook's own scale variable
    scaling_factor = 1.0 / high_res_scale  # microns per pixel

    via_pixels_per_micron = _calc_radial_expansion(
        gdf_nuclei,
        gdf_cells,
        radii_um=[1],
        id_col="cell_id",
        is_pixel_space=True,
        pixels_per_micron=high_res_scale,
    )
    via_scale_um_per_pixel = _calc_radial_expansion(
        gdf_nuclei,
        gdf_cells,
        radii_um=[1],
        id_col="cell_id",
        is_pixel_space=True,
        scale_um_per_pixel=scaling_factor,
    )

    pd.testing.assert_frame_equal(
        via_pixels_per_micron[1.0].drop(columns="color"),
        via_scale_um_per_pixel[1.0].drop(columns="color"),
    )

    # matches `buffer_dist = expand_um * high_res_scale`: a 2x2 nucleus buffered by
    # 1um * 2px/um = 2px on each side -> 6x6 = 36 px^2, well inside the 10x10 bound
    gdf_1 = via_pixels_per_micron[1.0]
    np.testing.assert_allclose(sorted(gdf_1["area_px2"]), [36.0, 36.0])
    # area_um2 = area_px2 * scale_um_per_pixel**2 = 36 * 0.25 = 9
    np.testing.assert_allclose(sorted(gdf_1["area_um2"]), [9.0, 9.0])


def test_calc_radial_expansion_scale_um_per_pixel_takes_precedence():
    gdf_nuclei, gdf_cells = _synthetic_nucleus_cell_inputs()

    result = _calc_radial_expansion(
        gdf_nuclei,
        gdf_cells,
        radii_um=[1],
        id_col="cell_id",
        is_pixel_space=True,
        scale_um_per_pixel=0.5,
        pixels_per_micron=999,  # should be ignored since scale_um_per_pixel is given
    )
    np.testing.assert_allclose(sorted(result[1.0]["area_px2"]), [36.0, 36.0])


def test_calc_radial_expansion_raises_when_pixel_space_scale_missing():
    gdf_nuclei, gdf_cells = _synthetic_nucleus_cell_inputs()

    with pytest.raises(ValueError, match="scale_um_per_pixel, pixels_per_micron, or technology"):
        _calc_radial_expansion(
            gdf_nuclei, gdf_cells, radii_um=[1], id_col="cell_id", is_pixel_space=True
        )


def test_neighborhood_collection_calc_radial_expansion_accepts_pixels_per_micron():
    gdf_nuclei, gdf_cells = _synthetic_nucleus_cell_inputs()
    nbhd_nuclei = NeighborhoodCollection(gdf=gdf_nuclei, nbhd_type="nucleus", nbhd_col="cell_id")

    series = nbhd_nuclei.calc_radial_expansion(
        gdf_cells, radii_um=[1], is_pixel_space=True, pixels_per_micron=2.0
    )

    np.testing.assert_allclose(sorted(series[1.0].gdf["area_px2"]), [36.0, 36.0])


def test_calc_radial_expansion_works_for_non_nucleus_entities():
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

    series = _calc_radial_expansion(gdf_core, gdf_zone, radii_um=[0, 10], id_col="region_id")

    assert list(series.keys()) == [0.0, 10.0]
    assert set(series[0.0]["region_id"]) == {"r1", "r2"}
    # radius 10 overshoots every zone -> clipped to each 5x5 zone, area 25
    np.testing.assert_allclose(sorted(series[10.0]["area_um2"]), [25.0, 25.0])


def test_calc_radial_expansion_add_colors():
    gdf_nuclei, gdf_cells = _synthetic_nucleus_cell_inputs()

    with_colors = _calc_radial_expansion(gdf_nuclei, gdf_cells, radii_um=[0, 1, 2], id_col="cell_id")
    assert all("color" in gdf.columns for gdf in with_colors.values())
    # one shade per radius, shared across entities within that radius
    assert with_colors[0.0]["color"].nunique() == 1
    assert len({gdf["color"].iloc[0] for gdf in with_colors.values()}) == 3

    without_colors = _calc_radial_expansion(
        gdf_nuclei, gdf_cells, radii_um=[0, 1], id_col="cell_id", add_colors=False
    )
    assert all("color" not in gdf.columns for gdf in without_colors.values())


def test_calc_radial_expansion_raises_on_duplicate_ids():
    gdf_nuclei, gdf_cells = _synthetic_nucleus_cell_inputs()
    gdf_cells_dup = pd.concat([gdf_cells, gdf_cells.iloc[[0]]], ignore_index=True)
    gdf_cells_dup = gpd.GeoDataFrame(gdf_cells_dup, geometry="geometry")

    with pytest.raises(ValueError, match="duplicate"):
        _calc_radial_expansion(gdf_nuclei, gdf_cells_dup, radii_um=[0, 1], id_col="cell_id")


def test_calc_radial_expansion_raises_on_missing_bound_match():
    gdf_nuclei, gdf_cells = _synthetic_nucleus_cell_inputs()
    gdf_cells_missing = gdf_cells.iloc[[0]].reset_index(drop=True)

    with pytest.raises(ValueError, match="no matching row"):
        _calc_radial_expansion(gdf_nuclei, gdf_cells_missing, radii_um=[0, 1], id_col="cell_id")


def test_neighborhood_collection_calc_radial_expansion_returns_series():
    gdf_nuclei, gdf_cells = _synthetic_nucleus_cell_inputs()
    nbhd_nuclei = NeighborhoodCollection(gdf=gdf_nuclei, nbhd_type="nucleus", nbhd_col="cell_id")

    series = nbhd_nuclei.calc_radial_expansion(gdf_cells, radii_um=[0, 1, 5])

    assert list(series.keys()) == [0.0, 1.0, 5.0]
    for nbhd in series.values():
        assert isinstance(nbhd, NeighborhoodCollection)
        assert nbhd.nbhd_col == "cell_id"
        assert set(nbhd.obs.index) == {"c1", "c2"}
        assert nbhd.nbhd_type == "radial_expansion"


def test_calc_signature_cell_free_accepts_custom_gdf_trx():
    gdf_nuclei, gdf_cells = _synthetic_nucleus_cell_inputs()
    nbhd_nuclei = NeighborhoodCollection(gdf=gdf_nuclei, nbhd_type="nucleus", nbhd_col="cell_id")
    series = nbhd_nuclei.calc_radial_expansion(gdf_cells, radii_um=[0, 5])

    # Custom transcript format: "name" for gene, arbitrary x/y columns already
    # converted to points -- exercises the feature_col override end to end.
    gdf_trx = gpd.GeoDataFrame(
        {"name": ["GeneA", "GeneB", "GeneA"]},
        geometry=[Point(5, 5), Point(1, 1), Point(25, 25)],
    )

    nbhd_r0 = series[0.0]
    nbhd_r0.calc_signature(by="cell-free", gdf_trx=gdf_trx, feature_col="name", drop_missing=False)
    modality_r0 = nbhd_r0.mod["gene_cell_free"]
    df_r0 = pd.DataFrame(modality_r0.X, index=modality_r0.obs_names, columns=modality_r0.var_names)
    # at radius 0 the source polygon doesn't reach (1, 1); only the point inside it counts
    # ("GeneB" never falls inside any neighborhood at this radius, so it has no column)
    assert df_r0.loc["c1", "GeneA"] == 1
    assert "GeneB" not in df_r0.columns
    assert df_r0.loc["c2", "GeneA"] == 1

    nbhd_r5 = series[5.0]
    nbhd_r5.calc_signature(by="cell-free", gdf_trx=gdf_trx, feature_col="name", drop_missing=False)
    modality_r5 = nbhd_r5.mod["gene_cell_free"]
    df_r5 = pd.DataFrame(modality_r5.X, index=modality_r5.obs_names, columns=modality_r5.var_names)
    # at radius 5 the source polygon has expanded to the full bound, now capturing (1, 1) too
    assert df_r5.loc["c1", "GeneA"] == 1
    assert df_r5.loc["c1", "GeneB"] == 1


def test_calc_signature_cell_free_requires_data_dir_or_gdf_trx():
    gdf_nuclei, _gdf_cells = _synthetic_nucleus_cell_inputs()
    nbhd = NeighborhoodCollection(gdf=gdf_nuclei, nbhd_type="nucleus", nbhd_col="cell_id")

    with pytest.raises(ValueError, match="data_dir, gdf_trx, or trx_parquet_path"):
        nbhd.calc_signature(by="cell-free")


def test_calc_signature_cell_free_streams_from_parquet_across_radii(tmp_path):
    gdf_nuclei, gdf_cells = _synthetic_nucleus_cell_inputs()
    nbhd_nuclei = NeighborhoodCollection(gdf=gdf_nuclei, nbhd_type="nucleus", nbhd_col="cell_id")
    series = nbhd_nuclei.calc_radial_expansion(gdf_cells, radii_um=[0, 5])

    trx_path = tmp_path / "transcripts.parquet"
    pd.DataFrame(
        {
            "x": [5, 1, 25],
            "y": [5, 1, 25],
            "name": ["GeneA", "GeneB", "GeneA"],
        }
    ).to_parquet(trx_path)

    nbhd_r0 = series[0.0]
    nbhd_r0.calc_signature(
        by="cell-free",
        trx_parquet_path=str(trx_path),
        feature_col="name",
        drop_missing=False,
    )
    df_r0 = pd.DataFrame(
        nbhd_r0.mod["gene_cell_free"].X,
        index=nbhd_r0.mod["gene_cell_free"].obs_names,
        columns=nbhd_r0.mod["gene_cell_free"].var_names,
    )
    assert df_r0.loc["c1", "GeneA"] == 1
    assert "GeneB" not in df_r0.columns

    nbhd_r5 = series[5.0]
    nbhd_r5.calc_signature(
        by="cell-free",
        trx_parquet_path=str(trx_path),
        feature_col="name",
        drop_missing=False,
    )
    df_r5 = pd.DataFrame(
        nbhd_r5.mod["gene_cell_free"].X,
        index=nbhd_r5.mod["gene_cell_free"].obs_names,
        columns=nbhd_r5.mod["gene_cell_free"].var_names,
    )
    assert df_r5.loc["c1", "GeneA"] == 1
    assert df_r5.loc["c1", "GeneB"] == 1


def test_calc_transcript_assignment_streaming_mode_computes_totals(tmp_path):
    gdf_nuclei, gdf_cells = _synthetic_nucleus_cell_inputs()
    nbhd_nuclei = NeighborhoodCollection(gdf=gdf_nuclei, nbhd_type="nucleus", nbhd_col="cell_id")
    series = nbhd_nuclei.calc_radial_expansion(gdf_cells, radii_um=[5])

    trx_path = tmp_path / "transcripts.parquet"
    pd.DataFrame(
        {
            "x": [5, 1, 25],
            "y": [5, 1, 25],
            "name": ["GeneA", "GeneB", "GeneA"],
        }
    ).to_parquet(trx_path)

    nbhd_r5 = series[5.0]
    nbhd_r5.calc_transcript_assignment(trx_parquet_path=str(trx_path), gene_col="name")

    assert nbhd_r5.obs.loc["c1", "total_transcripts"] == 2
    assert nbhd_r5.obs.loc["c2", "total_transcripts"] == 1
    assert "unassigned_transcripts" not in nbhd_r5.obs.columns


def test_calc_transcript_assignment_requires_data_dir_or_trx_parquet_path():
    gdf_nuclei, _gdf_cells = _synthetic_nucleus_cell_inputs()
    nbhd = NeighborhoodCollection(gdf=gdf_nuclei, nbhd_type="nucleus", nbhd_col="cell_id")

    with pytest.raises(ValueError, match="data_dir or trx_parquet_path"):
        nbhd.calc_transcript_assignment()
