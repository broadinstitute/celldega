"""Griffe extension that renders Sphinx cross-reference roles as inline code.

Some docstrings refer to other objects with Sphinx roles (``:func:`name```,
``:class:`~package.module.Name```). mkdocstrings renders Markdown, so the
roles would appear literally in the API reference. This extension rewrites
them, when the docs are built, as Markdown inline code: the name as written,
the last component after ``~``, or the title of ``title <target>``.

Configured in mkdocs.yaml under the mkdocstrings Python handler's
``extensions`` option.
"""

import re

import griffe


_ROLE = re.compile(
    r":(?:py:)?(?:func|class|meth|mod|attr|data|obj|exc|const):"
    r"`(?P<tilde>~?)(?P<text>[^`<]+?)(?:\s*<(?P<target>[^>`]+)>)?`"
)


def render_roles(text: str) -> str:
    """Replace Sphinx cross-reference roles in ``text`` with inline code."""

    def code(match: re.Match) -> str:
        name = match["text"].strip()
        if match["tilde"] and not match["target"]:
            name = name.rsplit(".", 1)[-1]
        return f"`{name}`"

    return _ROLE.sub(code, text)


class SphinxRoles(griffe.Extension):
    """Render Sphinx cross-reference roles in docstrings as inline code."""

    def on_object(self, *, obj: griffe.Object, **kwargs) -> None:
        if obj.docstring is not None:
            obj.docstring.value = render_roles(obj.docstring.value)
