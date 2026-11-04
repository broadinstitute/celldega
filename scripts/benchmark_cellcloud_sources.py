"""Serve a browser benchmark for the hosted mouse-brain CellCloud sources.

The browser requests data directly from GitHub and Hugging Face. This server
only supplies the benchmark page/current Celldega bundle and records results.
No datasets are proxied, uploaded, or modified. Run from the repository::

    python scripts/benchmark_cellcloud_sources.py --port 8770

Use the page's controls to load each source and color Dcx. Data requests bypass
the browser HTTP cache; CDN cache state remains uncontrolled. A second Dcx
selection in the same widget measures Celldega's in-memory expression cache.
"""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from statistics import median
import threading
from urllib.parse import urlsplit


DEFAULT_DEGAFILES = (
    "https://raw.githubusercontent.com/broadinstitute/"
    "celldega_xenium_E15.5_cell_cloud/main/xenium_E15.5_cell_cloud_compact"
)
DEFAULT_ZARR = (
    "https://huggingface.co/datasets/broadinstitute/Celldega_Supporting_Data/"
    "resolve/main/Allen-Broad_Dev-Mouse-Brain/E15.5/cellcloud_v2_1um.zarr"
)

PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Hosted CellCloud source benchmark</title><style>
body{font:15px system-ui;margin:18px;color:#243344}h1{font-size:24px;margin:0 0 8px}
p{margin:9px 0}select,button{font:inherit;padding:6px;margin-right:8px}#status{font-weight:600}
#cloud{min-height:420px}table{border-collapse:collapse;margin:12px 0;width:100%;font-size:14px}
th,td{padding:6px 10px;border:1px solid #dce1e6;text-align:left}th{background:#edf3f8}
.note{max-width:1100px;color:#526575;font-size:13px}#error{color:#a32323;white-space:pre-wrap}
</style></head><body><h1>CellCloud: hosted DegaFiles vs AnnData Zarr</h1>
<p>Same 3,787,366 cells · same 480 genes · same neighborhood alignment · same current browser renderer</p>
<label>Data source <select id="source"><option value="degafiles">GitHub compact DegaFiles</option><option value="zarr">Hugging Face AnnData Zarr</option></select></label>
<button id="load">Load selected source</button><button id="gene" disabled>Color Dcx</button><button id="suite">Run 3 trials per source</button>
<p id="status" role="status">Loading current browser bundle…</p><p id="error"></p>
<p class="note">Data is fetched directly from each host with browser HTTP caching disabled. CDN cache state is uncontrolled.
Times include transfer, decoding, and two animation frames after the public API finishes; bundle startup is excluded.
Counting response bytes clones each response and can add a small amount of CPU/memory overhead. These are observations, not a controlled network-speed test.</p>
<table><thead><tr><th>Run</th><th>Source</th><th>Operation</th><th>Seconds</th><th>Payload MB</th><th>Requests</th><th>HTTP errors</th></tr></thead><tbody id="results"></tbody></table>
<div id="cloud"></div>
<script type="module">
const config=await fetch('/config.json',{cache:'no-store'}).then(r=>r.json());
const originalFetch=window.fetch.bind(window);
let active=null,current=null,busy=false,suiteRunning=false,geneSelected=false,geneHasLoaded=false;
const rows=[];
const source=document.getElementById('source'),loadButton=document.getElementById('load'),geneButton=document.getElementById('gene');
const suiteButton=document.getElementById('suite');
const status=document.getElementById('status'),errorBox=document.getElementById('error'),cloud=document.getElementById('cloud');
const sources={degafiles:config.degafiles_url.replace(/\/+$/,''),zarr:config.zarr_url.replace(/\/+$/,'')};
function isDataset(url){return Object.values(sources).some(base=>url===base||url.startsWith(base+'/'));}
window.fetch=async(input,init)=>{
 const url=new URL(typeof input==='string'||input instanceof URL?input:input.url,location.href).href;
 if(!isDataset(url))return originalFetch(input,init);
 const operation=active;
 const request={url,started_ms:performance.now(),status:null,bytes:0};
 if(operation)operation.requests.push(request);
 try{
  const response=await originalFetch(input,{...init,cache:'no-store'});
  request.status=response.status;
  request.response_ms=performance.now()-request.started_ms;
  const body=response.clone().arrayBuffer().then(buffer=>{
   request.bytes=buffer.byteLength;request.body_ms=performance.now()-request.started_ms;
  }).catch(error=>{request.body_error=error.message;});
  if(operation)operation.bodies.push(body);
  return response;
 }catch(error){request.error=error.message;throw error;}
};
const {default:celldega}=await import('/celldega.js');
const frame=()=>new Promise(resolve=>requestAnimationFrame(resolve));
function controls(){source.disabled=busy||suiteRunning;loadButton.disabled=busy||suiteRunning;geneButton.disabled=busy||suiteRunning||!current;suiteButton.disabled=busy||suiteRunning;}
function resultRow(result){
 const tr=document.createElement('tr');
 for(const value of [rows.length,result.source,result.operation,result.seconds.toFixed(3),(result.payload_bytes/1e6).toFixed(3),result.request_count,result.http_errors]){
  const td=document.createElement('td');td.textContent=String(value);tr.appendChild(td);
 }
 document.getElementById('results').appendChild(tr);
}
async function measure(operation,action){
 const operationState={requests:[],bodies:[]};active=operationState;
 const started=performance.now();
 let failure=null;
 try{await action();await frame();await frame();}
 catch(error){failure=error;errorBox.textContent=error.stack||error.message;console.error(error);}
 const renderSeconds=(performance.now()-started)/1000;
 // Data loading is awaited by the API. Finish any response-byte accounting
 // without folding that instrumentation-only wait into the operation time.
 let recorded=-1;
 while(recorded!==operationState.bodies.length){recorded=operationState.bodies.length;await Promise.all(operationState.bodies);}
 active=null;
 const requests=operationState.requests.map(({started_ms,...request})=>request);
 const result={timestamp:new Date().toISOString(),source:source.value,source_url:sources[source.value],operation,
  seconds:renderSeconds,payload_bytes:requests.reduce((sum,r)=>sum+r.bytes,0),request_count:requests.length,
  http_errors:requests.filter(r=>r.error||r.status>=400).length,requests,
  cache_policy:'no-store for dataset requests; CDN cache state uncontrolled',
  renderer:'local current docs/assets/js/celldega.js',error:failure?.message||null};
 rows.push(result);resultRow(result);
 await originalFetch('/results',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(result)});
 if(failure)throw failure;
 status.textContent=`${source.selectedOptions[0].textContent}: ${operation} finished in ${result.seconds.toFixed(2)} s, ${(result.payload_bytes/1e6).toFixed(2)} MB, ${result.request_count} requests.`;
 return result;
}
async function load(){
 if(busy)return;busy=true;controls();errorBox.textContent='';status.textContent='Loading '+source.selectedOptions[0].textContent+'…';
 current?.finalize?.();current=null;cloud.replaceChildren();geneSelected=false;geneHasLoaded=false;geneButton.textContent='Color Dcx';
 try{await measure('initial view (new widget)',async()=>{
  current=await celldega.landscape(cloud,{technology:'point-cloud',manifest_name:'cell_cloud.json',
   ...(source.value==='zarr'?{zarr_url:sources.zarr}:{base_url:sources.degafiles}),
   alignment:'neighborhood',cluster_attr:'leiden_1.0',use_adata_3d_centroids:false,
   ini_zoom:-3.8,rotation_x:20,rotation_orbit:-25,height:420,cell_size:10});
 });}catch(error){status.textContent='Source failed: '+error.message;}
 finally{busy=false;controls();}
}
async function gene(){
 if(busy||!current)return;busy=true;controls();errorBox.textContent='';
 try{
  if(geneSelected){
   status.textContent='Clearing Dcx (cached toggle; not a measured run)…';
   await current.update_matrix_gene('Dcx');geneSelected=false;geneButton.textContent='Color Dcx (widget cache)';status.textContent='Dcx cleared. Select it again to measure the widget cache.';
  }else{
   status.textContent='Loading Dcx expression…';
   await measure(geneHasLoaded?'Dcx (widget cache)':'Dcx (first selection)',()=>current.update_matrix_gene('Dcx'));
   geneHasLoaded=true;geneSelected=true;geneButton.textContent='Clear Dcx';
  }
 }catch(error){status.textContent='Gene failed: '+error.message;}
 finally{busy=false;controls();}
}
async function suite(){
 if(busy||suiteRunning)return;suiteRunning=true;controls();
 try{
  for(let trial=0;trial<3;trial+=1){
   const order=trial%2===0?['degafiles','zarr']:['zarr','degafiles'];
   for(const kind of order){
    source.value=kind;await load();
    if(!current)throw new Error('Initial load failed; stopping the comparison.');
    await gene();
    if(!geneHasLoaded)throw new Error('Gene coloring failed; stopping the comparison.');
   }
  }
  status.textContent='Comparison complete: 3 initial-load and 3 first-gene trials per source. Results are saved in the local JSONL file.';
 }catch(error){status.textContent=error.message;}
 finally{suiteRunning=false;controls();}
}
suiteButton.addEventListener('click',suite);
source.addEventListener('change',()=>{geneButton.disabled=true;status.textContent='Choose Load selected source to create a fresh widget.';});
loadButton.addEventListener('click',load);geneButton.addEventListener('click',gene);
status.textContent='Ready. Load a source, then color Dcx.';
const query=new URL(location.href).searchParams;if(query.has('source'))source.value=query.get('source');
if(query.get('auto')==='1')load();
</script></body></html>"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8770)
    parser.add_argument("--degafiles-url", default=DEFAULT_DEGAFILES)
    parser.add_argument("--zarr-url", default=DEFAULT_ZARR)
    parser.add_argument("--bundle", type=Path, default=Path("docs/assets/js/celldega.js"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/allen_mouse_brain_cellcloud_v2/hosted-benchmark-results.jsonl"),
    )
    parser.add_argument(
        "--summarize",
        action="store_true",
        help="Summarize the existing JSONL output without starting a server",
    )
    args = parser.parse_args()
    if args.summarize:
        groups = {}
        failed = 0
        for line in args.output.read_text().splitlines():
            if not line.strip():
                continue
            result = json.loads(line)
            if result.get("error"):
                failed += 1
                continue
            key = f"{result['source']} | {result['operation']}"
            groups.setdefault(key, []).append(result)
        summary = {}
        for key, records in groups.items():
            seconds = [record["seconds"] for record in records]
            summary[key] = {
                "trials": len(records),
                "median_seconds": round(median(seconds), 3),
                "min_seconds": round(min(seconds), 3),
                "max_seconds": round(max(seconds), 3),
                "median_payload_mb": round(
                    median([record["payload_bytes"] for record in records]) / 1e6, 3
                ),
                "median_requests": median([record["request_count"] for record in records]),
            }
        print(
            json.dumps(
                {"successful_measurements": summary, "failed_measurements": failed}, indent=2
            )
        )
        return
    if not args.bundle.is_file():
        parser.error(f"Bundle not found: {args.bundle}; run npm run build from the checkout")
    for url in [args.degafiles_url, args.zarr_url]:
        if urlsplit(url).scheme not in {"http", "https"}:
            parser.error("Dataset URLs must use HTTP or HTTPS")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    lock = threading.Lock()
    config = {"degafiles_url": args.degafiles_url, "zarr_url": args.zarr_url}

    class Handler(BaseHTTPRequestHandler):
        def send(self, code, content, content_type):
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(content)

        def do_GET(self):
            path = urlsplit(self.path).path
            if path == "/":
                self.send(200, PAGE.encode(), "text/html; charset=utf-8")
            elif path == "/config.json":
                self.send(200, json.dumps(config).encode(), "application/json")
            elif path == "/celldega.js":
                self.send(200, args.bundle.read_bytes(), "text/javascript; charset=utf-8")
            else:
                self.send(404, b"Not found", "text/plain")

        def do_POST(self):
            if urlsplit(self.path).path != "/results":
                self.send(404, b"Not found", "text/plain")
                return
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size < 4 * 1024 * 1024:
                self.send(413, b"Invalid result size", "text/plain")
                return
            try:
                result = json.loads(self.rfile.read(size))
                if not isinstance(result, dict) or not isinstance(result.get("requests"), list):
                    raise ValueError("Invalid result")
            except (ValueError, UnicodeDecodeError):
                self.send(400, b"Invalid JSON result", "text/plain")
                return
            with lock, args.output.open("a") as output:
                output.write(json.dumps(result) + "\n")
            print(
                f"{result.get('source')} | {result.get('operation')} | "
                f"{result.get('seconds', 0):.3f}s | {result.get('payload_bytes', 0) / 1e6:.3f}MB | "
                f"{result.get('request_count')} requests",
                flush=True,
            )
            self.send(200, b'{"recorded": true}', "application/json")

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Benchmark: http://127.0.0.1:{args.port}/", flush=True)
    print(f"Results append to: {args.output.resolve()}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
