import geopandas as gpd
from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import unary_union
from typing import Union, Optional


def calc_grad_nbhd_from_roi(
    shape: Union[Polygon, MultiPolygon, gpd.GeoDataFrame],
    *,
    gdf_reference: Optional[gpd.GeoDataFrame] = None,
    band_width: float = 300,
    max_distance: float = 3000,
    shape_name: Union[str, int] = None,
) -> gpd.GeoDataFrame:
    """
    Generate concentric gradient bands radiating outward from a polygon or multipolygon.
    Optionally clip the bands to the convex hull of a reference GeoDataFrame.

    Parameters
    ----------
    shape : Polygon, MultiPolygon, or GeoDataFrame
        Either a direct shapely geometry or a GeoDataFrame containing the shape(s).
    gdf_reference : GeoDataFrame, optional
        Reference GeoDataFrame to define clipping boundary (convex hull). If None, no clipping.
    band_width : float
        Width of each concentric band (default 300).
    max_distance : float
        Maximum distance to extend the bands outward (default 3000).
    shape_name : str or int, optional
        Row label or index to select geometry from the GeoDataFrame `shape`.

    Returns
    -------
    GeoDataFrame
        GeoDataFrame containing gradient bands as rows.
    """
    if isinstance(shape, gpd.GeoDataFrame):
        if shape_name is None:
            if len(shape) != 1:
                raise ValueError("Provide a shape_name or ensure GeoDataFrame has only one row.")
            roi_geom = shape.geometry.iloc[0]
            crs = shape.crs
        else:
            roi_geom = shape.loc[shape_name].geometry
            crs = shape.crs
    elif isinstance(shape, (Polygon, MultiPolygon)):
        roi_geom = shape
        crs = gdf_reference.crs if gdf_reference is not None else None
    else:
        raise TypeError("Input must be a Polygon, MultiPolygon, or GeoDataFrame.")

    if not isinstance(roi_geom, (Polygon, MultiPolygon)):
        raise TypeError("Selected geometry must be a Polygon or MultiPolygon.")

    # Compute convex hull only if gdf_reference is provided
    boundary = gdf_reference.unary_union.convex_hull if gdf_reference is not None else None

    bands = []
    current_geom = roi_geom
    band_idx = 0
    distance = 0.0

    bands.append({"band": f"grad_{band_idx}", "geometry": roi_geom, "distance": distance})

    while True:
        distance += band_width
        print('distance', distance)
        if distance > max_distance:
            break

        band_idx += 1
        print('buffered')
        buffered = current_geom.buffer(band_width)
        print('ring')
        ring = buffered.difference(current_geom)

        # Clip only if boundary is defined
        ring = ring.intersection(boundary) if boundary is not None else ring

        if ring.is_empty:
            break

        print('append')
        bands.append({"band": f"grad_{band_idx}", "geometry": ring, "distance": distance})
        current_geom = buffered

    return gpd.GeoDataFrame(bands, crs=crs)
