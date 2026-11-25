"""Stage 2 of the storyboard -> figure pipeline: compose the figure.

Lays out a storyboard's text (per row a letter, title, narration and takeaways; per
panel a title, an action bubble and an insight box; color keys) around the captures
in ``manifest.json`` (from capture.py) with figures/style/comic.css, draws locator
boxes and arrows from the captures' geometry, and renders the figure in headless
Chrome. A row's ``layout`` nests ``row`` (side by side, one height) and ``col``
(stacked, one width) groups of panel ids; panels are sized by their aspect ratios so
the groups line up. Writes, under figures/build/<id>/:

- ``figure.png`` (one large PNG, 2x), ``figure.pdf`` and ``figure.html``;
- ``caption.md``: the caption (methods, statistics) with each panel's reopen link
  (its Snapshot PNG, which ``dega.viz.from_png`` turns back into the live view).

Rewording or relaying out never needs a recapture: edit the storyboard or the style
and run this again.

    python figures/tools/compose.py figures/storyboards/hcrc.yaml
"""

from __future__ import annotations

import argparse
import asyncio
import html
import json
from pathlib import Path
import string

from PIL import Image
import yaml


REPO = Path(__file__).resolve().parents[2]
STYLE = REPO / "figures/style/comic.css"
FONTS = "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=block"
PAGE_WIDTH = 1944  # CSS px; must match --page-width in comic.css


class _Facts(string.Formatter):
    """Formats {name} / {name:,} from facts.json; leaves unknown names as written."""

    def __init__(self, facts: dict):
        self.facts = facts

    def get_value(self, key, args, kwargs):
        if isinstance(key, str) and key in self.facts:
            return self.facts[key]
        raise KeyError(key)

    def format_text(self, text: str) -> str:
        try:
            return self.format(text)
        except (KeyError, IndexError, ValueError):
            return text


# --- Geometry: anchors on panels, as fractions of a panel's image ---


def _camera_box(entry: dict) -> list[float]:
    """The data-coordinate box a Landscape panel shows."""
    camera, (w, h) = entry["geometry"]["camera"], entry["geometry"]["canvas_px"]
    scale = 2 ** camera["zoom"]
    tx, ty = camera["target"]
    return [tx - w / 2 / scale, ty - h / 2 / scale, tx + w / 2 / scale, ty + h / 2 / scale]


def _to_panel(entry: dict, x: float, y: float) -> tuple[float, float]:
    """Data coordinates -> fractions of a Landscape panel's image."""
    geometry = entry["geometry"]
    camera, (w, h) = geometry["camera"], geometry["canvas_px"]
    c0x, c0y, c1x, c1y = geometry["canvas"]
    scale = 2 ** camera["zoom"]
    fx = ((x - camera["target"][0]) * scale + w / 2) / w
    fy = ((y - camera["target"][1]) * scale + h / 2) / h
    return c0x + fx * (c1x - c0x), c0y + fy * (c1y - c0y)


def locator_box(box: dict, manifest: dict) -> list[float] | None:
    """Where one panel's view sits on another: a Landscape zoom (``view_of``), or
    the rows and columns a zoomed Clustergram shows (``rows_of``)."""
    on = manifest.get(box["over"])
    other = manifest.get(box.get("view_of") or box.get("rows_of"))
    if not on or not other:
        return None
    if "view_of" in box:
        x0, y0, x1, y1 = _camera_box(other)
        a, b = _to_panel(on, x0, y0), _to_panel(on, x1, y1)
        return [a[0], a[1], b[0], b[1]]
    geometry = on["geometry"]
    rows = [r for r in other["visible"]["rows"] if r in geometry["rows"]]
    cols = [c for c in other["visible"]["cols"] if c in geometry["cols"]]
    if not rows or not cols:
        return None
    mx0, my0, mx1, my1 = geometry["matrix"]
    half_row = (my1 - my0) / len(geometry["rows"]) / 2
    half_col = (mx1 - mx0) / len(geometry["cols"]) / 2
    ys = [geometry["rows"][r]["y"] for r in rows]
    xs = [geometry["cols"][c]["x"] for c in cols]
    return [min(xs) - half_col, min(ys) - half_row, max(xs) + half_col, max(ys) + half_row]


