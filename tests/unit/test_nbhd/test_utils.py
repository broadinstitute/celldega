import pandas as pd
import pytest
from shapely.geometry import Polygon

from celldega.nbhd import (
    make_column_names_unique_fast,
    safe_polygon,
    simple_format,
    transform_polygon,
)
from celldega.nbhd.utils import _find_transcripts_parquet


def test_safe_polygon_builds_from_vertex_columns():
    row = pd.Series({"vertex_x": [0, 10, 10, 0], "vertex_y": [0, 0, 10, 10]})
    assert safe_polygon(row).area == 100.0


def test_safe_polygon_returns_empty_on_malformed_row():
    row = pd.Series({"vertex_x": [0, 1], "vertex_y": [0]})
    assert safe_polygon(row).is_empty


def test_simple_format_rescales_coordinates():
    geometry = [[[10, 20], [30, 40]]]
    assert simple_format(geometry, image_scale=2) == [[[5.0, 10.0], [15.0, 20.0]]]


def test_transform_polygon_returns_exterior_as_object_array():
    poly = Polygon([(0, 0), (1, 0), (1, 1)])
    result = transform_polygon(poly)
    assert result.shape == (1, 4, 2)
    assert list(result[0][0]) == [0, 0]


def test_make_column_names_unique_fast_dedupes_columns():
    df = pd.DataFrame([[1, 2, 3]], columns=["gene", "gene", "gene"])
    result = make_column_names_unique_fast(df)
    assert list(result.columns) == ["gene", "gene_1", "gene_2"]


def test_find_transcripts_parquet_matches_literal_name(tmp_path):
    (tmp_path / "transcripts.parquet").write_bytes(b"")
    assert _find_transcripts_parquet(str(tmp_path)) == str(tmp_path / "transcripts.parquet")


def test_find_transcripts_parquet_matches_prefixed_name(tmp_path):
    (tmp_path / "aziz_1_20260217_5_transcripts.parquet").write_bytes(b"")
    assert _find_transcripts_parquet(str(tmp_path)) == str(
        tmp_path / "aziz_1_20260217_5_transcripts.parquet"
    )


def test_find_transcripts_parquet_ignores_unrelated_files(tmp_path):
    (tmp_path / "data1_transcripts.parquet").write_bytes(b"")
    (tmp_path / "cells.parquet").write_bytes(b"")
    (tmp_path / "notes.txt").write_bytes(b"")
    assert _find_transcripts_parquet(str(tmp_path)) == str(tmp_path / "data1_transcripts.parquet")


def test_find_transcripts_parquet_raises_when_none_found(tmp_path):
    (tmp_path / "cells.parquet").write_bytes(b"")
    with pytest.raises(FileNotFoundError, match=r"transcripts\.parquet"):
        _find_transcripts_parquet(str(tmp_path))


def test_find_transcripts_parquet_raises_when_ambiguous(tmp_path):
    (tmp_path / "data1_transcripts.parquet").write_bytes(b"")
    (tmp_path / "data2_transcripts.parquet").write_bytes(b"")
    with pytest.raises(ValueError, match="Multiple files"):
        _find_transcripts_parquet(str(tmp_path))
