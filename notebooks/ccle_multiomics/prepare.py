"""Build a coverage-preserving CCLE MuData/DatasetCollection archive."""

from __future__ import annotations

import argparse
from collections.abc import Iterable
import colorsys
import json
from pathlib import Path
import re
from typing import Any
import warnings

from anndata import AnnData
import mudata
from mudata import MuData
import numpy as np
import pandas as pd

from celldega.dataset import DatasetCollection


# Large source files and derived archives live under the repository's ignored
# ``data/`` directory.  The notebook sources remain small and reviewable.
DEFAULT_RAW_DIR = Path("data/ccle_multiomics/raw")
DEFAULT_OUTPUT = Path("data/ccle_multiomics/processed/ccle_multiomics.h5mu")
EXPRESSION_FILE = "OmicsExpressionProteinCodingGenesTPMLogp1BatchCorrected.csv"
MODEL_FILE = "Model.csv"
METABOLOMICS_FILE = "CCLE_metabolomics_20190502.csv"
RPPA_FILE = "CCLE_RPPA_20181003.csv"
CRISPR_FILE = "CRISPRGeneEffect.csv"

METADATA_COLUMNS = [
    "PatientID", "CellLineName", "StrippedCellLineName", "DepmapModelType",
    "OncotreeLineage", "OncotreePrimaryDisease", "OncotreeSubtype",
    "OncotreeCode", "LegacyMolecularSubtype", "LegacySubSubtype",
    "PatientMolecularSubtype", "RRID", "Age", "AgeCategory", "Sex",
    "PrimaryOrMetastasis", "SampleCollectionSite", "SourceType",
    "GrowthPattern", "TissueOrigin", "CCLEName", "SangerModelID", "COSMICID",
]

COLOR_ANNOTATIONS = ("OncotreeLineage", "OncotreePrimaryDisease", "OncotreeSubtype")
MODALITY_COLORS = {
    "rna": "#4C78A8",
    "rppa": "#F58518",
    "metabolomics": "#54A24B",
    "crispr": "#B279A2",
}

SOURCES = {
    "expression_and_metadata": {
        "name": "DepMap 24Q2 Public, Figshare version 1",
        "url": "https://plus.figshare.com/articles/dataset/DepMap_24Q2_Public/25880521",
    },
    "metabolomics": {
        "name": "CCLE metabolomics",
        "url": "https://data.broadinstitute.org/ccle/CCLE_metabolomics_20190502.csv",
    },
    "rppa": {
        "name": "CCLE RPPA",
        "url": "https://data.broadinstitute.org/ccle/CCLE_RPPA_20181003.csv",
    },
    "crispr": {
        "name": "DepMap 24Q2 Chronos CRISPR gene effect",
        "url": "https://plus.figshare.com/articles/dataset/DepMap_24Q2_Public/25880521",
    },
}


def _model_ids(index: Iterable[object]) -> pd.Index:
    return pd.Index(index, dtype="string").astype(str)


def _category_colors(categories: Iterable[str]) -> list[str]:
    """Generate a stable, readable palette with gray reserved for unknown."""
    levels = list(categories)
    known = [level for level in levels if level != "unknown"]
    palette: dict[str, str] = {"unknown": "#9E9E9E"}
    for index, level in enumerate(known):
        hue = (index * 0.61803398875) % 1
        red, green, blue = colorsys.hsv_to_rgb(hue, 0.60, 0.85)
        palette[level] = f"#{int(red * 255):02X}{int(green * 255):02X}{int(blue * 255):02X}"
    return [palette[level] for level in levels]


def harmonize_annotation_colors(modalities: dict[str, AnnData]) -> None:
    """Apply one category order and palette to every modality's model metadata.

    Celldega's ``Matrix`` reads ``adata.uns['<field>_colors']`` together with
    categorical ``adata.obs[field]``. Keeping both aligned in every native
    assay prevents a lineage, disease, or subtype from changing color between
    independent Clustergrams and DatasetCollection-derived views.
    """
    for field in COLOR_ANNOTATIONS:
        values = [
            adata.obs[field].astype("string").fillna("unknown").astype(str)
            for adata in modalities.values()
            if field in adata.obs
        ]
        if not values:
            continue
        observed_levels = set(pd.concat(values))
        levels = sorted(observed_levels.difference({"unknown"}))
        if "unknown" in observed_levels:
            levels.append("unknown")
        colors = _category_colors(levels)
        for adata in modalities.values():
            if field not in adata.obs:
                continue
            adata.obs[field] = pd.Categorical(
                adata.obs[field].astype("string").fillna("unknown").astype(str),
                categories=levels,
            )
            adata.uns[f"{field}_colors"] = colors