def anchor(spec: dict | str, manifest: dict, panels: dict, boxes: dict) -> dict:
    """An arrow end: a panel (its top), a locator box, a dendrogram group, a row, or
    a marked element, as {panel, fx, fy} (fractions of the panel's image) or
    {panel, side}."""
    if isinstance(spec, str):
        return {"panel": spec, "side": "top"}
    if "bubble" in spec:
        return {"bubble": spec["bubble"]}
    panel = spec["panel"]
    geometry = manifest.get(panel, {}).get("geometry", {})
    if "box" in spec:
        x0, y0, x1, y1 = boxes[(panel, spec["box"])]
        side = spec.get("side", "bottom")
        if side == "bottom":
            return {"panel": panel, "fx": (x0 + x1) / 2, "fy": y1}
        if side == "right":
            return {"panel": panel, "fx": x1, "fy": (y0 + y1) / 2}
        return {"panel": panel, "fx": x0, "fy": (y0 + y1) / 2}
    if "group" in spec:
        clusters = {str(c) for c in panels[spec["group"]]["changes"]["clusters"]}
        for group in geometry.get("groups", []):
            if set(group["members"]) == clusters:
                return {"panel": panel, "fx": group["x"], "fy": group["y"]}
        raise KeyError(f"no dendrogram group {sorted(clusters)} in {panel}")
    if "trapezoid" in spec:
        # The middle of the dendrogram trapezoid a meta-cluster panel shows.
        clusters = {str(c) for c in panels[spec["trapezoid"]]["changes"]["clusters"]}
        for group in geometry.get("groups", []):
            if set(group["members"]) == clusters:
                return {
                    "panel": panel,
                    "fx": group["x"],
                    "fy": (geometry["matrix"][3] + group["y"]) / 2,
                }
        raise KeyError(f"no dendrogram group {sorted(clusters)} in {panel}")
    if "col_label" in spec:
        col = geometry["cols"][spec["col_label"]]
        return {"panel": panel, "fx": col["x"], "fy": col["y_top"] - 0.012}
    if "cell" in spec:
        # A matrix cell: [row, column], e.g. a cluster's block for a gene; with
        # edge: right, its right edge (so an arrow leaves the tile uncovered).
        row, col = spec["cell"]
        fx = geometry["cols"][col]["x"]
        if spec.get("edge") == "right":
            mx0, _, mx1, _ = geometry["matrix"]
            fx += (mx1 - mx0) / len(geometry["cols"]) / 2
        return {"panel": panel, "fx": fx, "fy": geometry["rows"][row]["y"]}
    if "col" in spec:
        col = geometry["cols"][spec["col"]]
        return {"panel": panel, "fx": col["x"], "fy": col["y_matrix"] - 0.006}
    if "row" in spec:
        row = geometry["rows"][spec["row"]]
        return {"panel": panel, "fx": row["x_end"] + 0.004, "fy": row["y"]}
    if "mark" in spec:
        x0, y0, x1, y1 = geometry["marks"][spec["mark"]]
        return {"panel": panel, "fx": x0, "fy": (y0 + y1) / 2}
    return {"panel": panel, "side": spec.get("side", "top")}


# --- HTML ---


def legend_html(spec, labels: str, story: dict, facts: dict, esc, names=None) -> str:
    """A color key: ``all`` (every label of a label set), a list of labels, or
    ``expression`` (the gene color ramp)."""
    if not spec:
        return ""
    if spec == "expression":
        return (
            "<div class='legend'><span class='key'><i class='ramp'></i>"
            "gene expression (darker = more; cells without it are not drawn)</span></div>"
        )
    palette = facts.get("palettes", {}).get(labels, {})
    names = {**story.get("names", {}).get(labels, {}), **(names or {})}
    keys = list(palette) if spec == "all" else [str(key) for key in spec]
    items = [
        f"<span class='key'><i style='background:{palette[key]}'></i>{esc(names.get(key, key))}</span>"
        for key in keys
        if key in palette
    ]
    return f"<div class='legend'>{''.join(items)}</div>"


