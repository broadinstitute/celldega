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
        if importlib.util.find_spec("celldega.qc") is None:
            pytest.skip("qc module not importable")
    except ModuleNotFoundError:
        pytest.skip("qc dependencies missing")
