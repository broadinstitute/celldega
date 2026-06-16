import importlib.util
from pathlib import Path
import sys
import types

from anndata import AnnData
import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Polygon


ROOT_DIR = Path(__file__).resolve().parents[3]
NBHD_ROOT = ROOT_DIR / "src" / "celldega" / "nbhd"

CELLPKG = types.ModuleType("celldega")
CELLPKG.__path__ = [str(ROOT_DIR / "src" / "celldega")]
sys.modules.setdefault("celldega", CELLPKG)

NBHDPKG = types.ModuleType("celldega.nbhd")
NBHDPKG.__path__ = [str(NBHD_ROOT)]
sys.modules.setdefault("celldega.nbhd", NBHDPKG)

spec = importlib.util.spec_from_file_location(
    "celldega.nbhd.neighborhoods", NBHD_ROOT / "neighborhoods.py"
)
neighborhoods = importlib.util.module_from_spec(spec)
neighborhoods.__package__ = "celldega.nbhd"
sys.modules["celldega.nbhd.neighborhoods"] = neighborhoods
spec.loader.exec_module(neighborhoods)

NBHD = neighborhoods.NBHD
from celldega.nbhd.collection import NeighborhoodCollection


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


def test_nbhd_constructor_builds_collection_from_geometry():
    gdf, _adata = _synthetic_nbhd_inputs()

    nbhd = NBHD(gdf, "manual")

    assert list(nbhd.collection.obs.index) == ["A", "B"]
    assert list(nbhd.collection.geometry.index) == ["A", "B"]
    assert nbhd.collection.obs.loc["A", "neighborhood_type"] == "manual"
    assert nbhd.to_collection() is nbhd.collection
    assert not hasattr(nbhd, "adata")
    assert not hasattr(nbhd.collection, "adata")


def test_nbhd_modality_constructors_attach_aligned_modalities():
    gdf, adata = _synthetic_nbhd_inputs()
    nbhd = NBHD(gdf, "manual")

    gene = nbhd.construct_gene_space(min_cells=1, adata=adata)
    result = nbhd.calc_nbhd_by_pop(adata, min_cells=1, output="counts")
    population = nbhd.collection.mod["population"]

    assert result is None
    assert nbhd.collection.mod["gene"] is gene
    assert nbhd.collection.mod["population"] is population
    assert list(gene.var["entity_type"]) == ["gene", "gene"]
    assert list(population.var["entity_type"]) == [
        "cell_population",
        "cell_population",
    ]
    assert list(gene.obs_names) == ["A", "B"]
    assert list(population.obs_names) == ["A", "B"]
    np.testing.assert_allclose(gene.X, np.array([[0.5, 1.0], [3.0, 1.0]]))
    np.testing.assert_array_equal(population.X, np.array([[1, 1], [0, 1]]))


def test_neighborhood_collection_calculates_population_modality_directly():
    gdf, adata = _synthetic_nbhd_inputs()
    collection = NeighborhoodCollection(gdf=gdf, nbhd_type="manual")

    result = collection.calc_nbhd_by_pop(
        adata,
        modality_name="cell_type_population",
        min_cells=1,
        output="counts",
    )
    population = collection.mod["cell_type_population"]

    assert result is None
    assert collection.to_collection() is collection
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

    result = collection.calc_nbhd_by_gene(
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

    result = collection.calc_nbhd_by_pop(adata, min_cells=2, output="counts")
    population = collection.mod["population"]

    assert result is None
    assert list(collection.obs.index) == ["A"]
    assert list(collection.gdf.index) == ["A"]
    assert list(collection.geometry.index) == ["A"]
    assert list(population.obs_names) == ["A"]
    np.testing.assert_array_equal(population.X, np.array([[1, 1]]))


def test_nbhd_min_cells_filters_collection_axis_and_existing_modalities():
    gdf, adata = _synthetic_nbhd_inputs()
    nbhd = NBHD(gdf, "manual")

    nbhd.construct_gene_space(min_cells=1, adata=adata)
    result = nbhd.calc_nbhd_by_pop(adata, min_cells=2, output="counts")

    assert result is None
    assert list(nbhd.collection.obs.index) == ["A"]
    assert list(nbhd.gdf.index) == ["A"]
    assert list(nbhd.collection.mod["gene"].obs_names) == ["A"]
    assert list(nbhd.collection.mod["population"].obs_names) == ["A"]
    np.testing.assert_array_equal(nbhd.collection.mod["population"].X, np.array([[1, 1]]))


def test_nbhd_set_derived_populates_legacy_and_collection_storage():
    gdf, adata = _synthetic_nbhd_inputs()
    nbhd = NBHD(gdf, "manual")

    nbhd.set_derived("NBG-CD", adata=adata)
    nbhd.set_derived("NBP", adata=adata)

    assert nbhd.derived["NBG-CD"] is nbhd.collection.mod["gene"]
    assert nbhd.derived["NBP"]["prop"] is nbhd.collection.mod["population"]
    assert nbhd.derived["NBP"]["abs"] is nbhd.collection.mod["population_counts"]


def test_nbhd_relation_constructor_attaches_sparse_relation():
    gdf, _adata = _synthetic_nbhd_inputs()
    nbhd = NBHD(gdf, "manual")

    bordering = nbhd.construct_bordering_relation(metric="binary")

    assert nbhd.collection.relations["bordering"] is bordering
    assert bordering.shape == (2, 2)
    assert bordering[0, 1] == 1
    assert bordering[1, 0] == 1
