"""Capture documentation screenshots of Celldega visualizations.

Renders each visualization with the documentation bundle
(docs/assets/js/celldega.js) in the installed Google Chrome, performs the
declared interactions, and writes images under
docs/assets/img/visualizations/<group>/. No Python kernel is needed; the
data are read from their public hosts.

Run from the repository root (Playwright is not a Celldega dependency):

    uv run --with playwright python scripts/docs_screenshots/capture.py
    uv run --with playwright python scripts/docs_screenshots/capture.py --only visualizations
    uv run --with playwright python scripts/docs_screenshots/capture.py --list

Rebuild the bundle (`npm run build`) first when capturing unreleased changes.
Set CELLDEGA_ESM_VERSION to a published npm version (e.g. 0.28.0) so notebook
captures load that bundle from jsdelivr instead of inlining the local one.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import functools
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
from urllib.parse import quote

from playwright.sync_api import Page, sync_playwright


REPO = Path(__file__).resolve().parents[2]
OUT_DIR = REPO / "docs" / "assets" / "img" / "visualizations"
GALLERY_DIR = REPO / "docs" / "assets" / "img"
VIEWER = "scripts/docs_screenshots/viewer.html"

# Size budget for committed media (bytes).
MAX_IMAGE_BYTES = 300_000
MAX_GIF_BYTES = 5_000_000  # animations are lazy-loaded; history is the real cost

ATERA_KIDNEY = (
    "https://raw.githubusercontent.com/broadinstitute/"
    "Celldega_Atera_v1_WTA_Kidney_non_diseased_FFPE/"
    "3a46ab4db67821eef3b8ff8d1c3704fb7b3bb48f"
)


@dataclass
class Capture:
    """One image: what to render, what to do, and what to keep."""

    group: str  # output subdirectory, usually the docs page
    name: str  # file stem
    spec: dict = field(default_factory=dict)  # viewer.html panels and links
    viewport: tuple[int, int] = (960, 760)
    steps: list[dict] = field(default_factory=list)
    crop: str = "#stage"  # element to capture
    annotate: list[dict] = field(default_factory=list)
    settle_ms: int = 6000  # time for tiles to arrive after rendering
    pad_top: int = 12  # room above the panels for callouts
    scale: float = 2  # device pixel ratio; lower for dense tissue views
    root: Path = OUT_DIR  # e.g. GALLERY_DIR for gallery thumbnails
    pad_left: int = 12  # room left of the panels for callouts
    clip: tuple[int, int, int, int] | None = None  # x, y, w, h within `crop`
    frames: list[dict] = field(default_factory=list)  # steps, one GIF frame each
    fps: int = 10
    cursor: bool = False  # draw a mouse pointer (screenshots omit the real one)
    anim: str = "gif"  # animation format: "gif", or "webp" for tissue (much smaller)
    notebook: str | None = None  # Python code run in the dega env instead of `spec`
    quality: int | None = None  # WebP quality (default 80 for images, 70 for animations)
    fit_widget: bool = True  # notebook captures: size the first widget like a viewer panel
    notebook_file: str | None = None  # an executed docs notebook (repo path), rendered as is

    @property
    def path(self) -> Path:
        suffix = self.anim if self.frames else "webp"
        return self.root / self.group / f"{self.name}.{suffix}"


def kidney_landscape(**options) -> dict:
    return {
        "kind": "landscape",
        "width": options.get("width", 880),
        "options": {
            "base_url": ATERA_KIDNEY,
            "ini_x": 28322,
            "ini_y": 16570,
            "ini_zoom": -6.1,
            "width": 880,
            "height": 520,
            **options,
        },
    }


# Thick-tissue MERFISH as a CellCloud (point-cloud DegaFiles, centroids in µm).
THICK_MERFISH = {
    "technology": "point-cloud",
    "manifest_name": "landscape_parameters.json",
    "base_url": (
        "https://raw.githubusercontent.com/broadinstitute/"
        "scverse-owkin_thick_merfish/main/landscape_files"
    ),
    "cell_size": 10,
    "ini_x": 1461,
    "ini_y": 1196,
    "ini_z": 50,
    "ini_zoom": -2.3,
    "rotation_x": 45,
    "rotation_orbit": -30,
    "width": 880,
    "height": 520,
}

PBMC3K = (
    "https://huggingface.co/datasets/broadinstitute/Celldega_Supporting_Data/resolve/main/pbmc3k"
)


def pbmc_clustergram(**options) -> dict:
    """PBMC 3k Leiden-cluster marker dot plot, opening at 5 markers per cluster."""
    return {
        "panels": [
            {
                "kind": "clustergram",
                "options": {
                    "url": f"{PBMC3K}/pbmc3k_leiden_markers.zarr",
                    "width": 460,
                    "height": 460,
                    "rank_dim": 5,
                    **options,
                },
            }
        ]
    }


# Positions in the PBMC 3k Clustergram canvas ("#panel-0 .fill") at 460 x 460.
CGM = "#panel-0 .fill"
CGM_PPBP_CLUSTER_8 = [302, 293]  # platelet marker in the platelet cluster
CGM_PPBP_LABEL = [57, 293]
CGM_GZMB_LABEL = [57, 352]
CGM_PLATELET_DENDRO = [545, 304]  # row dendrogram branch of platelet genes (narrow)
ROW_SLIDER_THUMB = [127, 39]  # within "#panel-0" at the default cut (50)
COL_ORDER_DROPDOWN = [61, 14]  # within "#panel-0"
ROW_ORDER_DROPDOWN = [61, 39]
PANEL_BLANK = [500, 60]  # empty control-panel space, right of the search box
CROP_BUTTON = [20, 88]
UNDO_BUTTON = [57, 88]
PROP_BUTTON = [100, 88]
UNIT_BUTTON = [133, 88]
SEARCH_BOX = [330, 14]
CGM_CROPPED_DENDRO = [545, 250]  # the platelet branch after cropping to it

# Callout anchors in the Clustergram control panel and canvas.
CLUSTERGRAM_CALLOUTS = [
    {"label": "1", "selector": "#panel-0 .matrix_controls", "place": "at", "xy": [-14, 18]},
    {"label": "2", "selector": "#panel-0 .matrix_controls", "place": "at", "xy": [-14, 64]},
    {"label": "3", "selector": "#panel-0 .matrix_controls", "place": "at", "xy": [-14, 88]},
    {"label": "4", "selector": "#panel-0 .matrix-cat-bar-container"},
    {"label": "5", "selector": "#panel-0 .search_logo_row", "parent": True},
    {"label": "6", "selector": "#panel-0 .logo_button", "place": "right"},
    {"label": "7", "selector": CGM, "place": "at", "xy": [300, 14]},
    {"label": "8", "selector": CGM, "place": "at", "xy": [-14, 300]},
    {"label": "9", "selector": CGM, "place": "at", "xy": [98, 100]},
    {"label": "10", "selector": CGM, "place": "at", "xy": [552, 470]},
    {"label": "10", "selector": CGM, "place": "at", "xy": [200, 548]},
]

# Landscape: Atera kidney (spatial) positions.
KIDNEY_GLOMERULUS = {"ini_x": 19484, "ini_y": 16408}  # a glomerulus in the cortex
KIDNEY_CORTEX = {"ini_x": 18572, "ini_y": 16190}  # several glomeruli
LS = "#panel-0 .fill"  # the Landscape map
LS_CENTER = [440, 260]  # center of an 880 x 520 map
GENE_SEARCH = "#panel-0 .search_logo_row input"
VISIUM_HD_CRC = (
    "https://raw.githubusercontent.com/SharkieJones/celldega_Visium-HD_hCRC/refs/heads/main/"
    "Visium_HD_Human_Colon_Cancer_2025-10-25_2um"
)
VISIUM_HD_CRYPTS = [545, 330]  # normal crypts ringed by plasma cells, in the default view


def loop(center, radius, points=28):
    """Mouse positions around an ellipse, for drawing a neighborhood by dragging."""
    import math

    cx, cy = center
    rx, ry = radius
    return [
        [cx + rx * math.cos(2 * math.pi * i / points), cy + ry * math.sin(2 * math.pi * i / points)]
        for i in range(points + 1)
    ]


def draw_neighborhood(center, radius, name, sketch_key=False):
    """Frames: start sketching, drag a loop, name the neighborhood, and apply."""
    path = loop(center, radius)
    start = (
        [
            {"mouse": path[0], "relative_to": LS, "steps": 6, "wait": 150},
            {"key": "s", "wait": 300, "hold": 3},
        ]
        if sketch_key
        else [
            {"click_text": "SKTCH", "within": "#panel-0", "wait": 300, "hold": 3},
            {"mouse": path[0], "relative_to": LS, "steps": 8, "wait": 150},
        ]
    )
    return [
        {"click_text": "NBHD", "within": "#panel-0", "wait": 600, "hold": 3},
        *start,
        {"mouse": path[0], "relative_to": LS, "action": "down", "wait": 60},
        *[{"mouse": xy, "relative_to": LS, "steps": 2, "wait": 50} for xy in path[1:]],
        {"mouse": path[-1], "relative_to": LS, "action": "up", "wait": 700, "hold": 4},
        {"key": "Meta+A", "wait": 60},
        *[{"type": c, "wait": 90} for c in name],
        {"wait": 300, "hold": 3},
        {"click_text": "Apply", "within": "body", "wait": 1200, "hold": 16},
    ]


def gene_bar(name: str) -> str:
    """A gene bar's label in the Landscape TRX bar graph."""
    return f'#panel-0 .gene_container svg text:text-is("{name}")'


def cluster_bar(name: str) -> str:
    """A cluster bar's label in the Landscape CELL bar graph."""
    return f'#panel-0 .cell_container svg text:text-is("{name}")'


