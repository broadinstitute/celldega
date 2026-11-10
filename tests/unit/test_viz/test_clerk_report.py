"""Clerk's exported record: HTML / notebook report, JSON record, findings, AnnData."""

import base64
import json
import re

import pandas as pd
import pytest


try:
    import anndata as ad

    from celldega import clerk as clerk_llm
    from celldega.clerk import report
    from celldega.viz import Clerk
    from celldega.viz.widget import _clustergram_reproduction, _landscape_reproduction
except Exception as e:  # pragma: no cover - skip if deps missing
    pytest.skip(f"celldega modules unavailable: {e}", allow_module_level=True)

PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="


def _record() -> tuple[list[dict], list[dict]]:
    finding = {
        "cluster": "4",
        "label": "Goblet cells",
        "confidence": "high",
        "markers": ["MUC2", "TFF3"],
        "notes": "",
        "question": "What is cluster 4?",
        "recorded": "2026-11-07 10:00:00",
    }
    record = [
        {
            "question": "What is cluster 4?",
            "asked": "2026-11-07 10:00:00",
            "model": "opus",
            "effort": "high",
            "message_index": 0,
            "sent_with": ["Landscape view"],
            "context": "",
            "gene_list": [],
            "steps": [
                {
                    "kind": "capture",
                    "text": "When asked",
                    "image": PNG,
                    "landscape": {"space": "spatial", "view": {"target": [1, 2], "zoom": -1}},
                    "clustergram": {"marker_level": 25},
                    "view_state": {},
                },
                {"kind": "action", "text": "Read the top 25 ranked markers of clusters 4"},
                {"kind": "lookups", "text": "Enrichr for cluster 4: Goblet cell"},
                {"kind": "answer", "text": "Checking markers."},
                {
                    "kind": "answer",
                    "text": "Goblet cells (high).\n\nEvidence:\n- MUC2 high\n- TFF3 high\n\n"
                    "Check cluster 7 too?",
                },
                {"kind": "findings", "text": "4 → Goblet cells", "cell_types": [finding]},
            ],
        }
    ]
    return record, [finding]


def test_reproductions_map_state_to_setters() -> None:
    landscape = _landscape_reproduction(
        {
            "space": "spatial",
            "view_state": {"target": [5.0, 6.0, 0], "zoom": 1.5},
            "color_by": "MUC2",
            "selected_clusters": [],
            "selected_genes": ["MUC2"],
        }
    )
    assert landscape == {
        "space": "spatial",
        "view": {"target": [5.0, 6.0, 0], "zoom": 1.5},
        "genes": ["MUC2"],
    }
    assert _landscape_reproduction(None) == {}
    cgm = _clustergram_reproduction(
        {
            "marker_level": {"current": None},
            "display": {"mode": "dotplot", "size": "unit", "focused_row": "MUC2"},
        }
    )
    assert cgm == {"marker_level": "all", "mode": "dotplot", "size": "unit", "focus_gene": "MUC2"}


def test_split_evidence_matches_the_panel() -> None:
    assert report.split_evidence("Goblet.\n\n**Evidence:**\n- MUC2\n- TFF3\n\nMore?") == (
        "Goblet.",
        "- MUC2\n- TFF3",
        "More?",
    )
    assert report.split_evidence("Evidence suggests goblet.") == (
        "Evidence suggests goblet.",
        "",
        "",
    )


def test_usage_line() -> None:
    usage = {
        "calls": 3,
        "input_tokens": 1000,
        "cache_creation_input_tokens": 5000,
        "cache_read_input_tokens": 35000,
        "output_tokens": 1000,
        "cost_usd": 0.0612,
    }
    assert report._usage_text(usage) == (
        " · 3 model calls · 42k tokens (35k from cache) · ~$0.061 est."
    )
    assert report._usage_text(None) == ""


def test_reproduction_code_uses_apply_state() -> None:
    code = report.reproduction_code(
        {"landscape": {"clusters": ["4"]}, "clustergram": {"marker_level": 10}},
        names={"landscape": "ls"},
    )
    assert code == "ls.apply_state({'clusters': ['4']})\ncgm.apply_state({'marker_level': 10})"


