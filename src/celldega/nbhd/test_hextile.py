from . import *

def test_hextile():

    gdf_dummy_hextile = create_hextile(radius=5, img_width=100, img_height=100)

    assert hextile_area(gdf_dummy_hextile, img_width=100, img_height=100) is True