# The Broad-Allen E15.5 mouse brain: 43 aligned Xenium sections, 3.8M cells
# (compact DegaFiles, as on gallery/gallery_broad_allen_mouse_brain_3d.md).
BROAD_ALLEN_3D = {
    "technology": "point-cloud",
    "manifest_name": "cell_cloud.json",
    "base_url": (
        "https://raw.githubusercontent.com/cornhundred/celldega_xenium_E15.5_cell_cloud/"
        "8d3cd06fc1a478f386826c27ba0e900b40703a3a/xenium_E15.5_cell_cloud_compact"
    ),
    "alignment": "neighborhood",
    "cluster_attr": "leiden_1.0",
    "use_adata_3d_centroids": False,
    "ini_zoom": -3.6,
    "rotation_orbit": -25,
    "rotation_x": 20,
    "cell_size": 10,
    "width": 880,
    "height": 520,
}

# Callout anchors in the Landscape control panel (js/ui/ui_containers.js).
CONTROL_PANEL_CALLOUTS = [
    {"label": "1", "selector": "#panel-0 .image_container"},
    {"label": "2", "selector": "#panel-0 .cell_container"},
    {"label": "3", "selector": "#panel-0 .gene_container"},
    {"label": "4", "selector": "#panel-0 .nbhd_container"},
    {"label": "5", "selector": "#panel-0 .search_logo_row", "parent": True},
    {"label": "6", "selector": "#panel-0 .logo_button", "place": "right"},
    {"label": "7", "selector": "#panel-0 .fill", "place": "inside"},
]

# A Python-built kidney Landscape with the AnnData's UMAP (rendered from saved
# widget state). Reads only labels and X_umap, not the expression matrix.
KIDNEY_H5AD = (
    REPO
    / "notebooks/data/atera_data/Atera_v1_WTA_Kidney_non_diseased_FFPE"
    / "Atera_v1_WTA_Kidney_non_diseased_FFPE.h5ad"
)
KIDNEY_H5AD_URL = (
    "https://huggingface.co/datasets/broadinstitute/Celldega_Supporting_Data/resolve/main/"
    "Atera_v1_WTA_Kidney_non_diseased_FFPE.h5ad"
)
KIDNEY_UMAP_NOTEBOOK = f"""
from pathlib import Path
from urllib.request import urlopen, urlretrieve

import anndata as ad
import numpy as np
import celldega as dega

BASE_URL = "{ATERA_KIDNEY}"
h5ad = Path("{KIDNEY_H5AD}")
if not h5ad.exists():
    h5ad = Path("kidney.h5ad")
    if not h5ad.exists():
        urlretrieve("{KIDNEY_H5AD_URL}", h5ad)
source = ad.read_h5ad(h5ad, backed="r")
cells = ad.AnnData(obs=source.obs[["leiden", "azimuth_coarse"]].copy())
cells.obsm["X_umap"] = np.asarray(source.obsm["X_umap"])
cells.uns["leiden_colors"] = list(source.uns["leiden_colors"])
source.file.close()
with urlopen(f"{{BASE_URL}}/micron_to_image_transform.csv") as response:
    transform = np.loadtxt(response)
dega.viz.Landscape(
    base_url=BASE_URL, transform=transform, adata=cells,
    cluster_attr="leiden", cell_attr=["leiden", "azimuth_coarse"],
    ini_x=28322, ini_y=16570, ini_zoom=-6.5, width=880, height=520,
)
"""

# Tabula Sapiens atlas UMAP (AnnData Zarr) with a cell-type signature store:
# zooming in shows estimated viewport expression (purple TRX).
TABULA_SAPIENS = (
    "https://huggingface.co/datasets/broadinstitute/Celldega_Supporting_Data/resolve/main/"
    "Tabula_Sapiens"
)
TABULA_LANDSCAPE = {
    "kind": "landscape",
    "width": 880,
    "options": {
        "zarr_url": f"{TABULA_SAPIENS}/tabula_sapiens.zarr",
        "zarr_layer": "log1p_csc",
        "gene_signature_url": f"{TABULA_SAPIENS}/tabula_sapiens_cell_type_signatures.zarr",
        "cell_attr": ["cell_type", "tissue_in_publication", "compartment"],
        "cluster_attr": "cell_type",
        "landscape_state": "umap",
        "ini_zoom": -4.6,
        "ini_x": 5000,
        "ini_y": 5000,
        "width": 880,
        "height": 520,
    },
}

# PBMC 3k single-cell Landscape (AnnData Zarr) for UMAP views.
PBMC3K_LANDSCAPE = {
    "kind": "landscape",
    "width": 880,
    "options": {
        "zarr_url": f"{PBMC3K}/pbmc3k.zarr",
        "cluster_attr": "leiden",
        "ini_zoom": -4.1,
        "ini_x": 5000,
        "ini_y": 5000,
        "width": 880,
        "height": 520,
    },
}

# Xenium pancreas DegaFiles with the precomputed Scanpy UMAP from the hosted
# AnnData (as in the Scanpy-Squidpy tutorial); obs_names become Xenium cell IDs.
PANCREAS = (
    "https://raw.githubusercontent.com/broadinstitute/celldega_Xenium_human_Pancreas_FFPE/main/"
    "Landscape_Xenium_V1_human_Pancreas_FFPE_outs_webp"
)
PANCREAS_H5AD = REPO / "data/celldega_supporting_data/Xenium_V1_human_Pancreas_FFPE_outs.h5ad"
PANCREAS_H5AD_URL = (
    "https://huggingface.co/datasets/broadinstitute/Celldega_Supporting_Data/resolve/main/"
    "Xenium_V1_human_Pancreas_FFPE_outs.h5ad"
)
PANCREAS_UMAP_NOTEBOOK = f"""
from pathlib import Path
from urllib.request import urlretrieve

import anndata as ad
import numpy as np
import celldega as dega

h5ad = Path("{PANCREAS_H5AD}")
if not h5ad.exists():
    h5ad = Path("pancreas.h5ad")
    if not h5ad.exists():
        urlretrieve("{PANCREAS_H5AD_URL}", h5ad)
source = ad.read_h5ad(h5ad, backed="r")
cells = ad.AnnData(obs=source.obs[["leiden"]].copy())
cells.obs_names = source.obs["cell_id"].astype(str).to_numpy()
cells.obsm["X_umap"] = np.asarray(source.obsm["X_umap"])
cells.uns["leiden_colors"] = list(source.uns["leiden_colors"])
source.file.close()
dega.viz.Landscape(
    technology="Xenium", base_url="{PANCREAS}", adata=cells, cluster_attr="leiden",
    ini_x=17064, ini_y=6887, ini_zoom=-5.4, width=880, height=520,
)
"""
# The linked pancreas Landscape, marker dot plot, and Enrich from the "Visualize
# your own data" page, built from the hosted Scanpy AnnData.
PANCREAS_LINKED_NOTEBOOK = f"""
from pathlib import Path
from urllib.request import urlretrieve

import anndata as ad
import scanpy as sc
import celldega as dega

h5ad = Path("{PANCREAS_H5AD}")
if not h5ad.exists():
    h5ad = Path("pancreas.h5ad")
    if not h5ad.exists():
        urlretrieve("{PANCREAS_H5AD_URL}", h5ad)
adata = ad.read_h5ad(h5ad)
adata.obs_names = adata.obs["cell_id"].astype(str).to_numpy()

sc.tl.rank_genes_groups(adata, groupby="leiden")
markers = dega.clust.Matrix(adata, groupby="leiden")
markers.filter_by_size(0.05)
markers.norm("row", by="zscore")
markers.cluster(view="rank_genes_groups", levels=[1, 3, 5, 10])

landscape = dega.viz.Landscape(
    base_url="{PANCREAS}", adata=adata, cluster_attr="leiden",
    ini_x=17064, ini_y=6887, ini_zoom=-5.6,
)
cgm = dega.viz.Clustergram(matrix=markers, rank_dim=3, width=420, height=520)
dega.viz.spatial_clustergram(landscape, cgm, enrich=True, width="560px", height="660px")
"""

# Enrich with the islet cluster's top Scanpy markers (the hosted pancreas AnnData).
PANCREAS_ENRICH_NOTEBOOK = f"""
from pathlib import Path
from urllib.request import urlretrieve

import anndata as ad
import scanpy as sc
import celldega as dega

h5ad = Path("{PANCREAS_H5AD}")
if not h5ad.exists():
    h5ad = Path("pancreas.h5ad")
    if not h5ad.exists():
        urlretrieve("{PANCREAS_H5AD_URL}", h5ad)
adata = ad.read_h5ad(h5ad)
sc.tl.rank_genes_groups(adata, groupby="leiden")
genes = sc.get.rank_genes_groups_df(adata, group="9")["names"][:20].tolist()

enrich = dega.viz.Enrich(width=640, height=620)
enrich.gene_list = genes
enrich
"""
ENRICH_TERM = '.celldega-enrich svg text:text-is("{}")'
ENRICH_GENE = '.celldega-enrich__paragraph span:text-matches("^{},")'

TABULA_SPERMATIDS = [460, 75]  # the swirl at the top of the Tabula Sapiens UMAP


def kidney_yearbook(query: dict, rows: int = 2, cols: int = 4) -> dict:
    """An Atera kidney Yearbook: celldega.yearbook(el, ...args)."""
    args = [
        {},
        "",
        ATERA_KIDNEY,
        "Atera kidney",
        [],
        rows,
        cols,
        50,
        4,
        920,
        560,
        {},
        [],
        {},
        [],
        "default",
        {},
        None,
        0,
        query,
    ]
    return {"panels": [{"kind": "yearbook", "width": 920, "args": args}]}


