# Portable saved views

Landscape and Clustergram expose `snapshot()` and `restore_snapshot()` independently
of agent interfaces and notebook widgets. The goal is to **preserve an interactive observation as reproducible visual evidence**.
A snapshot keeps the rendered image, semantic visualization state, bounded scientific
observations, complete supported replay settings, and provenance together.

## Terms and scope

| Term | Meaning |
| --- | --- |
| Raster / image | Pixels only, returned by `capture_raster`. |
| Screenshot | A user-facing saved image; Celldega's exports attach saved-view metadata. |
| Snapshot / saved view | The versioned image + semantic state + provenance + replay contract. These are synonyms here. |
| Evidence artifact | A saved view used to support or contradict a scientific claim. The description explains why it matters. |
| Case / report | A higher-level collection of evidence and reasoning, outside the Viz API. |

A scientist can use this API for exploration, figures, tutorials, reports, web or
desktop applications without constructing an agent. Agents consume this same contract.

```javascript
await viz.apply_state({ /* supported changes */ });
const saved = await viz.snapshot({
  max_size: 1600,
  state: { max_rows: 25 }, // Observation cap only; replay settings are uncapped.
  description: 'The marker-enriched population occupies the tissue boundary.',
  author: 'scientist',
});
const json = JSON.stringify(saved);

// A separately constructed visualization with the same data and canvas dimensions:
await freshViz.restore_snapshot(JSON.parse(json));
```

The browser waits for its canvas to initialize, then reads the image, observations,
replay settings and data identity in one JavaScript task. Capture represents the
current rendered frame: wait for animations and data loading to settle when you need
a stable figure. Each widget in a composite has its own capture time; a composite is
not a cross-widget transaction.

## The contract

The JSON envelope uses `schema: "celldega.view"` and `version: 2`:

| Field | Meaning |
| --- | --- |
| `kind` | `landscape` or `clustergram` |
| `renderer` | Celldega package version used to capture the view |
| `captured_at` | UTC timestamp for the coordinated capture |
| `state` | Semantic replay inputs from `get_replay_state()`, independent of observation caps |
| `description`, `author` | Why the observation matters, and who recorded it |
| `source` | Where the data came from: URLs, name, declared revision (recorded, not compared) |
| `observed_state` | The scientific observations returned by the getter |
| `image` | Base64 PNG, thumbnail and dimensions |
| `identity` | What data the view is of: counts and hashes of its names (see below) |
| `viewport` | Canvas size in CSS pixels |
| `capture` | Image size and observation options used |
| `restoration` | `partial`: see the [control coverage](viz-api.md#replaying-supported-settings) |

`restore_snapshot` rejects other schema versions, wrong widget kinds, different data
and a different canvas size before changing the view, and its error names what
differs. `allow_resize: true` permits a different canvas size; the same camera then
frames a different extent. The size is in CSS pixels, so a view saved on a
high-density display restores on a standard one. Additive fields may be ignored by
readers; incompatible schema changes require a new version (version 1 views, which
hashed all loaded data, need recapturing). This is a data/view contract, not a
promise of identical pixels across browser, GPU or Celldega renderer versions.
Python screenshot/report records also record the installed Celldega version. The
original PNG remains the visual evidence.

### What the identity checks

A saved view records what its data is by name, cheaply enough to compute on every
capture:

| Visualization | Identity |
| --- | --- |
| Landscape (and the spatial clouds) | Cell names, gene names and each cell's cluster label (with the cluster attribute), each as a count and a fast hash |
| Clustergram | Row names and column names, each as a count and a fast hash |

Restoring onto other cells, genes, clusterings, rows or columns is refused. Hashes
are computed once per loaded array, so captures stay fast on large datasets, and
need no secure (HTTPS) page. They tell datasets apart; they are not cryptographic
and do not cover values: the same names with different expression values match.

For exact content identity, declare a `data_revision` when constructing the
visualization: any immutable identifier, such as a release tag, a commit hash, or a
digest of the files. Saved views record it, and restoring compares it whenever both
the view and the visualization declare one. For a local dataset:

```python
revision = dega.viz.fingerprint_dataset("data/my-dataset")
landscape = dega.viz.Landscape(base_url=dataset_url, data_revision=revision)
```

`fingerprint_dataset` hashes file contents and relative names. It can be slow for
large stores; compute it when publishing immutable data, keep exports outside the
dataset, and regenerate it after edits. Clustergram and the JS constructors accept
`data_revision` too.

Restoring a Clustergram view never discards annotations made since it was saved:
an axis's saved manual annotations are applied only when that axis has none now (or
the same ones), and the result lists any axis whose current annotations were kept.
Use `apply_state({annotations: ...})` to replace them deliberately.

## Notebook use

```python
request_id = cgm.request_snapshot(max_rows=25)
# In a later cell, after the browser replies:
saved = cgm.latest_snapshot
restore_id = fresh_cgm.restore_snapshot(saved)
# In a later cell: None while pending, else {"event": "applied" or "apply_error", ...}
fresh_cgm.get_apply_result(restore_id)
```

The browser's reply reaches Python only after the cell that sent the request
finishes, so don't `await` it in that cell (`wait_for_apply` would time out). From a
background task or an application, `await fresh_cgm.wait_for_apply(restore_id)`
raises on failure or timeout.

`latest_snapshot`, `snapshot_error` and `snapshot_capture_id` are Python-side traits,
never synced into the notebook's saved widget state. Requests carry IDs and responses
are matched individually, so concurrent captures cannot substitute a newer image for
an older request. `widget.screenshot()` and the PIC button use this same capture path.

Screenshot records (PNG metadata and JSON sidecars) contain a compact restore envelope
under each widget's `snapshot` (its `state` holds the replay settings), with pixels
stored in the PNG and observations under `observed_state`. Reopen with:

```python
record = dega.viz.load_screenshot("figure.png")
fresh_cgm.restore_snapshot(record["widgets"][0]["snapshot"])
```

Manual exports default to `celldega_files/screenshots/`; set `screenshot_dir` or
pass `path` to choose a location. The notebook PIC button writes PNG/JSON/Markdown.
Without a kernel, PIC downloads one saved-view JSON with the image embedded, and its
description can be supplied in the dialog. An application may persist the same JSON
in its own storage; no Clerk or notebook objects are required.

Earlier screenshot records remain readable, but their plain `state` has no verified
data binding. `apply_state` remains available for intentional edits; use
`restore_snapshot` for compatibility-checked replay.

## JavaScript-only example and browser check

The repository's `examples/viz-api/index.html` uses a small synthetic matrix and the
built JS bundle. It supports JSON download/upload, restoration into a new instance,
and executable checks for capture → significant change → restore, fresh-instance
state/pixel equality, rejection of different data (a renamed row) and future-schema
rejection. The exercise
includes dendrogram cuts, selections/highlights, annotations, crop, order and camera.

From the repository root:

```sh
npm run build
python -m http.server 8000 --bind 127.0.0.1
```

Open `http://127.0.0.1:8000/examples/viz-api/`. No notebook, Python analysis runtime
or model account is needed; the command above only serves static files. For automation
in an environment with Playwright installed:

```sh
python scripts/check_viz_snapshot.py --channel chrome
```

The page exposes `window.celldegaSnapshotExample.check()` for another test runner.
The same instance methods can be called by an application renderer.
