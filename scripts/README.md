# 🧬 Celldega Development Scripts

**Get started in 30 seconds:**

```bash
./scripts/setup.sh
source dega/bin/activate
npm run dev
```

That's it! 🎉

## What You Need

- **Python 3.11 or 3.12** → [Download here](https://python.org/downloads/)
- **uv** → [Installation guide](https://docs.astral.sh/uv/getting-started/installation/)
- **Node.js and npm** → [Package requirements](../package.json)

## 🗂️ Scripts Overview

| Script     | What it does              | When to use            |
| ---------- | ------------------------- | ---------------------- |
| `setup.sh` | **Gets everything ready** | First time setup       |
| `test.sh`  | **Runs your tests**       | Before submitting work |

## Quick Commands

```bash
bash ./scripts/setup.sh              # Set up everything
bash ./scripts/setup.sh --status     # Check what's installed
bash ./scripts/test.sh               # Run all tests
```

## Daily Workflow

```bash
# Start your work session
source dega/bin/activate
npm run dev

# Before committing your work
bash ./scripts/test.sh
```

## Prepare compact Allen mouse brain CellCloud data

[`prepare_allen_mouse_brain_cellcloud.py`](prepare_allen_mouse_brain_cellcloud.py)
downloads pinned public inputs and creates new DegaFiles and AnnData Zarr
alternatives for the same 3.8-million-cell stack:

```bash
python scripts/prepare_allen_mouse_brain_cellcloud.py --download
```

Run from the checkout with Celldega and the `hf` CLI installed. Outputs go to
`data/allen_mouse_brain_cellcloud_v2/artifacts/`:

- `github/xenium_E15.5_cell_cloud_v2_1um/`: compact Parquet DegaFiles with numeric cell references and original IDs stored once.
- `huggingface/Allen-Broad_Dev-Mouse-Brain/E15.5/cellcloud_v2_1um.zarr/`: AnnData Zarr with CSC counts and both alignments.
- `size-report.json` and `SHA256SUMS`: storage comparison, validation results, and checksums.

Coordinates are rounded to 1 µm; original cell IDs, raw counts, cluster labels,
and colors are retained. The script performs no uploads and refuses an existing
completed output. Choose another `--work-dir` for a separate export; `--resume`
can reuse completed DegaFiles after an interrupted Zarr export.

See the [3D mouse brain example](../docs/gallery/gallery_broad_allen_mouse_brain_3d.md)
for using either source with `CellCloud`.

## ❤️‍🩹 Common Issues & Solutions

**"Permission denied"?**

```bash
chmod +x scripts/*.sh
```

**"Command not found"?**

- Make sure Python, Node.js, and npm are installed
- Check you're in the right folder (should see `pyproject.toml`)

**Something broken?**

```bash
./scripts/setup.sh --reset     # Clean slate
./scripts/setup.sh             # Fresh setup
```

**Need more details?**

```bash
bash ./scripts/setup.sh --verbose   # See everything that happens
bash ./scripts/test.sh --verbose    # Detailed test output
```

## 😎 For Advanced Users

<details>
<summary>Click to see advanced options</summary>

### Full Test Options

```bash
bash ./scripts/test.sh python          # Python tests only
bash ./scripts/test.sh js              # JavaScript tests only
bash ./scripts/test.sh lint            # Code quality checks
bash ./scripts/test.sh coverage       # Generate coverage report
bash ./scripts/test.sh python tests/unit/  # Run specific directory
```

### Setup Options

```bash
./scripts/setup.sh --status      # Check environment status
./scripts/setup.sh --reset       # Clean install
./scripts/setup.sh --verbose     # Show all details
```

### Debugging

```bash
export VERBOSE=true              # Show detailed output
export DEBUG=true                # Show debug information
```

### npm Commands

```bash
npm install                      # Install dependencies
npm run dev                      # Start development server
npm run build                    # Build for production
npm run test:js                  # Run JavaScript tests
npm run lint:js                  # Lint JavaScript code
```

</details>

---

**🆘 Still stuck?** Check the main project README or ask for help!
