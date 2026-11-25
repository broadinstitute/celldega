"""Stage 1 of the storyboard -> figure pipeline: capture every panel.

For each panel of a storyboard, render it with Celldega's web API in headless Chrome
(figures/tools/capture.html), apply its view, run its ``actions`` (clicks, as a
reader would make them), and save from the same render:

- ``captures/<panel>.png``: the screenshot the reader sees (the whole widget, its
  map, or its controls, as the panel's ``shot`` says), at 2x;
- ``captures/<panel>.snapshot.png``: a Celldega screenshot PNG carrying the saved
  view, which ``dega.viz.from_png`` reopens (reproducibility);

and record both in ``manifest.json``, with the panel's ``geometry``: where its map
or matrix sits in the screenshot, so the composed figure can draw locator boxes and
arrows onto it. This is the only stage that touches widgets: rewording or relaying
out the figure (compose.py) never needs a recapture.

    python figures/tools/capture.py figures/storyboards/hcrc.yaml [--panels a1 c2]

Needs Playwright, NumPy and Pillow (``uv run --with playwright --with pyyaml
--with numpy --with pillow python ...``) and Chrome.
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
import re
import threading

import numpy as np
from PIL import Image
import yaml


REPO = Path(__file__).resolve().parents[2]
SCALE = 2  # device pixels per CSS pixel in the captures


def build_dir(story: dict) -> Path:
    return REPO / "figures/build" / story["id"]


def load(storyboard: Path) -> tuple[dict, dict]:
    story = yaml.safe_load(storyboard.read_text())
    facts_path = build_dir(story) / "data/facts.json"
    facts = json.loads(facts_path.read_text()) if facts_path.exists() else {}
    return story, facts


def all_panels(story: dict) -> list[dict]:
    """Panels rendered by a widget (not copies of another panel or static art)."""
    return [panel for row in story["rows"] for panel in row["panels"] if "widget" in panel]


def camera(view: dict, size: list[int]) -> dict:
    """A {target, zoom} camera: as given, or framing a box [x0, y0, x1, y1] (data
    coordinates) in a panel of this size (zoom: screen pixels per unit, log2)."""
    if "box" not in view:
        return view
    x0, y0, x1, y1 = view["box"]
    width, height = size
    zoom = math.log2(min(width / (x1 - x0), height / (y1 - y0))) - view.get("pad", 0.05)
    return {"target": [(x0 + x1) / 2, (y0 + y1) / 2], "zoom": round(zoom, 3)}


def from_facts(value, facts: dict):
    """A storyboard value, or the facts.json entry it names ("facts.plasma.cells")."""
    if isinstance(value, str) and value.startswith("facts."):
        node = facts
        for key in value.split(".")[1:]:
            node = node[key]
        return node
    return value


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
        "settle_ms": panel.get("settle_ms", 6000 if panel["widget"] != "enrich" else 4000),
    }
    for key in (
        "matrix",
        "rank_dim",
        "manual_cat",
        "highlighted_cols",
        "library",
        "num_terms",
        "num_rows",
        "num_cols",
        "portrait_size_um",
        "portrait_gap",
        "focused_gene",
        "zoom_to_focus",
        "max_tiles_to_view",
        "intermediate_zoom_limit",
        "front_end_query",
        "microns_per_pixel",
        "label_sets",
        "cell_attribute",
    ):
        if key in panel:
            spec[key] = from_facts(panel[key], facts)
    if panel.get("label_set"):
        # Cells shown (and the bars counted) by cluster labels, e.g. the cell types
        # annotated in a Clustergram: {name, values: {cluster: label}, colors}.
        labeling = panel["label_set"]
        spec["label_sets"] = {
            labeling["name"]: {"labels": labeling["values"], "colors": labeling["colors"]}
        }
        spec["cell_attribute"] = labeling["name"]
    if panel["widget"] == "enrich":
        genes = panel.get("genes")
        spec["genes"] = facts[genes] if isinstance(genes, str) else list(genes or [])
    if panel["widget"] == "yearbook":
        spec["cells"] = from_facts(panel.get("cells", []), facts)
        spec["genes"] = list(panel.get("genes") or [])
    return spec


def link_from(panel: dict, spec: dict, manifest: dict) -> None:
    """Carry a linked panel's state over: an Enrich term's genes turn blue in a
    Clustergram, and the gene clicked in Enrich turns bold (``linked_to``)."""
    source = panel.get("linked_to")
    if not source or source not in manifest:
        return
    state = manifest[source].get("state") or {}
    if state.get("term_genes"):
        spec["highlighted_genes"] = state["term_genes"]
    if state.get("focused_gene") and "focused_gene" not in spec:
        spec["focused_gene"] = state["focused_gene"]


def capture_order(panels: list[dict]) -> list[dict]:
    """Panels, with each linked panel after the panel it is linked to."""
    ids = {panel["id"] for panel in panels}
    first = [p for p in panels if p.get("linked_to") not in ids]
    return first + [p for p in panels if p.get("linked_to") in ids]


# --- Geometry: where things sit in a screenshot (fractions of its width/height) ---


def _runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """Start and end (exclusive) of each run of True in a 1-D mask."""
    padded = np.concatenate([[False], mask, [False]])
    edges = np.flatnonzero(np.diff(padded.astype(np.int8)))
    return list(zip(edges[0::2], edges[1::2], strict=True))


def _span(mask: np.ndarray, max_gap: int = 6) -> tuple[int, int, float]:
    """The longest stretch of True allowing gaps of up to max_gap, and how much of
    it is True."""
    best = (0, 0, 0.0)
    runs = _runs(mask)
    i = 0
    while i < len(runs):
        start, end = runs[i]
        covered = end - start
        j = i
        while j + 1 < len(runs) and runs[j + 1][0] - runs[j][1] <= max_gap:
            j += 1
            covered += runs[j][1] - runs[j][0]
            end = runs[j][1]
        if end - start > best[1] - best[0]:
            best = (int(start), int(end), covered / (end - start))
        i = j + 1
    return best


def matrix_box(image: np.ndarray, region: tuple[int, int, int, int]) -> tuple[int, ...]:
    """A Clustergram's matrix, in screenshot pixels: the extent of its category
    strips and dendrograms, the longest unbroken bands next to the matrix."""
    # Skip the frame's own border lines: they run the full width or height.
    edge = 6
    x0, y0, x1, y1 = region[0] + edge, region[1] + edge, region[2] - edge, region[3] - edge
    crop = image[y0:y1, x0:x1]
    ink = crop.min(axis=2) < 232
    height, width = ink.shape

    def score(span, extent):
        length = span[1] - span[0]
        return length * (span[2] > 0.85) * (length < 0.97 * extent)

    rows = [_span(ink[y]) for y in range(height)]
    cols = [_span(ink[:, x]) for x in range(width)]
    h = max(rows, key=lambda r: score(r, width))
    v = max(cols, key=lambda c: score(c, height))
    return (x0 + h[0], y0 + v[0], x0 + h[1], y0 + v[1])


def label_extent(image: np.ndarray, region, mx0: int, n_rows: int) -> tuple[int, int]:
    """Top and bottom of a matrix's rows from its row labels' ink (the first label's
    top sits a little below its row's top, the last label's bottom a little above)."""
    x0 = max(region[0], mx0 - int(0.08 * (region[2] - region[0])))
    strip = image[region[1] : region[3], x0 : mx0 - 3]
    ys = np.flatnonzero((strip.min(axis=2) < 120).any(axis=1))
    if not ys.size:
        return region[1], region[3]
    top, bottom = region[1] + int(ys[0]), region[1] + int(ys[-1])
    row_h = (bottom - top) / max(n_rows - 0.3, 1)
    return int(top - 0.15 * row_h), int(bottom + 0.15 * row_h)


def _gray(pixel: np.ndarray) -> bool:
    return bool(abs(int(pixel[0]) - 165) < 14 and np.ptp(pixel.astype(int)) < 8)


def clustergram_geometry(png: Path, canvas: tuple[float, ...], state: dict) -> dict:
    """Fractions locating a Clustergram's rows, columns and dendrogram groups."""
    image = np.asarray(Image.open(png).convert("RGB"))
    height, width = image.shape[:2]
    region = (
        int(canvas[0] * width),
        int(canvas[1] * height),
        int(canvas[2] * width),
        int(canvas[3] * height),
    )
    mx0, my0, mx1, my1 = matrix_box(image, region)
    rows = state["rows"]["names"]
    cols = state["cols"]["names"]
    if my1 - my0 < 0.3 * (region[3] - region[1]) and rows:
        # No row dendrogram or attribute strip to measure (e.g. rows ranked by a
        # column): take the rows' extent from their labels, left of the matrix.
        my0, my1 = label_extent(image, region, mx0, len(rows))
    row_h = (my1 - my0) / max(len(rows), 1)
    col_w = (mx1 - mx0) / max(len(cols), 1)

    def row_end(y: int) -> int:
        """Right end of a row: past the row dendrogram, if it is drawn."""
        x, gap = mx1, 0
        while x < region[2] - 1 and gap < 4:
            x += 1
            gap = 0 if _gray(image[y, x]) else gap + 1
        return x - gap

    def band_bottom(x: int) -> int:
        """Bottom of the column dendrogram under a column."""
        y, gap, last = my1, 0, my1
        while y < region[3] - 1 and gap < 6:
            y += 1
            if _gray(image[y, x]):
                last, gap = y, 0
            else:
                gap += 1
        return last

    def strip_top(x: int) -> int:
        """Top of the column category strips above a column."""
        y = my0 - 1
        while y > region[1] and image[y, x].min() < 232:
            y -= 1
        return y

    row_pos = {}
    for i, name in enumerate(rows):
        y = int(my0 + (i + 0.5) * row_h)
        row_pos[name] = {
            "y": y / height,
            "x_matrix": mx1 / width,
            "x_end": row_end(y) / width,
            "x_start": mx0 / width,
        }
    col_pos = {}
    for j, name in enumerate(cols):
        x = int(mx0 + (j + 0.5) * col_w)
        col_pos[name] = {"x": x / width, "y_top": strip_top(x) / height, "y_matrix": my0 / height}
    groups = []
    for group in (state["cols"].get("groups") or {}).get("groups", []):
        slots = [cols.index(m) for m in group["members"] if m in cols]
        if not slots:
            continue
        left, right = mx0 + min(slots) * col_w, mx0 + (max(slots) + 1) * col_w
        mid = int((left + right) / 2)
        groups.append(
            {
                "members": group["members"],
                "x0": left / width,
                "x1": right / width,
                "x": mid / width,
                "y": band_bottom(mid) / height,
            }
        )
    return {
        "kind": "clustergram",
        "matrix": [mx0 / width, my0 / height, mx1 / width, my1 / height],
        "rows": row_pos,
        "cols": col_pos,
        "groups": groups,
        "order": {"row": state["rows"].get("order"), "col": state["cols"].get("order")},
    }


