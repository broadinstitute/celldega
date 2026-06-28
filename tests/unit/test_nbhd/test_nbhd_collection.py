from anndata import AnnData
import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import Polygon

from celldega.nbhd import NeighborhoodCollection


def _synthetic_nbhd_inputs():
    gdf = gpd.GeoDataFrame(
        {
            "name": ["A", "B"],
            "cat": ["region_a", "region_b"],
            "geometry": [
                Polygon([(0, 0), (0, 10), (10, 10), (10, 0)]),
                Polygon([(10, 0), (10, 10), (20, 10), (20, 0)]),
            ],
        }
    )

    adata = AnnData(
        X=np.array(
            [
                [1.0, 0.0],
                [0.0, 2.0],
                [3.0, 1.0],
            ]
        ),
        obs=pd.DataFrame(
            {"leiden": ["T", "B", "T"]},
            index=["cell_1", "cell_2", "cell_3"],
        ),
        var=pd.DataFrame(index=["GeneA", "GeneB"]),
    )
    adata.obsm["spatial"] = np.array([[1, 1], [2, 2], [11, 1]])

    return gdf, adata


def test_neighborhood_collection_builds_from_geometry():
    gdf, _adata = _synthetic_nbhd_inputs()

    collection = NeighborhoodCollection(gdf=gdf, nbhd_type="manual")

    assert list(collection.obs.index) == ["A", "B"]
    assert list(collection.geometry.index) == ["A", "B"]
    assert collection.geometry is collection.gdf
    assert collection.obs.loc["A", "neighborhood_type"] == "manual"
    assert not hasattr(collection, "adata")
    assert not hasattr(collection, "to_collection")


def test_neighborhood_collection_calculates_population_modality_directly():
    gdf, adata = _synthetic_nbhd_inputs()
    collection = NeighborhoodCollection(gdf=gdf, nbhd_type="manual")

    result = collection.calc_population(
        adata,
        modality_name="cell_type_population",
        min_cells=1,
        output="counts",
    )
    population = collection.mod["cell_type_population"]

    assert result is None
    assert collection.mod["cell_type_population"] is population
    assert collection.nbhd_type == "manual"
    assert not hasattr(collection, "adata")
    assert list(population.obs_names) == ["A", "B"]
    assert list(population.var["entity_type"]) == [
        "cell_population",
        "cell_population",
    ]
    np.testing.assert_array_equal(population.X, np.array([[1, 1], [0, 1]]))
    assert not hasattr(collection, "construct_population_space")


def test_neighborhood_collection_calculates_gene_modality_directly():
    gdf, adata = _synthetic_nbhd_inputs()
    collection = NeighborhoodCollection(gdf=gdf, nbhd_type="manual")

    result = collection.calc_signature(
        adata=adata,
        modality_name="expression",
        min_cells=1,
    )
    expression = collection.mod["expression"]

    assert result is None
    assert collection.mod["expression"] is expression
    assert list(expression.obs_names) == ["A", "B"]
    assert list(expression.var["entity_type"]) == ["gene", "gene"]
    np.testing.assert_allclose(expression.X, np.array([[0.5, 1.0], [3.0, 1.0]]))


def test_neighborhood_collection_min_cells_filters_collection_axis():
    gdf, adata = _synthetic_nbhd_inputs()
    collection = NeighborhoodCollection(gdf=gdf, nbhd_type="manual")

    result = collection.calc_population(adata, min_cells=2, output="counts")
    population = collection.mod["population"]

    assert result is None
    assert list(collection.obs.index) == ["A"]
    assert list(collection.gdf.index) == ["A"]
    assert list(collection.geometry.index) == ["A"]
    assert list(population.obs_names) == ["A"]
    np.testing.assert_array_equal(population.X, np.array([[1, 1]]))


def test_neighborhood_collection_keeps_axis_when_drop_missing_false():
    gdf, adata = _synthetic_nbhd_inputs()
    collection = NeighborhoodCollection(gdf=gdf, nbhd_type="manual")

    result = collection.calc_population(
        adata,
        min_cells=2,
        output="counts",
        drop_missing=False,
    )
    population = collection.mod["population"]

    assert result is None
    assert list(collection.obs.index) == ["A", "B"]
    assert list(collection.gdf.index) == ["A", "B"]
    assert list(population.obs_names) == ["A", "B"]
    np.testing.assert_array_equal(population.X, np.array([[1, 1], [0, 0]]))


