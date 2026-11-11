"""How widgets locate their front-end bundle (CDN shim, inlined file, or served file)."""

import re
import urllib.request

import pytest

from celldega.viz import widget


def test_local_esm_inlines_the_file(monkeypatch) -> None:
    monkeypatch.setenv("CELLDEGA_LOCAL_ESM", "1")
    assert widget._resolve_widget_esm() == widget._LOCAL_ESM


def test_esm_version_uses_cdn_shim(monkeypatch) -> None:
    monkeypatch.delenv("CELLDEGA_LOCAL_ESM", raising=False)
    monkeypatch.delenv("ANYWIDGET_HMR", raising=False)
    monkeypatch.setenv("CELLDEGA_ESM_VERSION", "1.2.3")
    shim = widget._resolve_widget_esm()
    assert "cdn.jsdelivr.net/npm/celldega@1.2.3" in shim
    assert shim.startswith("export { default } from")


@pytest.mark.skipif(not widget._LOCAL_ESM.exists(), reason="JS bundle not built")
def test_serve_mode_serves_the_bundle_once(monkeypatch) -> None:
    monkeypatch.setenv("CELLDEGA_LOCAL_ESM", "serve")
    shim = widget._resolve_widget_esm()

    # Each widget stores only this small shim instead of the whole bundle.
    assert len(shim) < 200
    url = re.search(r"from '([^']+)'", shim).group(1)
    assert url.startswith("http://localhost:")

    # The browser imports the module cross-origin: it needs CORS and a JS MIME type.
    with urllib.request.urlopen(url, timeout=10) as resp:
        assert resp.status == 200
        assert resp.headers["Access-Control-Allow-Origin"] == "*"
        assert "javascript" in resp.headers["Content-Type"]
        assert len(resp.read()) == widget._LOCAL_ESM.stat().st_size
