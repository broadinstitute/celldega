"""Stage 2 of the storyboard -> figure pipeline: compose the figure.

Lays out a storyboard's text (headline, subtitle; per row a POW banner, narration
and takeaway; per panel an action bubble and an insight box) around the captures in
``manifest.json`` (from capture.py) with figures/style/comic.css, and renders it in
headless Chrome. Panels in a row share one height and fill the page width. Writes,
under figures/build/<id>/:

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
FONTS = (
    "https://fonts.googleapis.com/css2?family=Bangers&family=Inter:wght@400;600;700&display=block"
)
PAGE_WIDTH = 2000  # CSS px; must match --page-width in comic.css
FIGURE_PADDING = 40
ROW_BORDER = 4
ROW_PADDING = 18
GAP = 18
FRAME_BORDER = 3


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


def panel_widths(images: list[Path]) -> list[float]:
    """Widths (CSS px) giving a row's panels one height across the page."""
    aspects = []
    for image in images:
        with Image.open(image) as im:
            aspects.append(im.width / im.height)
    inner = PAGE_WIDTH - 2 * FIGURE_PADDING - 2 * (ROW_BORDER + ROW_PADDING)
    available = inner - GAP * (len(images) - 1) - 2 * FRAME_BORDER * len(images)
    height = available / sum(aspects)
    return [height * aspect + 2 * FRAME_BORDER for aspect in aspects]


def legend_html(panel: dict, story: dict, facts: dict, esc) -> str:
    """A color key under a panel: ``legend: all`` (every label of the panel's label
    set), a list of labels, or ``expression`` (the gene color ramp)."""
    spec = panel.get("legend")
    if not spec:
        return ""
    if spec == "expression":
        return (
            "<div class='legend'><span class='key'><i class='ramp'></i>"
            "gene expression (darker = more; cells without it are not drawn)</span></div>"
        )
    labels = panel.get("labels", "leiden")
    palette = facts.get("palettes", {}).get(labels, {})
    names = story.get("names", {}).get(labels, {})
    keys = list(palette) if spec == "all" else [str(key) for key in spec]
    items = [
        f"<span class='key'><i style='background:{palette[key]}'></i>{esc(names.get(key, key))}</span>"
        for key in keys
        if key in palette
    ]
    return f"<div class='legend'>{''.join(items)}</div>"


def figure_html(story: dict, manifest: dict, facts: dict, build: Path) -> str:
    text = _Facts(facts).format_text
    esc = lambda value: html.escape(text(str(value)))  # noqa: E731
    parts = [
        "<!doctype html><html><head><meta charset='utf-8'>",
        f"<link rel='stylesheet' href='{FONTS}'>",
        f"<style>{STYLE.read_text()}</style></head><body><div class='figure'>",
        f"<h1 class='headline'>{esc(story['headline'])}</h1>",
        f"<p class='subtitle'>{esc(story.get('subtitle', ''))}</p>",
    ]
    for row in story["rows"]:
        panels = [p for p in row["panels"] if p["id"] in manifest]
        images = [build / "captures" / manifest[p["id"]]["screenshot"] for p in panels]
        widths = panel_widths(images) if images else []
        parts.append(f"<section class='row' id='row-{row['id']}'><div class='row-head'>")
        parts.append(f"<span class='row-letter'>{esc(row['id'])}</span>")
        if row.get("pow"):
            parts.append(f"<span class='pow'>{esc(row['pow'])}</span>")
        if row.get("narration"):
            parts.append(f"<p class='narration'>{esc(row['narration'])}</p>")
        parts.append("</div><div class='panels'>")
        for panel, image, width in zip(panels, images, widths, strict=True):
            parts.append(f"<figure class='panel' style='width:{width:.1f}px'>")
            if panel.get("title"):
                parts.append(f"<div class='panel-title'>{esc(panel['title'])}</div>")
            relative = image.relative_to(build).as_posix()
            parts.append(f"<div class='frame'><img src='{relative}' alt=''>")
            if panel.get("action"):
                # Where the bubble sits: top-left (default), top-right, bottom-left,
                # bottom-right, so it never hides what the panel shows.
                where = panel.get("bubble", "top-left")
                parts.append(f"<div class='bubble {where}'>{esc(panel['action'])}</div>")
            parts.append("</div>")
            parts.append(legend_html(panel, story, facts, esc))
            if panel.get("insight"):
                parts.append(f"<div class='insight'>{esc(panel['insight'])}</div>")
            parts.append("</figure>")
        parts.append("</div>")
        if row.get("takeaway"):
            parts.append(f"<div class='takeaway'>{esc(row['takeaway'])}</div>")
        parts.append("</section>")
    parts.append("</div></body></html>")
    return "".join(parts)


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
    page.write_text(figure_html(story, manifest, facts, build))
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
