import importlib.util

from anndata import AnnData
import geopandas as gpd
import numpy as np
import pandas as pd
from scipy import sparse
from shapely.geometry import Point

from celldega.collections import (
    CelldegaCollection,
    HierarchyResult,
    NeighborhoodCollection,
)
from celldega.dataset import (
    Dataset,
    calc_dataset_by_pop,
    construct_population_space,
    from_adata,
    read,
)


def test_dataset_holds_aligned_spaces_relations_and_hierarchies():
    adata = AnnData(X=np.ones((2, 1)))
    adata.obs["sample_id"] = ["sample_001", "sample_002"]
    adata.obs["condition"] = ["a", "b"]
    dataset_ids = pd.Index(["sample_001", "sample_002"])
    population = AnnData(
        X=np.array([[0.25, 0.75], [0.5, 0.5]]),
        obs=pd.DataFrame(index=dataset_ids),
        var=pd.DataFrame(index=["T cell", "B cell"]),
    )
    relation = sparse.csr_matrix([[1.0, 0.2], [0.2, 1.0]])
    hierarchy = HierarchyResult(
        id="population__hierarchical",
        input_kind="space",
        input_key="population",
        method="hierarchical",
        labels=pd.Series(["left", "right"], index=dataset_ids),
        leaf_order=list(dataset_ids),
    )

    dataset = Dataset(
        adata,
        dataset_col="sample_id",
        obs_columns=["condition"],
        spaces={"population": population},
        relations={"similarity": relation},
        hierarchies={hierarchy.id: hierarchy},
        provenance={"source": "unit-test"},
    )

    assert isinstance(dataset, CelldegaCollection)
    assert dataset.collection_type == "dataset"
    assert list(dataset.spaces["population"].obs_names) == list(dataset.obs.index)
    assert dataset.relations["similarity"].shape == (2, 2)
    assert dataset.hierarchies["population__hierarchical"].input_key == "population"
    assert dataset.neighborhood_collections == {}


def test_neighborhood_collection_holds_geometry_spaces_relations_and_memberships():
    obs = pd.DataFrame(
        {
            "sample_id": ["sample_001", "sample_001"],
            "neighborhood_type": ["manual", "manual"],
        },
        index=["sample_001::nbhd_00001", "sample_001::nbhd_00002"],
    )
    geometry = gpd.GeoDataFrame(
        {"area_um2": [10.0, 12.0]},
        geometry=[Point(0, 0), Point(1, 1)],
        index=obs.index,
    )
    gene = AnnData(
        X=np.array([[1, 0, 3], [0, 2, 4]]),
        obs=pd.DataFrame(index=obs.index),
        var=pd.DataFrame(index=["GeneA", "GeneB", "GeneC"]),
    )
    bordering = sparse.csr_matrix([[0.0, 1.0], [1.0, 0.0]])
    cell_membership = sparse.csr_matrix([[1.0, 0.0], [0.0, 1.0], [0.0, 1.0]])

    collection = NeighborhoodCollection(
        obs=obs,
        geometry=geometry,
        spaces={"gene": gene},
        relations={"bordering": bordering},
        memberships={"cell_to_neighborhood": cell_membership},
    )

    assert collection.collection_type == "neighborhood"
    assert list(collection.geometry.index) == list(obs.index)
    assert list(collection.spaces["gene"].obs_names) == list(obs.index)
    assert collection.relations["bordering"].shape == (2, 2)
    assert collection.memberships["cell_to_neighborhood"].shape == (3, 2)


def test_dataset_can_link_neighborhood_collections():
    adata = AnnData(X=np.ones((1, 1)))
    adata.obs["sample_id"] = ["sample_001"]
    neighborhood_obs = pd.DataFrame(
        {"sample_id": ["sample_001"]},
        index=["sample_001::nbhd_00001"],
    )
    neighborhoods = NeighborhoodCollection(obs=neighborhood_obs)

    dataset = Dataset(
        adata,
        dataset_col="sample_id",
        neighborhood_collections={"manual_regions": neighborhoods},
    )

    assert dataset.neighborhood_collections["manual_regions"] is neighborhoods


