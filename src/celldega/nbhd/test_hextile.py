from . import *

def test_hextile():

    img_width=100
    img_height=100

    gdf_dummy_trx = generate_random_points_gdf(n_points=100, x_range=(0, img_width), y_range=(0, img_height))

    gdf_dummy_hextile = create_hextile(radius=5, img_width=img_width, img_height=img_height)

    hextile_assigned_trx = unassigned_transcripts_tiled_view(gdf_hextile = gdf_dummy_hextile,
                                                    gdf_transcripts = gdf_dummy_trx)

    assert hextile_trx_assignment_check(hextile_assigned_trx) == (False, False)
    assert round(sum(gdf_dummy_hextile.area.tolist())) == round(img_width * img_height)