PODOCYTES = {"cluster": {"attr": "cluster", "value": "16"}, "gene": "NPHS2", "max_cells": 64}
YEARBOOK_CALLOUTS = [
    {"label": "1", "selector": "#panel-0 .image_container"},
    {"label": "2", "selector": "#panel-0 .cell_container"},
    {"label": "3", "selector": "#panel-0 .gene_container"},
    {"label": "4", "selector": "#panel-0 .ctrl_container > div:nth-child(4)"},
    {"label": "5", "selector": "#panel-0 .query_container"},
    {"label": "6", "selector": "#panel-0 .pagination_container"},
    {"label": "7", "selector": "#panel-0 .logo_button", "place": "at", "xy": [-14, 8]},
    {"label": "8", "selector": "#panel-0 .yearbook-portrait-selection", "place": "inside"},
    {"label": "9", "selector": "#panel-0 .yearbook-select-cell", "place": "left"},
]
YB_CHECK = "#panel-0 .yearbook-select-cell >> nth="

# Positions in the linked pancreas Clustergram (".widget-hbox > :nth-child(2) .fill").
PANCREAS_CGM = ".widget-hbox > :nth-child(2) .fill"
PANCREAS_INS_LABEL = [50, 314]
PANCREAS_ISLET_COLUMN = [80, 38]
PANCREAS_ISLET_BRANCH = [500, 330]


# The linked view in the Tabula Sapiens notebook (its first widget row).
TABULA_NOTEBOOK = (
    "docs/examples/tutorial_notebooks/Tabula_Sapiens_Landscape-Clustergram-Enrich.ipynb"
)
TS_LS = ".widget-hbox >> nth=0 >> .fill >> nth=0"
TS_CGM = ".widget-hbox >> nth=0 >> .fill >> nth=1"
TS_COL_SLIDER = ".widget-hbox >> nth=0 >> .matrix_controls input.slider >> nth=0"
TS_GENE_SEARCH = ".widget-hbox >> nth=0 >> .search_logo_row input >> nth=0"
TS_SWIRL = [300, 185]  # spermatids in the linked UMAP
TS_CENTER = [299, 375]

# The same anchors without NBHD (drawing off), numbered 1-6.
LANDSCAPE_CALLOUTS = [
    {**c, "label": str(i)}
    for i, c in enumerate((c for c in CONTROL_PANEL_CALLOUTS if c["label"] != "4"), start=1)
]