def test_export_writes_html_notebook_record_and_findings(tmp_path) -> None:
    pytest.importorskip("nbconvert")
    w = Clerk()
    w.record, w.findings = _record()
    adata = ad.AnnData(obs=pd.DataFrame({"leiden": ["4", "5", "4"]}, index=["a", "b", "c"]))

    written = w.export(tmp_path / "out", adata=adata, groupby="leiden")

    assert set(written) == {"record", "findings", "notebook", "html", "cell_types"}
    page = written["html"].read_text()
    text = re.sub(r"<[^>]+>", "", page)  # code is syntax-highlighted
    assert "What is cluster 4?" in page
    assert "landscape.apply_state" in text and "cgm.apply_state" in text
    assert "<details" in page and "Work · 3 steps" in page
    assert f"data:image/png;base64,{PNG}" in page
    assert "Check cluster 7 too?" in page

    saved = json.loads(written["record"].read_text())
    shot = saved["questions"][0]["steps"][0]["image"]
    assert shot == "images/q1_1.png"
    assert (tmp_path / "out" / shot).read_bytes() == base64.b64decode(PNG)
    assert saved["findings"][0]["label"] == "Goblet cells"

    findings = pd.read_csv(written["findings"])
    assert findings.loc[0, "markers"] == "MUC2, TFF3"
    assert list(adata.obs["clerk_cell_type"]) == ["Goblet cells", "Unassigned", "Goblet cells"]
    # Exporting again replaces Clerk's own column instead of failing.
    w.export(tmp_path / "again", adata=adata, groupby="leiden")


def test_export_needs_groupby_with_adata(tmp_path) -> None:
    w = Clerk()
    adata = ad.AnnData(obs=pd.DataFrame({"leiden": ["4"]}, index=["a"]))
    with pytest.raises(ValueError, match="groupby"):
        w.export(tmp_path / "x", adata=adata, html=False)


