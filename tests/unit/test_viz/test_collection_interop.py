"""Collections are accepted by Celldega's plain-data functions and widgets
through duck typing (to_geodataframe() / .mod / .obs), not by type checks."""

from anndata import AnnData
import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Point, Polygon, box

import celldega as dega
from celldega.dataset import DatasetCollection
from celldega.nbhd import NeighborhoodCollection
from celldega.select import Selector


def _two_squares() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {"name": ["a", "b"]},
        geometry=[
            Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]),
            Polygon([(2, 0), (3, 0), (3, 1), (2, 1)]),
        ],
    )


def test_landscape_accepts_neighborhood_collection():
    collection = NeighborhoodCollection(gdf=_two_squares(), nbhd_type="hextile")
    collection.obs["cat"] = ["0", "1"]
    collection.obs["color"] = ["#ff0000", "#00ff00"]

    widget = dega.viz.Landscape(nbhd=collection, transform=np.eye(3))

    properties = [feature["properties"] for feature in widget.nbhd_geojson["features"]]
    assert [prop["name"] for prop in properties] == ["a", "b"]
    assert [prop["cat"] for prop in properties] == ["0", "1"]
    assert [prop["color"] for prop in properties] == ["#ff0000", "#00ff00"]
    assert len(widget.nbhd) == 2


def test_composition_accepts_dataset_collection():
    obs = pd.DataFrame(
        {
            "sample_id": ["s1"] * 10 + ["s2"] * 40,
            "cell_type": (["T"] * 6 + ["B"] * 4) + (["T"] * 20 + ["B"] * 20),
        },
        index=[f"c{i}" for i in range(50)],
    )
    adata = AnnData(X=np.zeros((50, 3)), obs=obs)
    dc = DatasetCollection(adata, dataset_col="sample_id")
    dc.calc_population(adata, category="cell_type")

    comp = dega.viz.Composition(dc, category="cell_type", adata=adata)

    assert comp.composition_col_weights == {"s1": 10.0, "s2": 40.0}


def test_yearbook_accepts_selection_result():
    obs = pd.DataFrame(
        {"cluster": ["B cell", "T cell", "B cell"]},
        index=["cell_1", "cell_2", "cell_3"],
    )
    adata = AnnData(np.ones((3, 1)), obs=obs, var=pd.DataFrame(index=["MS4A1"]))
    selector = Selector(adata)
    selection = selector.select(query=selector.attr("cluster") == "B cell")

    widget = dega.viz.Yearbook(
        base_url="https://example.org/data", selection=selection, current_page=4
    )

    assert widget.cells == ["cell_1", "cell_3"]
    assert widget.current_page == 0
    assert widget.selection["query"] == selection.to_json()["query"]
    assert widget.selection["candidate_count"] == 2


def test_celldega_nbhd_functions_accept_neighborhood_collection():
    gdf = gpd.GeoDataFrame({"name": ["A", "B"]}, geometry=[box(0, 0, 10, 10), box(10, 0, 20, 10)])
    collection = NeighborhoodCollection.from_gdf(gdf, nbhd_type="manual")
    adata = AnnData(
        X=np.arange(8, dtype=float).reshape(4, 2),
        obs=pd.DataFrame({"leiden": ["0", "1", "0", "1"]}, index=[f"c{i}" for i in range(4)]),
    )
    adata.obsm["spatial"] = np.array([[1, 1], [2, 2], [11, 1], [12, 2]], dtype=float)

    by_gene = dega.nbhd.calc_nbhd_by_gene(collection, adata=adata)
    by_pop = dega.nbhd.calc_nbhd_by_pop(adata, collection, category="leiden", min_cells=1)

    assert list(by_gene.obs_names) == ["A", "B"]
    assert list(by_pop.obs_names) == ["A", "B"]


def test_matrix_accepts_collection_modalities():
    gdf = gpd.GeoDataFrame({"name": ["A", "B"]}, geometry=[box(0, 0, 10, 10), box(10, 0, 20, 10)])
    collection = NeighborhoodCollection.from_gdf(gdf, nbhd_type="manual")
    adata = AnnData(
        X=np.ones((4, 2)),
        obs=pd.DataFrame({"leiden": ["0", "1", "0", "1"]}, index=[f"c{i}" for i in range(4)]),
    )
    adata.obsm["spatial"] = np.array([[1, 1], [2, 2], [11, 1], [12, 2]], dtype=float)
    collection.add_mod(
        "population", dega.nbhd.calc_nbhd_by_pop(adata, collection, category="leiden", min_cells=1)
    )

    mat = dega.clust.Matrix(mdata=collection, color_by="population")

    assert mat.data.shape == (2, 2)
    assert mat.col_entity == {"entity": "nbhd", "attr": "name"}


def test_calc_gradient_from_a_collection_neighborhood():
    """calc_gradient takes one of a collection's neighborhoods; the rings can be stored
    as a new collection with one obs per ring."""
    source = NeighborhoodCollection(
        gdf=gpd.GeoDataFrame(
            {"name": ["islet", "other"]},
            geometry=[Point(0, 0).buffer(100), Point(500, 0).buffer(10)],
        ),
        nbhd_type="alpha_shape",
    )
    rings = dega.nbhd.calc_gradient(source.gdf.loc[["islet"]], bin_width=10, max_dist=50)
    grad_nbhd = NeighborhoodCollection(gdf=rings, nbhd_type="gradient")

    assert grad_nbhd.nbhd_type == "gradient"
    assert grad_nbhd.obs.shape[0] == 10
    assert "direction" in grad_nbhd.obs.columns
    whole = dega.nbhd.calc_gradient(source, bin_width=10, max_dist=50)
    assert whole.geometry.unary_union.area > rings.geometry.unary_union.area