CAPTURES = [
    Capture(
        group="index",
        name="control_panel",
        # A glomerulus-rich region of the kidney cortex.
        spec={
            "panels": [
                kidney_landscape(
                    nbhd_edit=True, height=330, ini_x=18572, ini_y=16190, ini_zoom=-3.6
                )
            ]
        },
        annotate=CONTROL_PANEL_CALLOUTS,
        pad_top=30,
        scale=1.6,
    ),
    Capture(
        group="gallery",
        name="merfish_thick_tissue",
        # Same camera as docs/assets/js/gallery_merfish_thick_tissue.js.
        spec={"panels": [{"kind": "landscape", "width": 880, "options": THICK_MERFISH}]},
        crop="#panel-0 .fill",
        root=GALLERY_DIR,
        scale=1.25,
    ),
    # Landscape guide: Atera kidney, whole-transcriptome Xenium.
    Capture(
        group="landscape",
        name="overview",
        # Close up on a glomerulus: image, cell boundaries, and transcripts.
        spec={"panels": [kidney_landscape(**KIDNEY_GLOMERULUS, ini_zoom=-0.4)]},
        annotate=LANDSCAPE_CALLOUTS,
        pad_top=30,
        settle_ms=15000,
        scale=1.4,
    ),
    Capture(
        group="landscape",
        name="zoom",
        # Scroll from tissue scale into a glomerulus until transcripts load.
        spec={"panels": [kidney_landscape(**KIDNEY_GLOMERULUS, ini_zoom=-5.5)]},
        frames=[
            {"mouse": LS_CENTER, "relative_to": LS, "steps": 6, "wait": 300, "hold": 6},
            *[
                {
                    "mouse": LS_CENTER,
                    "relative_to": LS,
                    "action": "wheel",
                    "delta": -60,
                    "wait": 450,
                }
                for _ in range(17)
            ],
            # Keep recording while the transcript tiles in view load and draw.
            *[{"wait": 700} for _ in range(10)],
            {"wait": 800, "hold": 6},
        ],
        crop="#panel-0",
        settle_ms=6000,
        scale=1,
        fps=8,
        cursor=True,
        anim="webp",
    ),
    Capture(
        group="landscape",
        name="select_clusters",
        # Podocytes (cluster 16), then add glomerular endothelium (20).
        spec={"panels": [kidney_landscape(**KIDNEY_CORTEX, ini_zoom=-3.6)]},
        frames=[
            {"mouse": LS_CENTER, "relative_to": LS, "steps": 4, "wait": 200, "hold": 4},
            {"click": cluster_bar("16"), "wait": 1500, "hold": 10},
            {"click": cluster_bar("20"), "modifiers": ["Shift"], "wait": 1500, "hold": 12},
        ],
        crop="#panel-0",
        settle_ms=8000,
        scale=1,
        fps=6,
        cursor=True,
        anim="webp",
    ),
    Capture(
        group="landscape",
        name="search_genes",
        # Two orthogonal markers across the whole section, then their transcripts
        # in one glomerulus: podocytes (NPHS2) and endothelium (EMCN).
        spec={"panels": [kidney_landscape(**KIDNEY_GLOMERULUS, ini_zoom=-6.3)]},
        frames=[
            {"mouse": LS_CENTER, "relative_to": LS, "steps": 4, "wait": 200, "hold": 3},
            {"click": GENE_SEARCH, "wait": 200},
            *[{"type": c, "wait": 120} for c in "NPHS2, EMCN"],
            {"key": "Enter", "wait": 3000, "hold": 8},
            # Stronger cell colors zoomed out; the same slider sets transcript size
            # once zoomed in.
            {
                "set_range": "#panel-0 .trx_container input.slider",
                "value": "max",
                "wait": 1200,
                "hold": 10,
            },
            {"mouse": LS_CENTER, "relative_to": LS, "steps": 4, "wait": 100},
            *[
                {
                    "mouse": LS_CENTER,
                    "relative_to": LS,
                    "action": "wheel",
                    "delta": -60,
                    "wait": 450,
                }
                for _ in range(19)
            ],
            *[{"wait": 700} for _ in range(16)],
            {"wait": 1000, "hold": 16},
        ],
        crop="#panel-0",
        settle_ms=8000,
        scale=1,
        fps=6,
        cursor=True,
        anim="webp",
    ),
    Capture(
        group="landscape",
        name="genes_zoomed_out",
        # The whole section, to see where the genes are expressed.
        spec={"panels": [kidney_landscape(ini_zoom=-6.4)]},
        steps=[
            {"fill": GENE_SEARCH, "value": "NPHS2, EMCN", "enter": True, "wait": 4000},
            # Zoomed out, the TRX slider sets how strongly cells are colored.
            {"set_range": "#panel-0 .trx_container input.slider", "value": "max", "wait": 1500},
        ],
        crop="#panel-0",
        settle_ms=8000,
        scale=1.6,
    ),
    Capture(
        group="landscape",
        name="genes_zoomed_in",
        # Only the two markers' transcripts over DAPI: cells and other channels off.
        spec={"panels": [kidney_landscape(**KIDNEY_GLOMERULUS, ini_zoom=0.3)]},
        steps=[
            {"fill": GENE_SEARCH, "value": "NPHS2, EMCN", "enter": True, "wait": 6000},
            {"set_range": "#panel-0 .trx_container input.slider", "value": "max", "wait": 1000},
            {"click_text": "CELL", "within": "#panel-0", "wait": 800},
            {"click_text": "BOUND", "within": "#panel-0", "wait": 800},
            {"click_text": "RNA", "within": "#panel-0", "wait": 1500},
        ],
        crop="#panel-0",
        settle_ms=15000,
        scale=1.6,
    ),
    Capture(
        group="landscape",
        name="transcript_tooltip",
        spec={"panels": [kidney_landscape(**KIDNEY_GLOMERULUS, ini_zoom=0.6)]},
        steps=[{"mouse": LS_CENTER, "relative_to": LS, "wait": 4000}],
        crop="#panel-0",
        settle_ms=15000,
        scale=1.3,
    ),
    Capture(
        group="landscape",
        name="image_channels",
        # Hide cells, turn channels off and on, and change the DAPI brightness.
        spec={"panels": [kidney_landscape(**KIDNEY_GLOMERULUS, ini_zoom=-1.2)]},
        frames=[
            {"mouse": LS_CENTER, "relative_to": LS, "steps": 4, "wait": 200, "hold": 3},
            {"click_text": "CELL", "within": "#panel-0", "wait": 800, "hold": 6},
            {"click_text": "BOUND", "within": "#panel-0", "wait": 800, "hold": 6},
            {"click_text": "RNA", "within": "#panel-0", "wait": 800, "hold": 6},
            *[
                {
                    "set_range": "#panel-0 .image_container input.slider >> nth=0",
                    "value": v,
                    "wait": 300,
                }
                for v in (60, 70, 80, 90, 80, 60, 40, 30, 50)
            ],
            {"click_text": "BOUND", "within": "#panel-0", "wait": 800},
            {"click_text": "RNA", "within": "#panel-0", "wait": 800},
            {"click_text": "CELL", "within": "#panel-0", "wait": 1200, "hold": 8},
        ],
        crop="#panel-0",
        settle_ms=10000,
        scale=1,
        fps=6,
        cursor=True,
        anim="webp",
    ),
    Capture(
        group="landscape",
        name="visium_hd",
        # Visium HD colorectal cancer: zoom from the whole section into plasma
        # cells around crypts, where IGKC leads the bars; select IGKC to see its
        # jittered transcripts, then zoom out to its expression across the section.
        spec={
            "panels": [
                {
                    "kind": "landscape",
                    "width": 880,
                    "options": {
                        "base_url": VISIUM_HD_CRC,
                        "technology": "Visium-HD",
                        "width": 880,
                        "height": 520,
                    },
                }
            ]
        },
        frames=[
            {"mouse": VISIUM_HD_CRYPTS, "relative_to": LS, "steps": 6, "wait": 300, "hold": 6},
            *[
                {
                    "mouse": VISIUM_HD_CRYPTS,
                    "relative_to": LS,
                    "action": "wheel",
                    "delta": -100,
                    "wait": 450,
                }
                for _ in range(11)
            ],
            # Transcript tiles load; IGKC tops the TRX bars.
            *[{"wait": 700} for _ in range(8)],
            {"wait": 500, "hold": 10},
            {"click": gene_bar("IGKC"), "wait": 600},
            {"mouse": PANEL_BLANK, "steps": 6, "wait": 1800, "hold": 4},
            # Hide the H&E so the IGKC transcripts stand out.
            {"click_text": "IMG", "within": "#panel-0", "wait": 1000, "hold": 2},
            {
                "set_range": "#panel-0 .trx_container input.slider",
                "value": 45,
                "wait": 1200,
                "hold": 12,
            },
            *[
                {
                    "mouse": VISIUM_HD_CRYPTS,
                    "relative_to": LS,
                    "action": "wheel",
                    "delta": 100,
                    "wait": 350,
                }
                for _ in range(11)
            ],
            # Zoomed out, the same slider sets how strongly cells are colored.
            {
                "set_range": "#panel-0 .trx_container input.slider",
                "value": "max",
                "wait": 2000,
                "hold": 16,
            },
        ],
        crop="#panel-0",
        settle_ms=10000,
        scale=1,
        fps=8,
        cursor=True,
        anim="webp",
    ),
    Capture(
        group="landscape",
        name="spaces",
        # Pancreas: tissue to UMAP, select the islet cluster (9), and back to tissue.
        notebook=PANCREAS_UMAP_NOTEBOOK,
        frames=[
            {"mouse": LS_CENTER, "relative_to": LS, "steps": 4, "wait": 300, "hold": 4},
            # Zoom out first: the UMAP keeps the tissue view's zoom.
            *[
                {"mouse": LS_CENTER, "relative_to": LS, "action": "wheel", "delta": 60, "wait": 250}
                for _ in range(4)
            ],
            {"wait": 300, "hold": 3},
            {"click_text": "UMAP", "within": "#panel-0", "wait": 80},
            *[{"wait": 120} for _ in range(12)],
            {"wait": 300, "hold": 6},
            {"click": cluster_bar("9"), "wait": 1500, "hold": 8},
            {"click_text": "SPATIAL", "within": "#panel-0", "wait": 80},
            *[{"wait": 120} for _ in range(12)],
            {"wait": 2500, "hold": 12},
        ],
        settle_ms=15000,
        crop="#panel-0",
        scale=1,
        fps=8,
        cursor=True,
        anim="webp",
    ),
    Capture(
        group="landscape",
        name="single_cell",
        # Tabula Sapiens: query the spermatids' neighborhood, then see one gene's reach.
        spec={"panels": [TABULA_LANDSCAPE]},
        frames=[
            {"mouse": TABULA_SPERMATIDS, "relative_to": LS, "steps": 6, "wait": 300, "hold": 4},
            *[
                {
                    "mouse": TABULA_SPERMATIDS,
                    "relative_to": LS,
                    "action": "wheel",
                    "delta": -60,
                    "wait": 400,
                }
                for _ in range(14)
            ],
            {"mouse": TABULA_SPERMATIDS, "relative_to": LS, "steps": 2, "wait": 2500, "hold": 8},
            # The bars now describe the spermatids in view; select their top
            # non-mitochondrial gene.
            {"click": gene_bar("RGMB-AS1"), "wait": 2500, "hold": 8},
            *[
                {
                    "mouse": TABULA_SPERMATIDS,
                    "relative_to": LS,
                    "action": "wheel",
                    "delta": 60,
                    "wait": 350,
                }
                for _ in range(14)
            ],
            {"wait": 2000, "hold": 14},
        ],
        settle_ms=25000,
        crop="#panel-0",
        scale=1,
        fps=6,
        cursor=True,
        anim="webp",
    ),
    # "Visualize your own data" page: the linked pancreas views.
    Capture(
        group="your-data",
        name="linked",
        # Click the islet cluster (9) in the Clustergram: the Landscape shows its
        # cells and Enrich receives its top marker genes.
        notebook=PANCREAS_LINKED_NOTEBOOK,
        fit_widget=False,
        viewport=(1700, 1000),
        steps=[
            {"mouse": [80, 38], "relative_to": ".fill >> nth=1", "action": "click", "wait": 4000},
            {"mouse": [5, 5], "relative_to": ".widget-hbox", "wait": 800},
        ],
        annotate=[
            # 1: the clicked column label; 2: the Landscape; 3: Enrich.
            {
                "label": "1",
                "selector": ".widget-hbox > :nth-child(2) .fill",
                "place": "at",
                "xy": [80, 10],
            },
            {
                "label": "2",
                "selector": ".widget-hbox > :nth-child(1) .fill",
                "place": "at",
                "xy": [24, 24],
            },
            {
                "label": "3",
                "selector": ".widget-hbox > :nth-child(3)",
                "place": "at",
                "xy": [-12, 44],
            },
        ],
        crop=".widget-hbox",
        settle_ms=15000,
        scale=1.2,
    ),
    # Yearbook guide: Atera kidney portraits.
    Capture(
        group="yearbook",
        name="overview",
        spec=kidney_yearbook(PODOCYTES),
        annotate=YEARBOOK_CALLOUTS,
        pad_top=30,
        pad_left=34,
        settle_ms=15000,
        scale=1.4,
    ),
    Capture(
        group="yearbook",
        name="query_review",
        # Query glomerular endothelial cells (cluster 20) ranked by EMCN, zoom
        # every portrait at once, check cells on two pages, and return.
        spec=kidney_yearbook(PODOCYTES),
        frames=[
            {"mouse": [460, 300], "relative_to": "#panel-0", "steps": 4, "wait": 300, "hold": 3},
            {"click": "#panel-0 .query_container input >> nth=0", "wait": 150},
            {"key": "Meta+A", "wait": 50},
            *[{"type": c, "wait": 120} for c in "20"],
            {"click": "#panel-0 .query_container input >> nth=1", "wait": 150},
            {"key": "Meta+A", "wait": 50},
            *[{"type": c, "wait": 120} for c in "EMCN"],
            {"click_text": "Query", "within": "#panel-0", "wait": 5000, "hold": 8},
            *[
                {
                    "mouse": [115, 225],
                    "relative_to": "#panel-0",
                    "action": "wheel",
                    "delta": 120,
                    "wait": 500,
                }
                for _ in range(3)
            ],
            {"wait": 2500, "hold": 6},
            {"click": YB_CHECK + "0", "wait": 500, "hold": 3},
            {"click": YB_CHECK + "2", "wait": 500, "hold": 3},
            {"click_text": "▶", "within": "#panel-0", "wait": 4000, "hold": 4},
            {"click": YB_CHECK + "1", "wait": 500, "hold": 3},
            {"click_text": "START", "within": "#panel-0", "wait": 4000, "hold": 14},
        ],
        crop="#panel-0",
        settle_ms=15000,
        scale=1,
        fps=6,
        cursor=True,
        anim="webp",
    ),
    # Enrich guide: the islet cluster's top markers.
    Capture(
        group="enrich",
        name="overview",
        notebook=PANCREAS_ENRICH_NOTEBOOK,
        fit_widget=False,
        steps=[
            {"click": ENRICH_TERM.format("Alpha Cell Pancreas Human"), "wait": 1200},
            {"click": ENRICH_GENE.format("GCG"), "wait": 3000},
            {"mouse": [5, 5], "relative_to": ".celldega-enrich", "wait": 500},
        ],
        annotate=[
            {"label": "1", "selector": ".celldega-enrich select", "place": "left"},
            {"label": "2", "selector": ".celldega-enrich svg", "place": "at", "xy": [-14, 40]},
            {
                "label": "3",
                "selector": ".celldega-enrich__paragraph",
                "place": "at",
                "xy": [-14, 14],
            },
            {
                "label": "4",
                "selector": ".celldega-enrich__gene-info",
                "place": "at",
                "xy": [-14, 14],
            },
            {"label": "5", "selector": ".celldega-enrich a", "place": "left"},
            {"label": "6", "selector": ".celldega-enrich .logo_button", "place": "left"},
        ],
        crop="#stage",
        pad_left=34,
        settle_ms=8000,
        scale=1.3,
    ),
    Capture(
        group="enrich",
        name="terms_and_genes",
        notebook=PANCREAS_ENRICH_NOTEBOOK,
        fit_widget=False,
        frames=[
            {
                "mouse": [320, 300],
                "relative_to": ".celldega-enrich",
                "steps": 4,
                "wait": 200,
                "hold": 3,
            },
            {
                "mouse": [90, 160],
                "relative_to": ".celldega-enrich",
                "steps": 8,
                "wait": 900,
                "hold": 5,
            },
            {"click": ENRICH_TERM.format("Delta Cell Pancreas Human"), "wait": 1200, "hold": 7},
            {"click": ENRICH_TERM.format("Alpha Cell Pancreas Human"), "wait": 1200, "hold": 7},
            {"hover": ENRICH_GENE.format("SST"), "wait": 2500, "hold": 6},
            {"click": ENRICH_GENE.format("GCG"), "wait": 2500, "hold": 10},
            {"click": ENRICH_TERM.format("Alpha Cell Pancreas Human"), "wait": 1200, "hold": 6},
        ],
        crop="#stage",
        settle_ms=8000,
        scale=1,
        fps=6,
        cursor=True,
        anim="webp",
    ),
    # CellCloud guide: the Broad-Allen developing mouse brain in 3D.
    Capture(
        group="cell-cloud",
        name="overview",
        spec={"panels": [{"kind": "landscape", "width": 880, "options": BROAD_ALLEN_3D}]},
        annotate=[
            {"label": "1", "selector": "#panel-0 .cell_container"},
            {"label": "2", "selector": "#panel-0 .gene_container"},
            {"label": "3", "selector": "#panel-0 .search_logo_row", "parent": True},
            {"label": "4", "selector": "#panel-0 .logo_button", "place": "right"},
            {"label": "5", "selector": "#panel-0 .fill", "place": "inside"},
        ],
        pad_top=30,
        settle_ms=40000,
        scale=1.3,
    ),
    Capture(
        group="cell-cloud",
        name="orbit",
        # Turn the brain fully around and tilt it, select cluster 2, then show
        # SPARC, which marks the meninges.
        spec={"panels": [{"kind": "landscape", "width": 880, "options": BROAD_ALLEN_3D}]},
        frames=[
            {"mouse": [140, 300], "relative_to": LS, "steps": 4, "wait": 300, "hold": 3},
            # A full turn around the brain, then a tilt.
            {"mouse": [140, 300], "relative_to": LS, "action": "down", "wait": 60},
            *[
                {"mouse": [140 + 25 * i, 300], "relative_to": LS, "steps": 2, "wait": 90}
                for i in range(1, 25)
            ],
            {"mouse": [740, 300], "relative_to": LS, "action": "up", "wait": 100},
            {"mouse": [140, 300], "relative_to": LS, "steps": 2, "wait": 60},
            {"mouse": [140, 300], "relative_to": LS, "action": "down", "wait": 60},
            *[
                {"mouse": [140 + 25 * i, 300], "relative_to": LS, "steps": 2, "wait": 90}
                for i in range(1, 25)
            ],
            {"mouse": [740, 300], "relative_to": LS, "action": "up", "wait": 100},
            {"mouse": [440, 380], "relative_to": LS, "steps": 2, "wait": 60},
            {"mouse": [440, 380], "relative_to": LS, "action": "down", "wait": 60},
            *[
                {"mouse": [440, 380 - 15 * i], "relative_to": LS, "steps": 2, "wait": 90}
                for i in range(1, 11)
            ],
            {"mouse": [440, 230], "relative_to": LS, "action": "up", "wait": 300, "hold": 3},
            {"mouse": [440, 260], "relative_to": LS, "action": "wheel", "delta": -60, "wait": 600},
            {"click": cluster_bar("2"), "wait": 2500, "hold": 10},
            {"click": cluster_bar("2"), "wait": 1000},
            {"click": GENE_SEARCH, "wait": 200},
            *[{"type": c, "wait": 120} for c in "SPARC"],
            {"key": "Enter", "wait": 600},
            {"mouse": [700, 60], "relative_to": "#panel-0", "steps": 4, "wait": 3000, "hold": 12},
        ],
        crop="#panel-0",
        settle_ms=40000,
        scale=1,
        fps=8,
        cursor=True,
        anim="webp",
    ),
    # Landscape-Clustergram-Enrich: spatial and single-cell linking.
    Capture(
        group="landscape-clustergram-enrich",
        name="spatial",
        notebook=PANCREAS_LINKED_NOTEBOOK,
        fit_widget=False,
        viewport=(1700, 1000),
        frames=[
            {"mouse": [300, 300], "relative_to": PANCREAS_CGM, "steps": 4, "wait": 300, "hold": 4},
            # A gene: INS colors the cells in the tissue.
            {
                "mouse": PANCREAS_INS_LABEL,
                "relative_to": PANCREAS_CGM,
                "action": "click",
                "wait": 300,
            },
            {
                "mouse": [520, 60],
                "relative_to": ".widget-hbox",
                "steps": 4,
                "wait": 3000,
                "hold": 10,
            },
            # A cluster: the islets, and their top markers in Enrich.
            {
                "mouse": PANCREAS_ISLET_COLUMN,
                "relative_to": PANCREAS_CGM,
                "action": "click",
                "wait": 300,
            },
            {
                "mouse": [520, 60],
                "relative_to": ".widget-hbox",
                "steps": 4,
                "wait": 4000,
                "hold": 10,
            },
            # A gene group: the dendrogram branch's genes go to Enrich.
            {
                "mouse": PANCREAS_ISLET_BRANCH,
                "relative_to": PANCREAS_CGM,
                "action": "click",
                "wait": 300,
            },
            {
                "mouse": [520, 60],
                "relative_to": ".widget-hbox",
                "steps": 4,
                "wait": 4000,
                "hold": 10,
            },
            # A term: its genes turn blue in the Clustergram.
            {"click": ".celldega-enrich svg text >> nth=0", "wait": 2500, "hold": 14},
        ],
        crop=".widget-hbox",
        settle_ms=15000,
        scale=1,
        fps=6,
        cursor=True,
        anim="webp",
    ),
    Capture(
        group="landscape-clustergram-enrich",
        name="single_cell_tabula",
        notebook_file=TABULA_NOTEBOOK,
        fit_widget=False,
        viewport=(1700, 1000),
        frames=[
            {"mouse": TS_SWIRL, "relative_to": TS_LS, "steps": 6, "wait": 400, "hold": 4},
            # Zoom in near the spermatids: the CELL and gene bars describe the view.
            *[
                {
                    "mouse": TS_SWIRL,
                    "relative_to": TS_LS,
                    "action": "wheel",
                    "delta": -100,
                    "wait": 450,
                }
                for _ in range(6)
            ],
            {"wait": 1500, "hold": 6},
            # Pan the spermatids to the center and show PRM1.
            {"mouse": TS_SWIRL, "relative_to": TS_LS, "action": "down", "wait": 60},
            *[
                {"mouse": [300, 185 + 19 * i], "relative_to": TS_LS, "steps": 2, "wait": 80}
                for i in range(1, 11)
            ],
            {"mouse": TS_CENTER, "relative_to": TS_LS, "action": "up", "wait": 800, "hold": 4},
            {"click": TS_GENE_SEARCH, "wait": 200},
            *[{"type": c, "wait": 120} for c in "PRM1"],
            {"key": "Enter", "wait": 2500, "hold": 6},
            # Zoom out: PRM1 is confined to the spermatids.
            *[
                {
                    "mouse": TS_CENTER,
                    "relative_to": TS_LS,
                    "action": "wheel",
                    "delta": 100,
                    "wait": 350,
                }
                for _ in range(6)
            ],
            {"wait": 1500, "hold": 8},
            # The interactive dendrogram: drag the column cut, then restore it.
            {"mouse": [40, 10], "relative_to": TS_COL_SLIDER, "action": "down", "wait": 200},
            *[
                {"mouse": [40 - 3 * i, 10], "relative_to": TS_COL_SLIDER, "steps": 2, "wait": 150}
                for i in range(1, 10)
            ],
            {"wait": 300, "hold": 4},
            *[
                {"mouse": [13 + 4 * i, 10], "relative_to": TS_COL_SLIDER, "steps": 2, "wait": 150}
                for i in range(1, 13)
            ],
            {"wait": 300, "hold": 4},
            *[
                {"mouse": [61 - 3 * i, 10], "relative_to": TS_COL_SLIDER, "steps": 2, "wait": 150}
                for i in range(1, 8)
            ],
            {"mouse": [40, 10], "relative_to": TS_COL_SLIDER, "action": "up", "wait": 900},
            # Column dendrogram branches: meta-clusters of cell types in the UMAP.
            {"mouse": [275, 636], "relative_to": TS_CGM, "steps": 8, "wait": 900, "hold": 4},
            {
                "mouse": [275, 636],
                "relative_to": TS_CGM,
                "action": "click",
                "wait": 2500,
                "hold": 6,
            },
            {"mouse": [170, 636], "relative_to": TS_CGM, "steps": 8, "wait": 900, "hold": 3},
            {
                "mouse": [170, 636],
                "relative_to": TS_CGM,
                "action": "click",
                "wait": 2500,
                "hold": 6,
            },
            # Double-click the spermatid column: genes ranked by spermatid expression,
            # spermatids selected, and their markers sent to Enrich.
            {"mouse": [378, 78], "relative_to": TS_CGM, "steps": 8, "wait": 300},
            {"mouse": [378, 78], "relative_to": TS_CGM, "action": "dblclick", "wait": 300},
            {"mouse": [300, 700], "relative_to": TS_CGM, "steps": 4, "wait": 3500, "hold": 8},
            # A top-ranked gene in the UMAP.
            *[
                {
                    "mouse": [40, 118],
                    "relative_to": TS_CGM,
                    "action": "wheel",
                    "delta": -100,
                    "wait": 400,
                }
                for _ in range(4)
            ],
            {"wait": 1200, "hold": 4},
            {
                "seek_click": "Row Label: PRM1",
                "at": [60, 110, 135],
                "relative_to": TS_CGM,
                "wait": 300,
            },
            {"mouse": [300, 700], "relative_to": TS_CGM, "steps": 4, "wait": 3500, "hold": 8},
            *[
                {
                    "mouse": [40, 118],
                    "relative_to": TS_CGM,
                    "action": "wheel",
                    "delta": 100,
                    "wait": 300,
                }
                for _ in range(5)
            ],
            # Another column: plasma cells and a new enrichment.
            {"mouse": [388, 78], "relative_to": TS_CGM, "steps": 8, "wait": 300},
            {"mouse": [388, 78], "relative_to": TS_CGM, "action": "click", "wait": 300},
            {"mouse": [300, 700], "relative_to": TS_CGM, "steps": 4, "wait": 4500, "hold": 14},
        ],
        crop=".widget-hbox",
        settle_ms=30000,
        scale=1,
        fps=6,
        cursor=True,
        anim="webp",
    ),
    # Landscape UMAP page.
    Capture(
        group="landscape/umap-xy",
        name="spatial_umap",
        # Kidney cells move between tissue and UMAP coordinates.
        notebook=KIDNEY_UMAP_NOTEBOOK,
        frames=[
            {"mouse": [440, 260], "relative_to": LS, "steps": 4, "wait": 300, "hold": 6},
            {"click_text": "UMAP", "within": "#panel-0", "wait": 80},
            *[{"wait": 120} for _ in range(14)],
            {"wait": 300, "hold": 12},
            {"click_text": "SPATIAL", "within": "#panel-0", "wait": 80},
            *[{"wait": 120} for _ in range(14)],
            {"wait": 3000, "hold": 12},
        ],
        settle_ms=20000,
        crop="#panel-0",
        scale=1,
        fps=8,
        cursor=True,
        anim="webp",
    ),
    Capture(
        group="landscape/umap-xy",
        name="viewport_estimates",
        # Zooming updates cell-type counts; gene bars become signature estimates.
        spec={"panels": [TABULA_LANDSCAPE]},
        frames=[
            {"mouse": [300, 300], "relative_to": LS, "steps": 6, "wait": 300, "hold": 6},
            *[
                {
                    "mouse": [300, 300],
                    "relative_to": LS,
                    "action": "wheel",
                    "delta": -60,
                    "wait": 500,
                }
                for _ in range(8)
            ],
            {"mouse": [40, 40], "relative_to": "#panel-0", "steps": 6, "wait": 1500, "hold": 14},
        ],
        settle_ms=25000,
        crop="#panel-0",
        scale=1,
        fps=6,
        cursor=True,
        anim="webp",
    ),
    Capture(
        group="landscape/umap-xy",
        name="pbmc_umap",
        spec={"panels": [PBMC3K_LANDSCAPE]},
        steps=[{"set_range": "#panel-0 .cell_container input.slider", "value": "max", "wait": 800}],
        annotate=LANDSCAPE_CALLOUTS,
        pad_top=30,
        settle_ms=6000,
        scale=1.6,
    ),
    Capture(
        group="landscape/umap-xy",
        name="pbmc_gene",
        # Color the UMAP by a monocyte marker.
        spec={"panels": [PBMC3K_LANDSCAPE]},
        frames=[
            {"mouse": [440, 260], "relative_to": LS, "steps": 4, "wait": 200, "hold": 4},
            {"click": GENE_SEARCH, "wait": 200},
            *[{"type": c, "wait": 120} for c in "LYZ"],
            {"key": "Enter", "wait": 2500, "hold": 6},
            # Larger cells and stronger expression opacity.
            {"set_range": "#panel-0 .cell_container input.slider", "value": "max", "wait": 600},
            {
                "set_range": "#panel-0 .trx_container input.slider",
                "value": "max",
                "wait": 1200,
                "hold": 14,
            },
        ],
        crop="#panel-0",
        settle_ms=6000,
        scale=1,
        fps=6,
        cursor=True,
        anim="webp",
    ),
    # Landscape neighborhoods page.
    Capture(
        group="landscape/neighborhoods",
        name="draw_tissue",
        spec={"panels": [kidney_landscape(**KIDNEY_GLOMERULUS, ini_zoom=-1.5, nbhd_edit=True)]},
        frames=[
            {"mouse": LS_CENTER, "relative_to": LS, "steps": 4, "wait": 200, "hold": 3},
            *draw_neighborhood(LS_CENTER, (175, 175), "glomerulus"),
        ],
        crop="#panel-0",
        settle_ms=12000,
        scale=1,
        fps=8,
        cursor=True,
        anim="webp",
    ),
    Capture(
        group="landscape/neighborhoods",
        name="draw_umap",
        spec={
            "panels": [
                {**PBMC3K_LANDSCAPE, "options": {**PBMC3K_LANDSCAPE["options"], "nbhd_edit": True}}
            ]
        },
        frames=[
            {"mouse": LS_CENTER, "relative_to": LS, "steps": 4, "wait": 200, "hold": 3},
            *draw_neighborhood((209, 257), (80, 150), "monocytes", sketch_key=True),
        ],
        crop="#panel-0",
        settle_ms=6000,
        scale=1,
        fps=8,
        cursor=True,
        anim="webp",
    ),
    # Clustergram guide: PBMC 3k marker genes of Leiden clusters.
    Capture(
        group="clustergram",
        name="overview",
        spec=pbmc_clustergram(),
        annotate=CLUSTERGRAM_CALLOUTS,
        pad_top=30,
        pad_left=34,
        settle_ms=3000,
    ),
    Capture(
        group="clustergram",
        name="matrix_tooltip",
        spec=pbmc_clustergram(),
        steps=[{"mouse": CGM_PPBP_CLUSTER_8, "relative_to": CGM, "wait": 800}],
        crop="#panel-0",
        settle_ms=3000,
    ),
    Capture(
        group="clustergram",
        name="gene_tooltip",
        spec=pbmc_clustergram(),
        steps=[{"mouse": CGM_PPBP_LABEL, "relative_to": CGM, "wait": 7000}],
        crop="#panel-0",
        clip=(0, 0, 680, 662),  # the tooltip extends past the panel
        settle_ms=3000,
    ),
    Capture(
        group="clustergram",
        name="dendrogram_slider",
        spec=pbmc_clustergram(),
        steps=[{"mouse": ROW_SLIDER_THUMB, "action": "down", "wait": 300}],
        # Drag the ROW cut lower (more groups), then higher (fewer), then release.
        frames=[
            {"mouse": ROW_SLIDER_THUMB, "action": "move", "wait": 100, "hold": 6},
            *[
                {"mouse": [x, 39], "action": "move", "steps": 2, "wait": 120}
                for x in range(124, 102, -3)
            ],
            {"mouse": [103, 39], "action": "move", "wait": 100, "hold": 6},
            *[
                {"mouse": [x, 39], "action": "move", "steps": 2, "wait": 120}
                for x in range(106, 170, 4)
            ],
            {"mouse": [169, 39], "action": "move", "wait": 100, "hold": 8},
            {"mouse": [169, 39], "action": "up", "wait": 900, "hold": 4},
        ],
        crop="#panel-0",
        settle_ms=3000,
        scale=1,
    ),
    Capture(
        group="clustergram",
        name="zoom_pan",
        spec=pbmc_clustergram(),
        # Scroll in (rows spread apart first, then both axes), drag to pan, and
        # scroll back out.
        frames=[
            {"mouse": [430, 360], "relative_to": CGM, "steps": 8, "wait": 100, "hold": 4},
            *[
                {
                    "mouse": [430, 360],
                    "relative_to": CGM,
                    "action": "wheel",
                    "delta": -25,
                    "wait": 120,
                }
                for _ in range(12)
            ],
            {"wait": 300, "hold": 6},
            {"mouse": [430, 360], "relative_to": CGM, "action": "down", "wait": 100},
            *[
                {"mouse": [430 - 15 * i, 360 - 20 * i], "relative_to": CGM, "steps": 2, "wait": 90}
                for i in range(1, 9)
            ],
            {"mouse": [310, 200], "relative_to": CGM, "action": "up", "wait": 300, "hold": 6},
            *[
                {
                    "mouse": [310, 200],
                    "relative_to": CGM,
                    "action": "wheel",
                    "delta": 40,
                    "wait": 120,
                }
                for _ in range(10)
            ],
            {"wait": 400, "hold": 8},
        ],
        crop="#panel-0",
        settle_ms=3000,
        scale=1,
        cursor=True,
    ),
    Capture(
        group="clustergram",
        name="reorder",
        spec=pbmc_clustergram(),
        # Double-click GZMB to sort the columns, sort the rows by SUM, then
        # restore the clustering order on both axes.
        frames=[
            {"mouse": [300, 300], "relative_to": CGM, "steps": 4, "wait": 80},
            {"mouse": CGM_GZMB_LABEL, "relative_to": CGM, "steps": 10, "wait": 120, "hold": 3},
            {"mouse": CGM_GZMB_LABEL, "relative_to": CGM, "action": "dblclick", "wait": 100},
            {"mouse": PANEL_BLANK, "steps": 4, "wait": 100},
            *[{"wait": 140} for _ in range(17)],
            {"wait": 300, "hold": 8},
            {"mouse": ROW_ORDER_DROPDOWN, "steps": 10, "wait": 120, "hold": 2},
            {"select": "#panel-0 .reorder-dropdown-row", "value": "rank", "wait": 150},
            *[{"wait": 140} for _ in range(18)],
            {"wait": 300, "hold": 8},
            {"mouse": COL_ORDER_DROPDOWN, "steps": 6, "wait": 120, "hold": 2},
            {"select": "#panel-0 .reorder-dropdown-col", "value": "clust", "wait": 100},
            {"select": "#panel-0 .reorder-dropdown-row", "value": "clust", "wait": 150},
            *[{"wait": 140} for _ in range(18)],
            {"wait": 300, "hold": 10},
        ],
        crop="#panel-0",
        settle_ms=3000,
        scale=1,
        fps=8,
        cursor=True,
    ),
    Capture(
        group="clustergram",
        name="dendrogram_branch",
        spec=pbmc_clustergram(),
        # Hover the platelet branch, click to select it, double-click to crop
        # to it, and double-click again to restore the rows.
        frames=[
            {"mouse": [430, 360], "relative_to": CGM, "steps": 4, "wait": 80},
            {"mouse": CGM_PLATELET_DENDRO, "relative_to": CGM, "steps": 10, "wait": 400, "hold": 8},
            {
                "mouse": CGM_PLATELET_DENDRO,
                "relative_to": CGM,
                "action": "click",
                "wait": 600,
                "hold": 10,
            },
            {"mouse": CGM_PLATELET_DENDRO, "relative_to": CGM, "action": "dblclick", "wait": 200},
            *[{"wait": 140} for _ in range(8)],
            {"mouse": PANEL_BLANK, "steps": 6, "wait": 300, "hold": 10},
            {"mouse": CGM_CROPPED_DENDRO, "relative_to": CGM, "steps": 8, "wait": 300},
            {"mouse": CGM_CROPPED_DENDRO, "relative_to": CGM, "action": "dblclick", "wait": 200},
            *[{"wait": 140} for _ in range(8)],
            {"mouse": PANEL_BLANK, "steps": 6, "wait": 300, "hold": 10},
        ],
        crop="#panel-0",
        settle_ms=3000,
        scale=1,
        cursor=True,
    ),
    Capture(
        group="clustergram",
        name="crop",
        spec=pbmc_clustergram(),
        # Click CROP, drag a rectangle over the matrix, then click UNDO.
        frames=[
            {"mouse": [430, 360], "relative_to": CGM, "steps": 4, "wait": 80},
            {"mouse": CROP_BUTTON, "steps": 10, "wait": 150, "hold": 2},
            {"click_text": "CROP", "within": "#panel-0", "wait": 300, "hold": 3},
            {"mouse": [76, 163], "relative_to": CGM, "steps": 10, "wait": 150, "hold": 2},
            {"mouse": [76, 163], "relative_to": CGM, "action": "down", "wait": 80},
            {"mouse": [77, 164], "relative_to": CGM, "steps": 1, "wait": 60},
            *[
                {
                    "mouse": [77 + 39.5 * i, 164 + 20.3 * i],
                    "relative_to": CGM,
                    "steps": 2,
                    "wait": 80,
                }
                for i in range(1, 13)
            ],
            {"mouse": [548, 408], "relative_to": CGM, "action": "up", "wait": 1500, "hold": 12},
            {"mouse": UNDO_BUTTON, "steps": 10, "wait": 150, "hold": 2},
            {"click_text": "UNDO", "within": "#panel-0", "wait": 1200, "hold": 10},
        ],
        crop="#panel-0",
        settle_ms=3000,
        scale=1,
        cursor=True,
    ),
    Capture(
        group="clustergram",
        name="dim_slider",
        spec=pbmc_clustergram(rank_dim=1),
        # DIM levels: 1, 3, 5, 10, 25, 50 markers per cluster, then back to 5.
        frames=[
            {
                "set_range": "#panel-0 .matrix_controls input.slider >> nth=2",
                "value": level,
                "wait": 1200,
                "hold": 9,
            }
            for level in [0, 1, 2, 3, 4, 5, 2]
        ],
        crop="#panel-0",
        settle_ms=3000,
        scale=1,
    ),
    Capture(
        group="clustergram",
        name="prop_unit",
        spec=pbmc_clustergram(),
        frames=[
            {"mouse": [430, 360], "relative_to": CGM, "steps": 4, "wait": 80, "hold": 4},
            {"mouse": UNIT_BUTTON, "steps": 10, "wait": 150, "hold": 2},
            {"click_text": "UNIT", "within": "#panel-0", "wait": 100},
            *[{"wait": 120} for _ in range(8)],
            {"wait": 300, "hold": 12},
            {"mouse": PROP_BUTTON, "steps": 6, "wait": 150, "hold": 2},
            {"click_text": "PROP", "within": "#panel-0", "wait": 100},
            *[{"wait": 120} for _ in range(8)],
            {"wait": 300, "hold": 12},
        ],
        crop="#panel-0",
        settle_ms=3000,
        scale=1,
        cursor=True,
    ),
    Capture(
        group="clustergram",
        name="search",
        spec=pbmc_clustergram(),
        # Type GZMB and press Enter, then search for CD79A.
        frames=[
            {"mouse": [430, 360], "relative_to": CGM, "steps": 4, "wait": 80},
            {"mouse": SEARCH_BOX, "steps": 10, "wait": 150, "hold": 2},
            {"click": "#panel-0 .search_logo_row input", "wait": 200},
            *[{"type": c, "wait": 150} for c in "GZMB"],
            {"key": "Enter", "wait": 100},
            *[{"wait": 120} for _ in range(8)],
            {"wait": 300, "hold": 12},
            {"click": "#panel-0 .search_logo_row input", "wait": 100},
            {"key": "Meta+A", "wait": 100},
            *[{"type": c, "wait": 150} for c in "LYZ"],
            {"key": "Enter", "wait": 100},
            *[{"wait": 120} for _ in range(8)],
            {"wait": 300, "hold": 12},
        ],
        crop="#panel-0",
        settle_ms=3000,
        scale=1,
        cursor=True,
    ),
]


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def serve_repo() -> tuple[ThreadingHTTPServer, int]:
    handler = functools.partial(_QuietHandler, directory=str(REPO))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, server.server_address[1]