def apply_modality_colors(adata: AnnData) -> AnnData:
    """Give feature-level modality categories a fixed cross-notebook palette."""
    if "modality" not in adata.var:
        return adata
    present = adata.var["modality"].astype("string").fillna("unknown").astype(str)
    categories = [name for name in MODALITY_COLORS if name in set(present)]
    categories.extend(sorted(set(present).difference(categories)))
    adata.var["modality"] = pd.Categorical(present, categories=categories)
    adata.uns["modality_colors"] = [MODALITY_COLORS.get(name, "#9E9E9E") for name in categories]
    return adata


def inherit_annotation_colors(adata: AnnData, source: AnnData) -> AnnData:
    """Copy canonical model-annotation palettes into a derived AnnData view."""
    for field in COLOR_ANNOTATIONS:
        color_key = f"{field}_colors"
        if field in adata.obs and color_key in source.uns:
            adata.uns[color_key] = list(source.uns[color_key])
    return adata


def _collapse_duplicates(frame: pd.DataFrame) -> pd.DataFrame:
    return frame if not frame.index.has_duplicates else frame.groupby(level=0, sort=False).median()


def read_metadata(raw_dir: Path) -> pd.DataFrame:
    """Read stable DepMap model annotations, including patient provenance."""
    models = pd.read_csv(raw_dir / MODEL_FILE)
    if "ModelID" not in models or models["ModelID"].duplicated().any():
        raise ValueError(f"{MODEL_FILE} must contain unique ModelID values")
    fields = [field for field in METADATA_COLUMNS if field in models]
    metadata = models.set_index("ModelID")[fields].copy()
    metadata.index = _model_ids(metadata.index)
    metadata.index.name = "ModelID"
    for field in metadata:
        if pd.api.types.is_object_dtype(metadata[field]) or pd.api.types.is_string_dtype(metadata[field]):
            metadata[field] = metadata[field].fillna("unknown").astype(str)
    return metadata


def read_expression(raw_dir: Path) -> pd.DataFrame:
    """DepMap batch-corrected log2(TPM + 1), returned features by ModelID."""
    frame = pd.read_csv(raw_dir / EXPRESSION_FILE, index_col=0)
    frame.index = _model_ids(frame.index)
    frame.columns = [re.sub(r"\s+\(\d+\)\s*$", "", str(name)) for name in frame.columns]
    values = frame.apply(pd.to_numeric, errors="coerce").T.astype(np.float32)
    values.index.name, values.columns.name = "feature_id", "ModelID"
    return _collapse_duplicates(values)


def read_metabolomics(raw_dir: Path) -> pd.DataFrame:
    """CCLE's already log10-transformed and calibrated metabolite values."""
    raw = pd.read_csv(raw_dir / METABOLOMICS_FILE)
    if "DepMap_ID" not in raw:
        raise ValueError(f"{METABOLOMICS_FILE} has no DepMap_ID column")
    values = raw.drop(columns=[col for col in ("CCLE_ID", "DepMap_ID") if col in raw])
    by_model = pd.DataFrame(values.apply(pd.to_numeric, errors="coerce").to_numpy(), index=raw["DepMap_ID"], columns=values.columns)
    by_model = by_model.loc[by_model.index.notna()]
    by_model.index = _model_ids(by_model.index)
    result = by_model.groupby(level=0, sort=False).median().T.astype(np.float32)
    result.index.name, result.columns.name = "feature_id", "ModelID"
    return _collapse_duplicates(result)


