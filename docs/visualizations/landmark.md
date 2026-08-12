# Landmark

!!! warning "Early / less developed"
    `Landmark` is newer and less polished than Celldega's other
    visualizations — expect rougher edges and API changes.

`Landmark` is a spatial widget for interactively marking corresponding
points across two tissue slices, to drive procrustes / thin-plate-spline
alignment between them.

## What it shows

- **Two side-by-side viewports**, each showing one slice's cells (optionally
  colored by a cluster column for visual context).
- **MARK** and **MODIFY** modes for placing and editing landmark points on
  each slice.
- A dropdown per viewport to switch which slice it displays, when more than
  two slices are available.

## Usage

```python
import celldega as dega

lm = dega.viz.Landmark(adatas=adata, slice_attr="slice_id")
lm
```

The resulting `lm.landmarks` table feeds
[`celldega.align.landmarks`](../python/align/api.md) alignment functions. See
the [Viz Module API reference](../python/viz/api.md) for the full set of
constructor arguments.

!!! note
    Screenshots and an example video are coming soon.
