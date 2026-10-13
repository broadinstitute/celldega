# %% [markdown]
# # Prepare the CCLE / DepMap multi-omics archive
#
# This reference notebook performs the one-time, data-heavy preparation step.
# It keeps each assay on its native cell-line axis in a `MuData` and then wraps
# that object in Celldega's `DatasetCollection`.  An unmeasured assay is never
# represented as an all-zero row.
#
# Raw files are expected in `data/ccle_multiomics/raw/`, which is ignored by
# git.  The required inputs are the DepMap 24Q2 `Model.csv`, batch-corrected
# protein-coding RNA expression, Chronos gene effects, and the CCLE RPPA and
# metabolomics CSV files.  See `ccle_multiomics/README.md` for filenames and
# sources.

# %%
from __future__ import annotations

from pathlib import Path
import sys


PROJECT = next(parent for parent in (Path.cwd(), *Path.cwd().parents) if (parent / "pyproject.toml").exists())
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from notebooks.ccle_multiomics import build_collection, load_collection


RAW = PROJECT / "data/ccle_multiomics/raw"
ARCHIVE = PROJECT / "data/ccle_multiomics/processed/ccle_multiomics.h5mu"

# %% [markdown]
# Set `REBUILD = True` only when raw inputs change.  The resulting H5MU stores
# native assay coverage: RNA has more models than the legacy RPPA panel, for
# example, rather than being reduced immediately to a complete-case cohort.

# %%
REBUILD = False

if REBUILD or not ARCHIVE.exists():
    collection = build_collection(RAW, ARCHIVE, include_crispr=True, overwrite=REBUILD)
else:
    collection = load_collection(ARCHIVE)

print(type(collection).__name__)
for modality, adata in collection.mod.items():
    print(f"{modality:14s} {adata.n_obs:4d} models x {adata.n_vars:6d} features")