def col_label_point(png: Path, geometry: dict, name: str) -> tuple[float, float]:
    """A point on a column's label (fractions of the screenshot): the label starts
    just above its column and runs up to the right, so take its lowest dark pixels."""
    image = np.asarray(Image.open(png).convert("RGB"))
    height, width = image.shape[:2]
    mx0, _, mx1, _ = geometry["matrix"]
    col_w = (mx1 - mx0) * width / len(geometry["cols"])
    col = geometry["cols"][name]
    cx, top = col["x"] * width, int(col["y_top"] * height)
    x0, x1 = max(int(cx - 0.4 * col_w), 0), min(int(cx + 0.6 * col_w), width)
    for y in range(top - 1, max(top - 160, 0), -1):
        dark = np.flatnonzero(image[y, x0:x1].max(axis=1) < 110)
        if dark.size:
            return (x0 + float(dark.mean())) / width, (y - 2) / height
    return cx / width, (top - 14) / height


def fraction_box(box: dict, frame: dict) -> list[float]:
    return [
        (box["x"] - frame["x"]) / frame["width"],
        (box["y"] - frame["y"]) / frame["height"],
        (box["x"] + box["width"] - frame["x"]) / frame["width"],
        (box["y"] + box["height"] - frame["y"]) / frame["height"],
    ]


