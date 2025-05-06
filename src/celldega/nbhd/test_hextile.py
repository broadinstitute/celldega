from . import *

def test_hextile():

    gdf_dummy_hextile = create_hextile(radius=5, img_width=100, img_height=100)
    img_width=100
    img_height=100
    assert round(sum(gdf_dummy_hextile.area.tolist())) == round(img_width * img_height)