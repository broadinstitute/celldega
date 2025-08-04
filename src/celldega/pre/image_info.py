"""
Image information utilities for different spatial transcriptomics technologies.
"""


def get_image_info(technology: str, image_tile_layer: str = "dapi") -> list[dict]:
    """
    Retrieve image information for a given technology and image tile layer.

    Args:
        technology: The technology for which image information is requested.
                    Supports 'Xenium', 'MERSCOPE', and 'Visium-HD'.
        image_tile_layer: The type of image tile layer to retrieve information for.
                         Options are 'dapi' or 'all' for Xenium/MERSCOPE.

    Returns:
        A list of dictionaries containing image information, including name,
        button name, and color.

    Raises:
        ValueError: If the technology is not supported or the image_tile_layer
                   is invalid.
    """
    # Validate technology
    supported_technologies = ["Xenium", "MERSCOPE", "Visium-HD"]
    if technology not in supported_technologies:
        raise ValueError(
            f"Unsupported technology: {technology}. Supported technologies are: {supported_technologies}."
        )

    if technology == "Visium-HD":
        return [{"name": "cells", "button_name": "CELLS", "color": [0, 0, 255]}]

    # Validate image_tile_layer for other technologies
    if image_tile_layer not in ["dapi", "all"]:
        raise ValueError(f"Invalid image_tile_layer: {image_tile_layer}. Must be 'dapi' or 'all'.")

    # Handle 'dapi' case for Xenium and MERSCOPE
    if image_tile_layer == "dapi":
        return [{"name": "dapi", "button_name": "DAPI", "color": [0, 0, 255]}]

    # Handle 'all' case (only for Xenium)
    if technology != "Xenium":
        raise ValueError(
            f"image_tile_layer='all' is only supported for 'Xenium'. "
            f"Received technology: {technology}."
        )

    return [
        {"name": "dapi", "button_name": "DAPI", "color": [0, 0, 255]},
        {"name": "bound", "button_name": "BOUND", "color": [0, 255, 0]},
        {"name": "rna", "button_name": "RNA", "color": [255, 0, 0]},
        {"name": "prot", "button_name": "PROT", "color": [255, 255, 255]},
    ]