def run_step(page: Page, step: dict) -> None:
    """Perform one declared interaction."""
    if "click_text" in step:
        scope = step.get("within", "#stage")
        page.locator(scope).get_by_text(step["click_text"], exact=True).first.click(
            modifiers=step.get("modifiers", [])
        )
    elif "click" in step:
        page.locator(step["click"]).first.click(modifiers=step.get("modifiers", []))
    elif "hover" in step:
        page.locator(step["hover"]).first.hover()
    elif "fill" in step:
        page.locator(step["fill"]).first.fill(step["value"])
        if step.get("enter"):
            page.keyboard.press("Enter")
    elif "select" in step:  # a <select> option by value
        page.locator(step["select"]).first.select_option(step["value"])
    elif "set_range" in step:  # an <input type=range>, as if dragged
        page.locator(step["set_range"]).first.evaluate(
            """(el, value) => {
                el.value = value === 'max' ? el.max : value;
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
            }""",
            str(step["value"]),
        )
    elif "mouse" in step:  # [x, y] relative to an element
        box = page.locator(step.get("relative_to", "#panel-0")).first.bounding_box()
        x, y = box["x"] + step["mouse"][0], box["y"] + step["mouse"][1]
        action = step.get("action", "move")
        if action == "move":
            page.mouse.move(x, y, steps=step.get("steps", 5))
        elif action == "click":  # e.g. "modifiers": ["Shift"] for shift-click
            for key in step.get("modifiers", []):
                page.keyboard.down(key)
            page.mouse.click(x, y)
            for key in step.get("modifiers", []):
                page.keyboard.up(key)
        elif action == "dblclick":
            page.mouse.dblclick(x, y)
        elif action == "down":
            page.mouse.move(x, y)
            page.mouse.down()
        elif action == "up":
            page.mouse.move(x, y, steps=step.get("steps", 5))
            page.mouse.up()
        elif action == "wheel":
            page.mouse.move(x, y)
            page.mouse.wheel(0, step["delta"])
    elif "seek_click" in step:
        # Slide down a column of pixels until the tooltip names the target, then
        # click there: for labels too small to place by coordinates alone.
        box = page.locator(step["relative_to"]).first.bounding_box()
        x, y0, y1 = step["at"]
        y = y0
        while y <= y1:
            page.mouse.move(box["x"] + x, box["y"] + y)
            page.wait_for_timeout(40)
            tip = page.evaluate(
                """() => [...document.querySelectorAll('.deck-tooltip')]
                    .filter(t => getComputedStyle(t).display !== 'none')
                    .map(t => t.innerText).join(' ')"""
            )
            if step["seek_click"] in tip:
                page.mouse.click(box["x"] + x, box["y"] + y)
                break
            y += 0.5
    elif "key" in step:
        page.keyboard.press(step["key"])
    elif "type" in step:  # keyboard input into the focused element
        page.keyboard.type(step["type"], delay=step.get("delay", 90))
    if "wait" in step:
        page.wait_for_timeout(step["wait"])


