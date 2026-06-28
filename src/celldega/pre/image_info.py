"""
Image information utilities for different spatial transcriptomics technologies.
"""

from pathlib import Path


def resolve_xenium_morphology_ome_path(data_dir: str | Path) -> Path:
    """
    Locate the morphology OME-TIFF for Xenium-class bundles (including Atera WTA preview).

    Standard Xenium output uses ``morphology_focus/morphology_focus_0000.ome.tif``.
    Some v4-compatible and Atera preview bundles use other names under ``morphology_focus/``
    or ship ``morphology.ome.tif`` at the bundle root.

    Resolution order:

    #. ``morphology_focus/morphology_focus_0000.ome.tif`` (classic Xenium)
    #. First ``morphology_focus/morphology_focus_*.ome.tif`` (lexicographic sort)
    #. First ``morphology_focus/*.ome.tif`` if no ``morphology_focus_*`` match
    #. ``morphology.ome.tif`` at bundle root

    Parameters
    ----------
    data_dir
        Path to the outs directory (e.g. containing ``experiment.xenium``).

    Returns
    -------
    Path
        Path to an existing ``.ome.tif`` file.

    Raises
    ------
    FileNotFoundError
        If no supported morphology TIFF is found.
    """
    root = Path(data_dir)
    classic = root / "morphology_focus" / "morphology_focus_0000.ome.tif"
    if classic.is_file():
        return classic

    focus_dir = root / "morphology_focus"
    if focus_dir.is_dir():
        numbered = sorted(focus_dir.glob("morphology_focus_*.ome.tif"))
        if numbered:
            return numbered[0]
        any_focus = sorted(focus_dir.glob("*.ome.tif"))
        if any_focus:
            return any_focus[0]

    root_morph = root / "morphology.ome.tif"
    if root_morph.is_file():
        return root_morph

    raise FileNotFoundError(
        f"No Xenium-compatible morphology OME-TIFF found under '{root}'. "
        "Looked for morphology_focus/morphology_focus_0000.ome.tif, "
        "morphology_focus/*.ome.tif, and morphology.ome.tif."
    )


def get_image_info(technology: str, image_tile_layer: str = "dapi") -> list[dict]:
    """
    Retrieve image information for a given technology and image tile layer.

    Args:
        technology: The technology for which image information is requested.
                   Currently supports 'Xenium' and 'MERSCOPE'.
        image_tile_layer: The type of image tile layer to retrieve information for.
                         Options are 'dapi' or 'all'. Defaults to 'dapi'.

    Returns:
        A list of dictionaries containing image information, including name,
        button name, and color.

    Raises:
        ValueError: If the technology is not supported or the image_tile_layer
                   is invalid.
    """
    # Validate technology
    supported_technologies = ["Xenium", "MERSCOPE"]
    if technology not in supported_technologies:
        raise ValueError(
            f"Unsupported technology: {technology}. Supported technologies are: {supported_technologies}."
        )

    # Handle 'dapi' case for both Xenium and MERSCOPE
    if image_tile_layer == "dapi":
        return [{"name": "dapi", "button_name": "DAPI", "color": [0, 0, 255]}]

    if image_tile_layer == "h&e":
        return [{"name": "h&e", "button_name": "H&E", "color": [255, 0, 0]}]

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
