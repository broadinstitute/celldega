"""Read-only lookups Clerk can ask for while answering: Enrichr and PubMed.

Both query public web services from the kernel and change nothing in the notebook.
Results are cached for the session, and formatted as short text for the prompt.
"""

from __future__ import annotations

import json
from pathlib import Path
import urllib.parse
import urllib.request
import uuid
import xml.etree.ElementTree as ET


ENRICHR_URL = "https://maayanlab.cloud/Enrichr"
EUTILS_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
DEFAULT_LIBRARIES = ("CellMarker_2024", "PanglaoDB_Augmented_2021")
USER_AGENT = "celldega-clerk"
_TIMEOUT = 30

_enrichr_cache: dict[tuple, list[dict]] = {}
_enrichr_links: dict[tuple, str] = {}
_pubmed_cache: dict[tuple, list[dict]] = {}

#: A folder to keep lookup results in between sessions (``None``: this session only).
#: Clerk sets it to ``<output_dir>/lookup_cache``; a repeated lookup is then read from
#: disk instead of asking Enrichr or PubMed again.
cache_dir: str | Path | None = None


def _disk_key(*parts) -> str:
    return json.dumps(parts, sort_keys=True, default=str)


def _disk_get(kind: str, key: str):
    if cache_dir is None:
        return None
    path = Path(cache_dir) / f"{kind}.json"
    try:
        return json.loads(path.read_text()).get(key)
    except (OSError, ValueError):
        return None


def _disk_put(kind: str, key: str, value) -> None:
    if cache_dir is None:
        return
    path = Path(cache_dir) / f"{kind}.json"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            stored = json.loads(path.read_text())
        except (OSError, ValueError):
            stored = {}
        stored[key] = value
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(stored))
        tmp.replace(path)
    except OSError:  # a cache that can't be written only costs a repeated lookup
        pass


class ClerkLookupError(RuntimeError):
    """A lookup service could not be reached or returned something unexpected."""


def _get_json(url: str, timeout: float = _TIMEOUT):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _get_text(url: str, timeout: float = _TIMEOUT) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8")