ANNOTATE_JS = """
(callouts) => {
  for (const c of callouts) {
    let el = document.querySelector(c.selector);
    if (!el) continue;
    if (c.parent) el = el.parentElement;
    const r = el.getBoundingClientRect();
    if (!r.width) continue;
    const badge = document.createElement('div');
    badge.textContent = c.label;
    Object.assign(badge.style, {
      position: 'absolute', zIndex: 10000, width: '20px', height: '20px',
      lineHeight: '20px', borderRadius: '50%', background: '#006DB6',
      color: '#fff', font: '700 12px system-ui, sans-serif', textAlign: 'center',
      boxShadow: '0 0 0 2px #fff, 0 1px 3px rgba(0,0,0,.4)',
    });
    let x = r.left + r.width / 2 - 10, y = r.top - 26;
    if (c.place === 'right') { x = r.right + 6; y = r.top + r.height / 2 - 10; }
    if (c.place === 'left') { x = r.left - 26; y = r.top + r.height / 2 - 10; }
    if (c.place === 'inside') { x = r.left + 10; y = r.top + 10; }
    if (c.place === 'at') { x = r.left + c.xy[0] - 10; y = r.top + c.xy[1] - 10; }
    badge.style.left = `${x + window.scrollX}px`;
    badge.style.top = `${y + window.scrollY}px`;
    document.body.appendChild(badge);
  }
}
"""


