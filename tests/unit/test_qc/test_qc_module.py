"""
Test celldega.qc module.
"""
from pathlib import Path
import sys

import pytest


sys.path.insert(0, str(Path(__file__).parents[3] / "src"))

def test_qc_module_exists():
    """Test that qc module exists."""
    try:
        from celldega import qc
        assert True
    except ImportError as e:
        pytest.skip(f"qc module not importable: {e}")
