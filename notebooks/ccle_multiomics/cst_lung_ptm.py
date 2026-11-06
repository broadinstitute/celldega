"""Load the published CST lung TMT PTM subset as a separate MuData object."""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path
import re

from anndata import AnnData
from mudata import MuData
import numpy as np
import pandas as pd

from .prepare import (
    DEFAULT_OUTPUT,
    apply_modality_colors,
    harmonize_annotation_colors,
    load_collection,
)


CST_LUNG_PTM_FILE = Path("cst_lung_ptm") / "CST_CCLE_ptm.txt"
DEFAULT_CST_LUNG_OUTPUT = Path("data/ccle_multiomics/processed/cst_lung_ptm_multiomics.h5mu")
CST_LUNG_PTM_SOURCE = "https://doi.org/10.6084/m9.figshare.5339689"


def _canonical_cell_line_name(value: object) -> str:
    """Normalize historical and current CCLE cell-line spellings for a strict map."""
    name = re.sub(r"[^A-Z0-9]", "", str(value).upper())
    return name.removeprefix("NCI")


def _parse_legacy_tuple(value: object) -> tuple[str, ...]:
    """Parse the tuple-like labels written by the original Clustergrammer data."""
    try:
        parsed = ast.literal_eval(str(value))
    except (SyntaxError, ValueError) as error:
        raise ValueError(f"Could not parse published CST label {value!r}") from error
    if not isinstance(parsed, tuple) or not all(isinstance(item, str) for item in parsed):
        raise ValueError(f"Expected a tuple of strings in published CST label {value!r}")
    return parsed


def _label_dict(items: tuple[str, ...]) -> dict[str, str]:
    labels: dict[str, str] = {}
    for item in items:
        key, separator, value = item.partition(": ")
        if separator:
            labels[key] = value
        else:
            labels[""] = item
    return labels


def _model_aliases(metadata: pd.DataFrame) -> dict[str, str]:
    """Make an unambiguous map from CCLE aliases to current DepMap ModelID."""
    available = [
        field for field in ("CellLineName", "StrippedCellLineName", "CCLEName") if field in metadata
    ]
    candidates: dict[str, set[str]] = {}
    for model_id, row in metadata.loc[:, available].iterrows():
        for value in row.astype("string").dropna():
            if value == "unknown":
                continue
            key = _canonical_cell_line_name(value)
            candidates.setdefault(key, set()).add(str(model_id))
    # Short aliases elsewhere in the full cell-line collection can collide
    # (for example, ``T.T``).  They are irrelevant unless a CST column uses
    # the same spelling; drop them now and report a missing mapping then.
    return {key: next(iter(ids)) for key, ids in candidates.items() if len(ids) == 1}


