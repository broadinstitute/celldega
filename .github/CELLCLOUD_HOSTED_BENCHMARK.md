# Hosted CellCloud benchmark

This benchmark compares the actual GitHub and Hugging Face services, using the
current local Celldega JavaScript bundle for both. It never uploads data or
proxies dataset requests through Python.

```bash
npm run build
python scripts/benchmark_cellcloud_sources.py --port 8770
```

Open the printed local URL. After both datasets are uploaded, select **Run 3
trials per source**. The page alternates source order and records three new-widget
initial loads and three first selections of Dcx for each format. The source
URLs can be pinned with `--degafiles-url` and `--zarr-url`.

Results append to:

```text
data/allen_mouse_brain_cellcloud_v2/hosted-benchmark-results.jsonl
```

Use a fresh `--output` path for a separate comparison. Summarize medians and
ranges without starting the server:

```bash
python scripts/benchmark_cellcloud_sources.py --summarize
```

For individual runs, use **Load selected source**, then **Color Dcx**. The next
click clears Dcx without recording a trial; selecting it once more measures the
widget's in-memory expression cache. A new widget resets that expression cache.

## What is measured

- **Initial view:** time from `celldega.landscape(...)` until its promise
  resolves, followed by two animation frames. This includes network, decoding,
  and scheduling the first view; JavaScript bundle import is outside the timer.
- **Gene coloring:** time spent awaiting the public
  `update_matrix_gene("Dcx")` method, followed by two animation frames. This
  includes gene transfer, expression-array updates, and scheduling the repaint.
- **Bytes:** actual response-body sizes, counted by cloning dataset fetch
  responses. Response headers and JavaScript/WASM downloads are excluded.
- **Request details:** response status, time to headers, time to complete the
  response body, and body bytes are included in each JSONL record.

Dataset fetches set `cache: "no-store"` to bypass the browser's HTTP cache.
CDN caches, server load, routing, and available bandwidth remain uncontrolled.
Response cloning can add a small amount of CPU/memory overhead. The page uses
one browser renderer and the same cells/alignment/camera for both formats;
results are observed service performance, not a universal speed guarantee.

Report median and range for both initial loading and first gene coloring.
Where results are comparable, AnnData Zarr offers a directly reusable scverse
object; where a service is noticeably slower, keep that distinction separate
from the total-byte savings. A Zarr load may transfer fewer bytes while making
more requests, which can matter on a high-latency connection.