def inset_html(inset: dict, panels: dict, manifest: dict, build: Path, esc) -> str:
    """A pop-out drawn over a panel (e.g. a widget's form), at {x, y, width} percent
    of the panel's frame."""
    entry = manifest.get(inset["panel"])
    if not entry:
        return ""
    image = (build / "captures" / entry["screenshot"]).relative_to(build).as_posix()
    caption = panels[inset["panel"]].get("action")
    style = f"left:{inset['x']}%;top:{inset['y']}%;width:{inset['width']}%"
    return (
        f"<div class='inset' id='p-{inset['panel']}' style='{style}'>"
        + (f"<div class='inset-caption'>{esc(caption)}</div>" if caption else "")
        + f"<div class='frame'><img src='{image}' alt=''></div></div>"
    )


def bubble_html(text: str, where, marks: dict, esc) -> str:
    """An action bubble. ``where``: top-left (default), top-right, bottom-left,
    bottom-right; {x, y} (percent of the frame; ``tail``: True, False or a length);
    or {mark | box, side, dx}: just below (tail up) or above (tail down) a marked
    element (e.g. the Enrich term or gene clicked) or a locator box on the panel. ``id`` lets an arrow start from it."""
    if not isinstance(where, dict):
        return f"<div class='bubble {where}'>{esc(text)}</div>"
    ident = f" id='b-{where['id']}'" if where.get("id") else ""
    key = where.get("mark") or (f"box:{where['box']}" if where.get("box") else None)
    if key in marks:
        x0, y0, _, y1 = marks[key]
        left = f"left:{x0 * 100 + where.get('dx', 0):.1f}%;right:auto"
        if where.get("side", "below") == "above":
            style = f"{left};bottom:calc({(1 - y0) * 100:.2f}% + 16px);top:auto"
            return f"<div class='bubble'{ident} style='{style}'>{esc(text)}</div>"
        style = f"{left};top:calc({y1 * 100:.2f}% + 16px);bottom:auto"
        return f"<div class='bubble tail-up'{ident} style='{style}'>{esc(text)}</div>"
    cls, tail_style = bubble_tail(where.get("tail", True))
    style = f"left:{where['x']}%;top:{where['y']}%;right:auto;bottom:auto{tail_style}"
    return f"<div class='bubble{cls}'{ident} style='{style}'>{esc(text)}</div>"


def bubble_tail(tail) -> tuple[str, str]:
    """A bubble's tail: True (the short default), False (none) or a length in px
    (a long, thin pointer down to what the bubble is about)."""
    if tail is False:
        return " no-tail", ""
    if isinstance(tail, (int, float)) and not isinstance(tail, bool):
        return " long-tail", f";--tail:{tail}px"
    return "", ""


def static_html(panel: dict, esc) -> str:
    """A panel drawn from files rather than a capture (e.g. tool logos)."""
    spec = panel["static"]
    images = "".join(f"<img src='{src}' alt=''>" for src in spec.get("images", []))
    caption = (
        f"<div class='tools-caption'>{esc(spec['caption'])}</div>" if spec.get("caption") else ""
    )
    return (
        f"<figure class='panel' id='p-{panel['id']}'>"
        f"<div class='frame tools' style='aspect-ratio:{panel.get('aspect', 1)}'>"
        f"{images}{caption}</div></figure>"
    )


