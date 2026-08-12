# Environments

Celldega widgets are Jupyter Widgets ([AnyWidget](https://anywidget.dev/)),
so they run anywhere a Jupyter notebook does — you're not tied to a single
notebook provider.

## Notebook environments

- **Local Jupyter** — JupyterLab or Jupyter Notebook running on your own
  machine, following the standard [Installation](../overview/installation.md)
  and [Getting Started](../overview/getting_started.md) guides.
- **Cloud notebook services** — hosted notebook environments such as
  Manifold, Google Colab, Marimo, and Molab. Celldega installs like any other
  PyPI package (`pip install celldega`); widget rendering depends on the
  service supporting the Jupyter Widgets protocol.

## Standalone web usage

Celldega's visualizations also run outside of a notebook entirely, as a
stand-alone JavaScript library against publicly hosted data — see the
[JavaScript API](../javascript/index.md). The [Gallery](../gallery/index.md)
is a collection of such stand-alone web pages showcasing datasets across
technologies (Xenium, CosMx, Visium HD, and more).

Support for a desktop Celldega app is planned for a future release.
