# Celldega for AI agents

A brief for AI coding agents working in this repository; people may find it a
useful summary too. [CONTRIBUTING.md](CONTRIBUTING.md) has the full setup,
testing and style guide.

## What Celldega is

A Python package plus a JavaScript front end for linked, interactive
visualization and analysis of spatial and single-cell omics. Python prepares and
analyzes data (`AnnData`, `MuData`, `GeoDataFrame`); anywidget widgets render it
in Jupyter with deck.gl. To get oriented:

- `python -c "import celldega; help(celldega)"`: the package docstring is a map
  of the widgets and modules. Each module's docstring maps that module.
- [docs/python/index.md](docs/python/index.md): which module to use for what.
- The published docs index for agents: https://broadinstitute.github.io/celldega/llms.txt

## Layout

| Path                                              | Contents                                                                                                                     |
| ------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `src/celldega/<module>/`                          | Python modules: `pre`, `clust`, `nbhd`, `collection`, `dataset`, `set`, `select`, `align`, `clerk`, `qc`, `viz`              |
| `src/celldega/viz/widget.py`                      | The widget classes (`Landscape`, `Clustergram`, `Yearbook`, `Clerk`, ...) and their synced traits                            |
| `src/celldega/viz/__init__.py`                    | Linking helpers (`spatial_clustergram`, `link_clerk`, ...)                                                                   |
| `js/celldega.js`                                  | Front-end entry: each widget's `render`, plus the standalone JavaScript API used by docs gallery pages                       |
| `js/viz/`, `js/widgets/`, `js/ui/`, `js/deck-gl/` | Visualizations (`landscape_ist.js`, `matrix_viz.js`, `yearbook.js`), panel widgets (Clerk, Enrich), controls, deck.gl layers |
| `tests/unit/test_<module>/`, `js/__tests__/`      | pytest and Jest tests                                                                                                        |
| `docs/`, `mkdocs.yaml`, `scripts/*.py` hooks      | MkDocs site, its nav, and build hooks                                                                                        |

## Commands

Set up once with `bash scripts/setup.sh` (creates the `dega/` virtual
environment with `uv`), then `source dega/bin/activate`.

| Task                               | Command                                                                |
| ---------------------------------- | ---------------------------------------------------------------------- |
| Python tests                       | `pytest tests/unit` (or one folder, e.g. `pytest tests/unit/test_viz`) |
| JavaScript tests                   | `npx jest`                                                             |
| Format and lint Python             | `ruff format src/ tests/` and `ruff check src/`                        |
| Format and lint JavaScript         | `npm run format:js` and `npm run lint:js`                              |
| Build the widget bundle            | `npm run build`                                                        |
| Rebuild on change while developing | `npm run dev`                                                          |
| Docs                               | `mkdocs serve`, or `mkdocs build -d <dir>`                             |

Run the formatters after editing: CI checks `ruff format --check src/`,
`ruff check src/`, `npm run lint:js` and `npm run format:js:check`, and runs the
Python tests on 3.11 and 3.12.

## Things that trip agents up

- **Two copies of the bundle.** `npm run build` writes
  `src/celldega/static/celldega.js` (what widgets load; not tracked) and copies
  it to `docs/assets/js/celldega.js` (tracked, used by docs pages). `npm run dev`
  rebuilds only the first, with an inline source map, so run `npm run build`
  before committing the docs copy. When the docs copy conflicts in a merge,
  rebuild it rather than resolving it by hand.
- **Python and JavaScript share widget state.** A trait tagged `sync=True` in
  `widget.py` is read in JavaScript with `model.get(...)` and watched with
  `model.on('change:...')`; rename both sides together. After a JavaScript
  change, rebuild and re-render the widget; set `CELLDEGA_LOCAL_ESM=1` so
  widgets load your local bundle instead of the published one from the CDN.
- **Gallery pages have no Python or kernel.** `docs/gallery/*.md` pages run
  `docs/assets/js/gallery_*.js`, which call the standalone API in
  `js/celldega.js` and link widgets with `link_models`. Their model may be a
  plain object, so front-end code must not assume `model.on` or `model.send`
  exist.
- **Docs notebooks are not executed at build time.** Their widgets render from
  widget state saved in the `.ipynb`; see "Rendering Docs Notebooks" in
  CONTRIBUTING.md for the `nbconvert` command. `*.ipynb` is gitignored, so
  allowlist a new docs notebook in `.gitignore` or `git add -f` it.
- **Unlisted pages** are listed under `not_in_nav` in `mkdocs.yaml`; the
  `scripts/unlisted_docs.py` hook marks them as work in progress.
- **`data/` folders are gitignored.** Example data is downloaded or hosted (for
  example on GitHub or Hugging Face), not committed.

## Writing code and docs

- New docstrings use Google style (`Args:`, `Returns:`, `Example::`) and say
  which widget displays the result where there is one.
- Keep the `celldega/__init__.py` docstring current when adding a widget or
  module: it is both `help(celldega)` and the introduction of `llms.txt`
  (generated from it and the docs nav by `scripts/llms_txt.py`).
- Follow the terminology in CONTRIBUTING.md ("Snapshot", "DegaFiles").
