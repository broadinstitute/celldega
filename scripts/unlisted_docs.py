"""Publish pages in not_in_nav as unlisted, work-in-progress examples."""

from mkdocs.structure.files import InclusionLevel


def _unlisted(file):
    return file.inclusion == InclusionLevel.NOT_IN_NAV


def on_page_content(html, *, page, config, files):
    """Apply metadata after notebook rendering and before search indexing."""
    if not _unlisted(page.file):
        return html
    page.meta.setdefault("search", {})["exclude"] = True
    return (
        '<div class="admonition warning">'
        '<p class="admonition-title">Work in progress · Unlisted example</p>'
        "<p>This example is shared for feedback. Its analysis, layout, and APIs "
        "may change before it joins the documentation.</p></div>" + html
    )


def on_post_page(output, *, page, config):
    """Ask search engines not to index the public, link-accessible page."""
    if _unlisted(page.file):
        return output.replace(
            "</head>", '<meta name="robots" content="noindex, nofollow">\n</head>', 1
        )
    return output


def on_template_context(context, *, template_name, config):
    """Exclude unlisted pages from both sitemap.xml and its gzipped copy."""
    if template_name == "sitemap.xml":
        context["pages"] = [file for file in context["pages"] if not _unlisted(file)]
    return context
