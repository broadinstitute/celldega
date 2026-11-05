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
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
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
MAX_GIF_BYTES = 2_000_000

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
    spec: dict  # viewer.html spec: panels and links
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

    @property
    def path(self) -> Path:
        suffix = "gif" if self.frames else "webp"
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
            *[{"type": c, "wait": 150} for c in "CD79A"],
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
    elif "fill" in step:
        page.locator(step["fill"]).first.fill(step["value"])
        if step.get("enter"):
            page.keyboard.press("Enter")
    elif "select" in step:  # a <select> option by value
        page.locator(step["select"]).first.select_option(step["value"])
    elif "set_range" in step:  # an <input type=range>, as if dragged
        page.locator(step["set_range"]).first.evaluate(
            """(el, value) => {
                el.value = value;
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


def capture(page: Page, port: int, item: Capture) -> Path:
    url = f"http://127.0.0.1:{port}/{VIEWER}?spec={quote(json.dumps(item.spec))}"
    page.set_viewport_size({"width": item.viewport[0], "height": item.viewport[1]})
    page.goto(url)
    page.add_style_tag(
        content=f"#stage {{ padding-top: {item.pad_top}px; padding-left: {item.pad_left}px; }}"
    )
    page.wait_for_function("window.__dega_ready || window.__dega_error", timeout=180_000)
    error = page.evaluate("window.__dega_error")
    if error:
        raise RuntimeError(f"{item.group}/{item.name}: {error}")
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
    subprocess.run(["magick", str(png), "-strip", "-quality", "80", str(item.path)], check=True)
    png.unlink()
    return item.path


def capture_gif(page: Page, item: Capture) -> Path:
    """One frame per step (a step's `hold` repeats its frame), then a GIF."""
    with tempfile.TemporaryDirectory() as tmp:
        count = 0
        for step in item.frames:
            run_step(page, step)
            frame = Path(tmp) / f"frame_{count:04d}.png"
            screenshot(page, item, frame)
            count += 1
            for _ in range(step.get("hold", 0)):
                shutil.copy(frame, Path(tmp) / f"frame_{count:04d}.png")
                count += 1
        # ImageMagick: delay is in hundredths of a second; Optimize keeps only
        # the pixels that change between frames.
        subprocess.run(
            [
                "magick",
                "-delay",
                str(round(100 / item.fps)),
                "-loop",
                "0",
                *sorted(str(f) for f in Path(tmp).glob("frame_*.png")),
                "-layers",
                "Optimize",
                str(item.path),
            ],
            check=True,
        )
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
                limit = MAX_GIF_BYTES if path.suffix == ".gif" else MAX_IMAGE_BYTES
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