def panel_html(
    panel: dict,
    story: dict,
    facts: dict,
    manifest: dict,
    build: Path,
    esc,
    row_boxes,
    insets=(),
    titles_inside=False,
) -> str:
    if panel.get("static"):
        return static_html(panel, esc)
    entry = manifest[panel.get("copy_of", panel["id"])]
    parts = [f"<figure class='panel' id='p-{panel['id']}'>"]
    # The title above the frame, or on it (`title_inside`: true or a corner, e.g.
    # bottom-right), which saves a line of height.
    inside = panel.get("title_inside", titles_inside)
    if inside is True:
        inside = "top-left"
    if panel.get("title") and not inside:
        parts.append(f"<div class='panel-title'>{esc(panel['title'])}</div>")
    if panel.get("insight") and panel.get("insight_above"):
        parts.append(f"<div class='insight above'>{esc(panel['insight'])}</div>")
    image = (build / "captures" / entry["screenshot"]).relative_to(build).as_posix()
    parts.append(f"<div class='frame'><img src='{image}' alt=''>")
    if panel.get("title") and inside:
        parts.append(f"<div class='panel-title inside {inside}'>{esc(panel['title'])}</div>")
    for (on, _), rect in row_boxes.items():
        if on != panel["id"] or rect is None:
            continue
        x0, y0, x1, y1 = rect
        parts.append(
            "<div class='locator' style='"
            f"left:{x0 * 100:.2f}%;top:{y0 * 100:.2f}%;"
            f"width:{(x1 - x0) * 100:.2f}%;height:{(y1 - y0) * 100:.2f}%'></div>"
        )
    parts.extend(insets)
    marks = dict(entry.get("geometry", {}).get("marks", {}))
    marks.update(
        {
            f"box:{other}": rect
            for (on, other), rect in row_boxes.items()
            if on == panel["id"] and rect
        }
    )
    parts.extend(
        bubble_html(extra["text"], extra, marks, esc) for extra in panel.get("bubbles", [])
    )
    if panel.get("action"):
        parts.append(bubble_html(panel["action"], panel.get("bubble", "top-left"), marks, esc))
    parts.append("</div>")
    parts.append(
        legend_html(
            panel.get("legend"),
            panel.get("labels", "leiden"),
            story,
            facts,
            esc,
            panel.get("legend_names"),
        )
    )
    if panel.get("insight") and not panel.get("insight_above"):
        parts.append(f"<div class='insight'>{esc(panel['insight'])}</div>")
    parts.append("</figure>")
    return "".join(parts)


def aspect(node, aspects: dict) -> float:
    """Width / height of a layout node (panel id, {row: [...]} or {col: [...]})."""
    if isinstance(node, str):
        return aspects[node]
    if "row" in node:
        return sum(aspect(child, aspects) for child in node["row"])
    return 1 / sum(1 / aspect(child, aspects) for child in node["col"])


def layout_html(node, aspects: dict, render, esc=html.escape, legend=None) -> str:
    grow = aspect(node, aspects)
    if isinstance(node, str):
        return f"<div class='cell' style='flex:{grow:.4f} 1 0px'>{render(node)}</div>"
    kind = "lrow" if "row" in node else "lcol"
    children = "".join(
        layout_html(child, aspects, render, esc, legend) for child in node.get("row") or node["col"]
    )
    extra = f";margin-right:{node['margin_right']}px" if node.get("margin_right") else ""
    if node.get("gap") is not None:
        extra += f";gap:{node['gap']}px"
    if node.get("margin_top"):
        # Room above this group only (e.g. for arrows running above it).
        extra += f";margin-top:{node['margin_top']}px"
    below = ""
    if node.get("insight"):
        # An insight under the whole group (e.g. a row of small maps).
        below += f"<div class='insight'>{esc(node['insight'])}</div>"
    if node.get("legend") and legend:
        # A color key under the whole group (e.g. for a panel elsewhere in the row).
        below += legend(node["legend"], "group-legend")
    if below:
        return (
            f"<div class='lcol' style='flex:{grow:.4f} 1 0px{extra};gap:6px'>"
            f"<div class='{kind}'>{children}</div>{below}</div>"
        )
    return f"<div class='{kind}' style='flex:{grow:.4f} 1 0px{extra}'>{children}</div>"


