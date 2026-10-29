"""Runs the JavaScript port against the same golden fixtures and fails if either port disagrees. Skipped only when node is missing (CI must have it)."""
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_js_port_matches_golden_fixtures():
    out = subprocess.run(["node", "--test", str(ROOT / "tests" / "golden.test.js")], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stdout[-3000:] + out.stderr[-1500:]