async def run_actions(page, actions: list[dict], scratch: Path) -> dict:
    """A panel's clicks and changes, in order; returns marked elements' boxes (page
    pixels) by mark name."""
    marks = {}
    for action in actions:
        if "click_text" in action:
            text = action["click_text"]
            pattern = re.compile(text) if action.get("regex") else text
            locator = page.locator(f"#panel {action.get('within', '*')}", has_text=pattern).first
            await locator.click()
            if action.get("mark"):
                marks[action["mark"]] = await locator.bounding_box()
        elif "dblclick_col" in action:
            # Double-click a column label: the Clustergram ranks its rows by that
            # column. Find the label from the matrix's geometry in a first shot.
            canvas = page.locator('#panel [data-shot="canvas"]').first
            await canvas.screenshot(path=str(scratch))
            frame = await canvas.bounding_box()
            state = await page.evaluate("() => window.panel_state('clustergram')")
            geometry = clustergram_geometry(scratch, (0, 0, 1, 1), state)
            fx, fy = col_label_point(scratch, geometry, action["dblclick_col"])
            await page.mouse.dblclick(
                frame["x"] + fx * frame["width"], frame["y"] + fy * frame["height"]
            )
            scratch.unlink(missing_ok=True)
        elif "click_button" in action:
            # A widget control by its label, e.g. the TRX button.
            await (
                page.locator("#panel").get_by_text(action["click_button"], exact=True).first.click()
            )
        elif "click_cat" in action:
            # Click a column's attribute cell (the strip just above the matrix):
            # the Clustergram opens its category form for that column.
            canvas = page.locator('#panel [data-shot="canvas"]').first
            await canvas.screenshot(path=str(scratch))
            frame = await canvas.bounding_box()
            state = await page.evaluate("() => window.panel_state('clustergram')")
            geometry = clustergram_geometry(scratch, (0, 0, 1, 1), state)
            col = geometry["cols"][action["click_cat"]]
            x = frame["x"] + col["x"] * frame["width"]
            y = frame["y"] + col["y_matrix"] * frame["height"] - action.get("above", 9)
            await page.mouse.click(x, y)
            scratch.unlink(missing_ok=True)
        elif "type" in action:
            within = action.get("within", "input")
            selector = within if within.startswith("xpath=") else f"#panel {within}"
            locator = page.locator(selector).first
            await locator.fill(action["type"])
            if action.get("press"):
                await locator.press(action["press"])
        elif "mark_dialog" in action:
            await page.evaluate("title => window.mark_dialog(title)", action["mark_dialog"])
        elif "zoom_rows" in action:
            await page.evaluate("count => window.zoom_rows(count)", action["zoom_rows"])
        elif "bold_gene" in action:
            await page.evaluate("gene => window.bold_gene(gene)", action["bold_gene"])
        elif "apply" in action:
            await page.evaluate("changes => window.apply_changes(changes)", action["apply"])
        if action.get("wait"):
            await page.wait_for_timeout(action["wait"])
    if not any("mark_dialog" in action for action in actions):
        await page.mouse.move(1, 1)  # no hover tooltip in the shot
    await page.wait_for_timeout(400)
    return marks


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
                viewport={"width": 1800, "height": 1400}, device_scale_factor=SCALE
            )
            for panel in capture_order(all_panels(story)):
                if only and panel["id"] not in only:
                    continue
                try:
                    await capture_panel(context, url, story, facts, panel, captures, manifest)
                except Exception as error:
                    print(f"{panel['id']}: FAILED {type(error).__name__}: {error}", flush=True)
                manifest_path.write_text(json.dumps(manifest, indent=2))
            await browser.close()
    finally:
        server.shutdown()
    manifest_path.write_text(json.dumps(manifest, indent=2))
    return manifest_path


