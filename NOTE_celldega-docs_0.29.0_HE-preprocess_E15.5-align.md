# Celldega docs 0.29.0: Atera H&E pre-process notebook + E15.5 Align (handoff)

Written 2026-11-20 on branch `v0.29.0_docs`. Only docs files changed; the package code is untouched.
The changes are **not committed yet**. Commit and push the branch, then pull it on the laptop
with more storage.

## Done on this laptop

### 1. Added the missing H&E pre-process notebook

- `docs/examples/brief_notebooks/Atera_Pre-process_with_HE.ipynb`, promoted from
  `~/Downloads/atera_h&e_notebooks/Atera_Pre-process_with_H&E_template.ipynb`.
- `.gitignore`: added `!docs/examples/brief_notebooks/Atera_Pre-process_with_HE.ipynb`
  (notebooks are ignored by default).
- The nav entry (`mkdocs.yaml`, "Atera Pre-process with H&E") and the `docs/examples/index.md`
  entry already existed, and the three H&E tutorials already link to the page. Nothing else was needed.
- Changes from the template (code cells unchanged):
  - Title "Atera Pre-process with H&E", matching the nav. Links to the three H&E tutorials,
    the `add_aligned_he` API page and Atera Pre-process.
  - Install `celldega[pre]>=0.29` (the template had `--pre`, for the alphas). Removed
    `pip install tifffile imagecodecs`: both are core Celldega dependencies.
  - Dataset table: added the 10x dataset pages, the GitHub DegaFiles repos used in the docs, and
    the CC BY 4.0 note.
  - Disk and RAM figures, measured from the real files: zips of 49 / 75 / 89 GB (hippocampus /
    colorectal / breast); the hippocampus extracts to ~28 GB without `morphology_3d/` (21 GB);
    the hippocampus H&E is 3 x 45,694 x 34,152, ~4.7 GB uncompressed.
  - Hosting: links `scripts/upload_degafiles_batched.py` for batched GitHub pushes.
- **Unexecuted**, like `Atera_Pre-process.ipynb`. It was checked against **celldega 0.29.0 from PyPI**
  (scratch venv, not the editable checkout):
  - `pre.main`, `pre.add_aligned_he`, `viz.Landscape` and `viz.get_local_server` bind with the
    notebook's arguments.
  - Synthetic tiled, planar RGB OME-TIFF: `add_aligned_he` rejects the original with
    `tiff2vips: tiled separate planes not supported`. The notebook's step 4 conversion followed by
    step 5 works, and the pixels are preserved.
  - The real hippocampus H&E header, read over HTTP: planar config 2, uint8, 1024 px tiles,
    uncompressed, 9 pyramid levels. The conversion step is still needed in 0.29.0.
  - All nine download URLs (3 samples x bundle / H&E / alignment CSV) return 200, and the bundle
    zip contains the files the Extract step names.

### 2. E15.5 Align notebook: re-executed on 0.29.0 and text fixed (no storage-heavy step left)

`docs/examples/tutorial_notebooks/Broad-Allen_Dev-Mouse-Brain_E15.5_Align.ipynb`

- **Re-executed top to bottom on celldega 0.29.0 from PyPI** (scratch uv venv, Python 3.12.11,
  `jupyter nbconvert --execute`, local 1.9 GB H5AD, 13 min). The saved `dega.__version__` is now
  `'0.29.0'` (it was `'0.26.1'`). No errors, and the code cells are unchanged.
- The results are the same as the 0.26.1 run: 3,828,568 cells, 38 clusters, 3,787,366 kept,
  1,278 landmarks, reference slice 22, 976 neighborhoods, 360 slice-optimizations, and
  **mean adjacent IoU 0.336 (centroids) -> 0.426 (neighborhood)**, identical.
- Intro: "uses `celldega>=0.28`" -> "uses Celldega 0.29 (`pip install "celldega>=0.29"`)".
- Section 5 timing: "about 15-20 minutes" -> "under 2 minutes [alpha shapes] and the refinement
  about 10 minutes". The saved run took 1 min 37 s and 10 min 21 s.
- Section 8, matching what the Viz page loads (the code is otherwise unchanged and was already
  0.29.0-correct):
  - `CELL_CLOUD_DIR = Path("DegaFiles/xenium_E15.5_cell_cloud_compact")` (was `..._v2_1um`)
  - `CELL_CLOUD_ZARR = DATA_DIR / "cellcloud_v2_1um.zarr"` (was `data/xenium_E15.5_cellcloud_v2_1um.zarr`)
  - The hosting text now lists both hosted sources with pinned links: the compact DegaFiles at
    `broadinstitute/celldega_xenium_E15.5_cell_cloud` @ `8d3cd06f` (see B below), and the AnnData
    Zarr on Hugging Face @ `f76a3fa9`. It had pointed at the repo root, which holds only the legacy
    `xenium_E15.5_cell_cloud` layout.