def read_rppa(raw_dir: Path, metadata: pd.DataFrame) -> pd.DataFrame:
    """Map CCLE-name-indexed RPPA measurements to ModelID without target collapse."""
    if "CCLEName" not in metadata:
        raise ValueError("Model metadata has no CCLEName column")
    # ``read_metadata`` makes absent annotations explicit as ``unknown`` for
    # categorical display.  They are not valid RPPA source identifiers.
    names = metadata["CCLEName"].replace("unknown", np.nan).dropna().astype(str)
    if names.duplicated().any():
        raise ValueError("CCLEName is not a unique map to ModelID")
    name_to_id = pd.Series(names.index, index=names)
    raw = pd.read_csv(raw_dir / RPPA_FILE, index_col=0)
    mapped = name_to_id.reindex(raw.index.astype(str))
    keep = mapped.notna()
    values = raw.loc[keep].apply(pd.to_numeric, errors="coerce")
    values.index = _model_ids(mapped.loc[keep])
    result = values.groupby(level=0, sort=False).median().T.astype(np.float32)
    result.index.name, result.columns.name = "feature_id", "ModelID"
    return _collapse_duplicates(result)


def read_crispr(raw_dir: Path) -> pd.DataFrame:
    """Return Chronos gene-effect scores as features by ModelID.

    This is a functional-dependency modality: more negative values indicate a
    stronger knockout effect. It is intentionally separate from abundance data.
    """
    frame = pd.read_csv(raw_dir / CRISPR_FILE, index_col=0)
    frame.index = _model_ids(frame.index)
    frame.columns = [re.sub(r"\s+\(\d+\)\s*$", "", str(name)) for name in frame.columns]
    values = frame.apply(pd.to_numeric, errors="coerce").T.astype(np.float32)
    values.index.name, values.columns.name = "feature_id", "ModelID"
    values = _collapse_duplicates(values)
    # Unlike abundance matrices, missing CRISPR calls must remain missing until
    # an analysis makes an explicit missingness decision.
    return values.dropna(axis=0, how="all").dropna(axis=1, how="all")


def _feature_metadata(feature_ids: pd.Index, modality: str) -> pd.DataFrame:
    """Describe the assay faithfully without inferring protein targets."""
    index = pd.Index(feature_ids.astype(str), name="feature_id")
    var = pd.DataFrame({"feature_name": index.astype(str), "modality": modality}, index=index)
    if modality == "rppa":
        var["is_phospho"] = index.str.contains(r"(?:^|_)p[STY]\\d", regex=True)
        var["is_caution"] = index.str.endswith("_Caution")
        var["assay_type"] = np.where(var["is_phospho"], "phospho", "antibody")
    return var


def _make_modality(values: pd.DataFrame, metadata: pd.DataFrame, modality: str) -> AnnData:
    """Make one modality while retaining only its genuinely measured cell lines."""
    model_ids = _model_ids(values.columns)
    obs = metadata.reindex(model_ids).copy()
    obs.index, obs.index.name = model_ids, "ModelID"
    obs["assay_present"] = True
    adata = AnnData(
        X=values.T.to_numpy(dtype=np.float32),
        obs=obs,
        var=_feature_metadata(values.index, modality),
    )
    scale = {
        "rna": "DepMap batch-corrected log2(TPM + 1)",
        "metabolomics": "CCLE calibrated log10 metabolite peak area",
        "rppa": "CCLE RPPA normalized antibody measurement",
        "crispr": "DepMap Chronos gene effect; more negative is stronger dependency",
    }[modality]
    adata.uns["ccle_multiomics"] = {
        "value_scale": scale,
        "preprocessing": "Source-scale values; no cross-modality normalization applied.",
    }
    return adata


def _qc_summary(modalities: dict[str, AnnData], metadata: pd.DataFrame) -> dict[str, Any]:
    coverage = pd.DataFrame(
        {name: metadata.index.isin(adata.obs_names) for name, adata in modalities.items()},
        index=metadata.index,
    )
    core = [name for name in ("rna", "rppa", "metabolomics") if name in coverage]
    return {
        "n_models_metadata": len(metadata),
        "n_models_union": int(coverage.any(axis=1).sum()),
        "n_models_complete_rna_rppa_metabolomics": int(coverage[core].all(axis=1).sum()),
        "n_models_complete_all_included_modalities": int(coverage.all(axis=1).sum()),
        "modalities": {
            name: {
                "n_models": int(adata.n_obs),
                "n_features": int(adata.n_vars),
                "n_missing_values": int(np.isnan(np.asarray(adata.X)).sum()),
            }
            for name, adata in modalities.items()
        },
    }


