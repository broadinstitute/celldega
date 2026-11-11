"""Clerk's read-only lookups (ranked markers, Enrichr, PubMed) and recorded findings."""

import json

import numpy as np
import pandas as pd
import pytest

from tests.unit.test_viz.snapshot_helpers import snapshot_browser


try:
    import anndata as ad

    from celldega import clerk as clerk_llm
    from celldega.clerk import lookups
    from celldega.clust import Matrix
    from celldega.viz import Clerk, Clustergram
except Exception as e:  # pragma: no cover - skip if deps missing
    pytest.skip(f"celldega modules unavailable: {e}", allow_module_level=True)


# ---- web lookups (network mocked) ------------------------------------------
class _Response:
    def __init__(self, body: str) -> None:
        self._body = body.encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        return None


def test_enrichr_uploads_once_and_ranks_terms(monkeypatch) -> None:
    lookups._enrichr_cache.clear()
    seen = []

    def fake_urlopen(request, timeout=None):
        url = request.full_url
        seen.append(url)
        if url.endswith("/addList"):
            assert b"MUC2\nTFF3" in request.data
            return _Response(json.dumps({"userListId": 7, "shortId": "abc"}))
        library = url.split("backgroundType=")[1]
        rows = [
            [2, "Paneth cell", 0.01, 5.0, 20.0, ["MUC2"], 0.05],
            [1, "Goblet cell", 1e-9, 90.0, 800.0, ["MUC2", "TFF3"], 1e-8],
        ]
        return _Response(json.dumps({library: rows}))

    monkeypatch.setattr(lookups.urllib.request, "urlopen", fake_urlopen)
    found = lookups.enrichr(
        ["MUC2", "TFF3"], ["CellMarker_2024", "PanglaoDB_Augmented_2021"], top=1
    )

    assert sum(url.endswith("/addList") for url in seen) == 1
    assert found["CellMarker_2024"] == [
        {
            "name": "Goblet cell",
            "score": 800.0,
            "adjusted_p": 1e-8,
            "odds_ratio": 90.0,
            "genes": ["MUC2", "TFF3"],
        }
    ]
    text = lookups.format_enrichr("cluster 4's top 2 markers", found)
    assert "Enrichr CellMarker_2024 for cluster 4's top 2 markers:" in text
    assert "1. Goblet cell (combined score 800; adj. p 1e-08): MUC2, TFF3" in text
    assert "Enrichr page" not in text
    # The upload's shortId is the list's page on the Enrichr website, in any order.
    page = "https://maayanlab.cloud/Enrichr/enrich?dataset=abc"
    assert lookups.enrichr_link(["TFF3", "MUC2"]) == page
    assert lookups.enrichr_link(["EPCAM"]) == ""
    text = lookups.format_enrichr("cluster 4's top 2 markers", found, url=page)
    assert text.endswith(f"Enrichr page for these results (cite it as a link): {page}")


_EFETCH = """<?xml version="1.0"?>
<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>123</PMID><Article>
<Journal><Title>Gut</Title><JournalIssue><PubDate><Year>2021</Year></PubDate></JournalIssue>
<ISOAbbreviation>Gut</ISOAbbreviation></Journal>
<ArticleTitle>Plasma cells of the colonic lamina propria.</ArticleTitle>
<Abstract><AbstractText>IgA plasma cells reside between crypts.</AbstractText></Abstract>
</Article></MedlineCitation></PubmedArticle></PubmedArticleSet>"""


def test_pubmed_search_returns_titles_and_abstracts(monkeypatch) -> None:
    lookups._pubmed_cache.clear()

    def fake_urlopen(request, timeout=None):
        if "esearch" in request.full_url:
            return _Response(json.dumps({"esearchresult": {"idlist": ["123"]}}))
        return _Response(_EFETCH)

    monkeypatch.setattr(lookups.urllib.request, "urlopen", fake_urlopen)
    articles = lookups.pubmed("plasma cells lamina propria", n=1)
    assert articles == [
        {
            "pmid": "123",
            "title": "Plasma cells of the colonic lamina propria.",
            "journal": "Gut",
            "year": "2021",
            "abstract": "IgA plasma cells reside between crypts.",
        }
    ]
    text = lookups.format_pubmed("plasma cells lamina propria", articles)
    assert "PMID 123 (Gut 2021): Plasma cells of the colonic lamina propria." in text


