from . import *
from ..pre.merge_segmentations import *

def test_hexatile():

    gdf_dummy_trx = generate_random_points_gdf(n_points=50, x_range=(0, 100), y_range=(0, 100))
    dummy_img = generate_dummy_image(width=100, height=100)
    gdf_dummy_hexatile = create_hexatile(radius=5, img_width=100, img_height=100)

    hexatile_assigned_trx = assigning_transcripts(gdf_polygons = gdf_dummy_hexatile,
                                                 gdf_transcripts = gdf_dummy_trx)

    assert hexatile_area(gdf_dummy_hexatile, dummy_img.shape) is True
    assert hexatile_trx_assignment(hexatile_assigned_trx) == (False, False)