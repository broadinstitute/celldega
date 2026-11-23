"""Write llms.txt, an index of the docs for AI agents (https://llmstxt.org).

The intro is the ``celldega`` package docstring, and each page in the nav is
listed with its first paragraph as a description, so both stay in sync with
the docs. Pages left out of the nav (unlisted pages) are left out here too.
"""

import ast
import json
from pathlib import Path
import re


DEFAULT_SITE_URL = "https://broadinstitute.github.io/celldega/"
MAX_SUMMARY = 220


def _package_docstring(config) -> str:
    init = Path(config.config_file_path).parent / "src" / "celldega" / "__init__.py"
    try:
        return ast.get_docstring(ast.parse(init.read_text())) or ""
    except (OSError, SyntaxError):
        return ""


def _plain(text: str) -> str:
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)  # images
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)  # links -> their text
    text = re.sub(r"<[^>]+>", "", text)  # inline HTML
    text = re.sub(r"(\*\*|__|\*)", "", text)  # emphasis
    return re.sub(r"\s+", " ", text).strip()


def _shorten(text: str) -> str:
    if len(text) <= MAX_SUMMARY:
        return text
    sentences = re.split(r"(?<=[.!?])\s+", text)
    summary = ""
    for sentence in sentences:
        if summary and len(summary) + len(sentence) + 1 > MAX_SUMMARY:
            break
        summary = f"{summary} {sentence}".strip()
    return summary if len(summary) <= MAX_SUMMARY else summary[: MAX_SUMMARY - 1] + "…"


def _first_paragraph(markdown: str) -> str:
    markdown = re.sub(r"\A---\n.*?\n---\n", "", markdown, flags=re.S)  # front matter
    paragraph, in_code, in_html = [], False, False
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith(("```", "~~~")):
            in_code = not in_code
            continue
        if in_code:
            continue
        # An HTML block (such as a figure caption) runs until the next blank line.
        if not paragraph and stripped.startswith("<"):
            in_html = True
        if in_html:
            in_html = bool(stripped)
            continue
        prose = stripped and not stripped.startswith(
            ("#", "<", "!!!", "???", "|", ":::", "- ", "* ", "1. ", ">", "![")
        )
        if prose:
            paragraph.append(stripped)
        elif paragraph:
            break
    return _shorten(_plain(" ".join(paragraph)))


def _title(path: Path) -> str:
    """The page's first level-one heading, or its file name."""
    try:
        if path.suffix == ".ipynb":
            cells = json.loads(path.read_text()).get("cells", [])
            text = "\n".join(
                "".join(c.get("source", [])) for c in cells if c.get("cell_type") == "markdown"
            )
        else:
            text = path.read_text()
    except (OSError, ValueError):
        text = ""
    match = re.search(r"^# (.+)$", text, flags=re.M)
    if match:
        return _plain(match.group(1))
    name = path.parent.name if path.stem == "index" else path.stem
    return name.replace("_", " ").replace("-", " ")


def _summary(path: Path) -> str:
    try:
        if path.suffix == ".ipynb":
            cells = json.loads(path.read_text()).get("cells", [])
            for cell in cells:
                if cell.get("cell_type") == "markdown":
                    text = _first_paragraph("".join(cell.get("source", [])))
                    if text:
                        return text
            return ""
        text = path.read_text()
        # An API page describes itself best with its module's docstring summary.
        module = re.search(r"^:::\s*(celldega(?:\.\w+)*)\s*$", text, flags=re.M)
        summary = _module_summary(module.group(1)) if module else ""
        return summary or _first_paragraph(text)
    except (OSError, ValueError):
        return ""


SRC_DIR = Path(__file__).resolve().parent.parent / "src"


def _module_summary(module: str) -> str:
    """The first line of a celldega module's docstring, read without importing it."""
    base = SRC_DIR.joinpath(*module.split("."))
    for candidate in (base / "__init__.py", base.with_suffix(".py")):
        if candidate.exists():
            try:
                doc = ast.get_docstring(ast.parse(candidate.read_text())) or ""
            except SyntaxError:
                return ""
            return _plain(doc.strip().split("\n\n")[0])
    return ""


def _page_url(src: str, site_url: str, use_directory_urls: bool) -> str:
    stem = src.rsplit(".", 1)[0]
    if stem == "index" or stem.endswith("/index"):
        path = stem[: -len("index")]
    else:
        path = f"{stem}/" if use_directory_urls else f"{stem}.html"
    return site_url + path


def _sections(nav, config, site_url):
    """Yield (section title, [list lines]) for the nav, one section per nav group."""
    docs_dir = Path(config.docs_dir)
    use_directory_urls = config.use_directory_urls

    def entry(title, target):
        if re.match(r"https?://", target):
            return f"- [{title}]({target})"
        summary = _summary(docs_dir / target)
        url = _page_url(target, site_url, use_directory_urls)
        return f"- [{title}]({url})" + (f": {summary}" if summary else "")

    def walk(items, section):
        lines, nested = [], []
        for item in items:
            if isinstance(item, str):
                lines.append(entry(_title(docs_dir / item), item))
                continue
            for title, target in item.items():
                if isinstance(target, list):
                    nested.extend(walk(target, f"{section}: {title}" if section else title))
                else:
                    lines.append(entry(title, target))
        return ([(section, lines)] if lines else []) + nested

    return walk(nav, "")


def on_post_build(config):
    """Write llms.txt to the site root."""
    site_url = (config.site_url or DEFAULT_SITE_URL).rstrip("/") + "/"
    doc = _package_docstring(config)
    summary, _, details = doc.partition("\n\n")
    summary = re.sub(r"^Celldega:\s*", "", " ".join(summary.split()))
    out = ["# Celldega", "", f"> {summary[:1].upper()}{summary[1:]}", ""]
    if details:
        out += [details.strip(), ""]
    for section, lines in _sections(config.nav or [], config, site_url):
        out += [f"## {section or 'Docs'}", "", *lines, ""]
    Path(config.site_dir, "llms.txt").write_text("\n".join(out))
