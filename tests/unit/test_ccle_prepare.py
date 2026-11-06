"""Tests for the reviewable CCLE multi-omics preparation helpers."""

from __future__ import annotations

import numpy as np
import pandas as pd

from notebooks.ccle_multiomics.prepare import (
    PROTEOMICS_MS_FILE,
    read_proteomics_ms,
)


def test_read_proteomics_ms_maps_bridge_samples_and_collapses_duplicates(tmp_path):
    """MS bridge samples resolve to ModelID without merging the RPPA modality."""
    pd.DataFrame(
        {
            "Gene_Symbol": ["CDH1", "BCL2", "CDH1"],
            "A_TenPx01": [1.0, 10.0, 5.0],
            "A_TenPx02": [3.0, 14.0, 7.0],
            "B_TenPx01": [7.0, 4.0, 9.0],
            "A_Peptides": [2, 2, 3],
        }
    ).to_csv(tmp_path / PROTEOMICS_MS_FILE, index=False)
    metadata = pd.DataFrame(
        {"StrippedCellLineName": ["A", "B"]},
        index=pd.Index(["ACH-000001", "ACH-000002"], name="ModelID"),
    )

    values = read_proteomics_ms(tmp_path, metadata)

    assert values.index.tolist() == ["CDH1", "BCL2"]
    assert values.columns.tolist() == ["ACH-000001", "ACH-000002"]
    np.testing.assert_allclose(
        values.to_numpy(),
        np.array([[4.0, 8.0], [12.0, 4.0]], dtype=np.float32),
    )
