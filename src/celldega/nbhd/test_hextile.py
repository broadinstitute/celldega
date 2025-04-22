from . import *
from ..pre.merge_segmentations import *

def test_hextile():

    gdf_dummy_trx = generate_random_points_gdf(n_points=50, x_range=(0, 100), y_range=(0, 100))
    dummy_img = generate_dummy_image(width=100, height=100)
    gdf_dummy_hextile = create_hextile(radius=5, img_width=100, img_height=100)

    hextile_assigned_trx = assigning_transcripts(gdf_polygons = gdf_dummy_hextile,
                                                 gdf_transcripts = gdf_dummy_trx)

    assert hextile_area(gdf_dummy_hextile, dummy_img.shape) is True
    assert hextile_trx_assignment(hextile_assigned_trx) == (False, False)