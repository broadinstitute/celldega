"""Tests for the published CST lung PTM subset loader."""

from __future__ import annotations

import numpy as np
import pandas as pd

from notebooks.ccle_multiomics.cst_lung_ptm import CST_LUNG_PTM_FILE, read_cst_lung_ptm


def test_read_cst_lung_ptm_maps_historical_names_and_preserves_ptm_annotations(tmp_path):
    """Historical CST labels map to ModelID while retaining site/type provenance."""
    source = tmp_path / CST_LUNG_PTM_FILE
    source.parent.mkdir()
    columns = [
        "('Cell Line: A549', 'Histology: NSCLC', 'mut-KRAS: true')",
        "('Cell Line: H69', 'Histology: SCLC', 'mut-RB1: true')",
    ]
    pd.DataFrame(
        [[1.0, -1.0], [0.5, -0.5]],
        index=[
            "('KRT8_phospho_S39', 'Data-Type: phospho')",
            "('NKX2-1_Rme1_R121', 'Data-Type: Rme1')",
        ],
        columns=columns,
    ).to_csv(source, sep="\t")
    metadata = pd.DataFrame(
        {"CellLineName": ["A549", "NCI-H69"]},
        index=pd.Index(["ACH-000681", "ACH-000358"], name="ModelID"),
    )

    values, annotations, features = read_cst_lung_ptm(tmp_path, metadata)

    assert values.index.tolist() == ["KRT8_phospho_S39", "NKX2-1_Rme1_R121"]
    assert values.columns.tolist() == ["ACH-000681", "ACH-000358"]
    assert annotations["CSTHistology"].astype(str).tolist() == ["NSCLC", "SCLC"]
    assert annotations["CSTKRASMutation"].iloc[0] == "true"
    assert pd.isna(annotations["CSTKRASMutation"].iloc[1])
    assert features.loc["NKX2-1_Rme1_R121", "ptm_type"] == "Rme1"
    np.testing.assert_allclose(values.to_numpy(), [[1.0, -1.0], [0.5, -0.5]])
