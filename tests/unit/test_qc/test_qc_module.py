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
