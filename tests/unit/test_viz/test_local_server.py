"""Tests for the local file server's byte-range support."""

import pytest
import requests

from celldega.viz.local_server import _parse_byte_range, get_local_server


@pytest.fixture
def served_file(tmp_path):
    """Serve a 10-byte file and return its URL."""
    (tmp_path / "data.bin").write_bytes(b"0123456789")
    port = get_local_server(file_server_root=tmp_path)
    return f"http://localhost:{port}/data.bin"


def test_full_request_returns_whole_file(served_file):
    response = requests.get(served_file, timeout=5)
    assert response.status_code == 200
    assert response.content == b"0123456789"
    assert response.headers["Access-Control-Allow-Origin"] == "*"


@pytest.mark.parametrize(
    ("range_header", "body", "content_range"),
    [
        ("bytes=2-4", b"234", "bytes 2-4/10"),
        ("bytes=-3", b"789", "bytes 7-9/10"),
        ("bytes=5-", b"56789", "bytes 5-9/10"),
        ("bytes=8-100", b"89", "bytes 8-9/10"),
    ],
)
def test_single_range_returns_partial_content(served_file, range_header, body, content_range):
    response = requests.get(served_file, headers={"Range": range_header}, timeout=5)
    assert response.status_code == 206
    assert response.content == body
    assert response.headers["Content-Range"] == content_range
    assert response.headers["Content-Length"] == str(len(body))
    assert response.headers["Accept-Ranges"] == "bytes"
    assert response.headers["Access-Control-Allow-Origin"] == "*"


def test_range_beyond_file_is_unsatisfiable(served_file):
    response = requests.get(served_file, headers={"Range": "bytes=100-"}, timeout=5)
    assert response.status_code == 416
    assert response.headers["Content-Range"] == "bytes */10"


def test_multiple_ranges_fall_back_to_whole_file(served_file):
    response = requests.get(served_file, headers={"Range": "bytes=0-1,4-5"}, timeout=5)
    assert response.status_code == 200
    assert response.content == b"0123456789"


def test_head_with_range_sends_partial_headers(served_file):
    response = requests.head(served_file, headers={"Range": "bytes=0-7"}, timeout=5)
    assert response.status_code == 206
    assert response.headers["Content-Range"] == "bytes 0-7/10"
    assert response.content == b""


def test_missing_file_with_range_is_not_found(served_file):
    response = requests.get(
        served_file.replace("data.bin", "missing.bin"), headers={"Range": "bytes=0-1"}, timeout=5
    )
    assert response.status_code == 404


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("bytes=0-0", (0, 0)),
        ("bytes=-20", (0, 9)),
        ("bytes=-0", "unsatisfiable"),
        ("bytes=10-", "unsatisfiable"),
        ("bytes=5-2", None),
        ("bytes=a-b", None),
        ("items=0-1", None),
        ("bytes=0-1,3-4", None),
    ],
)
def test_parse_byte_range(header, expected):
    assert _parse_byte_range(header, 10) == expected
