<div style="background-color:#016DB6; padding:12px 16px; display:flex; align-items:center; justify-content:space-between;">
  <div style="display:flex; align-items:center; gap:10px;">
    <img src="image-1.png" alt="Celldega logo" height="36" />
    <span style="font-size:1.75rem; font-weight:600; color:#ffffff;">Celldega</span>
  </div>
  <div style="display:flex; gap:8px;">
    <a href="https://broadinstitute.github.io/celldega/" style="background-color:#ffffff; color:#016DB6; padding:6px 14px; border-radius:4px; text-decoration:none; font-weight:600;">Docs</a>
    <a href="https://github.com/broadinstitute/celldega" style="background-color:#24292e; color:#ffffff; padding:6px 12px; border-radius:4px; text-decoration:none; font-weight:500; display:flex; align-items:center; gap:6px; transition:all 0.2s ease;">⭐ Star</a>
  </div>
</div>

<br>

[![PyPI version](https://badge.fury.io/py/celldega.svg)](https://badge.fury.io/py/celldega)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Documentation](https://img.shields.io/badge/docs-latest-brightgreen.svg)](https://broadinstitute.github.io/celldega/)

> **Interactive spatial‑omics analysis & visualisation toolkit for single‑cell and spatial transcriptomics data**

**Celldega** combines scalable computational pipelines with GPU‑accelerated, web‑native visualisations so you can explore **millions of cells and transcripts** directly inside Jupyter Lab, VS Code, or any modern browser. Built on deck.gl, PyArrow, and modern web tooling, it powers quality control, clustering, neighbourhood analysis, and high‑resolution *Landscape* & *Matrix* views for datasets from Xenium, Visium HD, MERFISH, and more.

## ✨ Features

* 🧬 **Spatial‑omics & single‑cell analysis** – pre‑processing, QC metrics, hierarchical clustering, and neighbourhood graphs for `AnnData`/`SpatialData` objects
* 🗺️ **Landscape & Matrix views** – tile‑based, zoomable rendering of tissue morphology and gene expression overlays
* ⚡ **GPU‑accelerated interactivity** – deck.gl & WebGL keep panning/zooming smooth even with >100 M transcripts
* 🌐 **Notebook & web integration** – AnyWidget components for Python plus an ESM bundle for React, Vue, and ObservableHQ
* ☁️ **Cloud‑ready** – Parquet/Arrow back‑ends and first‑class Terra.bio support
* 🧪 **Extensible** – modular API (`pre`, `clust`, `nbhd`, `viz`) for plugging in custom algorithms and tiles

## 🚀 Quick Start

### Installation

```bash
# core package
pip install celldega

# optional native pre‑processing extras (image tiling, etc.)
pip install "celldega[pre]"
```

### Basic Usage

```python
import celldega as cd
from celldega.viz import Landscape

# Load an AnnData/SpatialData file
data = cd.pre.load_file("path/to/dataset.h5ad")

# Run clustering / neighbourhood analysis
cd.clust.cluster_gene_expression(data)

# Launch an interactive Landscape widget
landscape = Landscape(dataset_name="My Xenium sample",
                      base_url="./",
                      ini_zoom=0.4)
landscape  # displays in Jupyter / VS Code
```

## 📋 Requirements

* **Python**: 3.10+
* **Optional (widget dev)**: Node.js 16+
* **System**: Linux, macOS, Windows
* **Memory**: ≥ 4 GB recommended (bigger datasets benefit from >16 GB)
* **Dependencies**: see [`pyproject.toml`](pyproject.toml) and [`package.json`](package.json)

### VIPS Installation (Terra.bio users)

If you're running on Terra.bio, add this to your startup script so the optional image‑tiling stage works:

```bash
#!/usr/bin/env bash
apt update && apt install -y libvips libvips-tools libvips-dev
```

See Terra's [pre‑configured environment guide](https://support.terra.bio/hc/en-us/articles/360058193872-Preconfigure-a-Cloud-Environment-with-a-startup-script) for details.

## 📁 Repository Structure

| Directory/File     | Purpose                                  |
| ------------------ | ---------------------------------------- |
| `src/celldega/`    | Core Python package (`pre/`, `viz/`, …)  |
| `js/`              | JavaScript widget source & build scripts |
| `docs/`            | MkDocs documentation source              |
| `examples/`        | Jupyter & Observable examples            |
| `tests/`           | Python tests (pytest)                    |
| `pyproject.toml`   | Python project configuration             |
| `package.json`     | JavaScript dependencies & scripts        |
| `eslint.config.js` | JavaScript linting configuration         |

## 🛠️ Development

> **For detailed contribution guidelines, see our [Contributing Guide](CONTRIBUTING.md)**

### Prerequisites

* Python 3.10+
* Node.js 16+
* npm or yarn

### Quick Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/broadinstitute/celldega.git
   cd celldega
   ```

2. **Create virtual environment**
   ```bash
   python -m venv dega
   source dega/bin/activate  # Windows: dega\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -e ".[dev]"
   npm install
   ```

4. **Start development server (hot‑reloads widget)**
   ```bash
   npm run dev
   ```

5. **Open demo notebook**
   ```bash
   jupyter lab examples/Landscape_View_Xenium.ipynb
   ```

### Testing & Code Quality

```bash
npm test                 # Run full JS + Py test suite
npm run test:js:watch    # JS tests in watch mode
npm run lint             # Ruff + ESLint checks
npm run format           # Prettier & Ruff formatters
```

Auto‑formatting is enabled on save in VS Code with the recommended extensions.

### VS Code Setup

Install these extensions for the best DX:
* **ESLint** – JavaScript/TypeScript linting
* **Prettier** – code formatter
* **Ruff** – Python linter & formatter
* **Python** – core Python support

## 📖 Documentation

* **[API Reference](https://broadinstitute.github.io/celldega/python/)** – full Python API
* **[Gallery](https://broadinstitute.github.io/celldega/gallery/)** – interactive Landscape demos
* **[Tutorials](https://broadinstitute.github.io/celldega/tutorials/)** – step‑by‑step guides
* **[Examples](examples/)** – notebooks you can run locally
* **[Contributing Guide](CONTRIBUTING.md)** – how to get involved

## 🤝 Contributing

We welcome PRs for new analysis modules, bug fixes, docs, and example datasets. See our [Contributing Guide](CONTRIBUTING.md) for details.

### Quick Contribution Steps

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add/update tests
5. Run tests & linting (`npm test && npm run lint`)
6. Commit (`git commit -m 'Add amazing feature'`)
7. Push (`git push origin feature/amazing-feature`)
8. Open a Pull Request

## 🐛 Issues & Support

* **Bug Reports / Feature Requests**: [GitHub Issues](https://github.com/broadinstitute/celldega/issues)

## 📄 License

This project is licensed under the MIT License – see [`LICENSE`](LICENSE).

## 🏛 Acknowledgments

* **Broad Institute** – primary development and funding
* **Contributors** – see [`CONTRIBUTORS.md`](CONTRIBUTORS.md)
* **Dependencies** – built on fantastic OSS such as deck.gl, PyArrow, pandas, and scikit‑learn

## 📊 Citation

If you use Celldega in your research, please cite:

```bibtex
@software{celldega,
  title   = {celldega: Interactive spatial‑omics analysis & visualisation toolkit},
  author  = {{Broad Institute}},
  url     = {https://github.com/broadinstitute/celldega},
  version = {0.8.2},
  year    = {2025}
}
```

## 🗺️ Roadmap

* [ ] Xenium HD segmentation overlay
* [ ] Visium FFPE deconvolution workflow
* [ ] Cloud‑based tiled‑view service

See our [Project Board](https://github.com/broadinstitute/celldega/projects) for detailed roadmap & progress.

---

<div align="center">

**[Docs](https://broadinstitute.github.io/celldega/)** • **[Examples](examples/)** • **[API](https://broadinstitute.github.io/celldega/python/)** • **[Contributing](CONTRIBUTING.md)**

Made with ❤️ by the [Broad Institute](https://broadinstitute.org/)

</div>
