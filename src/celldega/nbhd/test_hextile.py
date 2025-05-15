from . import *
import random
from shapely import Point
import geopandas as gpd
import numpy as np

def generate_random_points_gdf(n_points=100, x_range=(0, 100), y_range=(0, 100)):
    points = [
        Point(random.uniform(*x_range), random.uniform(*y_range))
        for _ in range(n_points)
    ]
    gdf_trx = gpd.GeoDataFrame(geometry=points)

    gdf_trx["x"] = gdf_trx.geometry.x
    gdf_trx["y"] = gdf_trx.geometry.y

    num_cells = 10
    cell_names = [f"cell_{i}" for i in range(num_cells)]

    gdf_trx["cell_index"] = np.random.choice(cell_names, size=n_points)

    return gdf_trx

def hextile_trx_assignment_check(hextile_assigned_trx):

    more_than_one_matches = (
        "more_than_one_matches" in hextile_assigned_trx["polygon_index"].unique()
    )
    unassigned = "UNASSIGNED" in hextile_assigned_trx["polygon_index"].unique()

    return more_than_one_matches, unassigned

def test_hextile():

    img_width=100
    img_height=100

    gdf_dummy_trx = generate_random_points_gdf(n_points=100, x_range=(0, img_width), y_range=(0, img_height))

    gdf_dummy_hextile = create_hextile(radius=5, img_width=img_width, img_height=img_height)

    hextile_assigned_trx = hexatile_specific_assigned_transcripts(gdf_hextile = gdf_dummy_hextile,
                                                    gdf_transcripts = gdf_dummy_trx,
                                                    py_test=True)

    hextile_assigned_trx, gdf_hextile = percentage_hextile_specific_unassigned_transcripts(gdf_hextile_assigned_trx=hextile_assigned_trx,
                                                       gdf_hextile=gdf_dummy_hextile,
                                                       percentage_unassigned_threshold=75,
                                                       py_test=True)


    assert hextile_trx_assignment_check(hextile_assigned_trx) == (False, False)
    assert round(sum(gdf_dummy_hextile.area.tolist())) == round(img_width * img_height)