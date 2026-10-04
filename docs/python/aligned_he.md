# Add aligned H&E to DegaFiles

`pre.add_aligned_he()` adds an optional RGB background to an existing DegaFiles
folder. Run your normal preprocessing first, then add H&E:

```python
from celldega import pre

pre.add_aligned_he("path/to/DegaFiles", "aligned_he.tif")
```

Without an alignment matrix, the image must already share the fluorescence
image's **pixel dimensions, pixel size, origin and orientation**. Matching image
sizes alone does not establish alignment. Inputs are 8-bit RGB/RGBA images,
including RGB OME-TIFF; RGBA is flattened onto white. Requires `celldega[pre]`
and a working libvips installation.

For an image with an existing affine alignment, pass the matrix or a headerless
CSV containing it:

```python
pre.add_aligned_he(
    "path/to/DegaFiles",
    "sample_he_image.ome.tif",
    alignment="sample_he_imagealignment.csv",
)
```

The 3×3 matrix maps **H&E pixels to DegaFiles reference-image pixels** using
column vectors: `[x_reference, y_reference, 1] = M @ [x_he, y_he, 1]`. Xenium
Explorer's image-alignment CSV uses this convention for the original Xenium
morphology image. If you cropped or rescaled the reference image, compose that
additional transform with the CSV first. A matrix expressed in microns must also
be converted into reference pixels before use.

The importer resamples onto the reference canvas, pads uncovered areas white,
and writes a WebP DeepZoom pyramid with the reference tile size. It uses the
existing image-packing helper for Parquet row-group DegaFiles. Original images,
cell coordinates, transcript coordinates, segmentations and other manifest
fields are preserved. An existing H&E image is not overwritten.

Reload Landscape or Yearbook after adding the image. DegaFiles with an
`aligned_he` entry in `landscape_parameters.json` show a **Fluorescence / H&E**
selector. Both backgrounds use the same cell and transcript overlays. The IMG
control still controls image visibility; fluorescence channel controls are
hidden while H&E is selected. Yearbook retains the selection when paging.
DegaFiles without the optional entry behave as before.

The new entry records the pyramid name, image format and supplied alignment:

```json
"aligned_he": {
  "name": "h_and_e",
  "button_name": "H&E",
  "image_format": ".webp",
  "alignment": [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
}
```

The stored transform documents how the image was resampled; the viewer does not
apply it again. Landmark-based alignment estimation is outside this workflow.

## Reproduce the tutorial example

For a step-by-step workflow, open
[the example notebook](../../notebooks/Xenium_Aligned_HE.ipynb). It prepares
fluorescence DegaFiles, imports H&E in a separate cell, inspects the saved
manifest, and displays a Landscape with the image-source toggle.

The [SpatialData Xenium tutorial](https://spatialdata.scverse.org/en/stable/tutorials/notebooks/notebooks/examples/technology_xenium.html)
uses [10x Genomics' FFPE Human Lung Cancer dataset, Xenium 2.0.0](https://www.10xgenomics.com/datasets/preview-data-ffpe-human-lung-cancer-with-xenium-multimodal-cell-segmentation-1-standard),
licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
10x supplies the H&E TIFF and its alignment CSV separately from the Xenium output
archive. The dataset's post-staining tissue deformation means the supplied
affine alignment is locally imperfect.

From the repository root, with the development environment active:

```bash
python scripts/prepare_xenium_he_example.py --download
npm run build
python -m http.server 8765 --bind 127.0.0.1
```

Open [the local example](http://127.0.0.1:8765/celldega_js_examples/xenium_aligned_he.html).
The script downloads approximately 1.9 GB of original H&E, DAPI, cell, expression
and transcript data to `data/xenium_h_and_e`, using HTTP ranges to skip unused
large archive entries. It prepares `data/xenium_he_dega` from the tutorial's
2,000 × 500 pixel region (`x=20000..22000`, `y=8000..8500`). It uses the original
expression counts and QV ≥ 20 biological transcripts; all cells share a single
display group, with no inferred cell-type assignments. Source files and generated
DegaFiles remain in the ignored `data/` directory.

Omit `--download` to reuse the downloaded sources. Use `--source` and `--output`
to choose different directories; the script refuses to overwrite its output.
