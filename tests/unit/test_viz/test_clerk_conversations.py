"""Saving a Clerk conversation and reopening it later, without Claude."""

import base64
import json
from pathlib import Path

import pytest


try:
    from celldega import clerk as clerk_llm
    from celldega.viz import Clerk
except Exception as e:  # pragma: no cover - skip if deps missing
    pytest.skip(f"celldega modules unavailable: {e}", allow_module_level=True)

IMAGE = base64.b64encode(b"a full-size capture").decode()


def _no_claude(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("reopening a conversation must not call Claude")

    monkeypatch.setattr(clerk_llm, "ask", fail)


def _talked(clerk_name="talked"):
    w = Clerk(name=clerk_name, context_info="Human kidney section.")
    w.messages = [
        {
            "role": "user",
            "content": "What is cluster 4?",
            "image": "thumb",
            "evidence": ["Landscape"],
        },
        {
            "role": "action",
            "content": "Ran Enrichr on cluster 4's top 5 markers",
            "genes": ["UMOD"],
        },
        {
            "role": "enrichment",
            "label": "cluster 4",
            "genes": ["UMOD"],
            "libraries": {
                "CellMarker_2024": [{"name": "Loop of Henle", "score": 9, "genes": ["UMOD"]}]
            },
        },
        {
            "role": "assistant",
            "content": "Cluster 4 is thick ascending limb [Fig 1A](view:1A).",
            "genes": ["UMOD"],
            "views": {"1A": {"landscape": {"clusters": ["4"]}}},
        },
    ]
    w.record = [
        {
            "question": "What is cluster 4?",
            "model": "",
            "effort": "",
            "sent_with": ["Landscape"],
            "steps": [
                {
                    "kind": "capture",
                    "image": IMAGE,
                    "clustergram_image": IMAGE,
                    "snapshots": {"landscape": {"state": {"clusters": ["4"]}}},
                },
                {
                    "kind": "answer",
                    "text": "Cluster 4 is thick ascending limb.",
                    "views": {"1A": {"landscape": {"clusters": ["4"]}}},
                },
            ],
        },
    ]
    w.findings = [{"cluster": "4", "label": "Thick ascending limb", "markers": ["UMOD"]}]
    w.cluster_names = ["4", "5"]
    return w


def test_a_saved_conversation_reopens_as_it_was_without_claude(tmp_path, monkeypatch):
    saved = _talked().save_conversation(tmp_path, title="Kidney demo")
    assert saved.parent == tmp_path and saved.name.startswith("kidney-demo_")
    _no_claude(monkeypatch)
    fresh = Clerk(name="fresh")
    info = fresh.load_conversation(saved)
    assert info["title"] == "Kidney demo" and info["context_info"] == "Human kidney section."
    # The panel shows it as it was, links and Enrichr results included.
    assert fresh.messages == _talked("again").messages
    assert fresh.findings[0]["label"] == "Thick ascending limb"
    assert fresh.context_info == "Human kidney section." and fresh.cluster_names == ["4", "5"]
    # Replay settings stay; full-size captures are left out of the light file.
    step = fresh.record[0]["steps"][0]
    assert "image" not in step and "clustergram_image" not in step
    assert step["snapshots"]["landscape"]["state"] == {"clusters": ["4"]}


def test_conversations_save_to_clerk_files_by_default(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    saved = _talked().save_conversation()
    assert saved.parent == Path("clerk_files/conversations")
    assert json.loads(saved.read_text())["celldega_clerk_conversation"] == 1


def test_an_exported_report_reopens_with_its_images(tmp_path, monkeypatch):
    written = _talked().export(tmp_path / "report", html=False)
    record = json.loads(written["record"].read_text())
    assert record["messages"][3]["views"] == {"1A": {"landscape": {"clusters": ["4"]}}}
    _no_claude(monkeypatch)
    fresh = Clerk(name="fresh")
    fresh.load_conversation(tmp_path / "report")
    assert fresh.messages == _talked("again").messages
    assert fresh.record[0]["steps"][0]["image"] == IMAGE  # read back from images/


def test_an_older_report_without_messages_is_rebuilt_from_its_record(tmp_path):
    folder = tmp_path / "old"
    folder.mkdir()
    (folder / "record.json").write_text(
        json.dumps(
            {
                "version": 1,
                "meta": {"context": "Human kidney section."},
                "questions": [
                    {
                        "question": "What is cluster 4?",
                        "sent_with": ["Landscape"],
                        "steps": [
                            {"kind": "action", "text": "Highlighted cluster 4"},
                            {
                                "kind": "answer",
                                "text": "Thick ascending limb.",
                                "views": {"1A": {}},
                            },
                        ],
                    }
                ],
                "findings": [],
            }
        )
    )
    w = Clerk(name="older")
    w.load_conversation(folder)
    assert [m["role"] for m in w.messages] == ["user", "action", "assistant"]
    assert w.messages[2]["content"] == "Thick ascending limb." and w.messages[2]["views"] == {
        "1A": {}
    }


def test_the_save_and_open_buttons(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    w = _talked()
    w.request = {"id": "save-1", "save_conversation": True}
    note = w.messages[-1]
    assert note["role"] == "note" and "clerk.load_conversation(" in note["content"]
    saved = next(Path("clerk_files/conversations").glob("*.json"))

    _no_claude(monkeypatch)
    fresh = Clerk(name="fresh")
    fresh._on_panel_msg(
        fresh, {"event": "load_conversation", "name": saved.name, "text": saved.read_text()}, []
    )
    assert fresh.messages[:-1] == _talked("again").messages
    assert fresh.messages[-1] == {
        "role": "note",
        "content": f"Opened the conversation saved in {saved.name}.",
    }
    fresh._on_panel_msg(fresh, {"event": "load_conversation", "name": "x.json", "text": "{}"}, [])
    assert (
        fresh.messages[-1]["role"] == "error"
        and "Couldn't open x.json" in fresh.messages[-1]["content"]
    )


def test_unreadable_or_untimely_loads_are_refused(tmp_path):
    w = Clerk(name="refuse")
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"celldega_clerk_conversation": 99, "messages": []}))
    with pytest.raises(ValueError, match="version 99"):
        w.load_conversation(bad)
    bad.write_text(json.dumps([1, 2]))
    with pytest.raises(ValueError, match="Not a saved Clerk conversation"):
        w.load_conversation(bad)
    good = _talked().save_conversation(tmp_path)
    w.pending = True
    with pytest.raises(RuntimeError, match="answering"):
        w.load_conversation(good)
