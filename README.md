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

**Celldega** combines scalable computational pipelines with GPU‑accelerated, web‑native visualisations so you can explore **millions of cells and transcripts** directly inside Jupyter Lab, VS Code, or any modern browser. Built for researchers working with Xenium, Visium HD, MERFISH, and other spatial omics technologies.

## 🚀 Quick Start (30 seconds)

### Installation
```bash
pip install celldega
```

### Basic Usage
```python
import celldega as cd
from celldega.viz import Landscape

# Load your spatial data
data = cd.pre.load_file("xenium_sample.h5ad")

# Run analysis
cd.clust.cluster_gene_expression(data)

# Visualize interactively
landscape = Landscape(dataset_name="My Sample", base_url="./")
landscape  # 🎉 Interactive visualization appears!
```

That's it! You're analyzing spatial omics data with GPU-accelerated visualizations.

## ✨ What Makes Celldega Special

* 🧬 **Built for Biology** – Designed by and for spatial omics researchers
* ⚡ **Blazingly Fast** – GPU acceleration handles millions of data points smoothly
* 🌐 **Works Everywhere** – Jupyter, VS Code, web browsers, Terra.bio
* 🗺️ **Beautiful Visualizations** – Zoomable tissue maps with gene expression overlays
* 🔧 **Easy to Extend** – Modular design for custom analysis pipelines
* ☁️ **Cloud Ready** – First-class support for Terra.bio and cloud workflows

## 📋 What You Need

- **Python 3.10+** → [Download here](https://python.org/downloads/)
- **4+ GB RAM** (16+ GB recommended for large datasets)
- **Modern browser** (Chrome, Firefox, Safari, Edge)

### For Terra.bio Users
Add this to your startup script for image processing features:
```bash
apt update && apt install -y libvips libvips-tools libvips-dev
```

## 🧬 Perfect for Spatial Omics Research

**Celldega handles the data types you work with:**
- 🔬 **Xenium** - 10x Genomics spatial transcriptomics
- 🧪 **Visium & Visium HD** - Spatial gene expression arrays
- 🧬 **MERFISH** - Multiplexed error-robust FISH
- 📊 **AnnData/SpatialData** - Standard single-cell formats
- 🗂️ **Custom formats** - Extensible data loading pipeline

**Common research workflows:**
- Quality control and filtering
- Hierarchical clustering analysis
- Neighborhood graph construction
- Interactive tissue exploration
- Gene expression mapping
- Multi-sample comparison

## 🛠️ Development Setup (for Contributors)

**Get started contributing in 30 seconds:**

```bash
git clone https://github.com/broadinstitute/celldega.git
cd celldega
./scripts/setup.sh
source dega/bin/activate
npm run dev
```

**Daily development workflow:**
```bash
source dega/bin/activate    # Start your session
npm run dev                 # Development server
./scripts/test.sh          # Run tests before committing
```

See our [Contributing Guide](CONTRIBUTING.md) for detailed instructions.

## 📖 Documentation & Examples

- **[📚 Documentation](https://broadinstitute.github.io/celldega/)** - Complete guides and API reference
- **[🎯 Tutorials](https://broadinstitute.github.io/celldega/tutorials/)** - Step-by-step analysis workflows
- **[🖼️ Gallery](https://broadinstitute.github.io/celldega/gallery/)** - Interactive visualization demos
- **[📓 Examples](examples/)** - Jupyter notebooks you can run locally
- **[🔧 API Reference](https://broadinstitute.github.io/celldega/python/)** - Complete Python API

## 🏗️ Repository Structure

| Directory/File     | Purpose                                  |
| ------------------ | ---------------------------------------- |
| `src/celldega/`    | 🐍 Core Python package                   |
| `js/`              | 🌐 JavaScript widgets & visualizations   |
| `examples/`        | 📓 Jupyter notebook examples             |
| `docs/`            | 📚 Documentation source                  |
| `js/__tests__/`    | 🧪 JS/TS Test suites                          |
| `tests/`           | 🧪 Python Test suites                          |
| `scripts/`         | 🔧 Development utilities                  |

## 🤝 Contributing

We welcome contributions from the spatial omics community! Whether you're a:

- 🧬 **Biology Researcher** - Share datasets, create tutorials, improve documentation
- 👩‍💻 **Developer** - Add features, fix bugs, optimize performance
- 📚 **Educator** - Create educational content, examples, workshops
- 🎨 **Designer** - Improve visualizations, user experience, documentation

**Getting started:**
1. Read our [Contributing Guide](CONTRIBUTING.md)
2. Check [open issues](https://github.com/broadinstitute/celldega/issues) for ideas
3. Join [discussions](https://github.com/broadinstitute/celldega/discussions) to ask questions

## 🆘 Getting Help

**Questions about using Celldega?**
- 💬 [GitHub Discussions](https://github.com/broadinstitute/celldega/discussions) - Ask the community
- 📖 [Documentation](https://broadinstitute.github.io/celldega/) - Comprehensive guides
- 📓 [Examples](examples/) - Working code you can adapt

**Found a bug or want a feature?**
- 🐛 [Report bugs](https://github.com/broadinstitute/celldega/issues/new?template=bug_report.md)
- ✨ [Request features](https://github.com/broadinstitute/celldega/issues/new?template=feature_request.md)

## 📊 Citation

If Celldega helps your research, please cite us:

```bibtex
@software{celldega,
  title   = {Celldega: Interactive spatial‑omics analysis & visualisation toolkit},
  author  = {{Broad Institute}},
  url     = {https://github.com/broadinstitute/celldega},
  version = {0.8.2},
  year    = {2025}
}
```

## 🏛️ About

**Celldega** is developed at the [Broad Institute](https://broadinstitute.org/) with the spatial omics research community. Our mission is to make spatial transcriptomics analysis accessible, interactive, and beautiful.

Built on amazing open source tools:
- **[deck.gl](https://deck.gl/)** - GPU-accelerated visualizations
- **[PyArrow](https://arrow.apache.org/docs/python/)** - Fast columnar data processing
- **[AnnData](https://anndata.readthedocs.io/)** - Annotated data matrices
- **[SpatialData](https://spatialdata.scverse.org/)** - Spatial omics data structures

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

---

<div align="center">

**[📚 Docs](https://broadinstitute.github.io/celldega/)** • **[📓 Examples](examples/)** • **[🔧 API](https://broadinstitute.github.io/celldega/python/)** • **[🤝 Contributing](CONTRIBUTING.md)**

Made with ❤️ by the spatial omics community at the [Broad Institute](https://broadinstitute.org/)

</div>
