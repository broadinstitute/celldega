# Documentation maintenance and manual work

Audit date: 2026-11-03. This is a maintainer checklist, outside the published docs.

The review inspected notebook source, execution counts, saved outputs, widget
state, embedded JavaScript versions, navigation, and the public directory
metadata of [Celldega Supporting Data](https://huggingface.co/datasets/broadinstitute/Celldega_Supporting_Data/tree/main).
It did not rerun the full analyses, download large datasets, validate every Zarr
chunk, or test every widget in a browser. A saved execution count is evidence of
an earlier run, not proof that the current source runs on 0.28.0.

Follow-up validation of the restored Broad–Allen pair ran the preprocessing,
alignment, export, and visualization code against a small synthetic dataset.
The built documentation was also checked with the full hosted cell stack:
the 3D gallery rendered, and the notebook supported orbiting and Clustergram
gene selection. The full scientific analysis was not rerun. The notebook's
2D image view still logs requests for tiles outside the image boundary.

There are 33 notebook files under `docs/examples/` in this checkout: 16 listed,
4 unlisted, 11 excluded, and 2 built without a navigation entry. Another 45
tracked development notebooks were inventoried, excluding historical archives.
One of the two non-navigation notebooks, Atera biological exploration, is an
untracked local draft. The two Broad–Allen mouse-brain notebooks have been
restored from the published documentation, retaining their saved outputs.
Development notebooks should be promoted selectively, rather than all rerun.

## Do these first

1. [ ] Repair and rerun **Custom Segmentation**: its saved widget output has no
   saved widget state. Host the segmentation inputs needed to reproduce it.
2. [ ] Validate the **local DegaFiles** workflow from a clean notebook. The local
   server guide contains local-server instructions, but its executed demo uses
   a GitHub URL. Keep the published demo remote so it works for readers, and
   clearly identify the local steps they should run themselves.
3. [ ] Publish a compatible **processed Atera breast cancer AnnData** and add its
   download to the neighborhood notebook. That notebook currently requires a
   local file from an earlier run of the main tutorial.
4. [ ] Publish a small **aligned H&E DegaFiles example**, then rerun its notebook
   against a shared URL. It currently depends on checkout helpers and localhost.
5. [ ] Refresh the five main linked tutorials: **Chromium PBMC**, **Atera kidney**,
   **Atera breast cancer**, **Atera neighborhoods**, and **Visium HD CRC**. Then
   record screenshots from those refreshed views.

## Release and rerun order

The npm registry currently reports `latest=0.27.0` and
`alpha=0.28.0-alpha.4`; `0.28.0` is not published. Python's `0.28.0a4` spelling
is not the npm version spelling. Do not embed an unpublished `celldega@0.28.0` URL.

- [ ] Test against the current checkout before publication; use the local bundle
  for development checks when the matching package is not yet published.
- [ ] Publish the matching JavaScript package before the final documentation
  reruns, then set `CELLDEGA_ESM_VERSION` to that published npm version.
- [ ] Rerun the notebook, save widget state, and build the docs. Merely replacing
  `_esm` version strings does not regenerate the Python state or its outputs.
- [ ] Open the built page without a live kernel and test gene search, cluster
  selections, linked selections, and any UMAP/XY or image-source controls.

See [Contributing](../CONTRIBUTING.md#-rendering-docs-notebooks-widget-embedding)
for embedding commands. Recorded version numbers below describe saved state,
not necessarily the current Python source.

## Listed notebook refresh queue

All paths in this table are under `docs/examples/`. "Already hosted" means the
referenced files or directories were present in the inspected data repository;
GitHub-hosted DegaFiles can stay on GitHub if their browser access works.

| Priority | Notebook | Evidence and rerun work | Data work |
| --- | --- | --- | --- |
| P0 | [Custom Segmentation](../docs/examples/brief_notebooks/Custom_Segmentation.ipynb) | One saved widget output, zero saved widget states; development HMR setup remains. Rerun and embed state. | Host the `cellpose2` segmentation inputs under a documented path. Existing visual DegaFiles are on GitHub; migrating them is optional. |
| P1 | [Landscape from a Local Server](../docs/examples/brief_notebooks/Landscape_Local_Server.ipynb) | Saved state pins 0.26.0; the live demo uses remote data, while the local steps are in Markdown. Verify local instructions separately and explain the distinction. | No new upload is required for the existing remote preview. Use a downloadable small DegaFiles fixture if adding a fully reproducible local exercise. |
| P1 | [Scanpy–Squidpy Xenium Pancreas](../docs/examples/tutorial_notebooks/Scanpy-Squidpy_Xenium_Pancreas.ipynb) | Saved state pins 0.24.2; source starts from a checkout-specific raw-data path. Rerun from a documented input/download step; replace deprecated `mat.clust()` in the example source. | Pancreas AnnData already exists on HF. Verify its metadata against this workflow before reusing it; alternatively document the vendor raw-data download. |
| P1 | [Atera preprocessing](../docs/examples/brief_notebooks/Atera_Pre-process.ipynb) | Two code cells, neither executed, no saved preview. Test the recipe with the intended bundle; a code-only preprocessing recipe need not embed an expensive full run. | Current `EA_s3_broad_DX002` input is a local sample. Choose a shareable source bundle or document how to obtain it, and provide a prepared output preview. Uploading the full raw instrument bundle is not necessary. |
| P1 | [Atera breast cancer neighborhoods](../docs/examples/tutorial_notebooks/Atera_Breast_Cancer_Neighborhood_Exploration.ipynb) | Saved state pins 0.26.0; source raises if the main tutorial's processed AnnData is absent. Add a hosted download or an explicit prerequisite, then rerun. | Publish `WTA_Preview_FFPE_Breast_Cancer_outs_AnnData_processed.h5ad` or a smaller cell-metadata/spatial-coordinate input. The similarly named hosted `..._clustered.h5ad` is not proven equivalent. |
| P1 | [Chromium PBMC](../docs/examples/tutorial_notebooks/Scanpy_Chromium.ipynb) | Saved state pins 0.28.0-alpha.1. Refresh UMAP/XY, marker dot plots, single-cell Clustergram, and Enrich with the matching release. | `pbmc3k/pbmc3k.zarr`, `pbmc3k_leiden_markers.zarr`, and `pbmc3k_raw.h5ad` are already hosted. No new upload is indicated by this audit. |
| P1 | [Atera kidney](../docs/examples/tutorial_notebooks/Atera_Kidney_Landscape-Clustergram.ipynb) | Saved state includes both 0.27.0 CDN shims and an approximately 10.8 MB inlined bundle. Regenerate consistently and test Yearbook/Composition as well as linked views. | `Atera_v1_WTA_Kidney_non_diseased_FFPE.h5ad` is already on HF; DegaFiles use a fixed GitHub revision. Migration is optional. |
| P1 | [Atera breast cancer](../docs/examples/tutorial_notebooks/Atera_Breast_Cancer_Landscape-Clustergram.ipynb) | Saved state pins 0.26.1. Rerun and verify the current Scanpy/AnnData flow and linked controls. | Raw matrix and a clustered AnnData already exist on HF. A validated processed cache would support this notebook and the neighborhood tutorial. |
| P1 | [Visium HD CRC](../docs/examples/tutorial_notebooks/Visium_HD_Human_CRC_Landscape-Clustergram-Enrich.ipynb) | Saved state pins 0.27.0. Rerun marker calculations, linked views, and the goblet-cell sub-analysis. | `crc_cluster.h5ad`, `crc_raw_feature_cell_matrix.h5`, `cluster-4_sub-cluster.h5ad`, and `Meta_crypt_clusters_with_vivid_colors.csv` are already hosted. No missing upload was identified. |
| P2 | [Pancreas islet gradients](../docs/examples/brief_notebooks/Gradient_Neighborhood_Pancreas_Islets.ipynb) | Saved state pins 0.27.0. Recheck neighborhood geometry, units, composition, and stored relationships. | Pancreas AnnData is already on HF; DegaFiles are on GitHub. Optionally save the final gradient geometry and summary matrices to shorten reruns. |
| P2 | [CellCloud thick MERFISH](../docs/examples/brief_notebooks/Landscape-3D_thick_MERFISH.ipynb) | Saved state imports the docs' local bundle; source forces `CELLDEGA_LOCAL_ESM=1`. Verify the built page and use a published version for a portable notebook export. | DegaFiles and `df_sig.parquet` already use GitHub. No mandatory HF migration. |
| P2 | [Landscape View Xenium](../docs/examples/brief_notebooks/Landscape_View_Xenium.ipynb) | Saved state pins 0.24.2. Rerun and confirm that the linked expression selection matches the displayed dataset. | DegaFiles and signatures are on GitHub. A more neutral sample name/title would make the ovarian-cancer example easier to identify. |
| P2 | [Landscape–Heatmap Visium HD](../docs/examples/brief_notebooks/Landscape-Heatmap-Visium-HD.ipynb) | Saved state inlines approximately 7.6 MB of JavaScript; HMR setup remains. Update terminology to Clustergram and rerun. | DegaFiles and signatures are on GitHub. Migration is optional. |
| P2 | [UMAP–Cluster Pancreas](../docs/examples/brief_notebooks/UMAP-Cluster_Pancreas_Xenium.ipynb) | Saved state inlines approximately 7.6 MB; source uses local SpatialData/AnnData paths and HMR setup. Refresh or consolidate with the Scanpy–Squidpy tutorial. | Reuse the existing hosted pancreas AnnData if compatible, or add a reproducible source-data preparation step. |
| P2 | [Broad–Allen mouse-brain preprocessing](../docs/examples/tutorial_notebooks/Broad-Allen_Dev-Mouse-Brain_E15.5_Align.ipynb) and [visualization](../docs/examples/tutorial_notebooks/Broad-Allen_Dev-Mouse-Brain_E15.5_Viz.ipynb) | Restored under Spatial Transcriptomics → 3D Spatial Transcriptomics. The preprocessing writer uses the current `pre.write_point_cloud_dataset`. Original analysis results and figures are retained; the saved Viz widgets use the published 0.28.0-alpha.4 renderer and a whole-brain camera. Recheck the full analysis during the release rerun. | The clustered H5AD is already on HF, and both alignment variants and slice-35 DegaFiles are on GitHub. No new upload is needed to restore these examples. |

P0 is a concrete saved-output problem; P1 is the onboarding/release queue; P2
is a useful follow-up. Old version pins alone do not establish that a widget is
broken.

## Unlisted, excluded, and orphaned work

Keep analysis review separate from final documentation publication. These
notebooks do not need to enter the 0.28.0 changelog.

| Notebook or group | Current state | Required work before promotion |
| --- | --- | --- |
| [Aligned H&E](../docs/examples/tutorial_notebooks/Xenium_Aligned_HE.ipynb) | Unlisted; six code cells unexecuted, no widget state; local helper and localhost dependencies. | Upload the cropped DegaFiles, transform/alignment provenance, and source/license notes. Replace the checkout-only display path with a hosted preview; rerun and capture fluorescence/H&E screenshots. |
| [Tabula Sapiens](../docs/examples/tutorial_notebooks/Tabula_Sapiens_Landscape-Clustergram-Enrich.ipynb) | Unlisted notebook; public gallery; saved state pins 0.28.0-alpha.2. | All five referenced Zarr directories, preparation notebook, README, and license are already hosted. Refresh saved widgets and test on a fresh browser; a full data re-upload is not indicated. |
| [MIX-seq drug screen](../docs/examples/tutorial_notebooks/MIX-seq_Drug_Screen_Landscape-Clustergram-Enrich.ipynb) | Unlisted; saved state pins 0.28.0-alpha.1. | H5AD, both referenced Zarr directories, and preparation notebook are already hosted under `McFarland_2020/`. Review the analysis and refresh linked views before promotion. |
| [CST lung cancer PTM](../docs/examples/tutorial_notebooks/CST_Lung_Cancer_PTM_Clustergram-Enrich.ipynb) | Unlisted; saved state pins 0.28.0-alpha.1. | H5MU and preparation notebook are already hosted. Rerun, verify data/feature labels and enrichment, and finish analysis review. |
| [Flex CITE-seq PBMC](../docs/examples/tutorial_notebooks/Flex_CITE-seq_PBMC_Landscape-Clustergram-Enrich.ipynb) | Excluded while revised; saved state pins 0.27.0. | H5MU and `matrices/cell_types.zarr` plus `cluster_markers.zarr` already exist on HF. Refresh and review RNA/protein interpretation, then restore the notebook, index, and gallery links together. |
| [CCLE/DepMap series](../notebooks/CCLE_Multiomics_README.md), chapters 00–09 | Ten docs notebooks excluded; visual chapters pin 0.26.1; inputs/archive are local. | Finalize the chosen data release, publish the processed `ccle_multiomics.h5mu` plus source/provenance information if redistribution permits, add a download path, then rerun 00 followed by 01–09. The inspected HF repo has no CCLE directory/archive. |
| Atera biological exploration (`docs/examples/tutorial_notebooks/Atera_Breast_Cancer_Biological_Exploration.ipynb`) | Untracked local draft; built locally but absent from nav; unexecuted, with no widget state. Its preparation helpers are also local, untracked files. | Keep it out of ordinary local search while being prepared, then deliberately add the notebook and helpers when ready. Publish `marker_<family>.h5ad`, cell observations, niche summaries and geometry, and remove local-only transform paths before rerunning. |
| [Visium HD mouse lung](../docs/examples/brief_notebooks/Visium-HD_Landscape_Mouse_Lung_FF.ipynb) | Built but absent from nav; old inlined bundle. | Either promote it with a current rerun and clear gallery/tutorial role, or mark it unlisted/exclude it. Existing DegaFiles are on GitHub. |
| AIFI Olink plasma proteomics | A path is declared in `not_in_nav`, but that notebook is absent from `docs/examples/` in this checkout. | Locate the intended source/data and complete its review, or remove the stale declaration. |
| Older `1.0_Preprocess_and_Align` / `2.0_Viz_CellCloud` drafts | Superseded by the restored, listed Broad–Allen E15.5 Align/Viz pair. | Use the listed notebooks for the current workflow; keep the old draft paths excluded. |

## What actually needs uploading

### Needed to make the current exercises reproducible

- [ ] **Custom segmentation:** the Cellpose input files used by the notebook,
  or a small equivalent fixture; document how they were generated. Keep the
  existing GitHub DegaFiles preview or migrate it separately.
- [ ] **Atera neighborhoods:** a verified processed breast-cancer AnnData or a
  compact metadata/coordinates-only derivative, with cell labels and colors.
- [ ] **Aligned H&E:** a small complete DegaFiles directory containing the
  fluorescence and aligned H&E pyramids, plus alignment/source metadata.
- [ ] **Atera preprocessing preview:** a shared prepared output for the chosen
  sample, or a smaller public sample with the same workflow. The raw bundle can
  remain at the instrument vendor or institutional source.

### Needed only if the drafts are promoted

- [ ] **Atera biological exploration:** marker/signature H5ADs, cell observations,
  niche summaries/geometry, and the preparation helpers or a reproducible recipe.
- [ ] **CCLE:** the selected processed MuData archive and its provenance; optional
  saved Matrix Zarr views can avoid recalculating each chapter's clustering.
- [ ] **Small alignment fixture (optional):** the restored mouse-brain notebooks
  cover the full workflow; a smaller multi-slice AnnData, saved transform, and
  point-cloud DegaFiles would make experimentation faster.

For each upload, preserve the full DegaFiles/Zarr directory structure and record
source URLs, data versions, license/attribution, preparation code and parameters,
units, cell-ID conventions, and checksums. Pin a revision in the final notebook.
Test one representative image tile, gene lookup, and range request where packed
row-group storage is used. An existing H5AD/H5MU input does not automatically
mean every optional cached analysis output has been published.

## Screenshots and videos

Capture screenshots after refreshing the corresponding examples so the controls
match the released widgets. Keep the first screenshot close to the guide's
opening explanation, followed by a short caption and a few actions to try.

| Order | Page | Capture |
| --- | --- | --- |
| 1 | Landscape | Tissue with cells/transcripts and an image; UMAP/XY with a selected gene or neighborhood. Use Atera kidney and PBMC for the main views. |
| 2 | Clustergram | A clustered heatmap and a marker-gene dot plot showing dendrograms, metadata tracks, and the view/marker control. |
| 3 | Linked Landscape–Clustergram–Enrich | One selected cell group, its expression pattern, and enrichment together, with the selection visible. |
| 4 | Yearbook | A meaningful cell selection displayed as portraits with a consistent zoom. |
| 5 | Enrich | A selected term, its genes, and the library selector. |
| 6 | Composition | Cell-type proportions across groups; show how the counts/proportions toggle changes interpretation. |
| 7 | CellCloud / linked CellCloud–Clustergram | An informative 3D angle and a corresponding selected cell group or gene. |
| 8 | NeighborhoodCloud | Neighborhood regions with selected on-demand cell detail; a current hosted example is still needed. |
| 9 | Aligned H&E | The same region and overlays on fluorescence and H&E backgrounds. |

Then record short narrated walkthroughs in the same order. A useful recording
shows the question, the inputs, three or four interactions, and how to read the
result. Keep the existing linked-workflow video as the shared introduction until
widget-specific videos are available; link to it rather than duplicating a large
embed on every page.

## Method-to-example coverage and follow-up

The Python overview now describes all nine previously listed modules, plus QC,
and points to actual examples or reference walkthroughs. The remaining gaps are:

| Area | Existing coverage | Next useful example |
| --- | --- | --- |
| `pre` | Atera recipe, custom segmentation, aligned H&E guide | A small downloadable raw-to-DegaFiles fixture with a hosted finished preview. |
| `viz` / `clust` | PBMC, Atera, Visium, linked guides | Refresh their saved state, then add screenshots and controls to the shorter widget guides. |
| `nbhd` / `collection` | Atera niches and pancreas gradients; the latter stores a NeighborhoodCollection | Keep calculations on plain objects and storage in the collection visibly distinct. |
| `dataset` | Reference construction/population/signature examples | A small two-sample notebook demonstrating DatasetCollection, Composition, and a signature Clustergram. |
| `set` | Reference membership/signature/overlap examples | Compare two clusterings of the same cells, with membership overlap and expression summaries. |
| `select` | Reference filters/samplers and Yearbook guide | A reproducible Selector → Selection → Yearbook notebook; current portrait examples do not demonstrate Selector directly. |
| `align` | Restored Broad–Allen preprocessing/Viz notebooks, current API, and 3D gallery | Add a smaller serial-slice fit/save/reload/apply fixture; keep aligned H&E import separate from estimating transforms. |
| `qc` | New API page; older [development QC notebook](../notebooks/Segmentation_QC.ipynb) | Update the QC notebook with a shared fixture and explain what the metrics mean before publishing. |

Additional maintenance:

- [ ] Run the most prominent notebooks in a fresh environment; saved outputs
  without recorded errors do not establish current reproducibility.
- [ ] Make the Getting Started first example runnable without placeholder URLs
  or an already defined `adata`.
- [ ] Resolve the two orphaned notebooks above: absent navigation is not the same
  as `not_in_nav`; ordinary orphan pages can still appear in site search.
- [ ] Configure the canonical `site_url` before relying on sitemap coverage.
  The current build's sitemap is empty because it has no site URL configured.
- [ ] Triage API docstring warnings, especially arguments described in docstrings
  but accepted through `**kwargs`; the build succeeds but remains noisy.
- [ ] Add a tested Manifold workspace/bucket walkthrough when the exact endpoint
  and access setup are available. The linked Manifold article establishes the
  deployment use case, not a step-by-step bucket configuration.
- [ ] Consider naming the gallery category “Single-cell and multi-omics” now that
  it includes Tabula Sapiens, while keeping gallery and navigation order aligned.

Keep public pages focused on how to use Celldega. Track reruns, upload status,
and unfinished example promotion in this maintainer checklist.
