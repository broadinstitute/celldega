"""Transport-independent saved-view validation and local dataset fingerprints.

The browser computes/compares the fingerprint of the data it actually renders.
These helpers are also usable by celldega-app without a notebook or widget.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path


SCHEMA = "celldega.view"
VERSION = 1


def restore_spec(snapshot: dict) -> dict:
    """Keep the portable restore contract without duplicating pixels/observations."""
    return deepcopy(
        {
            k: snapshot[k]
            for k in (
                "schema",
                "version",
                "kind",
                "renderer",
                "captured_at",
                "identity",
                "viewport",
                "capture",
                "restoration",
                "state",
            )
            if k in snapshot
        }
    )


def validate_snapshot(snapshot: dict) -> None:
    if (
        not isinstance(snapshot, dict)
        or snapshot.get("schema") != SCHEMA
        or snapshot.get("version") != VERSION
    ):
        raise ValueError("Unsupported saved-view schema/version")
    if snapshot.get("kind") not in ("landscape", "clustergram"):
        raise ValueError("Unsupported saved-view kind")
    if not isinstance(snapshot.get("state"), dict):
        raise ValueError("Saved view has no replay settings")
    identity = snapshot.get("identity") or {}
    if not isinstance(identity, dict):
        raise ValueError("Saved view has no valid SHA-256 data identity")
    digest = identity.get("digest", "")
    if (
        identity.get("algorithm") != "sha256"
        or not isinstance(digest, str)
        or len(digest) != 64
        or any(c not in "0123456789abcdef" for c in digest)
    ):
        raise ValueError("Saved view has no valid SHA-256 data identity")


def fingerprint_dataset(path: str | Path) -> str:
    """Hash all file contents and relative names in a local dataset (or one file).

    This can be expensive for large stores; call when publishing/loading an immutable
    dataset, pass the result as ``Landscape(data_revision=...)``, and regenerate it
    after modifying the data. The browser trusts that revision for remote assets it
    has not downloaded. Keep exports outside this directory. Symlinks are rejected.
    """
    root = Path(path)
    if not root.exists():
        raise FileNotFoundError(root)
    if root.is_symlink():
        raise ValueError("Dataset fingerprints require a regular directory or file")
    paths = sorted(root.rglob("*")) if root.is_dir() else [root]
    entries = []
    for item in paths:
        if item.is_symlink():
            raise ValueError(f"Dataset fingerprints require regular files, not symlinks: {item}")
        if not item.is_file():
            continue
        before = item.stat()
        with item.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        after = item.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError(f"Dataset changed while hashing: {item}")
        entries.append([str(item.relative_to(root)) if root.is_dir() else item.name, digest])
    if not entries:
        raise ValueError("Dataset contains no files")
    return (
        "sha256:" + hashlib.sha256(json.dumps(entries, separators=(",", ":")).encode()).hexdigest()
    )
