import sys

from anndata import AnnData
import geopandas as gpd
from mudata import MuData
import numpy as np
import pandas as pd
import pytest
from scipy import sparse
from shapely.geometry import Point

from celldega.collection import (
    CelldegaCollection,
    HierarchyResult,
)
from celldega.dataset import DatasetCollection
from celldega.nbhd import NeighborhoodCollection


def test_dataset_holds_aligned_modalities_relations_and_hierarchies():
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
        id="mod:population__hierarchical",
        input_mod="population",
        method="hierarchical",
        axis="bicluster",
        obs_leaf_order=list(dataset_ids),
        obs_linkage_matrix=np.array([[0.0, 1.0, 0.3, 2.0]]),
        var_leaf_order=["B cell", "T cell"],
        var_linkage_matrix=np.array([[0.0, 1.0, 0.5, 2.0]]),
    )

    dataset = DatasetCollection(
        adata,
        dataset_col="sample_id",
        obs_columns=["condition"],
        mod={"population": population},
        relations={"similarity": relation},
        hierarchies={hierarchy.id: hierarchy},
        provenance={"source": "unit-test"},
    )

    assert isinstance(dataset, CelldegaCollection)
    assert isinstance(dataset.mdata, MuData)
    assert dataset.collection_type == "dataset"
    assert not hasattr(dataset, "adata")
    assert list(dataset.mod["population"].obs_names) == list(dataset.obs.index)
    assert dataset.relations["similarity"].shape == (2, 2)
    assert dataset.hierarchies[hierarchy.id]["input_mod"] == "population"
    assert dataset.hierarchies[hierarchy.id]["axis"] == "bicluster"
    assert dataset.hierarchies[hierarchy.id]["var_leaf_order"] == ["B cell", "T cell"]
    np.testing.assert_array_equal(
        dataset.hierarchies[hierarchy.id]["obs_linkage"],
        np.array([[0.0, 1.0, 0.3, 2.0]]),
    )
    assert dataset.neighborhood_collections == {}


def test_neighborhood_collection_holds_geometry_modalities_relations_and_memberships():
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
        mod={"gene": gene},
        relations={"bordering": bordering},
        memberships={"cell_to_neighborhood": cell_membership},
    )

    assert collection.collection_type == "neighborhood"
    assert isinstance(collection.mdata, MuData)
    assert list(collection.geometry.index) == list(obs.index)
    assert list(collection.mod["gene"].obs_names) == list(obs.index)
    assert collection.relations["bordering"].shape == (2, 2)
    assert collection.memberships["cell_to_neighborhood"].shape == (3, 2)


def test_relation_can_be_materialized_as_clusterable_modality():
    obs = pd.DataFrame(index=pd.Index(["sample_001", "sample_002"], name="sample_id"))
    relation = sparse.csr_matrix([[1.0, 0.2], [0.2, 1.0]])
    dataset = DatasetCollection(obs=obs, relations={"similarity": relation})

    relation_mod = dataset.add_relation_modality("similarity")

    assert dataset.mod["similarity_relation"] is relation_mod
    assert relation_mod.shape == (2, 2)
    assert list(relation_mod.obs_names) == ["sample_001", "sample_002"]
    assert list(relation_mod.var_names) == ["sample_001", "sample_002"]
    assert list(relation_mod.var["entity_type"]) == ["dataset", "dataset"]
    assert relation_mod.uns["relation_key"] == "similarity"
    np.testing.assert_array_equal(relation_mod.X.toarray(), relation.toarray())


def test_dataset_can_link_neighborhood_collections():
    adata = AnnData(X=np.ones((1, 1)))
    adata.obs["sample_id"] = ["sample_001"]
    neighborhood_obs = pd.DataFrame(
        {"sample_id": ["sample_001"]},
        index=["sample_001::nbhd_00001"],
    )
    neighborhoods = NeighborhoodCollection(obs=neighborhood_obs)

    dataset = DatasetCollection(
        adata,
        dataset_col="sample_id",
        neighborhood_collections={"manual_regions": neighborhoods},
    )

    assert dataset.neighborhood_collections["manual_regions"] is neighborhoods


def test_dataset_constructor_uses_cell_adata_without_storing_it():
    adata = AnnData(X=np.ones((4, 1)))
    adata.obs["sample_id"] = ["s1", "s1", "s2", "s2"]
    adata.obs["patient_id"] = ["p1", "p1", "p2", "p2"]
    adata.obs["cell_type"] = ["T", "B", "B", "B"]

    dataset = DatasetCollection(
        adata,
        dataset_col="sample_id",
        obs_columns=["patient_id"],
    )

    assert isinstance(dataset, DatasetCollection)
    assert list(dataset.obs.index) == ["s1", "s2"]
    assert dataset.obs.loc["s1", "patient_id"] == "p1"
    assert not hasattr(dataset, "adata")


