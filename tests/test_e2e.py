"""Real end-to-end test: install the package and drive its console script.

This builds a throwaway virtual environment, performs an editable install of the
project into it, and runs the genuine ``tdmread`` console entry point as a subprocess
against the committed synthetic files. Nothing is mocked: it exercises the exact binary a
user gets from ``pip install tdmread`` and cross-checks the dumped numbers against the
sine identity the synthetic files were generated from.
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
FIXTURES = REPO / "tests" / "fixtures" / "synthetic"
SINE = str(FIXTURES / "Synthetic.tdm")


@pytest.fixture(scope="session")
def console_script(tmp_path_factory: pytest.TempPathFactory) -> Path:
    venv_dir = tmp_path_factory.mktemp("tdmread-e2e")
    subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
    bin_dir = venv_dir / ("Scripts" if os.name == "nt" else "bin")
    python = bin_dir / ("python.exe" if os.name == "nt" else "python")
    subprocess.run(
        [str(python), "-m", "pip", "install", "--disable-pip-version-check", "-e", str(REPO)],
        check=True,
        capture_output=True,
        text=True,
        timeout=600,
    )
    script = bin_dir / ("tdmread.exe" if os.name == "nt" else "tdmread")
    assert script.is_file(), f"console script was not installed at {script}"
    return script


def _run(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(script), *args], capture_output=True, text=True, timeout=120)


def test_installed_script_reports_version(console_script: Path) -> None:
    result = _run(console_script, "--version")
    assert result.returncode == 0
    assert result.stdout.strip() == "tdmread 0.2.1"


def test_installed_script_lists_channels(console_script: Path) -> None:
    result = _run(console_script, "channels", SINE)
    assert result.returncode == 0
    lines = result.stdout.strip().splitlines()
    assert len(lines) == 10
    assert lines[0].startswith("Amplitudes\tA = 1")


def test_installed_script_dump_matches_sine_oracle(console_script: Path) -> None:
    result = _run(console_script, "dump", SINE, "-g", "Amplitudes", "-c", "A = 1", "-f", "json")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["length"] == 100
    data = payload["data"]
    # Independent oracle: the synthetic A = 1 is sin(0.05 * index).
    for index in (0, 1, 25, 50, 99):
        assert abs(data[index] - math.sin(0.05 * index)) < 1e-9


def test_installed_script_errors_to_stderr(console_script: Path) -> None:
    result = _run(console_script, "info", str(FIXTURES / "does-not-exist.tdm"))
    assert result.returncode == 1
    assert "error" in result.stderr.lower()
    assert result.stdout == ""
