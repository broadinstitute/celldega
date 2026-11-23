"""
Test celldega.qc module.
"""

from pathlib import Path
import sys

import pytest


sys.path.insert(0, str(Path(__file__).parents[3] / "src"))


def test_qc_module_exists():
    """Test that qc module exists."""
    import importlib.util

    try:
        spec = importlib.util.find_spec("celldega.qc")
    except ModuleNotFoundError:
        pytest.skip("qc dependencies missing")

    if spec is None:
        pytest.skip("qc module not importable")


def test_qc_entry_points_warn_that_the_module_is_in_development(tmp_path):
    qc = pytest.importorskip("celldega.qc")
    with pytest.warns(UserWarning, match="in development"):
        # An unknown technology returns before reading any files.
        qc.qc_segmentation(tmp_path, technology="unknown", dataset_name="test")
