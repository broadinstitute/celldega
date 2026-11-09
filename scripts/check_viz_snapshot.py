"""Run the standalone saved-view example's checks in a real browser.

Build first (npm run build), then run with a Python environment containing Playwright:
    python scripts/check_viz_snapshot.py --channel chrome
No notebook kernel, model backend or external dataset is needed.
"""

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading

from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--channel", default=None, help="e.g. chrome; default uses Playwright Chromium"
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]

    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(root)))
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                channel=args.channel, args=["--enable-unsafe-swiftshader"]
            )
            try:
                page = browser.new_page(viewport={"width": 1600, "height": 1100})
                page.goto(f"http://127.0.0.1:{server.server_port}/examples/viz-api/")
                page.wait_for_function("window.celldegaSnapshotExample", timeout=60000)
                results = page.evaluate("() => window.celldegaSnapshotExample.check()")
                assert all(results.values()), results
                print(json.dumps(results, indent=2))
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)


if __name__ == "__main__":
    main()
