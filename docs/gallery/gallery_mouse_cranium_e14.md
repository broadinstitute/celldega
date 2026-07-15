# Mouse Cranium E14 (3D point cloud, local)

A 3D point-cloud `Landscape` of the E14 mouse cranium — one stage of the StrataMap
stacked cranium dataset (see the `StrataMap.ipynb` notebook), colored by the clustering
computed jointly across the E12/E13/E14 stages.

**This example runs against a local DegaFiles server** — the dataset isn't hosted
publicly yet. Before loading this page, serve the DegaFiles directory built by
`StrataMap.ipynb` (`data/michal_landscape_files/E14_62_together_raw_v2_point-cloud/`)
with a CORS-enabled static file server, e.g.:

```bash
npx http-server notebooks/data/michal_landscape_files/E14_62_together_raw_v2_point-cloud -p 8080 --cors
```

Then update `base_url` in `docs/assets/js/gallery_mouse_cranium_e14.js` to point at
that server (default assumes `http://localhost:8080`).

<div id="landscape-container" style="position: relative; display: flex; width: 100%; height: 700px; overflow: hidden; border: 1px solid #ccc;">
    <div id="landscape-mouse-cranium-e14" style="height: 700px; width: 100%;"></div>
</div>