ARROWS_JS = """
<script>
(async () => {
  // Measure the final layout: after the web fonts (line breaks) and images load.
  await document.fonts.ready;
  if (document.readyState !== 'complete') {
    await new Promise((resolve) => window.addEventListener('load', resolve));
  }
  const figure = document.querySelector('.figure');
  const origin = figure.getBoundingClientRect();
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('class', 'arrows');
  svg.setAttribute('width', figure.scrollWidth);
  svg.setAttribute('height', figure.scrollHeight);
  svg.innerHTML = `<defs><marker id="head" viewBox="0 0 10 10" refX="8.5" refY="5"
    markerWidth="5" markerHeight="5" orient="auto-start-reverse">
    <path d="M0,0 L10,5 L0,10 z" fill="#1a1a1a"/></marker></defs>`;
  figure.appendChild(svg);
  const box = (el) => {
    const r = el.getBoundingClientRect();
    return { left: r.left - origin.left, top: r.top - origin.top, width: r.width, height: r.height };
  };
  const point = (a) => {
    if (a.bubble) {
      const r = box(document.getElementById(`b-${a.bubble}`));
      return [r.left + r.width / 2, r.top + r.height + 1];
    }
    const panel = document.getElementById(`p-${a.panel}`);
    if (a.fx != null) {
      const r = box(panel.querySelector('.frame img'));
      return [r.left + a.fx * r.width, r.top + a.fy * r.height];
    }
    const r = box(panel);
    if (a.side === 'left') return [r.left, r.top + r.height / 2];
    if (a.side === 'right') return [r.left + r.width, r.top + r.height / 2];
    if (a.side === 'bottom') return [r.left + r.width / 2, r.top + r.height + 2];
    return [r.left + r.width / 2, r.top - 2];
  };
  let head = 'end';
  const draw = (d) => {
    for (const [cls] of [['halo'], ['line']]) {
      const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      path.setAttribute('d', d);
      path.setAttribute('class', cls);
      if (cls === 'line') path.setAttribute(`marker-${head}`, 'url(#head)');
      svg.appendChild(path);
    }
  };
  // Every arrow ends with a straight run longer than its head (15 px), so the
  // line meets the back of the head rather than a bend.
  const L = 16;
  for (const link of LINKS) {
    // Which end carries the arrowhead: 'end' (the `to` anchor) or 'start'.
    head = link.head === 'start' ? 'start' : 'end';
    const [x0, y0] = point(link.from);
    const [x1, y1] = point(link.to);
    if (link.route === 'elbow') {
      // Out of the source sideways to the gutter, then along it to the target.
      const gx = x1 - 2 - L;
      draw(`M${x0},${y0} H${gx} V${y1} H${x1 - 2}`);
    } else if (link.route === 'under') {
      // Squared off and under the panels in between: out to the gutter, down
      // below the row's panels, across, then (if needed) up the gutter and in.
      const src = box(document.getElementById(`p-${link.from.panel}`));
      const frame = box(document.getElementById(`p-${link.to.panel}`).querySelector('.frame'));
      const gx1 = src.left + src.width + 8;
      const gx2 = frame.left - 2 - L;
      // Just below the source and the panels it passes under.
      const under = [...document.getElementById(`row-${link.row}`).querySelectorAll('.panel')]
        .map(box)
        .filter((b) => b.left >= gx1 - 1 && b.left + b.width <= frame.left);
      const gy = Math.max(src.top + src.height, ...under.map((b) => b.top + b.height)) + 14;
      if (gy >= frame.top + 12 && gy <= frame.top + frame.height - 12) {
        draw(`M${x0},${y0} H${gx1} V${gy} H${frame.left - 2}`);
      } else {
        draw(`M${x0},${y0} H${gx1} V${gy} H${gx2} V${y1} H${frame.left - 2}`);
      }
    } else if (link.route === 'straight') {
      draw(`M${x0},${y0} L${x1},${y1}`);
    } else if (link.route === 'side') {
      // A smooth curve leaving horizontally, then a straight run into the target.
      const xe = x1 - 2 - L;
      const dx = Math.max(24, Math.abs(xe - x0) * 0.5);
      draw(`M${x0},${y0} C${x0 + dx},${y0} ${xe - dx},${y1} ${xe},${y1} H${x1 - 2}`);
    } else if (link.route === 'square') {
      // Squared off: straight across when the target's frame spans this height,
      // else out to the gutter, along it, and in.
      const frame = box(document.getElementById(`p-${link.to.panel}`).querySelector('.frame'));
      const ty = Math.min(Math.max(y0, frame.top + 12), frame.top + frame.height - 12);
      draw(
        ty === y0
          ? `M${x0},${y0} H${frame.left - 2}`
          : `M${x0},${y0} H${frame.left - 2 - L} V${ty} H${frame.left - 2}`
      );
    } else if (link.route === 'lane') {
      // Between a panel's title and a row of a matrix, via a channel just above
      // the panel and a lane beside the matrix (lanes keep the arrows from crossing).
      const top = box(document.getElementById(`p-${link.from.panel}`)).top;
      const cy = top - 12 - 9 * (link.n - 1 - link.lane);
      const lx = x1 + 18 + 11 * link.lane;
      draw(`M${x0},${y0} V${cy} H${lx} V${y1} H${x1 + 3}`);
    } else {
      // An arc: bowed to one side (link.bend: 1 or -1) by a fifth of its length,
      // so even a short arrow reads as an arrow rather than a rule; it ends with
      // a straight run along its last direction.
      const dx = x1 - x0;
      const dy = y1 - y0;
      const length = Math.hypot(dx, dy) || 1;
      // Gentle on short arrows (no U-turns), more on long ones.
      const bow = Math.min(110, Math.max(8, 0.2 * length)) * (link.bend ?? 1);
      const nx = -dy / length;
      const ny = dx / length;
      const c1 = [x0 + dx * 0.2 + nx * bow, y0 + dy * 0.2 + ny * bow];
      const c2 = [x0 + dx * 0.8 + nx * bow, y0 + dy * 0.8 + ny * bow];
      const tl = Math.hypot(x1 - c2[0], y1 - c2[1]) || 1;
      const ux = (x1 - c2[0]) / tl;
      const uy = (y1 - c2[1]) / tl;
      const ex = x1 - ux * L;
      const ey = y1 - uy * L;
      draw(
        `M${x0},${y0} C${c1[0]},${c1[1]} ${c2[0] - ux * L},${c2[1] - uy * L} ${ex},${ey} L${x1},${y1}`
      );
    }
  }
  window.arrows_ready = true;
})();
</script>
"""


