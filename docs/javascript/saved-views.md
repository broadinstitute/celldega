# Portable saved views

Landscape and Clustergram expose `snapshot()` and `restore_snapshot()` independently
of agent interfaces and notebook widgets. A snapshot keeps the rendered image, scientific
observations, supported replay settings and data identity together.

```javascript
await viz.apply_state({ /* supported changes */ });
const saved = await viz.snapshot({ max_size: 1600, state: { max_rows: 25 } });
const json = JSON.stringify(saved);

// A separately constructed visualization with the same data and canvas dimensions:
await freshViz.restore_snapshot(JSON.parse(json));
```

The browser waits for its canvas to initialize, then reads the image, observations
and identity material in one JavaScript task. Hashing completes afterward without
reading the live view again. Capture represents the current rendered frame: wait for
animations and data loading to settle when you need a stable figure. Each widget in
a composite has its own capture time; a composite is not a cross-widget transaction.

## The contract

The JSON envelope uses `schema: "celldega.view"` and `version: 1`:

| Field | Meaning |
| --- | --- |
| `kind` | `landscape` or `clustergram` |
| `renderer` | Celldega package version used to capture the view |
| `captured_at` | UTC timestamp for the coordinated capture |
| `state` | Inputs understood by `apply_state`; independent of observation caps |
| `observed_state` | The scientific observations returned by the getter |
| `image` | Base64 PNG, thumbnail and dimensions |
| `identity` | SHA-256 fingerprint, coverage and assets not verified |
| `viewport` | Canvas pixel dimensions, including device pixel ratio |
| `capture` | Image size and observation options used |
| `restoration` | `partial`: see the [control coverage](viz-api.md#replaying-supported-settings) |

`restore_snapshot` rejects unknown schema versions, wrong widget kinds, changed
data and different canvas dimensions before changing the view. `allow_resize: true`
permits different canvas dimensions; pixel equality is then not guaranteed. Additive
fields may be ignored by readers; incompatible schema changes require a new version.
This is a data/view contract, not a promise of identical pixels across browser, GPU
or Celldega renderer versions. Python screenshot/report records also record the
installed Celldega version. The original PNG remains the visual evidence.

### What the fingerprint establishes

Clustergram hashes the loaded matrix values, dot-size matrix, axis metadata,
linkages, marker rankings, rank views and entity definitions. Identical names and
dimensions with changed values do not pass. It does not depend on a widget instance ID.

Landscape hashes loaded cell identities, categories, positions, embedding, gene
metadata and source configuration. Images, transcripts and expression assets may
be streamed later, so this alone cannot identify the full remote dataset. By default
restore refuses snapshots with unidentified assets. Supply `data_revision` as a
`sha256:<64 lowercase hex digits>` content digest when constructing the Landscape.
The producer must publish immutable data under that revision and update it when any
asset changes. The browser trusts this declaration for assets it has not downloaded;
it does not crawl or independently re-hash the entire remote store.

For a local dataset, compute the revision before opening it:

```python
revision = dega.viz.fingerprint_dataset("data/my-dataset")
landscape = dega.viz.Landscape(base_url=dataset_url, data_revision=revision)
```

The helper hashes file contents and relative names. It can be expensive for large
stores; compute it when publishing immutable data, keep exports outside the dataset,
and regenerate it after edits. The equivalent JS constructor accepts `data_revision`.
Without a revision, an explicit `allow_unverified: true` (Python:
`allow_unverified=True`) checks loaded data only. This option never bypasses a
fingerprint mismatch. The snapshot's identity coverage remains visible in its record.

## Notebook use

```python
request_id = cgm.request_snapshot(max_rows=25)
# In a later cell, after the browser replies:
saved = cgm.latest_snapshot
restore_id = fresh_cgm.restore_snapshot(saved)
# Observe apply_capture_id / apply_error for completion.
```

`latest_snapshot`, `snapshot_error` and `snapshot_capture_id` are Python-side traits,
never synced into the notebook's saved widget state. Requests carry IDs and responses
are matched individually, so concurrent captures cannot substitute a newer image for
an older request. `widget.screenshot()` and the PIC button use this same capture path.

Screenshot records (PNG metadata and JSON sidecars) contain a compact restore envelope
under each widget's `snapshot`, with pixels stored in the PNG and observations under
`observed_state`. Reopen with:

```python
record = dega.viz.load_screenshot("figure.png")
fresh_cgm.restore_snapshot(record["widgets"][0]["snapshot"])
```

Earlier screenshot records remain readable, but their plain `state` has no verified
data binding. `apply_state` remains available for intentional edits; use
`restore_snapshot` for compatibility-checked replay.

## JavaScript-only example and browser check

The repository's `examples/viz-api/index.html` uses a small synthetic matrix and the
built JS bundle. It supports JSON download/upload, restoration into a new instance,
and an executable check for matching state/pixels, changed data and future schemas.

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