# A drawn pointer: follows the mouse, shows a filled ring while a button is held
# (dragging) and an open ring briefly after each scroll (zooming).
CURSOR_JS = """
() => {
  const pointer = document.createElement('div');
  pointer.innerHTML = '<svg width="20" height="24" viewBox="0 0 20 24">' +
    '<path d="M2 2 L2 19 L6.5 14.8 L9.6 21.5 L12.4 20.2 L9.4 13.6 L15.5 13.6 Z" ' +
    'fill="#111" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg>';
  Object.assign(pointer.style, {
    position: 'fixed', left: 0, top: 0, zIndex: 10001, pointerEvents: 'none', display: 'none',
  });
  const ring = document.createElement('div');
  Object.assign(ring.style, {
    position: 'absolute', left: '-9px', top: '-9px', width: '22px', height: '22px',
    borderRadius: '50%', border: '3px solid rgba(0, 109, 182, 0.85)',
    boxSizing: 'border-box', display: 'none',
  });
  pointer.prepend(ring);
  document.body.appendChild(pointer);
  let timer;
  const options = { capture: true, passive: true };
  window.addEventListener('mousemove', (e) => {
    pointer.style.display = 'block';
    pointer.style.transform = `translate(${e.clientX - 2}px, ${e.clientY - 2}px)`;
  }, options);
  window.addEventListener('mousedown', () => {
    ring.style.background = 'rgba(0, 109, 182, 0.25)';
    ring.style.display = 'block';
  }, options);
  window.addEventListener('mouseup', () => { ring.style.display = 'none'; }, options);
  window.addEventListener('wheel', () => {
    ring.style.background = 'none';
    ring.style.display = 'block';
    clearTimeout(timer);
    timer = setTimeout(() => { ring.style.display = 'none'; }, 400);
  }, options);
}
"""