def test_calc_dataset_by_pop_builds_dataset_population_space():
    adata = AnnData(X=np.ones((6, 1)))
    adata.obs["sample_id"] = ["s1", "s1", "s1", "s2", "s2", "s2"]
    adata.obs["cell_type"] = ["T", "B", "T", "B", "B", "T"]

    population = calc_dataset_by_pop(
        adata,
        dataset_col="sample_id",
        category="cell_type",
        output="counts",
    )

    assert population.shape == (2, 2)
    assert list(population.obs_names) == ["s1", "s2"]
    assert list(population.var_names) == ["B", "T"]
    np.testing.assert_array_equal(population.X, np.array([[1, 2], [2, 1]]))


def test_from_adata_attaches_population_space():
    adata = AnnData(X=np.ones((4, 1)))
    adata.obs["sample_id"] = ["s1", "s1", "s2", "s2"]
    adata.obs["patient_id"] = ["p1", "p1", "p2", "p2"]
    adata.obs["cell_type"] = ["T", "B", "B", "B"]

    dataset = from_adata(
        adata,
        dataset_col="sample_id",
        obs_columns=["patient_id"],
        population_category="cell_type",
    )

    assert isinstance(dataset, Dataset)
    assert list(dataset.obs.index) == ["s1", "s2"]
    assert dataset.obs.loc["s1", "patient_id"] == "p1"
    assert "population" in dataset.spaces
    assert list(dataset.spaces["population"].obs_names) == ["s1", "s2"]


def test_construct_population_space_attaches_to_existing_dataset_collection():
    adata = AnnData(X=np.ones((4, 1)))
    adata.obs["sample_id"] = ["s1", "s1", "s2", "s2"]
    adata.obs["cell_type"] = ["T", "B", "B", "B"]
    dataset = from_adata(adata, dataset_col="sample_id")

    population = construct_population_space(
        dataset,
        adata,
        category="cell_type",
        output="counts",
    )

    assert dataset.spaces["population"] is population
    assert list(population.obs_names) == ["s1", "s2"]
    np.testing.assert_array_equal(population.X, np.array([[1, 1], [2, 0]]))


def test_dataset_helper_constructs_population_space():
    adata = AnnData(X=np.ones((4, 1)))
    adata.obs["sample_id"] = ["s1", "s1", "s2", "s2"]
    adata.obs["condition"] = ["a", "a", "b", "b"]
    adata.obs["cell_type"] = ["T", "B", "B", "B"]

    dataset = Dataset(adata, dataset_col="sample_id", obs_columns=["condition"])
    population = dataset.construct_population_space(category="cell_type", output="counts")

    assert dataset.obs.loc["s1", "condition"] == "a"
    assert dataset.spaces["population"] is population
    assert list(population.obs_names) == ["s1", "s2"]


def test_dataset_write_read_round_trips_spaces(tmp_path):
    adata = AnnData(X=np.ones((4, 1)))
    adata.obs["sample_id"] = ["s1", "s1", "s2", "s2"]
    adata.obs["condition"] = ["a", "a", "b", "b"]
    adata.obs["cell_type"] = ["T", "B", "B", "B"]

    dataset = Dataset(adata, dataset_col="sample_id", obs_columns=["condition"])
    dataset.construct_population_space(category="cell_type", output="counts")
    dataset.relations["similarity"] = sparse.csr_matrix([[1.0, 0.2], [0.2, 1.0]])
    dataset.hierarchies["population__manual"] = HierarchyResult(
        id="population__manual",
        input_kind="space",
        input_key="population",
        method="manual",
        labels=pd.Series(["left", "right"], index=["s1", "s2"]),
        leaf_order=["s1", "s2"],
    )
    path = tmp_path / "dataset.h5ad"

    dataset.write(path)
    loaded = read(path)

    assert isinstance(loaded, Dataset)
    assert list(loaded.obs.index) == ["s1", "s2"]
    assert loaded.obs.loc["s2", "condition"] == "b"
    assert list(loaded.spaces) == ["population"]
    assert loaded.relations["similarity"].shape == (2, 2)
    assert loaded.hierarchies["population__manual"].input_key == "population"
    np.testing.assert_array_equal(loaded.spaces["population"].X, np.array([[1, 1], [2, 0]]))


def test_dataset_methods_are_not_exposed_at_package_root():
    import celldega as dega

    assert hasattr(dega, "dataset")
    assert not hasattr(dega, "calc_dataset_by_pop")
    assert not hasattr(dega, "from_adata")
    assert not hasattr(dega, "DatasetCollection")
    assert importlib.util.find_spec("celldega.datasets") is None
