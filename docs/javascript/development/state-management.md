# State management

How a Celldega visualization holds its state in the browser, how a change becomes a
redraw, and what to follow when you add a control or embed Celldega in an
application. To read or change a view from code, prefer the
[Viz API](../viz-api.md); this page explains what it builds on.

## Where state lives

Each visualization keeps its state in four places:

| Place | Holds | Read and written by |
| --- | --- | --- |
| **Model** (anywidget model, or `make_options_model` in a web page) | Constructor options and the traits shared with Python, such as `base_url`, `cluster_attr`, `landscape_state`, `xy_genes`, `selected_cells` and `update_trigger` | Python and the browser |
| **`viz_state`** | Everything one visualization has loaded or derived: cell and gene arrays (`cats`, `genes`, `spatial`), image metadata (`img`), the current layer instances (`layers_obj`), the camera (`current_view_state`) | Renderer code. A plain mutable object: changing it notifies no one |
| **`obs_store`** (`viz_state.obs_store`) | Observable interface state: selections, the view mode, layer visibility modes, whether the view is close up, and the redraw flags | Controls, linked widgets and the Viz API; subscribers react to changes |
| **deck.gl** | The layer instances it was last given, and its own camera | Only through `deck.setProps(...)` |

```text
      Python (notebook)                      Browser
 ┌────────────────────┐                     ┌────────────────────────────────────────┐
 │ widget             │                     │ model     change:<trait> events        │
 │ traits, request    │ ◄─ synced traits ─► │                                        │
 │ ids and replies    │                     │ viz_state  loaded and derived          │
 │                    │  ◄── msg:custom ──► │   └─ layers_obj  layer instances       │
 │                    │                     │ obs_store  observable UI state         │
 │                    │                     │   └─ deck_check ─► deck_ready ─┐       │
 └────────────────────┘                     └────────────────────────────────┼───────┘
                                                                             │  deck.setProps({ layers })
                                                                             ▼
                                                                          deck.gl
```