async def capture_panel(context, url, story, facts, panel, captures, manifest) -> None:
    """Render one panel, run its actions, and record its screenshot and Snapshot."""
    page = await context.new_page()
    # The EBI Proteins API refuses headless browsers; skip it so the widgets use
    # their fallback for gene descriptions, UniProt's REST API (which answers).
    await page.route("**/www.ebi.ac.uk/proteins/api/**", lambda route: route.abort())
    errors: list[str] = []
    page.on("pageerror", lambda error, errors=errors: errors.append(str(error)))
    await page.goto(url, wait_until="domcontentloaded")
    await page.wait_for_function("window.capture_ready === true", timeout=60000)
    spec = panel_spec(story, facts, panel)
    link_from(panel, spec, manifest)
    await page.evaluate("spec => window.render_panel(spec)", spec)
    marks = await run_actions(page, panel.get("actions", []), captures / f"{panel['id']}.tmp.png")
    shot = panel.get("shot", "canvas")
    target = page.locator(f'[data-shot="{shot}"]').first
    image = captures / f"{panel['id']}.png"
    await target.screenshot(path=str(image))
    frame = await target.bounding_box()
    parts = page.locator('#panel [data-shot="canvas"]')
    canvas = await parts.first.bounding_box() if await parts.count() else None
    state = await page.evaluate("kind => window.panel_state(kind)", panel["widget"])
    geometry = {
        "canvas": fraction_box(canvas, frame) if canvas else [0, 0, 1, 1],
        "canvas_px": [canvas["width"], canvas["height"]] if canvas else None,
        "marks": {k: fraction_box(v, frame) for k, v in marks.items() if v},
    }
    if panel["widget"] in ("landscape", "yearbook"):
        geometry["camera"] = spec["view"]
    if panel["widget"] == "clustergram" and shot in ("widget", "canvas"):
        geometry.update(clustergram_geometry(image, geometry["canvas"], state))
    snapshot = await page.evaluate(
        "([t, d]) => window.panel_snapshot(t, d)",
        [panel.get("title", panel["id"]), panel.get("insight", "")],
    )
    entry = {
        "screenshot": image.name,
        "shot": shot,
        "spec": spec,
        "geometry": geometry,
        "state": state if panel["widget"] == "enrich" else None,
        "captured_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "errors": errors,
    }
    if panel["widget"] == "clustergram":
        entry["visible"] = {
            "rows": state["rows"]["names"],
            "cols": state["cols"]["names"],
        }
    if snapshot:
        path = captures / f"{panel['id']}.snapshot.png"
        path.write_bytes(base64.b64decode(snapshot["png"]))
        entry["snapshot"] = path.name
        entry["identity"] = snapshot.get("identity")
    manifest[panel["id"]] = entry
    status = "errors: " + "; ".join(errors) if errors else "ok"
    if panel["widget"] == "clustergram":
        status += f" (order: {geometry.get('order')})"
    print(f"{panel['id']}: {image.name} ({status})", flush=True)
    await page.close()


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args) -> None:  # one line per panel is enough
        pass


def serve(root: Path) -> tuple[http.server.ThreadingHTTPServer, int]:
    handler = functools.partial(_QuietHandler, directory=str(root))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, server.server_address[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("storyboard", type=Path)
    parser.add_argument("--panels", nargs="*", help="only these panel ids")
    args = parser.parse_args()
    print(asyncio.run(capture(args.storyboard, args.panels)))


if __name__ == "__main__":
    main()
