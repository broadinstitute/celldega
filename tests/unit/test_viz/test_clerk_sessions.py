"""Clerk's CLI sessions: one per question, follow-up rounds resume it with only what's new."""

import json
import os
from pathlib import Path
import re

import pytest

from tests.unit.test_viz.snapshot_helpers import snapshot_browser


try:
    from celldega import clerk as clerk_llm
    from celldega.clerk import llm as clerk_impl
    from celldega.viz import Clerk
except Exception as e:  # pragma: no cover - skip if deps missing
    pytest.skip(f"celldega modules unavailable: {e}", allow_module_level=True)


class _Completed:
    def __init__(self, stdout: str) -> None:
        self.stdout, self.returncode, self.stderr = stdout, 0, ""


@pytest.fixture
def config_dir(tmp_path, monkeypatch) -> Path:
    """Point the CLI's config directory (where transcripts live) at a temp folder."""
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude"))
    return tmp_path / "claude"


def test_run_claude_starts_then_resumes_a_session(monkeypatch, config_dir) -> None:
    calls = []

    def fake_run(cmd, input=None, cwd=None, env=None, **kwargs):
        calls.append({"cmd": cmd, "cwd": cwd, "env": env})
        usage = {"input_tokens": 5, "cache_read_input_tokens": 100 * len(calls)}
        return _Completed(json.dumps({"result": "ok", "usage": usage, "total_cost_usd": 0.01}))

    monkeypatch.setattr(clerk_impl.shutil, "which", lambda _n: "/usr/bin/claude")
    monkeypatch.setattr(clerk_impl.subprocess, "run", fake_run)

    session = clerk_llm.Session()
    try:
        clerk_llm.ask("q", session=session)
        clerk_llm.follow_up(session, lookups=["PubMed: x"])
    finally:
        session.close()

    first, second = (c["cmd"] for c in calls)
    assert first[first.index("--session-id") + 1] == session.id
    assert second[second.index("--resume") + 1] == session.id
    for call in calls:
        assert "--no-session-persistence" not in call["cmd"]
        assert call["cmd"][call["cmd"].index("--tools") + 1] == ""
        assert call["cwd"] == session.workdir  # resume needs the same directory
        assert call["env"]["CLAUDE_CODE_DISABLE_AUTO_MEMORY"] == "1"
    # The follow-up sends only what's new, not the question's full evidence again.
    assert "## Lookup results" in " ".join(second)
    assert "## Question" not in " ".join(second)
    assert session.totals() == {
        "input_tokens": 10,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 300,
        "output_tokens": 0,
        "cost_usd": 0.02,
        "calls": 2,
    }


def test_single_shot_calls_still_save_nothing(monkeypatch) -> None:
    seen = {}

    def fake_run(cmd, **kwargs):
        seen["cmd"] = cmd
        return _Completed(json.dumps({"result": "ok"}))

    monkeypatch.setattr(clerk_impl.shutil, "which", lambda _n: "/usr/bin/claude")
    monkeypatch.setattr(clerk_impl.subprocess, "run", fake_run)
    clerk_llm.ask("q")
    assert "--no-session-persistence" in seen["cmd"]
    assert "--session-id" not in seen["cmd"] and "--resume" not in seen["cmd"]


def test_follow_up_needs_a_started_session() -> None:
    session = clerk_llm.Session()
    try:
        with pytest.raises(ValueError, match="start the session"):
            clerk_llm.follow_up(session, notes=["x"])
    finally:
        session.close()


def test_session_close_deletes_its_transcript(config_dir) -> None:
    session = clerk_llm.Session()
    own = config_dir / "projects" / re.sub(r"[^A-Za-z0-9]", "-", os.path.realpath(session.workdir))
    own.mkdir(parents=True)
    (own / f"{session.id}.jsonl").write_text("{}")
    other = config_dir / "projects" / "-Users-me-project"
    other.mkdir()
    (other / "keep.jsonl").write_text("{}")

    session.close()
    assert not own.exists()
    assert not Path(session.workdir).exists()
    assert (other / "keep.jsonl").exists()  # nothing else is touched


def test_stale_clerk_transcripts_are_removed(config_dir) -> None:
    stale = config_dir / "projects" / "-private-var-folders-x-celldega-clerk-abc"
    stale.mkdir(parents=True)
    (stale / "old.jsonl").write_text("{}")
    os.utime(stale, (0, 0))
    fresh = config_dir / "projects" / "-private-var-folders-x-celldega-clerk-new"
    fresh.mkdir()
    clerk_llm.Session().close()
    assert not stale.exists()
    assert fresh.exists()