def _post_gene_list(genes: list[str], timeout: float = _TIMEOUT) -> int:
    """Upload a gene list to Enrichr; returns its userListId."""
    boundary = uuid.uuid4().hex
    fields = {"list": "\n".join(genes), "description": "celldega clerk"}
    body = "".join(
        f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'
        for name, value in fields.items()
    )
    body += f"--{boundary}--\r\n"
    request = urllib.request.Request(
        f"{ENRICHR_URL}/addList",
        data=body.encode("utf-8"),
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if "userListId" not in payload:
        raise ClerkLookupError(f"Enrichr did not accept the gene list: {payload}")
    short_id = str(payload.get("shortId") or "")
    if short_id:
        _enrichr_links[tuple(sorted(genes))] = enrichr_app_url(short_id)
        _disk_put("enrichr", _disk_key("link", sorted(genes)), enrichr_app_url(short_id))
    return payload["userListId"]


def enrichr_app_url(short_id: str) -> str:
    """The Enrichr web page for an uploaded gene list (its ``shortId``)."""
    return f"{ENRICHR_URL}/enrich?" + urllib.parse.urlencode({"dataset": short_id})


def enrichr_link(genes: list[str]) -> str:
    """The Enrichr web page for a gene list uploaded this session, or ``""``.

    The page shows the same list's results in every Enrichr library.
    """
    genes = [str(g) for g in dict.fromkeys(genes) if str(g)]
    key = tuple(sorted(genes))
    if key not in _enrichr_links:
        stored = _disk_get("enrichr", _disk_key("link", sorted(genes)))
        if stored:
            _enrichr_links[key] = stored
    return _enrichr_links.get(key, "")


def enrichr(
    genes: list[str],
    libraries: list[str] | tuple[str, ...] = DEFAULT_LIBRARIES,
    top: int = 8,
) -> dict[str, list[dict]]:
    """Enrichment of a gene list against Enrichr libraries (read-only).

    Args:
        genes: Gene symbols.
        libraries: Enrichr library names, e.g. ``"CellMarker_2024"``.
        top: Terms kept per library, by combined score.

    Returns:
        dict: ``{library: [{"name", "score", "adjusted_p", "odds_ratio", "genes"}, ...]}``.
    """
    genes = [str(g) for g in dict.fromkeys(genes) if str(g)]
    if not genes:
        return {}
    results: dict[str, list[dict]] = {}
    user_list_id = None
    for library in libraries:
        key = (tuple(sorted(genes)), library)
        if key not in _enrichr_cache:
            stored = _disk_get("enrichr", _disk_key(library, sorted(genes)))
            if stored is not None:
                _enrichr_cache[key] = stored
        if key not in _enrichr_cache:
            if user_list_id is None:
                user_list_id = _post_gene_list(genes)
            query = urllib.parse.urlencode({"userListId": user_list_id, "backgroundType": library})
            rows = _get_json(f"{ENRICHR_URL}/enrich?{query}").get(library, [])
            # Enrichr rows: [rank, term, p, odds ratio, combined score, genes, adj. p, ...]
            terms = [
                {
                    "name": row[1],
                    "score": row[4],
                    "adjusted_p": row[6],
                    "odds_ratio": row[3],
                    "genes": list(row[5]),
                }
                for row in rows
            ]
            terms.sort(key=lambda term: term["score"], reverse=True)
            _enrichr_cache[key] = terms
            _disk_put("enrichr", _disk_key(library, sorted(genes)), terms)
        results[library] = _enrichr_cache[key][:top]
    return results


def pubmed(query: str, n: int = 5, abstract_chars: int = 600) -> list[dict]:
    """Search PubMed (read-only) and return the top matches with abstract excerpts.

    Returns:
        list[dict]: ``{"pmid", "title", "journal", "year", "abstract"}`` per article.
    """
    key = (query, n, abstract_chars)
    if key not in _pubmed_cache:
        stored = _disk_get("pubmed", _disk_key(*key))
        if stored is not None:
            _pubmed_cache[key] = stored
    if key in _pubmed_cache:
        return _pubmed_cache[key]
    search = urllib.parse.urlencode(
        {
            "db": "pubmed",
            "term": query,
            "retmax": n,
            "retmode": "json",
            "sort": "relevance",
            "tool": USER_AGENT,
        }
    )
    ids = (
        _get_json(f"{EUTILS_URL}/esearch.fcgi?{search}").get("esearchresult", {}).get("idlist", [])
    )
    if not ids:
        _pubmed_cache[key] = []
        _disk_put("pubmed", _disk_key(*key), [])
        return []
    fetch = urllib.parse.urlencode(
        {"db": "pubmed", "id": ",".join(ids), "retmode": "xml", "tool": USER_AGENT}
    )
    root = ET.fromstring(_get_text(f"{EUTILS_URL}/efetch.fcgi?{fetch}"))
    articles = []
    for article in root.iter("PubmedArticle"):
        abstract = " ".join("".join(node.itertext()) for node in article.iter("AbstractText"))
        articles.append(
            {
                "pmid": article.findtext(".//PMID", default=""),
                "title": "".join(article.find(".//ArticleTitle").itertext()).strip()
                if article.find(".//ArticleTitle") is not None
                else "",
                "journal": article.findtext(".//Journal/ISOAbbreviation", default="")
                or article.findtext(".//Journal/Title", default=""),
                "year": article.findtext(".//PubDate/Year", default="")
                or article.findtext(".//PubDate/MedlineDate", default="")[:4],
                "abstract": (abstract[:abstract_chars] + "…")
                if len(abstract) > abstract_chars
                else abstract,
            }
        )
    _pubmed_cache[key] = articles
    _disk_put("pubmed", _disk_key(*key), articles)
    return articles


def format_enrichr(
    gene_label: str, results: dict[str, list[dict]], max_genes: int = 10, *, url: str = ""
) -> str:
    """Short text for enrichment results, ending with the Enrichr page when known."""
    lines = []
    for library, terms in results.items():
        lines.append(f"Enrichr {library} for {gene_label}:")
        if not terms:
            lines.append("  (no terms)")
        for rank, term in enumerate(terms, start=1):
            genes = term.get("genes") or []
            shown = ", ".join(genes[:max_genes]) + (
                f", +{len(genes) - max_genes}" if len(genes) > max_genes else ""
            )
            lines.append(
                f"  {rank}. {term['name']} (combined score {term['score']:.3g}; "
                f"adj. p {term['adjusted_p']:.2g}): {shown}"
            )
    if url and lines:
        lines.append(f"Enrichr page for these results (cite it as a link): {url}")
    return "\n".join(lines)


def format_pubmed(query: str, articles: list[dict]) -> str:
    """Short text for PubMed results."""
    if not articles:
        return f"PubMed search {query!r}: no results."
    lines = [f"PubMed search {query!r}:"]
    lines.extend(
        f"- PMID {a['pmid']} ({a['journal']} {a['year']}): {a['title']} {a['abstract']}".rstrip()
        for a in articles
    )
    return "\n".join(lines)