# ---- ranked markers: Matrix payload and prompt text -------------------------
def _ranked_matrix() -> Matrix:
    sc = pytest.importorskip("scanpy")
    rng = np.random.default_rng(0)
    X = rng.poisson(1.0, (90, 12)).astype(float)
    X[:30, :3] += 8
    X[30:60, 3:6] += 8
    a = ad.AnnData(X, var=pd.DataFrame(index=[f"g{i}" for i in range(12)]))
    a.obs["leiden"] = pd.Categorical(np.repeat(["0", "1", "2"], 30))
    sc.pp.log1p(a)
    sc.tl.rank_genes_groups(a, "leiden")
    mat = Matrix(a, groupby="leiden")
    mat.cluster(view="rank_genes_groups", levels=[1, 2])
    return mat


def test_matrix_sends_ranked_markers_to_the_front_end() -> None:
    mat = _ranked_matrix()
    names = mat.data.index.astype(str)
    markers = mat.viz["markers"]
    assert set(markers) == {"0", "1", "2"}
    assert {names[i] for i in markers["0"][:3]} == {"g0", "g1", "g2"}


def test_format_clustergram_state_lists_ranked_markers() -> None:
    state = {
        "cluster_markers": [
            {
                "cluster": "4",
                "found": True,
                "genes": [
                    {"name": "MUC2", "rank": 1, "value": 2.91, "size": 0.73},
                    {"name": "TFF3", "rank": 2, "value": 3.08, "size": None},
                ],
            },
            {"cluster": "x", "found": False, "genes": []},
        ]
    }
    text = clerk_llm.format_clustergram_state(state)
    assert "  4: MUC2 2.91/0.73, TFF3 3.08" in text
    assert "  x: no ranked markers" in text
    assert "available (lookup.markers)" in clerk_llm.format_clustergram_state(
        {"marker_ranking": True}
    )


# ---- the action loop with lookups ----------------------------------------------
def _clerk(monkeypatch):
    df = pd.DataFrame(
        np.arange(12).reshape(3, 4).astype(float),
        index=["MUC2", "TFF3", "JCHAIN"],
        columns=["4", "5", "6", "7"],
    )
    mat = Matrix(df)
    mat.cluster()
    cgm = Clustergram(matrix=mat)
    w = Clerk(clustergram=cgm)
    w.snapshot_timeout = 5
    requests = []

    def fake_send(content):
        if content.get("event") == "get_state":
            options = content["options"]
            requests.append(options)
            state = {"kind": "clustergram"}
            if options.get("markers"):
                state["cluster_markers"] = [
                    {
                        "cluster": c,
                        "found": True,
                        "genes": [{"name": "MUC2", "rank": 1, "value": 2.9, "size": 0.7}],
                    }
                    for c in options["markers"]["clusters"]
                ]
            cgm._on_state_msg(cgm, {"event": "state", "id": content["id"], "state": state}, [])

    monkeypatch.setattr(cgm, "send", snapshot_browser(cgm, fake_send))
    return w, cgm, requests


