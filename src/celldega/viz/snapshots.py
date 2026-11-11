"""Transport-independent saved-view validation and local dataset fingerprints.

A saved view identifies its data by name: the browser records counts and fast hashes
of the loaded cell, gene and cluster-label names (or a Clustergram's row and column
names) and compares them on restore. A producer can also declare an immutable
``data_revision`` (for example from :func:`fingerprint_dataset`) for exact content
identity. These helpers are also usable by celldega-app without a notebook or widget.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path


SCHEMA = "celldega.view"
# 2: name-based data identity and canvas size in CSS pixels (1 hashed all loaded data).
VERSION = 2


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
                "description",
                "author",
                "identity",
                "source",
                "viewport",
                "capture",
                "restoration",
                "state",
            )
            if k in snapshot
        }
    )


def validate_snapshot(snapshot: dict) -> None:
    """Check a saved view's envelope before sending it to the browser.

    The browser checks the data identity and canvas size against what it shows.
    """
    if not isinstance(snapshot, dict) or snapshot.get("schema") != SCHEMA:
        raise ValueError("Not a Celldega saved view (unsupported schema/version)")
    if snapshot.get("version") != VERSION:
        raise ValueError(
            f"Unsupported saved-view schema/version {snapshot.get('version')!r}; this "
            f"Celldega reads version {VERSION}. Recapture the view."
        )
    if snapshot.get("kind") not in ("landscape", "clustergram"):
        raise ValueError("Unsupported saved-view kind")
    if not isinstance(snapshot.get("state"), dict):
        raise ValueError("Saved view has no replay settings")
    identity = snapshot.get("identity")
    if not isinstance(identity, dict) or not identity:
        raise ValueError("Saved view has no data identity")


def fingerprint_dataset(path: str | Path) -> str:
    """Hash all file contents and relative names in a local dataset (or one file).

    Use it to declare an exact content revision: compute it when publishing an
    immutable dataset, pass the result as ``Landscape(data_revision=...)`` (or
    ``Clustergram``), and regenerate it after modifying the data. Any immutable
    identifier works as a revision (a release tag or commit hash, say); this is one
    way to make one. It can be slow for large stores. Keep exports outside this
    directory. Symlinks are rejected.
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
