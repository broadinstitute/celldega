import pandas as pd
import pytest

from celldega.nbhd import df_to_anndata, gdf_from_contour_coords


def test_gdf_from_contour_coords_builds_polygons():
    df_contours = pd.DataFrame(
        {
            "cell_id": [1, 1, 1, 1, 2, 2, 2],
            "vertex_x": [0, 10, 10, 0, 20, 30, 25],
            "vertex_y": [0, 0, 10, 10, 0, 0, 10],
        }
    )

    gdf = gdf_from_contour_coords(df_contours)

    assert list(gdf["cell_id"]) == [1, 2]
    assert list(gdf.geometry.area) == [100.0, 50.0]
    assert {"center_x", "center_y"}.issubset(gdf.columns)


def test_gdf_from_contour_coords_custom_columns():
    df_contours = pd.DataFrame(
        {
            "id": ["a", "a", "a"],
            "x": [0, 4, 2],
            "y": [0, 0, 4],
        }
    )

    gdf = gdf_from_contour_coords(df_contours, id_col="id", x_col="x", y_col="y")

    assert list(gdf["id"]) == ["a"]
    assert gdf.geometry.iloc[0].area == pytest.approx(8.0)


def test_gdf_from_contour_coords_malformed_group_becomes_empty_geometry():
    # a group with only 2 vertices can't form a polygon
    df_contours = pd.DataFrame(
        {
            "cell_id": [1, 1, 2, 2, 2],
            "vertex_x": [0, 1, 0, 4, 2],
            "vertex_y": [0, 1, 0, 0, 4],
        }
    )

    gdf = gdf_from_contour_coords(df_contours)

    assert gdf.set_index("cell_id").loc[1, "geometry"].is_empty
    assert not gdf.set_index("cell_id").loc[2, "geometry"].is_empty


def test_df_to_anndata_wraps_matrix_without_extra_computation():
    df = pd.DataFrame(
        [[1, 2], [3, 4]],
        index=["nbhd_1", "nbhd_2"],
        columns=["GeneA", "GeneB"],
    )

    adata = df_to_anndata(df)

    assert list(adata.obs_names) == ["nbhd_1", "nbhd_2"]
    assert list(adata.var_names) == ["GeneA", "GeneB"]
    assert adata.X.tolist() == [[1, 2], [3, 4]]
    assert "X_pca" not in adata.obsm
    assert "neighbors" not in adata.uns