def read_cst_lung_ptm(
    raw_dir: str | Path,
    metadata: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Read the exact processed PTM matrix used by the published case study.

    Returns a feature-by-ModelID matrix, historical cell-line annotations, and
    PTM feature annotations.  The source matrix is already column-quantile
    normalized and row z-scored by the original study; it is not transformed
    again here.
    """
    source = Path(raw_dir) / CST_LUNG_PTM_FILE
    if not source.exists():
        raise FileNotFoundError(f"Missing CST lung PTM input: {source}")
    raw = pd.read_csv(source, sep="\t", index_col=0)
    if raw.empty or raw.columns.has_duplicates or raw.index.has_duplicates:
        raise ValueError(
            "Published CST PTM matrix must have non-empty unique row and column labels"
        )

    header_labels = [_label_dict(_parse_legacy_tuple(column)) for column in raw.columns]
    if any("Cell Line" not in labels or "Histology" not in labels for labels in header_labels):
        raise ValueError("Published CST PTM columns lack Cell Line or Histology annotations")
    aliases = _model_aliases(metadata)
    model_ids = pd.Index(
        [aliases.get(_canonical_cell_line_name(labels["Cell Line"])) for labels in header_labels],
        dtype="string",
        name="ModelID",
    )
    if model_ids.isna().any():
        missing = [
            labels["Cell Line"]
            for labels, model_id in zip(header_labels, model_ids, strict=True)
            if pd.isna(model_id)
        ]
        raise ValueError(f"Could not map CST cell lines to current ModelID: {missing}")
    if model_ids.has_duplicates:
        raise ValueError("Published CST cell lines mapped to duplicate current ModelIDs")

    feature_labels = [_label_dict(_parse_legacy_tuple(index)) for index in raw.index]
    if any("Data-Type" not in labels for labels in feature_labels):
        raise ValueError("Published CST PTM rows lack Data-Type annotations")
    feature_ids = pd.Index(
        [
            labels.get("", str(index))
            for labels, index in zip(feature_labels, raw.index, strict=True)
        ]
    )
    # PTM names are the first tuple value; _label_dict deliberately retains
    # it under an empty key because it has no `key: value` prefix.
    if feature_ids.has_duplicates:
        raise ValueError("Published CST PTM feature labels are not unique")

    values = raw.apply(pd.to_numeric, errors="coerce")
    if not np.isfinite(values.to_numpy(dtype=float)).all():
        raise ValueError("Published CST PTM matrix unexpectedly contains missing/non-finite values")
    values.index = pd.Index(feature_ids, name="feature_id")
    values.columns = model_ids.astype(str)
    values.columns.name = "ModelID"

    legacy = pd.DataFrame(header_labels, index=model_ids.astype(str))
    legacy.index.name = "ModelID"
    legacy = legacy.rename(
        columns={
            "Cell Line": "CSTCellLineName",
            "Histology": "CSTHistology",
            "Sub-Histology": "CSTSubHistology",
            "mut-TP53": "CSTTP53Mutation",
            "mut-EGFR": "CSTEGFRMutation",
            "mut-RB1": "CSTRB1Mutation",
            "mut-KRAS": "CSTKRASMutation",
        }
    )
    legacy["CSTHistology"] = pd.Categorical(legacy["CSTHistology"], categories=["SCLC", "NSCLC"])

    features = pd.DataFrame(
        {
            "feature_name": feature_ids.astype(str),
            "ptm_type": [labels["Data-Type"] for labels in feature_labels],
            "modality": "cst_ptm",
            "source_feature_label": raw.index.astype(str),
        },
        index=pd.Index(feature_ids, name="feature_id"),
    )
    return values.astype(np.float32), legacy, features


def build_cst_lung_ptm_mudata(
    raw_dir: str | Path = "data/ccle_multiomics/raw",
    base_archive: str | Path = DEFAULT_OUTPUT,
    output: str | Path = DEFAULT_CST_LUNG_OUTPUT,
    *,
    overwrite: bool = False,
) -> MuData:
    """Build the 37-model CST lung PTM plus current CCLE/DepMap MuData subset."""
    output_path = Path(output)
    if output_path.exists() and not overwrite:
        raise FileExistsError(f"{output_path} already exists; pass overwrite=True to replace it")

    base = load_collection(base_archive)
    reference = base.mod["rna"]
    values, legacy_annotations, feature_annotations = read_cst_lung_ptm(raw_dir, reference.obs)
    model_ids = pd.Index(values.columns.astype(str), name="ModelID")

    modalities: dict[str, AnnData] = {}
    for name in ("rna", "rppa", "metabolomics"):
        if name not in base.mod:
            continue
        missing = model_ids.difference(pd.Index(base.mod[name].obs_names.astype(str)))
        if len(missing):
            raise ValueError(f"Current {name} layer lacks CST models: {missing.tolist()}")
        modalities[name] = base.mod[name][model_ids].copy()

    cst_obs = reference.obs.reindex(model_ids).copy()
    cst_obs = cst_obs.join(legacy_annotations, how="left")
    cst = AnnData(
        X=values.T.to_numpy(dtype=np.float32),
        obs=cst_obs,
        var=feature_annotations,
    )
    cst.uns["ccle_multiomics"] = {
        "value_scale": "Published CST processed PTM values: column quantile-normalized, then row z-scored",
        "preprocessing": "Retained exactly as distributed for the Clustergrammer lung case study.",
        "source": CST_LUNG_PTM_SOURCE,
    }
    modalities["cst_ptm"] = apply_modality_colors(cst)

    for adata in modalities.values():
        for field in legacy_annotations:
            adata.obs[field] = legacy_annotations.reindex(adata.obs_names)[field].to_numpy()
        adata.obs["CSTHistology"] = pd.Categorical(
            adata.obs["CSTHistology"], categories=["SCLC", "NSCLC"]
        )
        adata.uns["CSTHistology_colors"] = ["#E45756", "#4C78A8"]
    harmonize_annotation_colors(modalities)

    mdata = MuData(modalities)
    mdata.obs = reference.obs.reindex(model_ids).copy()
    for field in legacy_annotations:
        mdata.obs[field] = legacy_annotations.reindex(model_ids)[field].to_numpy()
    mdata.obs["CSTHistology"] = pd.Categorical(
        mdata.obs["CSTHistology"], categories=["SCLC", "NSCLC"]
    )
    mdata.uns["CSTHistology_colors"] = ["#E45756", "#4C78A8"]
    source_path = Path(raw_dir) / CST_LUNG_PTM_FILE
    mdata.uns["cst_lung_ptm"] = {
        "n_models": len(model_ids),
        "n_ptm_features": int(values.shape[0]),
        "source": CST_LUNG_PTM_SOURCE,
        "source_file": str(CST_LUNG_PTM_FILE),
        "source_sha1": hashlib.sha1(source_path.read_bytes()).hexdigest(),
        "comparison": "TMT PTM ratios for lung cancer cell lines relative to non-cancerous lung tissue",
        "assays": list(modalities),
        "mapping": "Historical CST cell-line labels mapped unambiguously to current DepMap ModelID using CCLE aliases.",
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    mdata.write_h5mu(output_path)
    return mdata
