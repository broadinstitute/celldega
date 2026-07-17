import pandas as pd
from shapely.geometry import Polygon

from celldega.nbhd import (
    make_column_names_unique_fast,
    safe_polygon,
    simple_format,
    transform_polygon,
)


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