def _clustergram():
    import numpy as np
    import pandas as pd

    from celldega.clust import Matrix
    from celldega.viz import Clustergram

    df = pd.DataFrame(
        np.arange(12).reshape(3, 4).astype(float),
        index=["g1", "g2", "g3"],
        columns=["s1", "s2", "s3", "s4"],
    )
    mat = Matrix(df)
    mat.cluster()
    return Clustergram(matrix=mat)


def _clerk_with_clustergram(monkeypatch):
    cgm = _clustergram()
    w = Clerk(clustergram=cgm)
    w.snapshot_timeout = 5

    def fake_send(content):
        if content.get("event") == "get_state":
            state = {"kind": "clustergram", "marker_level": {"current": cgm.rank_dim}}
            cgm._on_state_msg(cgm, {"event": "state", "id": content["id"], "state": state}, [])

    monkeypatch.setattr(cgm, "send", snapshot_browser(cgm, fake_send))
    return w, cgm


def _fake_backend(monkeypatch, replies):
    """Fake ask / follow_up that track the session like the CLI would."""
    asked, followed = [], []

    def fake_ask(question, session=None, **kwargs):
        asked.append(kwargs)
        if session is not None:
            session.calls += 1
            session.usage.append({"input_tokens": 1000, "cost_usd": 0.05})
        return replies.pop(0)

    def fake_follow_up(session, **kwargs):
        followed.append(kwargs)
        session.calls += 1
        session.usage.append({"cache_read_input_tokens": 1000, "cost_usd": 0.005})
        return replies.pop(0)

    monkeypatch.setattr(clerk_llm, "ask", fake_ask)
    monkeypatch.setattr(clerk_llm, "follow_up", fake_follow_up)
    return asked, followed


def test_clerk_rounds_resume_the_session_with_only_new_results(monkeypatch, config_dir) -> None:
    from celldega.clerk import lookups

    w, _cgm = _clerk_with_clustergram(monkeypatch)
    monkeypatch.setattr(lookups, "pubmed", lambda query, **kw: [])
    monkeypatch.setattr(lookups, "format_pubmed", lambda query, found: f"PubMed {query}")
    asked, followed = _fake_backend(
        monkeypatch,
        [
            '```celldega-actions\n{"lookup": {"pubmed": ["first"]}}\n```',
            '```celldega-actions\n{"lookup": {"pubmed": ["second"]}}\n```',
            '```celldega-actions\n{"clustergram": {"marker_level": 10}, "continue": true}\n```',
            "Answer.",
        ],
    )
    w.request = {"id": "1", "question": "search"}
    assert w.wait(timeout=5)

    assert len(asked) == 1  # the full evidence is sent once
    assert [f["lookups"] for f in followed] == [["PubMed first"], ["PubMed second"], []]
    # An unchanged Clustergram isn't resent; a changed one is.
    assert "clustergram_state" not in followed[0] and "clustergram_state" not in followed[1]
    assert followed[2]["clustergram_state"]["marker_level"]["current"] == 10
    assert w.messages[-1]["content"] == "Answer."
    assert w.record[-1]["usage"]["calls"] == 4
    assert w.record[-1]["usage"]["cost_usd"] == pytest.approx(0.065)
    assert not list((config_dir / "projects").glob("*celldega-clerk-*"))


def test_clerk_falls_back_to_a_fresh_call_if_resume_fails(monkeypatch) -> None:
    w, _cgm = _clerk_with_clustergram(monkeypatch)
    replies = ['```celldega-actions\n{"lookup": {"genes": ["g1"]}}\n```', "Answer."]
    asked, _followed = _fake_backend(monkeypatch, replies)

    def broken_follow_up(session, **kwargs):
        raise clerk_llm.ClerkBackendError("No conversation found with session ID")

    monkeypatch.setattr(clerk_llm, "follow_up", broken_follow_up)
    w.request = {"id": "1", "question": "q"}
    assert w.wait(timeout=5)
    assert len(asked) == 2  # resent everything in a new session
    assert w.messages[-1]["content"] == "Answer."
    assert any(s["kind"] == "note" for s in w.record[-1]["steps"])


def test_a_paused_question_keeps_its_session_until_continued(monkeypatch) -> None:
    w, _cgm = _clerk_with_clustergram(monkeypatch)
    w.max_action_rounds = 1
    replies = [
        '```celldega-actions\n{"lookup": {"genes": ["g1"]}}\n```',
        '```celldega-actions\n{"lookup": {"genes": ["g2"]}}\n```',
        "Done.",
    ]
    _asked, followed = _fake_backend(monkeypatch, replies)
    w.request = {"id": "1", "question": "q"}
    assert w.wait(timeout=5)
    session = w._paused["call"]["session"]
    assert Path(session.workdir).exists()

    w.request = {"id": "2", "continue": True}
    assert w.wait(timeout=5)
    assert len(followed) == 2  # the resumed round continued the same session
    assert not Path(session.workdir).exists()