def test_calc_dataset_by_pop_attaches_population_modality():
    adata = AnnData(X=np.ones((4, 1)))
    adata.obs["sample_id"] = ["s1", "s1", "s2", "s2"]
    adata.obs["condition"] = ["a", "a", "b", "b"]
    adata.obs["cell_type"] = ["T", "B", "B", "B"]

    dataset = DatasetCollection(adata, dataset_col="sample_id", obs_columns=["condition"])
    result = dataset.calc_dataset_by_pop(adata, category="cell_type", output="counts")
    population = dataset.mod["population"]

    assert result is None
    assert dataset.obs.loc["s1", "condition"] == "a"
    assert dataset.mod["population"] is population
    assert list(population.obs_names) == ["s1", "s2"]
    assert list(population.var["entity_type"]) == ["cell_population", "cell_population"]
    np.testing.assert_array_equal(population.X, np.array([[1, 1], [2, 0]]))

    proportion_dataset = DatasetCollection(adata, dataset_col="sample_id", obs_columns=["condition"])
    assert proportion_dataset.calc_dataset_by_pop(adata, category="cell_type") is None
    population_proportion = proportion_dataset.mod["population"]
    assert population_proportion.uns["output"] == "proportion"
    np.testing.assert_allclose(population_proportion.X, np.array([[0.5, 0.5], [1.0, 0.0]]))

    named_dataset = DatasetCollection(adata, dataset_col="sample_id", obs_columns=["condition"])
    assert (
        named_dataset.calc_dataset_by_pop(
            adata,
            category="cell_type",
            modality_name="cell_type_population",
        )
        is None
    )
    assert "cell_type_population" in named_dataset.mod


def test_calc_dataset_signature_attaches_gene_modality():
    adata = AnnData(
        X=np.array(
            [
                [10, 0, 0],
                [0, 5, 5],
                [4, 0, 6],
                [0, 7, 3],
                [2, 2, 2],
                [0, 1, 1],
            ],
            dtype=float,
        ),
        var=pd.DataFrame(index=["CD3D", "GZMB", "IFNG"]),
    )
    adata.obs["sample_id"] = ["s1", "s1", "s2", "s2", "s2", "s3"]
    adata.obs["condition"] = ["a", "a", "b", "b", "b", "c"]
    adata.obs["cell_type"] = ["CD8 T", "B", "CD8 T", "CD8 T", "B", "B"]

    dataset = DatasetCollection(adata, dataset_col="sample_id", obs_columns=["condition"])
    result = dataset.calc_dataset_signature(
        adata,
        category="cell_type",
        value="CD8 T",
        modality_name="cd8_t_expression",
    )
    signature = dataset.mod["cd8_t_expression"]

    expected_counts = np.array([[10, 0, 0], [4, 7, 9]], dtype=float)
    expected = np.log1p(expected_counts / expected_counts.sum(axis=1, keepdims=True) * 1_000_000)

    assert result is None
    assert list(signature.obs_names) == ["s1", "s2", "s3"]
    assert signature.obs.loc["s1", "condition"] == "a"
    assert list(signature.obs["cell_count"]) == [1, 2, 0]
    assert list(signature.var_names) == ["CD3D", "GZMB", "IFNG"]
    assert list(signature.var["entity_type"]) == ["gene", "gene", "gene"]
    assert signature.uns["feature_type"] == "dataset_signature"
    assert signature.uns["category"] == "cell_type"
    assert signature.uns["value"] == "CD8 T"
    assert signature.uns["missing_datasets"] == "nan"
    np.testing.assert_allclose(signature.X[:2], expected)
    assert np.isnan(signature.X[2]).all()


def test_calc_dataset_signature_adds_nan_rows_when_category_value_is_absent():
    adata = AnnData(X=np.ones((3, 2)), var=pd.DataFrame(index=["GeneA", "GeneB"]))
    adata.obs["sample_id"] = ["s1", "s1", "s2"]
    adata.obs["cell_type"] = ["B", "T", "B"]

    dataset = DatasetCollection(adata, dataset_col="sample_id")

    result = dataset.calc_dataset_signature(
        adata,
        category="cell_type",
        value="CD8 T",
        modality_name="cd8_t_expression",
    )
    signature = dataset.mod["cd8_t_expression"]

    assert result is None
    assert list(signature.obs_names) == ["s1", "s2"]
    assert list(signature.obs["cell_count"]) == [0, 0]
    assert np.isnan(signature.X).all()
    assert signature.uns["available_values"] == ["B", "T"]


def test_calc_dataset_signature_can_raise_when_category_value_is_absent():
    adata = AnnData(X=np.ones((3, 2)), var=pd.DataFrame(index=["GeneA", "GeneB"]))
    adata.obs["sample_id"] = ["s1", "s1", "s2"]
    adata.obs["cell_type"] = ["B", "T", "B"]

    dataset = DatasetCollection(adata, dataset_col="sample_id")

    with pytest.raises(
        ValueError,
        match=r"No cells found where adata\.obs\['cell_type'\] == 'CD8 T'",
    ):
        dataset.calc_dataset_signature(
            adata,
            category="cell_type",
            value="CD8 T",
            modality_name="cd8_t_expression",
            missing_datasets="raise",
        )

    assert "cd8_t_expression" not in dataset.mod


