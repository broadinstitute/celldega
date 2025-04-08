from . import *
from ..pre.merge_segmentations import *

def test_hexagrid():

    dummy_trx_gdf = generate_random_points_gdf(n_points=50, x_range=(0, 100), y_range=(0, 100))
    dummy_img = generate_dummy_image(width=100, height=100)
    dummy_hexagrid_gdf = create_hexagrid(r=5, img_width=100, img_height=100)

    hexagrid_assigned_trx = assigning_transcripts(polygons_gdf = dummy_hexagrid_gdf,
                                                 transcripts_gdf = dummy_trx_gdf)

    assert hexagrid_area(dummy_hexagrid_gdf, dummy_img.shape) is True
    assert hexagrid_trx_assignment(hexagrid_assigned_trx) == (False, False)