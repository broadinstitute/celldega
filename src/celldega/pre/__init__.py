import pyvips

# function for pre-processing landscape data
def landscape(data):

    print('landscape: ' + data) 

    return data


def reduce_image_size(image_path, scale_image=0.5):
    """
    Reduce the size of an image by a factor of 0.5

    Parameters
    ----------
    image_path : str
        Path to the image file
    scale_image : float (default=0.5)
        Scale factor for the image resize

    Returns
    -------
    new_image_path : str
        Path to the resized image file
    """
        
    image = pyvips.Image.new_from_file(image_path, access="sequential")

    resized_image = image.resize(scale_image)

    new_image_path = image_path.replace(".tif", "_downsize.tif")
    resized_image.write_to_file(new_image_path)

    return new_image_path


def convert_to_jpeg(image_path, quality=80):
    """
    Convert a TIFF image to a JPEG image with a quality of score

    Parameters
    ----------
    image_path : str
        Path to the image file
    quality : int (default=80)
        Quality score for the JPEG image
    
    Returns
    -------
    new_image_path : str
        Path to the JPEG image file

    """

    # Load the TIFF image
    image = pyvips.Image.new_from_file(image_path, access="sequential")

    # Save the image as a JPEG with a quality of 80
    new_image_path = image_path.replace(".tif", ".jpeg")
    image.jpegsave(new_image_path, Q=quality)

    return new_image_path





__all__ = ["landscape"]