def test_calc_dataset_signature_adds_nan_rows_when_no_dataset_passes_min_cells():
    adata = AnnData(X=np.ones((2, 2)), var=pd.DataFrame(index=["GeneA", "GeneB"]))
    adata.obs["sample_id"] = ["s1", "s2"]
    adata.obs["cell_type"] = ["CD8 T", "CD8 T"]

    dataset = DatasetCollection(adata, dataset_col="sample_id")

    result = dataset.calc_dataset_signature(
        adata,
        category="cell_type",
        value="CD8 T",
        modality_name="cd8_t_expression",
        min_cells=2,
    )
    signature = dataset.mod["cd8_t_expression"]

    assert result is None
    assert list(signature.obs["cell_count"]) == [1, 1]
    assert np.isnan(signature.X).all()


def test_calc_dataset_signature_can_raise_when_dataset_is_below_min_cells():
    adata = AnnData(X=np.ones((2, 2)), var=pd.DataFrame(index=["GeneA", "GeneB"]))
    adata.obs["sample_id"] = ["s1", "s2"]
    adata.obs["cell_type"] = ["CD8 T", "CD8 T"]

    dataset = DatasetCollection(adata, dataset_col="sample_id")

    with pytest.raises(ValueError, match="Some datasets have fewer than 2 cells"):
        dataset.calc_dataset_signature(
            adata,
            category="cell_type",
            value="CD8 T",
            modality_name="cd8_t_expression",
            min_cells=2,
            missing_datasets="raise",
        )

    assert "cd8_t_expression" not in dataset.mod


def test_dataset_write_read_round_trips_mudata(tmp_path):
    adata = AnnData(X=np.ones((4, 1)))
    adata.obs["sample_id"] = ["s1", "s1", "s2", "s2"]
    adata.obs["condition"] = ["a", "a", "b", "b"]
    adata.obs["cell_type"] = ["T", "B", "B", "B"]

    dataset = DatasetCollection(adata, dataset_col="sample_id", obs_columns=["condition"])
    assert dataset.calc_dataset_by_pop(adata, category="cell_type", output="counts") is None
    dataset.relations["similarity"] = sparse.csr_matrix([[1.0, 0.2], [0.2, 1.0]])
    dataset.add_hierarchy(
        HierarchyResult(
            id="mod:population__hierarchical",
            input_mod="population",
            method="hierarchical",
            axis="bicluster",
            obs_leaf_order=["s1", "s2"],
            obs_linkage_matrix=np.array([[0.0, 1.0, 0.3, 2.0]]),
            var_leaf_order=["B", "T"],
            var_linkage_matrix=np.array([[0.0, 1.0, 0.5, 2.0]]),
        )
    )

    path = tmp_path / "dataset.h5mu"
    dataset.write(path)
    loaded = DatasetCollection.read(path)

    assert isinstance(loaded.mdata, MuData)
    assert list(loaded.obs.index) == ["s1", "s2"]
    assert list(loaded.mod) == ["population"]
    assert loaded.relations["similarity"].shape == (2, 2)
    assert loaded.hierarchies["mod:population__hierarchical"]["input_mod"] == "population"
    np.testing.assert_array_equal(
        loaded.hierarchies["mod:population__hierarchical"]["obs_linkage"],
        np.array([[0.0, 1.0, 0.3, 2.0]]),
    )
    np.testing.assert_array_equal(loaded.mod["population"].X, np.array([[1, 1], [2, 0]]))


def test_dataset_methods_are_not_exposed_at_package_root():
    for module in ("celldega", "celldega.nbhd", "celldega.nbhd.neighborhoods"):
        sys.modules.pop(module, None)

    import celldega as dega
    import celldega.collection as collection_module
    import celldega.dataset as dataset_module

    assert hasattr(dega, "collection")
    assert hasattr(dega, "dataset")
    assert not hasattr(dega, "calc_dataset_by_pop")
    assert not hasattr(dega, "construct_population_space")
    assert not hasattr(dega, "from_adata")
    assert hasattr(dega, "DatasetCollection")
    assert not hasattr(dega, "Dataset")
    assert not hasattr(dataset_module, "calc_dataset_by_pop")
    assert not hasattr(dataset_module, "construct_population_space")
    assert not hasattr(dataset_module, "from_adata")
    assert not hasattr(dataset_module, "read")
    assert not hasattr(dataset_module, "Dataset")
    assert hasattr(dataset_module, "DatasetCollection")
    assert hasattr(collection_module, "CelldegaCollection")
    assert hasattr(DatasetCollection, "write")
    assert not hasattr(DatasetCollection, "construct_population_space")
    assert not hasattr(DatasetCollection(obs=pd.DataFrame(index=["s1"])), "spaces")