def test_clerk_reads_markers_and_runs_enrichr_and_pubmed(monkeypatch) -> None:
    w, cgm, requests = _clerk(monkeypatch)
    enrichr_calls, pubmed_calls = [], []
    monkeypatch.setattr(
        lookups,
        "enrichr",
        lambda genes, libraries, top=8: (
            enrichr_calls.append((genes, libraries)) or {"CellMarker_2024": []}
        ),
    )
    monkeypatch.setattr(lookups, "pubmed", lambda query: pubmed_calls.append(query) or [])
    calls = []
    block = {
        "lookup": {
            "markers": {"clusters": ["4", "5"], "n": 25},
            "enrichr": [{"cluster": "4", "n": 25}],
            "pubmed": "goblet cells colon",
        }
    }
    replies = [
        f"```celldega-actions\n{json.dumps(block)}\n```",
        "Cluster 4 looks like goblet cells.",
    ]

    def fake_ask(question, **kwargs):
        calls.append(kwargs)
        return replies[len(calls) - 1]

    monkeypatch.setattr(clerk_llm, "ask", fake_ask)
    rank_before = cgm.rank_dim

    w.request = {"id": "1", "question": "What are clusters 4 and 5?"}
    assert w.wait(timeout=5)

    assert cgm.rank_dim == rank_before  # read-only: the view didn't change
    assert requests[-1]["markers"] == {"clusters": ["4", "5"], "n": 25}
    assert enrichr_calls == [(["MUC2"], lookups.DEFAULT_LIBRARIES)]
    assert pubmed_calls == ["goblet cells colon"]
    assert "lookup.markers" not in calls[0].get("lookups", [])
    assert any("Enrichr CellMarker_2024" in r for r in calls[1]["lookups"])
    action = w.messages[1]["content"]
    assert "Read the top 25 ranked markers of clusters 4, 5" in action
    assert "Ran Enrichr (default libraries) on cluster 4's top 25 markers" in action
    assert "Searched PubMed: 'goblet cells colon'" in action


# ---- findings ------------------------------------------------------------------
def test_extract_findings() -> None:
    text, findings, problem = clerk_llm.extract_findings(
        'Goblet cells.\n```celldega-findings\n{"cell_types": [{"cluster": "4", "label": "Goblet"}]}\n```'
    )
    assert text == "Goblet cells."
    assert findings == {"cell_types": [{"cluster": "4", "label": "Goblet"}]}
    assert problem is None
    assert clerk_llm.extract_findings("plain") == ("plain", None, None)


def test_clerk_records_findings_and_writes_them_to_anndata(monkeypatch) -> None:
    w, _cgm, _ = _clerk(monkeypatch)
    findings = {
        "cell_types": [
            {"cluster": "4", "label": "Goblet cells", "confidence": "high", "markers": ["MUC2"]},
            {"cluster": "5", "label": "Plasma cells", "confidence": "medium"},
        ]
    }
    answer = f"4 is goblet, 5 is plasma.\n```celldega-findings\n{json.dumps(findings)}\n```"
    monkeypatch.setattr(clerk_llm, "ask", lambda question, **kw: answer)

    w.request = {"id": "1", "question": "Label 4 and 5"}
    assert w.wait(timeout=5)

    assert w.messages[1] == {"role": "assistant", "content": "4 is goblet, 5 is plasma."}
    assert w.messages[2]["content"] == "Recorded tentative cell types for 2 clusters"
    assert w.messages[2]["detail"] == (
        "Recorded cell types: 4 → Goblet cells (high), 5 → Plasma cells (medium)"
    )
    df = w.findings_df()
    assert list(df["label"]) == ["Goblet cells", "Plasma cells"]
    assert df.loc[0, "markers"] == "MUC2"

    cells = ad.AnnData(obs=pd.DataFrame({"leiden": ["4", "5", "6", "4"]}))
    column = w.write_cell_types(cells, "leiden")
    assert list(column) == ["Goblet cells", "Plasma cells", "Unassigned", "Goblet cells"]
    assert cells.uns["clerk_cell_types"]["clerk_cell_type"]["labels"] == {
        "4": "Goblet cells",
        "5": "Plasma cells",
    }
    with pytest.raises(ValueError):
        w.write_cell_types(cells, "leiden")  # add-only unless overwrite=True
    w.write_cell_types(cells, "leiden", overwrite=True)


def test_actions_help_matches_linked_widgets() -> None:
    with_cgm = clerk_llm.actions_help(clustergram=True)
    assert '"markers"' in with_cgm and "marker_level" in with_cgm
    without = clerk_llm.actions_help(clustergram=False)
    assert "marker_level" not in without and "pubmed" in without
