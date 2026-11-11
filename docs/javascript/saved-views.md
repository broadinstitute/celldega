# Portable saved views

Landscape and Clustergram expose `snapshot()` and `restore_snapshot()` independently
of agent interfaces and notebook widgets. The goal is to **preserve an interactive observation as reproducible visual evidence**.
A snapshot keeps the rendered image, semantic visualization state, bounded scientific
observations, complete supported replay settings, and provenance together.

The exported **PNG is the saved-view file**: it contains both the image and the
metadata needed to replay supported settings. Python also writes a human-readable
Markdown companion. No separate JSON file is required.

## Terms and scope

Celldega captures a view at three levels, each built on the one before:

| | What it is | JavaScript | Python | Reopen with |
| --- | --- | --- | --- | --- |
| **Raster** | The image alone: a base64 PNG, a thumbnail and the camera at capture time | `viz.capture_raster()` | `widget.request_raster()`, then `widget.raster_png` | (an image only) |
| **Saved view** | An in-memory object, one per widget: the raster plus the observed state, complete replay settings, data identity, source and canvas size | `await viz.snapshot()` | `widget.request_snapshot()`, then `widget.latest_snapshot` | `restore_snapshot(saved_view)` |
| **Screenshot** | A PNG file: the image, with each widget's saved view embedded (minus its pixels, which are the PNG itself), links to the data and a description. Python also writes a readable `.md` and combines linked widgets into one image. | `celldega.screenshot_png(saved_view)`; the PIC button downloads one | `widget.screenshot()`, `dega.viz.screenshot(linked)`, the PIC button | `from_png(file)`, `widget.restore_png(path)` |

The methods that make a saved view are named `snapshot`; these pages call the object a
saved view. Two broader ideas build on these and sit outside the API:

| Term | Meaning |
| --- | --- |
| Evidence artifact | A screenshot or saved view used to support or contradict a scientific claim. The description explains why it matters. |
| Case / report | A collection of evidence and reasoning. |

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
| `source` | Data URLs, name, declared revision, widget type and supported constructor options for reopening |
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

## Reopen a PNG as an interactive visualization

In a notebook, `from_png` reads the metadata, constructs the appropriate widget from
its recorded data source and dimensions, and restores the supported settings when
the widget first renders:

```python
view = dega.viz.from_png("figure.png")
display(view)

# In a later cell, inspect the browser's acknowledgement:
view.get_apply_result(view.apply_request_id)
```

The returned widget is interactive. A result of `None` means restoration is pending;
an `apply_error` result explains why restoration failed. As with `restore_snapshot`,
do not wait for the reply inside the notebook cell that displays the widget.

The PNG references the scientific data; it does not embed the dataset. It records
links (a `base_url`, `zarr_url`, or the Zarr store a Matrix was read from with
`Matrix.read_zarr`) and constructor options, typically a few KB in all. The source
must still be accessible, and private data needs the same access as a normal
constructor call.

An object passed in memory has no link to record: a Matrix built in the notebook, or
an AnnData given as `adata=` (`read_h5ad` keeps no path). The PNG stores its shape and
marks it as required, and `from_png` asks for it by name. Supply the original object:

```python
cgm = dega.viz.from_png("markers.png", matrix=mat)
# The PNG still records the Landscape's base_url; adata adds its in-memory metadata.
landscape = dega.viz.from_png("tissue.png", adata=adata)
```

To make a Matrix reopenable from its link alone, write it once with
`mat.write_zarr(path)` and open it with `Matrix.read_zarr(path)` before displaying it.

Constructor keyword arguments can also relocate a source, for example
`base_url="https://example.org/data"`. Reopening still checks the saved schema,
data identity and canvas size. Pass `allow_resize=True` only when accepting the
different field of view implied by a different canvas size. The original renderer
version is recorded; exact pixel equality across versions or GPUs is not promised.

Each call opens one panel. For a composite screenshot, use `panel=0`, `panel=1`,
and so on to reopen its widgets separately; cross-widget links must be reconnected.
An existing widget with its data already loaded can instead use
`request_id = widget.restore_png("figure.png", panel=0)` and check that request's
acknowledgement in a later cell.

In a web or desktop application:

```javascript
// `file` is a PNG File from an <input type="file" accept="image/png">.
const record = await celldega.read_png(file); // Inspect metadata without rendering.
const viz = await celldega.from_png(container, file);

// A saved view of an in-memory network needs that network again:
const cgm = await celldega.from_png(otherContainer, file, { network });
```

`from_png` resolves after restoration succeeds and rejects on failure. It accepts
`panel`, `allow_resize`, and constructor options, including a replacement source.
`read_png` accepts a `File`, `Blob`, `ArrayBuffer`, or `Uint8Array`.

### What the PNG stores

The PNG's `celldega` iTXt metadata contains a versioned screenshot record
(`celldega_screenshot: 3`). Each entry in `widgets` contains a compact saved-view
envelope under `snapshot`, with replay settings in `snapshot.state`, observations
under `observed_state`, and source/constructor information under `source`. Pixels
live in the PNG image data and are not duplicated as base64 inside the metadata.
Descriptions, authors, capture times, renderer version, canvas dimensions and data
identity travel with the image.

Inspect the record from Python with `dega.viz.load_screenshot("figure.png")`, or
discover a folder's records with `dega.viz.load_screenshots("figures")`. Keep the
original exported PNG when passing it through tools that remove image metadata.

Manual exports default to `celldega_files/screenshots/`; set `screenshot_dir` or
pass `path` to choose a location. The notebook PIC button writes a PNG and Markdown
companion with a description, image preview, provenance and reopening code. The
Markdown is for readers and is not required for replay. Without a kernel, PIC
downloads the PNG with its description and saved-view metadata embedded.

For a programmatic browser export:

```javascript
const saved_view = await viz.snapshot({ description: 'A marker-enriched boundary.' });
const screenshot = celldega.screenshot_png(saved_view); // Blob with type image/png.
```

An application can store this Blob or download it using
`URL.createObjectURL(screenshot)`. The saved view itself is plain JSON, so an
application can also keep it and restore it with `restore_snapshot()`; the screenshot
is the portable file, and needs no Clerk or notebook.

Earlier screenshot records remain readable, but their plain `state` has no verified
data binding. `apply_state` remains available for intentional edits; use
`restore_snapshot` for compatibility-checked replay.

## JavaScript-only example and browser check

The repository's `examples/viz-api/index.html` uses a small synthetic matrix and the
built JS bundle. It supports PNG download/upload, restoration into a new instance,
and executable checks for capture → significant change → restore, fresh-instance
state/pixel equality, PNG export and reopening with `from_png` (state and pixels),
and rejection of different data (a renamed row), of a different declared
`data_revision`, and of a future schema. The exercise includes dendrogram cuts,
selections/highlights, annotations, crop, order and camera.

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