Every visualization creates its own `viz_state` and `obs_store`, so two Landscapes
on a page never share a selection. Links between widgets go through their models
(see [below](#the-model-and-python)).

## The observable store

`create_obs_store()` (`js/obs_store/obs_store.js`) returns an object of observables.
Each one has:

- `get()`: the current value.
- `set(value)`: store the value and call every subscriber with it.
- `subscribe(fn, { immediate })`: call `fn` on each change, and also once right away
  unless `immediate: false`. Returns a function that unsubscribes.
- `getDefault()`: the initial value.

Subscribers run synchronously inside `set`, in the order they subscribed. A `set` made
inside a subscriber runs its own subscribers before the outer `set` returns.

**Change detection differs between stores.** The Landscape store notifies when the
new value is not the same object (`!==`). Setting the same array does nothing, and a
new array with equal contents notifies. So always set a new value, such as
`selected_cats.set([...names])`, and never mutate an observable's array in place: a
mutation is invisible to subscribers, and a later `set` of that same array is
skipped. The Clustergram store (`create_clustergram_store()`) compares values as
JSON instead, so a value with equal contents does not notify.

The Landscape observables you are most likely to touch:

| Observable | Meaning |
| --- | --- |
| `cat` | What colors the cells: `'cluster'` or a gene |
| `selected_cats`, `selected_genes`, `selected_cells` | The current selections |
| `landscape_view`, `umap_state` | The view mode: `'spatial'`, `'umap'` or `'xy'` |
| `close_up` | Zoomed in far enough to show transcripts and cell boundaries |
| `viz_image_layers`, `viz_background_layer` | Whether the tissue image and background are shown |
| `viz_nbhd_layer`, `viz_edit_layer` | Neighborhood mode and the drawing editor |
| `new_cell_bar_data`, `new_gene_bar_data` | What the cluster and gene bar charts show |
| `deck_check`, `deck_ready` | The redraw flags (next section) |

Some state is derived from other observables. For example,
`setup_image_visibility_manager` subscribes to `selected_cats`, `selected_genes`
and `close_up`. While clusters or a single gene are selected, it hides the image when
zoomed out (so the colored cells stand out) and shows it when zoomed in. With nothing
selected it shows the image, unless the IMG button is off.

Manual categories in a Clustergram use a small class instead,
`ManualCategoryStore` (`js/obs_store/manual_category_store.js`), one per axis at
`obs_store.manual_cat.row` and `.col`. Its `setAttribute` and `updateSelection` call
`emit()`, and its subscribers redraw the category strips and sync the result to
Python's `manual_cat`.

## How a change reaches the screen

deck.gl layers are immutable descriptions. To change one, clone it with new props
and give deck.gl the new list; deck.gl matches layers by `id`, updates only what
changed, and redraws on its next animation frame. Accessors such as
`getFillColor` re-run only when the layer's `data` changes or a value in its
`updateTriggers` changes.

A Landscape funnels every redraw through one place:

```text
 a control, a linked widget, or apply_state
     │
     ▼
 1. update viz_state, then clone the layer into layers_obj
        layers_obj.cell_layer = layers_obj.cell_layer.clone({ ... })
     │
     ▼
 2. refresh_layer(viz_state, layers_obj, 'cell_layer')
        deck_check.cell_layer:  true → false → true
     │
     ▼
 3. deck_check's subscriber:  deck_ready = every flag is true
        (stays false while a loader holds its flag false)
     │
     ▼
 4. deck_ready's subscriber, on false → true:
        deck.setProps({ layers: get_layers_list(viz_state.layers_obj, close_up, viz_state) })
     │
     ▼
 5. deck.gl diffs the layers by id and redraws on the next frame
```

**Why the flag goes false and back.** `deck_ready` is an observable, so it only
notifies when it changes. In steady state it is already `true`; writing `true` again
does nothing and nothing repaints. `refresh_layer` (`js/utils/refresh_layer.js`)
sets the layer's flag to `false` and then `true`, which drives `deck_ready` from
`false` to `true` and so calls `setProps`.

**Loaders hold the gate.** When the camera moves close enough, `calc_viewport` sets
`trx_data` and `path_data` to `false`, fetches the transcripts and cell boundaries in
view, clones those layers, and sets the flags back to `true`. While any flag is
`false`, `deck_ready` stays `false`, so the deck is never redrawn with half-loaded
layers; the last loader to finish triggers one `setProps` with everything.

**Selections and update triggers.** The cell layer's colors and sizes depend on
selections that live outside its `data`. Selecting cells increments
`viz_state.selection_token`, and the cell layer lists that token in
`updateTriggers` for `getFillColor` and `getRadius` (`getColor` in point clouds), so
deck.gl re-runs those accessors. A new accessor that reads state outside `data`
needs a trigger the same way, or it keeps showing the old values.

**Hide close-up layers, don't remove them.** `get_layers_list`
(`js/deck-gl/utils/layers_ist.js`) builds the list in drawing order: background,
the active image source, cell boundaries, cells, transcripts, neighborhoods, the
neighborhood-cloud layers, then the drawing editor. When zoomed out it passes the boundary
and transcript layers as hidden clones (`visible: false`) rather than leaving them
out. deck.gl finalizes a layer that leaves the list and cannot initialize that
instance again, so re-adding it on zoom-in would fail and could draw freed GPU
buffers.

## The camera

deck.gl owns the camera. Each frame of a pan or zoom calls `onViewStateChange`,
which records the camera in `viz_state.current_view_state` right away (getters and
screenshots read it there). A handler debounced to 200 ms then runs `calc_viewport`.
It decides whether the view is close up, loads what the viewport needs, and updates
the bar charts for what is in view.

To move the camera from code, call the visualization's
`update_view_state(view, close_up)` and await it; `apply_state({view})` does this.

deck.gl's 2D camera state inherits the 3D orbit camera's `rotationOrbit` and
`rotationX`, both 0, once the user pans or zooms. They mean nothing in a 2D view, so
the getters leave them out.

## The model and Python

The model carries the traits shared with Python.

- **From Python or a link:** a trait set in Python, or by a front-end link, fires
  `change:<name>` on the browser model. For example, `spatial_clustergram` links a
  Clustergram's `click_info` to the Landscape's `update_trigger`, and the Landscape's
  listener colors or selects cells.
- **To Python:** the browser calls `model.set(name, value)` and then
  `model.save_changes()`. Traits synced this way include `selected_cells`,
  `landscape_state`, `xy_genes` and the Clustergram's `manual_cat`.
- **Requests and replies:** the Viz API's requests and replies (`get_state`,
  `apply_state`, `capture_snapshot`, `restore_snapshot`, `capture_raster`, PIC saves)
  travel as one-off `msg:custom` messages instead. That keeps images and observations
  out of the notebook's saved widget state. Each reply carries its request's id.

In a web page without Python, `make_options_model` provides the same `get`, `set` and
`on` interface, and `link_models` connects two models' traits the way `jslink` does
in a notebook.

## The Clustergram

The Clustergram follows the same ideas with two differences:

- Its store is `create_clustergram_store()`, with JSON-equality observables, plus the
  `ManualCategoryStore`s above.
- It redraws directly: code clones layers into `layers_mat` and calls
  `deck_mat.setProps({ layers: get_mat_layers_list(layers_mat) })`. There is no
  `deck_check` gate; its layers are built from the matrix loaded when it opens. One
  deck draws several views (the matrix, labels and dendrograms), with the camera
  state in `viz_state.zoom`.

## Adding to it

- **Change state through observables.** Set new values, never mutate an observable's
  array in place.
- **Repaint through the gate.** After cloning a Landscape layer, call `refresh_layer`.
  For a Clustergram, pass the updated layer list to `setProps`.
- **Hold your flag while you load.** An asynchronous loader should set its
  `deck_check` flag to `false` before fetching and to `true` after cloning its
  layer, so the deck never draws a partial result.
- **Trigger accessors.** Put any state an accessor reads outside `data` into the
  layer's `updateTriggers`.
- **Hide, don't remove.** Keep a layer you will need again in the list with
  `visible: false`.
- **Clean up.** Keep each `subscribe`'s unsubscribe function and each `model.on`
  listener, and release them in `finalize`; `landscape_ist` collects them for this.
- **Keep large or transient data out of traits.** Synced traits are saved with the
  notebook; send requests and replies as `msg:custom` messages.
- **From outside, use the Viz API.** `get_state` reads `viz_state` and `obs_store`
  into plain JSON, and `apply_state` changes them through the same helpers as the
  controls, including the repaint above. See the [Viz API](../viz-api.md).