- "Next": "loads these DegaFiles" -> "loads these files" (the Viz page defaults to the Zarr).

### 3. Docs build

`mkdocs build` (into a scratch folder) passes. The new H&E page renders with all seven sections and
every relative link on it resolves. The hippocampus tutorial's link to it resolves. The Align page
shows the 0.29.0 output and the new section 8.

## To do on the laptop with more storage

### A. Execute the H&E pre-process notebook (optional; the docs page works unexecuted)

**Space, per sample (hippocampus, the smallest):** the 49 GB zip, ~28 GB extracted, the 6.5 GB H&E,
the converted H&E TIFF, and the DegaFiles. Running both layouts (tiles and row groups) doubles the
DegaFiles. Budget roughly 120 GB or more. Deleting the zip after extraction gives back 49 GB (the
notebook has a commented `rm`). Breast and colorectal need more.
**Memory:** the H&E conversion needs ~10 GB. `pre.main` on a large Atera WTA region peaked around
55 GB (see Atera Pre-process).

1. Set up the environment:
   `uv venv --python 3.12 && uv pip install "celldega[pre]==0.29.0"`, plus libvips
   (`brew install vips`). If `import celldega` fails with `cannot load library 'libvips.42.dylib'`
   (the pyvips wheel can't find Homebrew's libvips), run with
   `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib`.
2. Run a **copy** of the notebook in a work directory outside the repo. It writes `data/atera`,
   `data/atera_dl` and `data/dega_files` relative to the working directory, and nothing under
   `data/` should land in `docs/`.
3. Before copying the executed notebook back into `docs/examples/brief_notebooks/`:
   - Step 6's Landscape points at `localhost`, so its saved widget will be blank on the docs site.
     Either clear that cell's output or leave the cell unexecuted.
   - Trim long `pre.main` progress logs if they swamp the page.
   - Keep the kernelspec as `python3`.
4. Optional: compare the new `landscape_parameters.json` `aligned_he` entry with the hosted
   `celldega_atera-wta-ff-human-nd-brain` DegaFiles.

### B. Merge the E15.5 compact DegaFiles into broadinstitute (any machine, no storage needed)

- The compact DegaFiles are on the fork branch `cornhundred:codex/compact-cellcloud-batched` @
  `8d3cd06f`. Data PR [broadinstitute/celldega_xenium_E15.5_cell_cloud#1](https://github.com/broadinstitute/celldega_xenium_E15.5_cell_cloud/pull/1)
  is open and clean: 11 commits ahead of `main`, 0 behind.
- **Merge it with "Create a merge commit", not squash or rebase**, so commit `8d3cd06f` becomes part
  of broadinstitute's history and the pinned URLs keep the same SHA.
- The Align page now links `broadinstitute/.../tree/8d3cd06f.../xenium_E15.5_cell_cloud_compact`.
  It already resolves through GitHub's fork network, but it belongs to the repo only after the merge.
- Then on the Viz page, change `CELL_CLOUD_DEGAFILES_URL` from `cornhundred/` to `broadinstitute/`
  and keep the same SHA.

### C. Visual check of the built pages (optional; the build was checked here)

`mkdocs serve`, then look over the "Atera Pre-process with H&E" page, plus the Align page intro,
section 5 and section 8.

### D. Still open from the E15.5 note (not started)

- Viz page: the 0.28.0a5 pins and the `CELLDEGA_ESM_VERSION` override; stale or misaligned saved
  outputs (`In [7]` shows the Matrix cell's output); the heading "1. Visualize in 2D: a Landscape of
  one slice" loses "Landscape" in the TOC. Re-executing it embeds widgets; see the nbconvert
  `iopub_timeout` notes in CONTRIBUTING.
- Site-wide: leftover 0.28 alpha pins (Atera Kidney Yearbook Review, Tabula Sapiens,
  getting-started/desktop-app); `cornhundred/` URLs (Atera_viz, Atera Breast Cancer
  Landscape-Clustergram and Neighborhood Exploration, gallery_broad_allen_mouse_brain_3d).
- CHANGELOG upgrade notes for the APIs 0.29.0 removed or renamed: `write_alignment_point_cloud`,
  `write_nbhd_cloud`, `Matrix(collection=)`, `CellCloud(cluster_key=)`.
