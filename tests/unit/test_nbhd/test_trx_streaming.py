import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Polygon

from celldega.nbhd.trx_streaming import _assign_trx_to_entity_streaming_parquet


def _synthetic_entities():
    return gpd.GeoDataFrame(
        {
            "cell_id": ["c1", "c2"],
            "geometry": [
                Polygon([(0, 0), (10, 0), (10, 10), (0, 10)]),
                Polygon([(20, 20), (30, 20), (30, 30), (20, 30)]),
            ],
        }
    )


def _write_trx_parquet(tmp_path, rows):
    path = tmp_path / "transcripts.parquet"
    pd.DataFrame(rows, columns=["x", "y", "gene"]).to_parquet(path)
    return str(path)


def test_streaming_assignment_counts_points_per_entity_and_gene(tmp_path):
    gdf_entity = _synthetic_entities()
    trx_path = _write_trx_parquet(
        tmp_path,
        [
            (1, 1, "GeneA"),
            (2, 2, "GeneA"),
            (3, 3, "GeneB"),
            (25, 25, "GeneA"),
            (100, 100, "GeneA"),  # outside every entity -> dropped
        ],
    )

    counts = _assign_trx_to_entity_streaming_parquet(trx_path, gdf_entity, id_col="cell_id")

    assert counts.loc["c1", "GeneA"] == 2
    assert counts.loc["c1", "GeneB"] == 1
    assert counts.loc["c2", "GeneA"] == 1
    assert "c2" not in counts.index or counts.loc["c2"].get("GeneB", 0) == 0


def test_streaming_assignment_batches_across_multiple_reads(tmp_path):
    gdf_entity = _synthetic_entities()
    rows = [(1, 1, "GeneA") for _ in range(5)] + [(25, 25, "GeneB") for _ in range(3)]
    trx_path = _write_trx_parquet(tmp_path, rows)

    counts = _assign_trx_to_entity_streaming_parquet(
        trx_path, gdf_entity, id_col="cell_id", batch_size=2
    )

    assert counts.loc["c1", "GeneA"] == 5
    assert counts.loc["c2", "GeneB"] == 3


def test_streaming_assignment_custom_column_names(tmp_path):
    gdf_entity = _synthetic_entities()
    path = tmp_path / "custom_trx.parquet"
    pd.DataFrame({"xx": [1, 2], "yy": [1, 2], "name": ["GeneA", "GeneA"]}).to_parquet(path)

    counts = _assign_trx_to_entity_streaming_parquet(
        str(path), gdf_entity, id_col="cell_id", x_col="xx", y_col="yy", gene_col="name"
    )

    assert counts.loc["c1", "GeneA"] == 2


def test_streaming_assignment_raises_on_missing_id_col(tmp_path):
    gdf_entity = _synthetic_entities()
    trx_path = _write_trx_parquet(tmp_path, [(1, 1, "GeneA")])

    with pytest.raises(KeyError):
        _assign_trx_to_entity_streaming_parquet(trx_path, gdf_entity, id_col="not_a_column")


def test_streaming_assignment_no_matches_returns_empty_frame(tmp_path):
    gdf_entity = _synthetic_entities()
    trx_path = _write_trx_parquet(tmp_path, [(1000, 1000, "GeneA")])

    counts = _assign_trx_to_entity_streaming_parquet(trx_path, gdf_entity, id_col="cell_id")
    assert counts.empty
