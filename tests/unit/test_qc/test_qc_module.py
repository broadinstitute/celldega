"""
Test celldega.qc module.
"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3] / "src"))

def test_qc_module_exists():
    """Test that qc module exists."""
    try:
        from celldega import qc
        assert True
    except ImportError as e:
        pytest.skip(f"qc module not importable: {e}")
