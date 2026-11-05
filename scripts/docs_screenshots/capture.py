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
import subprocess
import threading
from urllib.parse import quote

from playwright.sync_api import Page, sync_playwright


REPO = Path(__file__).resolve().parents[2]
OUT_DIR = REPO / "docs" / "assets" / "img" / "visualizations"
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

    @property
    def path(self) -> Path:
        return OUT_DIR / self.group / f"{self.name}.webp"


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
    elif "mouse" in step:  # [x, y] relative to an element
        box = page.locator(step.get("relative_to", "#panel-0")).first.bounding_box()
        x, y = box["x"] + step["mouse"][0], box["y"] + step["mouse"][1]
        action = step.get("action", "move")
        if action == "move":
            page.mouse.move(x, y, steps=5)
        elif action == "click":
            page.mouse.click(x, y)
        elif action == "wheel":
            page.mouse.move(x, y)
            page.mouse.wheel(0, step["delta"])
    elif "key" in step:
        page.keyboard.press(step["key"])
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
    if (c.place === 'inside') { x = r.left + 10; y = r.top + 10; }
    badge.style.left = `${x + window.scrollX}px`;
    badge.style.top = `${y + window.scrollY}px`;
    document.body.appendChild(badge);
  }
}
"""


def capture(page: Page, port: int, item: Capture) -> Path:
    url = f"http://127.0.0.1:{port}/{VIEWER}?spec={quote(json.dumps(item.spec))}"
    page.set_viewport_size({"width": item.viewport[0], "height": item.viewport[1]})
    page.goto(url)
    page.add_style_tag(content=f"#stage {{ padding-top: {item.pad_top}px; }}")
    page.wait_for_function("window.__dega_ready || window.__dega_error", timeout=180_000)
    error = page.evaluate("window.__dega_error")
    if error:
        raise RuntimeError(f"{item.group}/{item.name}: {error}")
    page.wait_for_timeout(item.settle_ms)
    for step in item.steps:
        run_step(page, step)
    if item.annotate:
        page.evaluate(ANNOTATE_JS, item.annotate)

    item.path.parent.mkdir(parents=True, exist_ok=True)
    png = item.path.with_suffix(".png")
    page.locator(item.crop).screenshot(path=str(png))
    # WebP keeps dense tissue screenshots within the size budget.
    subprocess.run(["magick", str(png), "-strip", "-quality", "80", str(item.path)], check=True)
    png.unlink()
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
            for item in items:
                # A fresh page per capture: no state carries between images.
                page = browser.new_page(device_scale_factor=item.scale)
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
