# Viz API: getters, setters and exporters

Landscape and Clustergram expose an initial API for reading and changing views from
code. Support varies by widget and control. Three kinds of methods cover this:

- **Getters** report what a visualization shows right now, as plain JSON: the space
  and camera, what is selected or highlighted, which clusters and genes are on screen,
  and the values behind them.
- **Setters** change what it shows, as its controls would: select clusters, color by
  genes, zoom to cells, move the Clustergram's marker level, label columns.
- **Exporters** capture what it shows as an image. In Python, a screenshot also saves
  the observed state, supported replay settings and a description of why it matters.

`get_state()` returns bounded scientific observations. `get_replay_state()` returns
complete inputs for supported controls, without those observation caps. Only the
latter can be passed directly to `apply_state()`; saved views use it automatically. Saved settings replay the supported
parts of a view on widgets with the same data already loaded; full view restoration
is not implemented yet. Use [portable snapshots](saved-views.md) to capture image
and state together and validate data identity before restoring supported settings.

The API uses corresponding operations in a web page (JavaScript) and a notebook
(Python). Any web app, script or AI agent can use it to read a view, reason about it, show the
evidence it finds, and save it.

| | JavaScript (web page) | Python (notebook widget) |
| --- | --- | --- |
| Get | `viz.get_state(options)` returns the state | `widget.request_state(...)`, then `widget.latest_state` |
| Replay inputs | `viz.get_replay_state()` | `widget.latest_snapshot["state"]` after capture |
| Set | `await viz.apply_state(changes)` | `await widget.apply_state_async(changes)` |
| Export | `viz.capture_raster(options)` returns a PNG | `widget.request_raster()`, then `widget.raster_png`; or `widget.screenshot(description, path)` |
| Save view | `await viz.snapshot(options)` | `widget.request_snapshot(...)`, then `widget.latest_snapshot` |
| Restore | `await viz.restore_snapshot(saved)` | `widget.restore_snapshot(saved)`, then check `apply_capture_id` / `apply_error` |

In Python, getters and exporters are asynchronous: the browser replies after the
calling cell finishes, so read `latest_state` or `raster_png` in a later cell, or
`observe` them. Neither is ever saved into the notebook's widget state.

Design rules the API follows:

- **Scientific meaning, not interface details.** State names clusters, genes, spaces
  and marker levels, not buttons or DOM elements.
- **Input validation.** Unknown settings and invalid input are rejected. Runtime
  failures, such as unavailable data, can still leave a partial change. Python
  setters submit asynchronous requests. `apply_state_async` waits for the exact request
  acknowledgement; `apply_state` returns submission descriptions, not completion.
- **Same paths as the controls.** Setting clusters behaves like clicking cluster bars,
  setting genes like the gene search, and so on, so linked widgets update as usual.
- **Only what you pass changes.** Setting categories changes the labels you name and
  leaves the others alone, unless you ask to replace them all.

## Landscape

`celldega.landscape(el, options)` returns the Landscape object these methods are on
(see the [API reference](api.md)). CellCloud and NeighborhoodCloud support
the same state/snapshot API; their `view` also supports orbit rotation.

### `get_state(options)`

What the Landscape shows. `options.max_bars` caps the per-cluster and per-gene counts
(25 by default).

```json
{
  "kind": "landscape",
  "space": "spatial",
  "view_state": {"target": [5120.5, 3988.0, 0], "zoom": -2.3},
  "color_by": "cluster",
  "selected_clusters": ["4"],
  "selected_genes": [],
  "selected_cells": 0,
  "viewport": {
    "clusters": [{"name": "4", "value": 1203}, {"name": "5", "value": 980}],
    "genes": [{"name": "MUC2", "value": 512}]
  }
}
```