def figure_html(story: dict, manifest: dict, facts: dict, build: Path) -> tuple[str, list[str]]:
    text = _Facts(facts).format_text
    esc = lambda value: html.escape(text(str(value)))  # noqa: E731
    missing = []
    links = []
    parts = [
        "<!doctype html><html><head><meta charset='utf-8'>",
        f"<link rel='stylesheet' href='{FONTS}'>",
        f"<style>{STYLE.read_text()}</style></head><body><div class='figure'>",
    ]
    for row in story["rows"]:
        panels = {p["id"]: p for p in row["panels"]}
        missing += [pid for pid, p in panels.items() if "widget" in p and pid not in manifest]
        inset_ids = {inset["panel"] for inset in row.get("insets", [])}
        aspects = {}
        for pid, p in panels.items():
            source = p.get("copy_of", pid)
            if p.get("static"):
                aspects[pid] = float(p.get("aspect", 1))
            elif source in manifest:
                with Image.open(build / "captures" / manifest[source]["screenshot"]) as im:
                    aspects[pid] = im.width / im.height
        layout = row.get("layout") or {
            "row": [p for p in panels if p in aspects and p not in inset_ids]
        }
        boxes = {
            (box["over"], box.get("view_of") or box.get("rows_of")): locator_box(box, manifest)
            for box in row.get("boxes", [])
        }
        lane_links = [link for link in row.get("links", []) if link.get("route") == "lane"]
        lane_rows = sorted(
            lane_links,
            key=lambda link: manifest[link["to"]["panel"]]["geometry"]["rows"][link["to"]["row"]][
                "y"
            ],
        )
        for link in row.get("links", []):
            entry = {
                "from": anchor(link["from"], manifest, panels, boxes),
                "to": anchor(link["to"], manifest, panels, boxes),
                "route": link.get("route", "curve"),
                "bend": link.get("bend", 1),
                "head": link.get("head", "end"),
                "row": row["id"],
            }
            if link in lane_links:
                entry.update(lane=lane_rows.index(link), n=len(lane_links))
            links.append(entry)

        parts.append(f"<section class='row' id='row-{row['id']}'><div class='row-head'>")
        parts.append(f"<span class='row-letter'>{esc(row['id'])}</span>")
        if row.get("title"):
            parts.append(f"<span class='row-title'>{esc(row['title'])}</span>")
        parts.append("</div>")
        if row.get("narration"):
            parts.append(f"<p class='narration'>{esc(row['narration'])}</p>")
        row_insets = {}
        for inset in row.get("insets", []):
            row_insets.setdefault(inset["over"], []).append(
                inset_html(inset, panels, manifest, build, esc)
            )

        def render(pid, row_boxes=boxes, panels=panels, insets=row_insets, row=row):
            return panel_html(
                panels[pid],
                story,
                facts,
                manifest,
                build,
                esc,
                row_boxes,
                insets.get(pid, []),
                row.get("titles_inside", False),
            )

        def key_html(spec, cls="row-legend"):
            """A titled color key (a row's, or a layout group's)."""
            title = (
                f"<span class='legend-title'>{esc(spec['title'])}</span>"
                if spec.get("title")
                else ""
            )
            keys = legend_html(
                spec.get("keys", "all"),
                spec.get("labels", "leiden"),
                story,
                facts,
                esc,
                spec.get("names"),
            )
            return f"<div class='{cls}'>{title}{keys}</div>"

        style = f" style='margin-top:{row['channel']}px'" if row.get("channel") else ""
        parts.append(
            f"<div class='layout'{style}>{layout_html(layout, aspects, render, esc, key_html)}</div>"
        )
        if row.get("legend"):
            parts.append(key_html(row["legend"]))
        takeaways = row.get("takeaways") or ([row["takeaway"]] if row.get("takeaway") else [])
        if takeaways:
            items = "".join(f"<li>{esc(item)}</li>" for item in takeaways)
            parts.append(
                f"<div class='takeaways'><span class='label'>Takeaways</span><ul>{items}</ul></div>"
            )
        parts.append("</section>")
    parts.append("</div>")
    parts.append(f"<script>const LINKS = {json.dumps(links)};</script>{ARROWS_JS}")
    parts.append("</body></html>")
    return "".join(parts), missing


