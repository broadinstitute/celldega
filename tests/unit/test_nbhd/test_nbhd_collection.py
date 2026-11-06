from anndata import AnnData
import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import Polygon

from celldega.nbhd import (
    NeighborhoodCollection,
    calc_nbhd_bordering,
    calc_nbhd_by_gene,
    calc_nbhd_by_pop,
    calc_nbhd_overlap,
    calc_nbhd_transcript_assignment,
    read_transcripts,
)


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


def test_neighborhood_collection_is_storage_only():
    gdf, _adata = _synthetic_nbhd_inputs()
    collection = NeighborhoodCollection(gdf=gdf, nbhd_type="manual")

    methods = [name for name in dir(collection) if name.startswith("calc_")]
    assert methods == []


def test_population_function_result_is_stored_as_modality():
    gdf, adata = _synthetic_nbhd_inputs()
    collection = NeighborhoodCollection(gdf=gdf, nbhd_type="manual")

    population = calc_nbhd_by_pop(adata, collection, min_cells=1, output="counts")
    stored = collection.add_mod("cell_type_population", population)

    assert collection.mod["cell_type_population"] is stored
    assert list(stored.obs_names) == ["A", "B"]
    assert list(stored.var["entity_type"]) == ["cell_population", "cell_population"]
    np.testing.assert_array_equal(stored.X, np.array([[1, 1], [0, 1]]))


def test_gene_function_result_is_stored_as_modality():
    gdf, adata = _synthetic_nbhd_inputs()
    collection = NeighborhoodCollection(gdf=gdf, nbhd_type="manual")

    stored = collection.add_mod("expression", calc_nbhd_by_gene(collection, adata=adata))

    assert list(stored.obs_names) == ["A", "B"]
    assert list(stored.var["entity_type"]) == ["gene", "gene"]
    np.testing.assert_allclose(stored.X, np.array([[0.5, 1.0], [3.0, 1.0]]))


def test_add_mod_zero_fills_filtered_neighborhoods_and_keeps_layers():
    gdf, adata = _synthetic_nbhd_inputs()
    collection = NeighborhoodCollection(gdf=gdf, nbhd_type="manual")

    # B has only 1 cell (below min_cells=2), so the function drops it; storing
    # without subsetting zero-fills B and must keep the variance layer.
    expression = calc_nbhd_by_gene(collection, adata=adata, min_cells=2, include_variance=True)
    stored = collection.add_mod("expression", expression)

    assert list(stored.obs_names) == ["A", "B"]
    assert "variance" in stored.layers
    np.testing.assert_allclose(stored.layers["variance"][0], [0.25, 1.0])
    np.testing.assert_allclose(stored.layers["variance"][1], [0.0, 0.0])


def test_subset_drops_filtered_neighborhoods_everywhere():
    gdf, adata = _synthetic_nbhd_inputs()
    collection = NeighborhoodCollection(gdf=gdf, nbhd_type="manual")
    collection.add_mod("gene", calc_nbhd_by_gene(collection, adata=adata))
    collection.add_relation("bordering", calc_nbhd_bordering(collection, metric="binary"))

    population = calc_nbhd_by_pop(adata, collection, min_cells=2, output="counts")
    collection.subset(population.obs_names)
    collection.add_mod("population", population)

    assert list(collection.obs.index) == ["A"]
    assert list(collection.gdf.index) == ["A"]
    assert list(collection.geometry.index) == ["A"]
    assert list(collection.mod["gene"].obs_names) == ["A"]
    assert collection.relations["bordering"].shape == (1, 1)
    np.testing.assert_array_equal(collection.mod["population"].X, np.array([[1, 1]]))

    with pytest.raises(ValueError, match="missing"):
        collection.subset(["Z"])


def test_add_relation_aligns_square_results_and_checks_matrices():
    gdf, _adata = _synthetic_nbhd_inputs()
    collection = NeighborhoodCollection(gdf=gdf, nbhd_type="manual")

    bordering = collection.add_relation(
        "bordering", calc_nbhd_bordering(collection, metric="binary")
    )
    assert collection.relations["bordering"] is not None
    assert bordering.shape == (2, 2)
    assert bordering[0, 1] == 1

    overlap = calc_nbhd_overlap(collection)[["B", "A"], ["B", "A"]]  # reordered
    stored = collection.add_relation("overlap", overlap)
    np.testing.assert_allclose(stored.toarray(), np.eye(2))

    collection.add_relation("identity", np.eye(2))
    with pytest.raises(ValueError, match="shape"):
        collection.add_relation("bad", np.eye(3))


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


def test_transcript_assignment_result_joins_onto_obs(tmp_path):
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
    stats = calc_nbhd_transcript_assignment(collection, read_transcripts(str(tmp_path)))
    collection.obs = collection.obs.join(stats)

    obs = collection.obs
    assert list(obs["total_transcripts"]) == [3, 2]
    assert list(obs["unassigned_transcripts"]) == [1, 2]
    assert np.isclose(obs["transcript_assignment_proportion"].loc["A"], 2 / 3)
    assert obs["transcript_assignment_proportion"].loc["B"] == 0.0


def test_transformation_matrix_round_trips_through_uns():
    gdf, _adata = _synthetic_nbhd_inputs()
    matrix = np.array([[0.5, 0.0, 10.0], [0.0, 0.5, 20.0], [0.0, 0.0, 1.0]])

    collection = NeighborhoodCollection(gdf=gdf, nbhd_type="manual")
    collection.set_transformation_matrix(matrix)
    assert "transformation_matrix" in collection.uns

    restored = NeighborhoodCollection(mdata=collection.mdata)
    np.testing.assert_array_equal(restored.transformation_matrix, matrix)