def screenshot(page: Page, item: Capture, path: Path) -> None:
    """Capture the `crop` element, or the `clip` region within it."""
    if item.clip:
        box = page.locator(item.crop).first.bounding_box()
        x, y, w, h = item.clip
        page.screenshot(
            path=str(path), clip={"x": box["x"] + x, "y": box["y"] + y, "width": w, "height": h}
        )
    else:
        page.locator(item.crop).screenshot(path=str(path))


CACHE = Path(__file__).resolve().parent / ".cache"
JUPYTER = Path(os.environ.get("DEGA_JUPYTER", REPO / "dega" / "bin" / "jupyter"))


def notebook_html(code: str) -> Path:
    """Run `code` as a notebook in the dega env and export it as HTML with widget state.

    Widgets built in Python (for example a Landscape with an AnnData's UMAP)
    render from the saved state without a kernel, as in the documentation.
    With CELLDEGA_ESM_VERSION set (e.g. 0.28.0), widgets load that published
    bundle from jsdelivr; otherwise each widget inlines the local bundle (about
    12 MB per widget), for capturing unreleased changes. Results are cached by
    code and bundle, so captures that share a notebook run it once.
    """
    CACHE.mkdir(exist_ok=True)
    esm_version = os.environ.get("CELLDEGA_ESM_VERSION")
    env = {**os.environ}
    if not esm_version:
        env["CELLDEGA_LOCAL_ESM"] = "1"
    key = f"{code}\n# esm: {esm_version or 'local'}"
    name = "nb_" + hashlib.sha1(key.encode()).hexdigest()[:12]
    html = CACHE / f"{name}.html"
    if html.exists():
        return html
    notebook = {
        "cells": [
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": code,
            }
        ],
        "metadata": {
            "kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"}
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    source = CACHE / f"{name}.ipynb"
    source.write_text(json.dumps(notebook))
    subprocess.run(
        [
            str(JUPYTER),
            "nbconvert",
            "--to",
            "html",
            "--execute",
            "--ExecutePreprocessor.timeout=1800",
            "--ExecutePreprocessor.iopub_timeout=300",
            "--output-dir",
            str(CACHE),
            "--output",
            name,
            str(source),
        ],
        check=True,
        cwd=CACHE,
        env=env,
    )
    return html


def executed_notebook_html(path: str) -> Path:
    """Export an executed notebook, with its saved widget state, to HTML."""
    source = REPO / path
    CACHE.mkdir(exist_ok=True)
    name = "file_" + hashlib.sha1(source.read_bytes()).hexdigest()[:12]
    html = CACHE / f"{name}.html"
    if not html.exists():
        subprocess.run(
            [
                str(JUPYTER),
                "nbconvert",
                "--to",
                "html",
                "--output-dir",
                str(CACHE),
                "--output",
                name,
                str(source),
            ],
            check=True,
        )
    return html


def capture(page: Page, port: int, item: Capture) -> Path:
    width, height = item.viewport
    if item.notebook or item.notebook_file:  # room beyond the widget's own width
        width = max(width, 1200)
    page.set_viewport_size({"width": width, "height": height})
    if item.notebook or item.notebook_file:
        html = (
            executed_notebook_html(item.notebook_file)
            if item.notebook_file
            else notebook_html(item.notebook)
        ).relative_to(REPO)
        page.goto(f"http://127.0.0.1:{port}/{html}")
        page.wait_for_selector(".ui_container, .celldega-enrich", timeout=300_000)
        # Show only the widget: hide code, prompts, and page margins.
        page.add_style_tag(
            content=".jp-InputArea, .jp-InputPrompt, .jp-OutputPrompt { display: none !important; }"
            " body, .jp-Notebook, .jp-Cell, .jp-OutputArea-output { margin: 0 !important;"
            " padding: 0 !important; }"
        )
        # Name the widget like viewer.html panels, so selectors are shared.
        page.evaluate(
            """(fit) => {
                const widget =
                    document.querySelector('.ui_container') ||
                    document.querySelector('.celldega-enrich');
                const root = widget.parentElement;
                root.id = 'panel-0';
                if (fit) root.style.width = '880px';  // the map fills its container here
                root.parentElement.id = 'stage';
            }""",
            item.fit_widget,
        )
        page.add_style_tag(
            content=f"#stage {{ padding-top: {item.pad_top}px; padding-left: {item.pad_left}px; }}"
        )
    else:
        url = f"http://127.0.0.1:{port}/{VIEWER}?spec={quote(json.dumps(item.spec))}"
        page.goto(url)
        page.add_style_tag(
            content=f"#stage {{ padding-top: {item.pad_top}px; padding-left: {item.pad_left}px; }}"
        )
        page.wait_for_function("window.__dega_ready || window.__dega_error", timeout=180_000)
        error = page.evaluate("window.__dega_error")
        if error:
            raise RuntimeError(f"{item.group}/{item.name}: {error}")
    page.locator(item.crop).first.evaluate("el => el.scrollIntoView({block: 'start'})")
    page.wait_for_timeout(item.settle_ms)
    if item.cursor:
        page.evaluate(CURSOR_JS)
    for step in item.steps:
        run_step(page, step)
    if item.annotate:
        page.evaluate(ANNOTATE_JS, item.annotate)

    item.path.parent.mkdir(parents=True, exist_ok=True)
    if item.frames:
        return capture_gif(page, item)
    png = item.path.with_suffix(".png")
    screenshot(page, item, png)
    # WebP keeps dense tissue screenshots within the size budget.
    subprocess.run(
        ["magick", str(png), "-strip", "-quality", str(item.quality or 80), str(item.path)],
        check=True,
    )
    png.unlink()
    return item.path


def capture_gif(page: Page, item: Capture) -> Path:
    """One frame per step (a step's `hold` repeats its frame), then a GIF."""
    # Every frame uses the first frame's region: panels can grow as their
    # text changes, and frames of different sizes break the animation.
    page.locator(item.crop).first.evaluate("el => el.scrollIntoView({block: 'start'})")
    box = page.locator(item.crop).first.bounding_box()
    if item.clip:
        x, y, w, h = item.clip
        box = {"x": box["x"] + x, "y": box["y"] + y, "width": w, "height": h}
    with tempfile.TemporaryDirectory() as tmp:
        count = 0
        for step in item.frames:
            run_step(page, step)
            frame = Path(tmp) / f"frame_{count:04d}.png"
            page.screenshot(path=str(frame), clip=box)
            count += 1
            for _ in range(step.get("hold", 0)):
                shutil.copy(frame, Path(tmp) / f"frame_{count:04d}.png")
                count += 1
        # ImageMagick: delay is in hundredths of a second. GIF keeps only the
        # pixels that change between frames; animated WebP suits tissue images.
        frames = sorted(str(f) for f in Path(tmp).glob("frame_*.png"))
        delay = ["-delay", str(round(100 / item.fps)), "-loop", "0"]
        if item.anim == "webp":
            options = ["-quality", str(item.quality or 70), "-define", "webp:method=6"]
        else:
            options = ["-layers", "Optimize"]
        subprocess.run(["magick", *delay, *frames, *options, str(item.path)], check=True)
    return item.path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", help="capture only this group (docs page)")
    parser.add_argument("--name", help="capture only this image name")
    parser.add_argument("--list", action="store_true", help="list captures")
    parser.add_argument("--headed", action="store_true", help="show the browser")
    args = parser.parse_args()

    items = [
        c
        for c in CAPTURES
        if (not args.only or c.group == args.only) and (not args.name or c.name == args.name)
    ]
    if args.list:
        for c in items:
            print(f"{c.group}/{c.name}")
        return

    server, port = serve_repo()
    over_budget = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                channel="chrome", headless=not args.headed, args=["--use-angle=metal"]
            )
            # Gene lookups (EBI Proteins API) reject the headless user agent.
            probe = browser.new_page()
            user_agent = probe.evaluate("navigator.userAgent").replace("HeadlessChrome", "Chrome")
            probe.close()
            for item in items:
                # A fresh page per capture: no state carries between images.
                page = browser.new_page(device_scale_factor=item.scale, user_agent=user_agent)
                path = capture(page, port, item)
                page.close()
                size = path.stat().st_size
                limit = MAX_GIF_BYTES if item.frames else MAX_IMAGE_BYTES
                flag = "" if size <= limit else "  OVER BUDGET"
                if flag:
                    over_budget.append(path)
                print(f"{path.relative_to(REPO)}  {size / 1000:.0f} KB{flag}")
            browser.close()
    finally:
        server.shutdown()
    if over_budget:
        raise SystemExit(f"{len(over_budget)} image(s) over the size budget")


if __name__ == "__main__":
    main()
