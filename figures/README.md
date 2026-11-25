# Storyboard → figure

Figures here are built by scripts from data, in two stages, so every pixel can be
regenerated and no image is drawn by hand or by a generative model.

| Path | What it is | In git |
| --- | --- | --- |
| `storyboards/<id>.yaml` | The figure's words (headline, subtitle; per row a POW banner, narration, takeaway; per panel an action bubble and an insight box; the caption) and each panel's view | yes |
| `style/comic.css` | Every color, font and spacing of the composed figure | yes |
| `tools/prepare_<id>.py` | The figure's data step: cell labels, matrices, framing facts | yes |
| `tools/capture.py`, `tools/capture.html` | Stage 1: render each panel with Celldega's web API in headless Chrome | yes |
| `tools/compose.py` | Stage 2: lay out the text around the captures and render the figure | yes |
| `tools/build_figure.py` | All of the above in one command | yes |
| `build/<id>/` | Data, captures, `manifest.json`, `figure.png`/`.pdf`/`.html`, `caption.md` | no (gitignored) |

## Stages

1. **Capture** is the only stage that touches widgets. For each panel it renders the
   widget (Landscape, Clustergram, Enrich) from the data, applies the panel's view,
   and saves from the same render a screenshot (what the reader sees: the whole
   widget, its map, or its controls) and a Snapshot, a Celldega screenshot PNG
   carrying the saved view that `dega.viz.from_png` reopens. Both go in
   `build/<id>/manifest.json`.
2. **Compose** builds the figure from the manifest and the storyboard with HTML and
   CSS, and renders one large PNG (2x) and a PDF. Rewording or relaying out never
   needs a recapture.

The figure carries enough text to read without its caption; the caption
(`caption.md`) keeps methods, statistics and each panel's reopen link. A readability
check: a fresh reviewer sees only the composed figure, retells its story and lists
what confused it.

## Build

```bash
python figures/tools/prepare_hcrc.py            # data (dega environment, ~10 s)
uv run --no-project --with playwright --with pyyaml --with pillow \
    python figures/tools/build_figure.py figures/storyboards/hcrc.yaml
# -> figures/build/hcrc/figure.png
```

`--panels a1 c2` recaptures only some panels; `--compose-only` re-lays out the text.
Capture needs Chrome; the data step needs the HCRC AnnData from the Visium HD CRC
tutorial in `notebooks/data/visium-hd_data/Visium_HD_Human_Colon_Cancer/`.

Settled figures and their captures are published to immutable URLs (for example a
Hugging Face revision) rather than committed; the companion links to those.
