from anndata import AnnData
import geopandas as gpd
import numpy as np
import pandas as pd
from scipy import sparse
from shapely.geometry import Point

from celldega.collections import (
    CelldegaCollection,
    DatasetCollection,
    HierarchyResult,
    NeighborhoodCollection,
)


def test_dataset_collection_holds_aligned_spaces_relations_and_hierarchies():
    obs = pd.DataFrame(
        {"sample_id": ["sample_001", "sample_002"], "condition": ["a", "b"]},
        index=["sample_001", "sample_002"],
    )
    population = AnnData(
        X=np.array([[0.25, 0.75], [0.5, 0.5]]),
        obs=pd.DataFrame(index=obs.index),
        var=pd.DataFrame(index=["T cell", "B cell"]),
    )
    relation = sparse.csr_matrix([[1.0, 0.2], [0.2, 1.0]])
    hierarchy = HierarchyResult(
        id="population__hierarchical",
        input_kind="space",
        input_key="population",
        method="hierarchical",
        labels=pd.Series(["left", "right"], index=obs.index),
        leaf_order=list(obs.index),
    )

    collection = DatasetCollection(
        obs=obs,
        spaces={"population": population},
        relations={"similarity": relation},
        hierarchies={hierarchy.id: hierarchy},
        provenance={"source": "unit-test"},
    )

    assert isinstance(collection, CelldegaCollection)
    assert collection.collection_type == "dataset"
    assert list(collection.spaces["population"].obs_names) == list(obs.index)
    assert collection.relations["similarity"].shape == (2, 2)
    assert collection.hierarchies["population__hierarchical"].input_key == "population"
    assert collection.neighborhood_collections == {}


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


def test_dataset_collection_can_link_neighborhood_collections():
    dataset_obs = pd.DataFrame(index=["sample_001"])
    neighborhood_obs = pd.DataFrame(
        {"sample_id": ["sample_001"]},
        index=["sample_001::nbhd_00001"],
    )
    neighborhoods = NeighborhoodCollection(obs=neighborhood_obs)

    datasets = DatasetCollection(
        obs=dataset_obs,
        neighborhood_collections={"manual_regions": neighborhoods},
    )

    assert datasets.neighborhood_collections["manual_regions"] is neighborhoods