def build_collection(
    raw_dir: str | Path = DEFAULT_RAW_DIR,
    output: str | Path = DEFAULT_OUTPUT,
    *,
    include_crispr: bool = True,
    overwrite: bool = False,
) -> DatasetCollection:
    """Build and write the first CCLE multi-omic DatasetCollection.

    The top-level axis is the union of annotated DepMap models.  Each AnnData
    modality maintains its own observation axis, so later comparisons must ask
    for a deliberate intersection instead of treating absence as a zero.
    """
    raw_path, output_path = Path(raw_dir), Path(output)
    required = [MODEL_FILE, EXPRESSION_FILE, METABOLOMICS_FILE, RPPA_FILE]
    if include_crispr:
        required.append(CRISPR_FILE)
    missing = [name for name in required if not (raw_path / name).exists()]
    if missing:
        raise FileNotFoundError(f"Missing raw CCLE inputs in {raw_path}: {', '.join(missing)}")
    if output_path.exists() and not overwrite:
        raise FileExistsError(f"{output_path} already exists; pass overwrite=True to replace it")

    metadata = read_metadata(raw_path)
    tables = {"rna": read_expression(raw_path), "metabolomics": read_metabolomics(raw_path)}
    tables["rppa"] = read_rppa(raw_path, metadata)
    if include_crispr:
        tables["crispr"] = read_crispr(raw_path)
    modalities = {name: _make_modality(table, metadata, name) for name, table in tables.items()}
    harmonize_annotation_colors(modalities)

    # This native MuData path is essential: DatasetCollection(mdata=...) does
    # not pad assays that are missing a model with artificial zero rows.
    mdata = MuData(modalities)
    union = pd.Index(mdata.obs_names.astype(str), name="ModelID")
    mdata.obs = metadata.reindex(union).copy()
    mdata.uns["ccle_multiomics"] = {
        "archive_version": "0.1",
        "sources": SOURCES,
        "missingness_policy": "Unmeasured assays are absent from their modality, never zero-filled.",
        "analysis_note": "Use an explicit matched cohort for every cross-modality comparison.",
    }
    collection = DatasetCollection(
        mdata=mdata,
        dataset_col="ModelID",
        name="CCLE multi-omics",
        source="DepMap 24Q2 / CCLE",
        provenance={"sources": SOURCES, "builder": "ccle_multiomics.prepare.build_collection"},
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    collection.write(output_path)
    output_path.with_suffix(".qc.json").write_text(
        json.dumps(_qc_summary(modalities, metadata), indent=2, sort_keys=True) + "\n"
    )
    return collection


def load_collection(path: str | Path = DEFAULT_OUTPUT) -> DatasetCollection:
    """Load the persisted CCLE DatasetCollection with canonical top-level metadata.

    MuData 0.3 defaults to rebuilding ``mdata.obs`` by pulling every modality's
    repeated annotations into prefixed columns on read.  The archive already has
    a canonical ModelID table, so retain it while loading; per-modality ``.obs``
    remains unchanged for Matrix annotations.
    """
    with warnings.catch_warnings():
        # Gene identifiers are intentionally shared between RNA and CRISPR.
        # They are scoped by modality, so global MuData variable-name uniqueness
        # is neither needed nor desirable for this archive.
        warnings.filterwarnings("ignore", message="var_names are not unique")
        with mudata.set_options(pull_on_update=False):
            collection = DatasetCollection.read(Path(path))
    harmonize_annotation_colors(collection.mod)
    return collection


def shared_model_ids(collection: DatasetCollection, modalities: Iterable[str]) -> pd.Index:
    """Return a consciously requested shared ModelID cohort."""
    requested = list(modalities)
    if not requested:
        raise ValueError("at least one modality is required")
    unknown = sorted(set(requested).difference(collection.mod))
    if unknown:
        raise KeyError(f"unknown modalities: {unknown}; available: {list(collection.mod)}")
    shared = pd.Index(collection.mod[requested[0]].obs_names)
    for name in requested[1:]:
        shared = shared.intersection(pd.Index(collection.mod[name].obs_names))
    return shared.sort_values()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--exclude-crispr", action="store_true")
    args = parser.parse_args()
    collection = build_collection(
        args.raw_dir,
        args.output,
        include_crispr=not args.exclude_crispr,
        overwrite=args.overwrite,
    )
    print(f"Wrote {args.output}")
    for name, adata in collection.mod.items():
        print(f"  {name:14s} {adata.n_obs:4d} models x {adata.n_vars:6d} features")


if __name__ == "__main__":
    main()
