# Installation

## Python

Celldega supports **Python 3.11 and 3.12**. Install it into the environment
used by your Jupyter notebook:

```bash
pip install celldega
```

For Scanpy-backed marker dot plots and marker ranking:

```bash
pip install "celldega[scanpy]"
```

For image preprocessing, including adding an aligned H&E background:

```bash
pip install "celldega[pre]"
```

Image operations also require a working native libvips installation. See
[preprocessing](../python/pre/api.md) and
[aligned H&E](../python/aligned_he.md) for the relevant workflows.

See [Usage](usage/index.md) for notebook, web, and desktop options, then follow
[Getting Started](index.md) or open an [example notebook](../examples/index.md).

## JavaScript

For an application managed with npm:

```bash
npm install celldega
```

```javascript
import celldega from "celldega";
```

A standalone web page can import the built module or load it from a CDN such
as esm.sh. See the [JavaScript quick start](../javascript/index.md) for
`landscape`, `clustergram`, and linked views.