def caption_md(story: dict, manifest: dict, facts: dict) -> str:
    text = _Facts(facts).format_text
    lines = [
        text(story.get("caption", "")).strip(),
        "",
        "**Reopen each panel.** Each Snapshot PNG carries its saved view: "
        "`dega.viz.from_png(path)` rebuilds the widget at that view. Panels whose cells "
        "are labeled from the AnnData (Leiden clusters, crypt depth, cancer sub-types) "
        "also need those labels: `dega.viz.from_png(path, adata=labels)`.",
        "",
    ]
    for row in story["rows"]:
        for panel in row["panels"]:
            entry = manifest.get(panel["id"])
            if not entry:
                continue
            reopen = entry.get("snapshot")
            where = f"`captures/{reopen}` (`dega.viz.from_png`)" if reopen else "no saved view"
            lines.append(f"- **{panel['id']}** {panel.get('title', '')}: {where}")
    return "\n".join(lines) + "\n"


async def render(page_html: Path, png: Path, pdf: Path) -> None:
    from playwright.async_api import async_playwright

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome", headless=True)
        page = await browser.new_page(
            viewport={"width": PAGE_WIDTH, "height": 1200}, device_scale_factor=2
        )
        await page.goto(page_html.as_uri(), wait_until="networkidle")
        await page.evaluate("document.fonts.ready")
        await page.wait_for_function("window.arrows_ready === true")
        await page.locator(".figure").screenshot(path=str(png))
        height = await page.evaluate("document.querySelector('.figure').scrollHeight")
        await page.pdf(
            path=str(pdf),
            width=f"{PAGE_WIDTH}px",
            height=f"{height + 2}px",
            print_background=True,
        )
        await browser.close()


def compose(storyboard: Path) -> Path:
    story = yaml.safe_load(storyboard.read_text())
    build = REPO / "figures/build" / story["id"]
    manifest = json.loads((build / "manifest.json").read_text())
    facts_path = build / "data/facts.json"
    facts = json.loads(facts_path.read_text()) if facts_path.exists() else {}
    page = build / "figure.html"
    content, missing = figure_html(story, manifest, facts, build)
    if missing:
        print("not captured yet:", ", ".join(missing))
    page.write_text(content)
    (build / "caption.md").write_text(caption_md(story, manifest, facts))
    png = build / "figure.png"
    asyncio.run(render(page, png, build / "figure.pdf"))
    return png


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("storyboard", type=Path)
    print(compose(parser.parse_args().storyboard))


if __name__ == "__main__":
    main()