def test_panel_export_button_writes_a_report(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    w = Clerk()
    w.record, w.findings = _record()
    w.request = {"id": "e1", "export": True}
    note = w.messages[-1]
    assert note["role"] == "note"
    assert "Saved this conversation to clerk_files/report_" in note["content"]
    assert list(tmp_path.glob("clerk_files/report_*/record.json"))
    # Notes are for the scientist, not the model.
    assert "Saved this" not in clerk_llm.build_prompt("q", history=w.messages)


def test_briefing_from_an_exported_record(tmp_path, monkeypatch) -> None:
    earlier = Clerk()
    earlier.record, earlier.findings = _record()
    earlier.export(tmp_path / "case1", html=False)

    w = Clerk()
    text = w.load_briefing(tmp_path / "case1")
    assert "What is cluster 4?" in text
    assert "Goblet cells (high)." in text  # the final answer, not the interim one
    assert "Checking markers." not in text
    assert "| 4 | Goblet cells | high | MUC2, TFF3 |" in text
    assert w.briefing_label.startswith("Briefing: ")
    assert w.briefing_label.endswith("of earlier work from case1")

    # It goes with every question, labeled as earlier conclusions to check.
    calls = []
    monkeypatch.setattr(clerk_llm, "ask", lambda q, **kw: calls.append(kw) or "ok")
    w.request = {"id": "1", "question": "q"}
    assert w.wait(timeout=5)
    assert calls[0]["briefing"] == text
    prompt = clerk_llm.build_prompt("q", briefing=text)
    assert "## Earlier work (shared by the scientist)" in prompt
    assert "not as evidence" in prompt
    assert w.record[-1]["briefing"] is True

    # Appending another source, then setting text directly (no source label).
    w.load_briefing(earlier, append=True)
    assert w.briefing_sources == ["case1", "another Clerk panel"]
    w.briefing = "My notes."
    assert w.briefing_sources == [] and w.briefing_label.endswith("of earlier work")
    w.briefing = ""
    assert w.briefing_label == ""


def test_briefing_from_a_text_file_and_missing_source(tmp_path) -> None:
    notes = tmp_path / "notes.md"
    notes.write_text("Cluster A looked mixed last time.")
    w = Clerk()
    assert w.load_briefing(notes) == "Cluster A looked mixed last time."
    with pytest.raises(FileNotFoundError):
        w.load_briefing(tmp_path / "missing")


def test_report_shows_the_briefing(tmp_path) -> None:
    pytest.importorskip("nbconvert")
    w = Clerk()
    w.record, w.findings = _record()
    w.briefing = "Cluster A looked mixed last time."
    written = w.export(tmp_path / "out")
    page = written["html"].read_text()
    assert "Briefing: Clerk was given earlier work" in page
    assert "Cluster A looked mixed last time." in page


def test_long_briefings_are_capped() -> None:
    prompt = clerk_llm.build_prompt("q", briefing="x" * 70_000)
    assert "[briefing truncated]" in prompt


def test_report_turns_cited_views_into_figures(tmp_path) -> None:
    pytest.importorskip("nbconvert")
    record, findings = _record()
    final = next(s for s in reversed(record[0]["steps"]) if s["kind"] == "answer")
    final["text"] = "Goblet cells line the crypts [Fig 1A](view:1A), not [x](view:9)."
    final["views"] = {"1A": {"caption": "Cluster 4 at low zoom", "landscape": {"clusters": ["4"]}}}
    nb = report.build_notebook(record, findings)
    sources = [c.source for c in nb.cells]
    answer = next(s for s in sources if s.startswith("**Clerk:**"))
    assert "[Fig 1A](#q1-fig-1A)" in answer
    assert "view:9" not in answer and "not x." in answer  # an undefined view is text
    i = next(k for k, s in enumerate(sources) if "**Fig 1A.** Cluster 4 at low zoom" in s)
    assert 'id="q1-fig-1A"' in sources[i]
    assert sources[i + 1] == "landscape.apply_state({'clusters': ['4']})"


def test_captures_keep_distinct_observations_and_sources(tmp_path):
    w = Clerk()
    w.record, w.findings = _record()
    w.record[0]["steps"] = []
    state = {
        "kind": "clustergram",
        "display": {"mode": "heatmap", "focused_row": None},
        "rows": {"names": ["A"]},
        "values": {"values": [[42]]},
        "view": {"target": [1, 2], "zoom": [0, 1]},
        "crop": {"row": None, "col": None},
        "order": {"row": "rank", "col": "ini"},
    }
    w._log_capture({"clustergram_state": state}, "first")
    state["values"]["values"][0][0] = 7
    w._log_capture({"clustergram_state": state}, "second")
    steps = w.record[0]["steps"]
    assert len(steps) == 2
    assert steps[0]["observations"]["clustergram_state"]["values"]["values"] == [[42]]
    assert steps[1]["clustergram"]["focus_gene"] == ""
    assert steps[1]["clustergram"]["view"] == state["view"]
    written = w.export(tmp_path, html=False)
    saved = json.loads(written["record"].read_text())["questions"][0]["steps"]
    assert saved[0]["observations"] == steps[0]["observations"]
    assert "partial restore" in written["notebook"].read_text()


def test_capture_dedup_preserves_changed_data_identity():
    w = Clerk()
    w.record, w.findings = _record()
    w.record[0]["steps"] = []
    saved = {
        "schema": "celldega.view",
        "version": 1,
        "kind": "clustergram",
        "state": {"mode": "heatmap"},
        "captured_at": "2026-11-08T12:00:00Z",
        "identity": {"algorithm": "sha256", "digest": "a" * 64},
    }
    views = {"clustergram_image": PNG, "snapshots": {"clustergram": saved}}
    w._log_capture(views, "first")
    saved["captured_at"] = "2026-11-08T12:01:00Z"
    w._log_capture(views, "unchanged")
    assert len(w.record[0]["steps"]) == 1
    # A value outside the visible/capped observations can change without new pixels.
    saved["identity"]["digest"] = "b" * 64
    w._log_capture(views, "changed data")
    steps = w.record[0]["steps"]
    assert len(steps) == 2
    assert steps[0]["snapshots"]["clustergram"]["identity"]["digest"] == "a" * 64
    assert steps[1]["snapshots"]["clustergram"]["identity"]["digest"] == "b" * 64