def test_neighborhood_collection_min_cells_subsets_existing_modalities():
    gdf, adata = _synthetic_nbhd_inputs()
    collection = NeighborhoodCollection(gdf=gdf, nbhd_type="manual")

    collection.calc_signature(adata=adata, modality_name="gene", min_cells=1, drop_missing=False)
    result = collection.calc_population(adata, min_cells=2, output="counts")

    assert result is None
    assert list(collection.obs.index) == ["A"]
    assert list(collection.gdf.index) == ["A"]
    assert list(collection.mod["gene"].obs_names) == ["A"]
    assert list(collection.mod["population"].obs_names) == ["A"]
    np.testing.assert_array_equal(collection.mod["population"].X, np.array([[1, 1]]))


def test_neighborhood_collection_calculates_bordering_relation():
    gdf, _adata = _synthetic_nbhd_inputs()
    collection = NeighborhoodCollection(gdf=gdf, nbhd_type="manual")

    bordering = collection.calc_bordering(metric="binary")

    assert collection.relations["bordering"] is bordering
    assert bordering.shape == (2, 2)
    assert bordering[0, 1] == 1


def test_neighborhood_collection_transforms_geometry_to_pixel_space():
    gdf, _adata = _synthetic_nbhd_inputs()
    matrix = np.array([[0.5, 0.0, 10.0], [0.0, 0.5, 20.0], [0.0, 0.0, 1.0]])

    collection = NeighborhoodCollection(gdf=gdf, nbhd_type="manual", transformation_matrix=matrix)
    viz = collection.to_pixel_gdf()

    # micron geometry is preserved; pixel geometry is added for visualization
    assert "geometry_pixel" in viz.columns
    assert viz.geometry.iloc[0].equals(gdf.geometry.iloc[0])
    # square A spans micron (0,0)-(10,10) -> pixel (10,20)-(15,25) under this affine
    minx, miny, maxx, maxy = viz["geometry_pixel"].iloc[0].bounds
    assert (minx, miny, maxx, maxy) == (10.0, 20.0, 15.0, 25.0)


def test_neighborhood_collection_transcript_assignment(tmp_path):
    gdf, _adata = _synthetic_nbhd_inputs()
    # A (x 0-10): 3 total, 1 unassigned -> 2/3; B (x 10-20): 2 total, 2 unassigned -> 0.0
    trx = pd.DataFrame(
        {
            "feature_name": ["g"] * 5,
            "x_location": [1, 2, 3, 11, 12],
            "y_location": [1, 2, 3, 1, 2],
            "cell_id": ["c1", "c2", "UNASSIGNED", "UNASSIGNED", "UNASSIGNED"],
        }
    )
    trx.to_parquet(tmp_path / "transcripts.parquet")

    collection = NeighborhoodCollection(gdf=gdf, nbhd_type="manual")
    result = collection.calc_transcript_assignment(data_dir=str(tmp_path))

    assert result is None
    obs = collection.obs
    assert list(obs["total_transcripts"]) == [3, 2]
    assert list(obs["unassigned_transcripts"]) == [1, 2]
    assert np.isclose(obs["transcript_assignment_proportion"].loc["A"], 2 / 3)
    assert obs["transcript_assignment_proportion"].loc["B"] == 0.0


def test_transcript_assignment_warns_when_no_unassigned_sentinel(tmp_path):
    gdf, _adata = _synthetic_nbhd_inputs()
    # cell_id present but no "UNASSIGNED" sentinel -> warns (may be fully assigned)
    trx = pd.DataFrame(
        {
            "feature_name": ["g"] * 3,
            "x_location": [1, 2, 3],
            "y_location": [1, 2, 3],
            "cell_id": ["c1", "c2", "c3"],
        }
    )
    trx.to_parquet(tmp_path / "transcripts.parquet")

    collection = NeighborhoodCollection(gdf=gdf, nbhd_type="manual")
    with pytest.warns(UserWarning, match="UNASSIGNED"):
        collection.calc_transcript_assignment(data_dir=str(tmp_path))

    # still computes: A has 3 transcripts, all assigned -> proportion 1.0
    assert collection.obs["transcript_assignment_proportion"].loc["A"] == 1.0
    assert collection.obs["unassigned_transcripts"].loc["A"] == 0


def test_transformation_matrix_round_trips_through_uns():
    gdf, _adata = _synthetic_nbhd_inputs()
    matrix = np.array([[0.5, 0.0, 10.0], [0.0, 0.5, 20.0], [0.0, 0.0, 1.0]])

    collection = NeighborhoodCollection(gdf=gdf, nbhd_type="manual")
    collection.set_transformation_matrix(matrix)
    assert "transformation_matrix" in collection.uns

    restored = NeighborhoodCollection(mdata=collection.mdata)
    np.testing.assert_array_equal(restored.transformation_matrix, matrix)