- `space`: `"spatial"`, `"umap"` or `"xy"`.
- `color_by`: `"cluster"`, a gene, or `"GENE1 + GENE2"` for several genes.
- `viewport`: values shown by the cluster and gene bar charts. In UMAP/XY,
  `gene_summary` records whether genes are a viewport estimate (`mode: "estimate"`),
  whole-dataset values with all cells visible (`"whole"`), or a whole-dataset fallback
  (`"dataset"`); it also records scope, known units and status. Without this metadata,
  do not assume the gene values are measured within the current field of view.

### `apply_state(changes)`

Returns a promise of short descriptions of what changed, for example
`["highlighted clusters 4", "zoomed to clusters 4"]`.

| Key | Value | Like |
| --- | --- | --- |
| `space` | `"spatial"`, `"umap"` or `"xy"` | the SPATIAL / UMAP / XY buttons |
| `clusters` | cluster names; `[]` clears the selection | clicking (and shift-clicking) cluster bars |
| `genes` | gene names (up to 20); `[]` returns to cluster colors | the comma-separated gene search |
| `zoom_to` | `{"clusters": [...]}` or `{"cells": [...]}` | framing those cells (spatial view) |
| `view` | `{"target": [x, y, z], "zoom": z}`; orbit views also accept `rotationOrbit`, `rotationX` | moving/rotating the camera |
| `selected_cells` | exact cell IDs; `[]` clears them | selecting cells |
| `xy` | `{"genes": ["GENE1", "GENE2"], "scale": "linear"}`; 0–2 genes, scale `linear` or `log1p` | XY axes and scaling |
| `reset_view` | `true` | the initial view |
| `layers` | booleans for `image`, `cells`, `transcripts`, `neighborhoods` | IMG / CELL / TRX / NBHD visibility |
| `channels` | `{channelName: {visible, intensity}}` | image channel toggles and sliders; intensity is 0–100 |
| `sliders` | `{cell, nbhd, trx: {size, opacity}}` | layer size/opacity sliders; only available sliders are accepted |
| `image_source` | `"primary"` or `"he"` | the image source selector; H&E must be available |

```javascript
await landscape.apply_state({ clusters: ['4'], zoom_to: { clusters: ['4'] } });
await landscape.apply_state({ genes: ['MUC2', 'TFF3'] });
await landscape.apply_state({
  layers: { image: true, cells: false },
  channels: { DAPI: { visible: true, intensity: 35 } },
});
```

`get_state()` returns these four layer fields in the same shape. Channel visibility
is preserved independently of the master image toggle. Cell and neighborhood slider
values range from 0–100. Transcript `opacity` ranges from 0–150; `size` uses the
dataset's slider range (100 times its transcript size scale). Both transcript modes
are saved, including the inactive mode. Older single-mode transcript sliders use
`trx: {value: ...}` instead. Fields describe the available controls, so do not assume
every dataset exposes the same channels or layers.

### `capture_raster(options)`

A screenshot of the view: `{png, thumb, width, height, view_state}`, where `png` and
`thumb` are base64 PNGs (no `data:` prefix). `options.max_size` and
`options.thumb_size` set their longest side in pixels (1024 and 192 by default). It
captures the visualization itself, not the control panel.

## Clustergram

`celldega.clustergram(el, options)` returns the Clustergram object these methods are on.

### `get_state(options)`

What the Clustergram shows. Options:

| Option | Default | Meaning |
| --- | --- | --- |
| `rows`, `cols` | `"viewport"` | which rows/columns to describe: `"viewport"` (on screen), `"ranked"` (the top of the current order), or a list of names |
| `max_rows`, `max_cols` | 50 | cap on rows/columns described |
| `extra_rows`, `extra_cols` | `[]` | names to add even if off screen (e.g. genes being asked about) |
| `include_values` | `true` | include the values (and dot sizes) for the described rows and columns |
| `markers` | none | `{"clusters": ["4"], "n": 25}`: each cluster's top-n ranked markers (`rank_genes_groups`), whatever the marker level shows |

The result has, per axis (`rows`, `cols`), the names described, which of them were
`added`, `missing` names, counts, the current `order`, `attributes` (e.g. `leiden`,
`cell_type`) and dendrogram `groups`. It also has:

- `marker_level`: the marker level (the DIM slider) and the levels available;
- `cluster_markers`: with the `markers` option, `[{cluster, genes: [{name, rank,
  value, size}]}]`;
- `display`: `mode`, `size` and `focused_row`;
- `selection`: the current click, selected genes, dendrogram group and crop;
- `values`: `{values, sizes}` for the rows by columns described.
- `view`: `{target: [x, y], zoom: [xZoom, yZoom]}` for the matrix camera;
- `crop`: `{row: [...names] | null, col: [...names] | null}`; null means uncropped;
- `order`: `{row, col}`, each a named order or the complete ordered list of names.
  These three control fields are independent of `max_rows` / `max_cols`: capped
  observations do not truncate the settings needed to restore the view.

```javascript
const state = clustergram.get_state({ rows: 'ranked', max_rows: 25 });
const markers = clustergram.get_state({
  markers: { clusters: ['4', '5'], n: 25 },
  include_values: false,
}).cluster_markers;
```

### `apply_state(changes)`

Returns short descriptions of what changed, for example
`["DIM -> 10 markers per cluster"]`.

| Key | Value | Like |
| --- | --- | --- |
| `marker_level` | markers per cluster, or `"all"` | the DIM slider |
| `mode` | `"heatmap"` or `"dotplot"` | the mode buttons |
| `size` | `"prop"` or `"unit"` | the PROP / UNIT buttons |
| `focus_gene` | a row name; `""` clears it | the row search |
| `categories` | as for `set_categories` | the category editor |
| `view` | `{target: [x, y], zoom: [xZoom, yZoom]}`; either field may be omitted | pan and independent axis zoom; the camera constrains legal positions |
| `crop` | `{row: [...names] \| null, col: [...names] \| null}` | crop or undo crop for either axis |
| `order` | `{row, col}`: `"clust"`, `"rank"`, `"rankvar"`, `"ini"`, `"alpha"`, or all axis names in display order | reorder controls; only orders available in the matrix are accepted |

An explicit order must include every name on the axis exactly once, including names
outside the crop. This preserves custom, gene-based and category-based orders without
depending on the current dropdown choice. A saved explicit order restores the
displayed sequence, not a live sorting rule. Order is applied before crop, and camera
last, so combined restores survive the controls' usual camera resets.

```javascript
clustergram.apply_state({
  order: { row: 'rank', col: 'clust' },
  crop: { col: ['4', '5'] },
  view: { zoom: [1, 2] },
});
```

### `set_categories(request)`

Label rows or columns in a manual category, as the category editor would; returns how
many were labeled.

```javascript
clustergram.set_categories({
  axis: 'col',                 // or 'row'
  attribute: 'cell_type',      // created if needed
  values: { 4: 'Goblet cells', 5: 'Plasma cells' },   // '' removes a label
  colors: { 'Goblet cells': '#1f77b4' },              // optional
  replace: false,              // true clears the axis's other labels first
});
```

### `capture_raster(options)`

A screenshot of the heatmap with its labels and category strips: `{png, thumb, width,
height}`, as for the Landscape.

## Example: read, show, capture

A web page (or an agent driving one) can read what is on screen, show the evidence for a
claim, and keep a picture of it:

```javascript
import celldega from 'celldega';

const landscape = await celldega.landscape(spatial_el, { base_url });
const clustergram = await celldega.clustergram(matrix_el, { url: matrix_url });
celldega.link_models(clustergram.model, 'click_info', landscape.model, 'update_trigger');

// Get: cluster 4's top markers, and what is in the field of view.
const { cluster_markers } = clustergram.get_state({
  markers: { clusters: ['4'], n: 25 },
  include_values: false,
});
const in_view = landscape.get_state().viewport.clusters;

// Set: show cluster 4 and its top two markers.
const top = cluster_markers[0].genes.slice(0, 2).map((gene) => gene.name);
await landscape.apply_state({ zoom_to: { clusters: ['4'] }, genes: top });
clustergram.apply_state({ focus_gene: top[0] });

// Export: an image and an observation of the result (not a complete restore recipe).
const image = landscape.capture_raster({ max_size: 1024 });
const record = { state: landscape.get_state(), image: image.png };
```

