"""Stage 1 of the storyboard -> figure pipeline: capture every panel.

For each panel of a storyboard, render it with Celldega's web API in headless Chrome
(figures/tools/capture.html), apply its view, and save from the same render:

- ``captures/<panel>.png``: the screenshot the reader sees (the whole widget, its
  map, or its controls, as the panel's ``shot`` says), at 2x;
- ``captures/<panel>.snapshot.png``: a Celldega screenshot PNG carrying the saved
  view, which ``dega.viz.from_png`` reopens (reproducibility);

and record both in ``manifest.json``. This is the only stage that touches widgets:
rewording or relaying out the figure (compose.py) never needs a recapture.

    python figures/tools/capture.py figures/storyboards/hcrc.yaml [--panels a1 c2]

Needs Playwright (``uv run --with playwright --with pyyaml python ...``) and Chrome.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
from datetime import UTC, datetime
import functools
import http.server
import json
import math
from pathlib import Path
import threading

import yaml


REPO = Path(__file__).resolve().parents[2]


def build_dir(story: dict) -> Path:
    return REPO / "figures/build" / story["id"]


def load(storyboard: Path) -> tuple[dict, dict]:
    story = yaml.safe_load(storyboard.read_text())
    facts_path = build_dir(story) / "data/facts.json"
    facts = json.loads(facts_path.read_text()) if facts_path.exists() else {}
    return story, facts


def camera(view: dict, size: list[int]) -> dict:
    """A {target, zoom} camera: as given, or framing a box [x0, y0, x1, y1] (data
    coordinates) in a panel of this size (zoom: screen pixels per unit, log2)."""
    if "box" not in view:
        return view
    x0, y0, x1, y1 = view["box"]
    width, height = size
    zoom = math.log2(min(width / (x1 - x0), height / (y1 - y0))) - view.get("pad", 0.05)
    return {"target": [(x0 + x1) / 2, (y0 + y1) / 2], "zoom": round(zoom, 3)}


def panel_spec(story: dict, facts: dict, panel: dict) -> dict:
    """What capture.html needs to render a panel."""
    view = panel.get("view", "tissue")
    if isinstance(view, str):
        view = story.get("views", {}).get(view) or facts["views"][view]
    view = camera(view, panel.get("size", [480, 420]))
    data = f"/figures/build/{story['id']}/data"
    spec = {
        "widget": panel["widget"],
        "size": panel.get("size", [480, 420]),
        "view": view,
        "data": data,
        "base_url": story.get("base_url", ""),
        "technology": story.get("technology", "Xenium"),
        "labels": panel.get("labels"),
        "changes": panel.get("changes") or {},
        "settle_ms": panel.get("settle_ms", 6000 if panel["widget"] == "landscape" else 2500),
    }
    for key in ("matrix", "rank_dim", "manual_cat", "highlighted_cols", "library", "num_terms"):
        if key in panel:
            spec[key] = panel[key]
    if panel["widget"] == "enrich":
        genes = panel.get("genes")
        spec["genes"] = facts[genes] if isinstance(genes, str) else list(genes or [])
    return spec


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args) -> None:  # one line per panel is enough
        pass


def serve(root: Path) -> tuple[http.server.ThreadingHTTPServer, int]:
    handler = functools.partial(_QuietHandler, directory=str(root))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, server.server_address[1]


async def capture(storyboard: Path, only: list[str] | None = None) -> Path:
    from playwright.async_api import async_playwright

    story, facts = load(storyboard)
    out = build_dir(story)
    captures = out / "captures"
    captures.mkdir(parents=True, exist_ok=True)
    manifest_path = out / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    server, port = serve(REPO)
    url = f"http://127.0.0.1:{port}/figures/tools/capture.html"
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(channel="chrome", headless=True)
            context = await browser.new_context(
                viewport={"width": 1800, "height": 1400}, device_scale_factor=2
            )
            for row in story["rows"]:
                for panel in row["panels"]:
                    if only and panel["id"] not in only:
                        continue
                    page = await context.new_page()
                    errors: list[str] = []
                    page.on("pageerror", lambda error, errors=errors: errors.append(str(error)))
                    await page.goto(url, wait_until="domcontentloaded")
                    await page.wait_for_function("window.capture_ready === true", timeout=60000)
                    spec = panel_spec(story, facts, panel)
                    await page.evaluate("spec => window.render_panel(spec)", spec)
                    shot = panel.get("shot", "canvas")
                    target = page.locator(
                        f'#panel [data-shot="{shot}"], #panel[data-shot="{shot}"]'
                    )
                    image = captures / f"{panel['id']}.png"
                    await target.first.screenshot(path=str(image))
                    snapshot = await page.evaluate(
                        "([t, d]) => window.panel_snapshot(t, d)",
                        [panel.get("title", panel["id"]), panel.get("insight", "")],
                    )
                    entry = {
                        "screenshot": image.name,
                        "shot": shot,
                        "spec": spec,
                        "captured_at": datetime.now(UTC).isoformat(timespec="seconds"),
                        "errors": errors,
                    }
                    if snapshot:
                        path = captures / f"{panel['id']}.snapshot.png"
                        path.write_bytes(base64.b64decode(snapshot["png"]))
                        entry["snapshot"] = path.name
                        entry["identity"] = snapshot.get("identity")
                    manifest[panel["id"]] = entry
                    status = "errors: " + "; ".join(errors) if errors else "ok"
                    print(f"{panel['id']}: {image.name} ({status})", flush=True)
                    await page.close()
            await browser.close()
    finally:
        server.shutdown()
    manifest_path.write_text(json.dumps(manifest, indent=2))
    return manifest_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("storyboard", type=Path)
    parser.add_argument("--panels", nargs="*", help="only these panel ids")
    args = parser.parse_args()
    print(asyncio.run(capture(args.storyboard, args.panels)))


if __name__ == "__main__":
    main()
