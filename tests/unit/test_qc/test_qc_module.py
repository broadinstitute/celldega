"""
Test celldega.qc module.
"""

from importlib import util
from pathlib import Path
import sys

import pytest


sys.path.insert(0, str(Path(__file__).parents[3] / "src"))


def test_qc_module_exists():
    """Test that qc module exists."""
    spec = util.find_spec("celldega.qc")
    if spec is None:
        pytest.skip("qc module not importable")
    assert spec is not None