## Replaying supported settings

Use `get_replay_state()` for a complete supported semantic view, or `snapshot()` for
that state together with the raster, bounded observations and provenance.

| Visualization | Supported replay state |
| --- | --- |
| Clustergram | Marker level, heatmap/dotplot mode and dot-size encoding, focused row; camera target and per-axis zoom; explicit or named order and crop; dendrogram cut percentages; selected rows/columns/genes and highlighted genes; selected dendrogram group by member names; both axes' manual annotation names, assignments and colors. |
| Landscape | Space and camera, cluster or gene coloring, selected cell IDs, XY genes/scale, layer visibility, image source, channels and sliders. |
| Orbit spatial views | The shared Landscape controls where available, plus camera `rotationOrbit` and `rotationX`. XY is unavailable in orbit views and is rejected. |

```javascript
clustergram.apply_state({
  dendrogram: { row: 35, col: 65 },
  selection: { rows: ['MUC2'], cols: ['4'], highlighted_genes: ['muc2'] },
  annotations: {
    col: { attribute: 'review', values: { '4': 'supported' }, colors: { supported: '#3377cc' } },
  },
});
await landscape.apply_state({
  space: 'xy', xy: { genes: ['MUC2', 'TFF3'], scale: 'log1p' },
  selected_cells: ['cell-1', 'cell-2'],
});
```

`annotations` replaces each supplied axis's manual annotation state; `null` clears
that axis. This updates the visualization and synced manual-category traits, not the
source AnnData. `categories` remains the patch-oriented assignment API. Do not pass
both in one operation. A saved dendrogram selection uses `{axis, members}` and must
exist at the restored cut/crop; unavailable groups fail explicitly. Selection lists
in replay state are uncapped, unlike the bounded observations returned by `get_state`.

Restore applies cuts before crop, selection after crop, and camera last. The XY
setter awaits expression loading and its position animation, and exposes failures.
An explicit layer restore also cancels delayed visibility resets from space changes.

### Completion and errors

Every Python `apply_state` call now sends one request, including trait-only controls.
The browser validates availability, applies the requested controls and replies with
`applied` or `apply_error`. Prefer:

```python
await cgm.apply_state_async({"dendrogram": {"row": 35}}, timeout=10)
request_id = cgm.restore_snapshot(saved)
await cgm.wait_for_apply(request_id, timeout=10)
```

For a nonblocking notebook cell, call `apply_state`, save `apply_request_id`, then
inspect `get_apply_result(request_id)` in a later cell. It returns `None` while pending
and never substitutes another request's success. `apply_capture_id` and `apply_error`
remain available for observers. JavaScript Landscape setters accept a second
`{timeout_ms: 30000}` option. Errors and timeouts never acknowledge success; they can
leave partial changes, and timeout does not cancel pending browser work. Recapture
before treating the outcome as evidence. Ordinary camera/reorder style animations
may still need to settle before comparing PNG pixels.

### Coverage boundaries

Saved views do not bundle source data or construct a visualization. Load the matching
data first. Transient hover/click history, drawn gates or edited neighborhood geometry,
non-manual attribute palettes, specialized composition controls, and the constructor's
2D dataset rotation transform are outside this replay contract. Orbit **camera**
rotation is supported. Linked visualizations have separate captures, not one atomic
transaction. Scientific state equality is the primary round-trip check; exact pixels
are only expected under matching canvas size, renderer, fonts, browser and GPU.

Records remain marked `restoration: "partial"` because of these boundaries. Older
saved views only restore the fields they contain. See [portable saved views](saved-views.md)
for identity checks, schema compatibility, and the explicit canvas-resize override.
