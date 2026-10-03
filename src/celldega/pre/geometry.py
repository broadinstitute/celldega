"""Round-trip conversion between shapely geometries and plain coordinate lists.

Kept apart from the rest of the package because these are the only shapely-dependent
functions that lived in ``__init__.py``, and they are pure -- no I/O, no dataframes.

Both are underscore-prefixed but are part of the effective public API: four BNB notebooks
do ``from celldega.pre import _to_geometry``, and ``notebooks/nbhd_class_eda.ipynb`` does
the same for ``_to_coords``.
"""

from shapely.geometry import MultiPolygon, Point, Polygon


def _to_geometry(coord_data):
    """
    Converts a coordinate structure back to a Shapely geometry object.

    Accepts:
      - [x, y] → Point
      - {"exterior": [...], "interiors": [...]} → Polygon
      - list of {"exterior": [...], "interiors": [...]} → MultiPolygon

    Args:
        coord_data (list or dict): Coordinate list or structured dict.

    Returns:
        shapely.geometry.Point, Polygon, or MultiPolygon

    Raises:
        TypeError: If the input structure is not recognized.
    """

    if isinstance(coord_data, Point | Polygon | MultiPolygon):
        return coord_data

    if (
        isinstance(coord_data, list | tuple)
        and all(isinstance(x, int | float) for x in coord_data)
        and len(coord_data) == 2
    ):
        return Point(coord_data)

    if isinstance(coord_data, dict) and "exterior" in coord_data:
        exterior = coord_data["exterior"]
        interiors = coord_data.get("interiors", [])
        return Polygon(exterior, interiors)

    if isinstance(coord_data, list) and all(
        isinstance(poly, dict) and "exterior" in poly for poly in coord_data
    ):
        return MultiPolygon(
            [Polygon(poly["exterior"], poly.get("interiors", [])) for poly in coord_data]
        )

    raise TypeError(f"Cannot convert {coord_data} to a Shapely geometry. Unexpected structure.")


def _to_coords(geom):
    """
    Converts a Shapely geometry object to a serializable coordinate structure.

    Supports:
      - Point → [x, y]
      - Polygon → {"exterior": [...], "interiors": [...]}
      - MultiPolygon → list of {"exterior": [...], "interiors": [...]}

    Args:
        geom (shapely.geometry): A Shapely Point, Polygon, or MultiPolygon.

    Returns:
        list or dict: Coordinate representation suitable for serialization.

    Raises:
        TypeError: If the geometry type is unsupported.
    """
    if isinstance(geom, Point):
        return list(geom.coords[0])
    if isinstance(geom, Polygon):
        return {
            "exterior": [list(coord) for coord in geom.exterior.coords],
            "interiors": [
                [list(coord) for coord in interior.coords] for interior in geom.interiors
            ],
        }
    if isinstance(geom, MultiPolygon):
        return [
            {
                "exterior": [list(coord) for coord in polygon.exterior.coords],
                "interiors": [
                    [list(coord) for coord in interior.coords] for interior in polygon.interiors
                ],
            }
            for polygon in geom.geoms
        ]
    raise TypeError(f"Unsupported geometry type: {type(geom)}")
