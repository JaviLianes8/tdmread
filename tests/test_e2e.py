"""Real end to end: build the wheel, install it into a fresh virtual environment, use it.

The wheel is built from this checkout (or taken from ``TDMREAD_WHEEL`` when set, which is
how the suite runs against a wheel built elsewhere). Nothing is mocked: the installed
console script and ``python -m tdmread`` run as subprocesses, and an outside script
imports the installed package.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tdmread import __version__

REPO = Path(__file__).resolve().parent.parent
FIXTURES = REPO / "tests" / "fixtures"
EVENT = str(FIXTURES / "labview2026" / "Example Event File.tdm")
TYPES = str(FIXTURES / "labview2026" / "gt_types_0.tdm")


def _wheel(folder: Path) -> Path:
    given = os.environ.get("TDMREAD_WHEEL")
    if given:
        return Path(given)
    if not (REPO / "src" / "tdmread").is_dir():
        pytest.skip("no source tree and no TDMREAD_WHEEL to install")
    subprocess.run(
        [sys.executable, "-m", "pip", "wheel", "--no-deps", "-q", "-w", str(folder), str(REPO)],
        check=True,
        timeout=600,
    )
    return next(folder.glob("tdmread-*.whl"))


@pytest.fixture(scope="session")
def venv(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("tdmread-e2e")
    wheel = _wheel(root / "dist")
    subprocess.run([sys.executable, "-m", "venv", str(root / "venv")], check=True, timeout=300)
    bin_dir = root / "venv" / ("Scripts" if os.name == "nt" else "bin")
    python = bin_dir / ("python.exe" if os.name == "nt" else "python")
    subprocess.run(
        [str(python), "-m", "pip", "install", "-q", "--no-deps", "--no-index", str(wheel)],
        check=True,
        timeout=600,
    )
    return bin_dir


def _run(command: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    env.pop("PYTHONPATH", None)
    return subprocess.run(
        command, capture_output=True, text=True, encoding="utf-8", timeout=120, env=env, cwd=cwd
    )


def _script(venv: Path) -> str:
    return str(venv / ("tdmread.exe" if os.name == "nt" else "tdmread"))


def _python(venv: Path) -> str:
    return str(venv / ("python.exe" if os.name == "nt" else "python"))


def test_installed_script_reports_the_version(venv: Path) -> None:
    result = _run([_script(venv), "--version"])
    assert (result.returncode, result.stdout.strip()) == (0, f"tdmread {__version__}")


def test_installed_script_lists_and_dumps_a_labview_file(venv: Path) -> None:
    listing = _run([_script(venv), "channels", EVENT])
    assert listing.returncode == 0 and "Untitled\tEvent Type\texplicit\t8" in listing.stdout
    dump = _run([_script(venv), "dump", TYPES, "-g", "Ints", "-c", "u8", "-f", "json"])
    assert dump.returncode == 0, dump.stderr
    assert json.loads(dump.stdout)["data"] == [0, 1, 255, 128, 42]


def test_python_dash_m_matches_the_script(venv: Path) -> None:
    by_module = _run([_python(venv), "-m", "tdmread", "channels", EVENT])
    assert by_module.stdout == _run([_script(venv), "channels", EVENT]).stdout


def test_installed_script_errors_to_stderr(venv: Path) -> None:
    result = _run([_script(venv), "info", str(FIXTURES / "does-not-exist.tdm")])
    assert (result.returncode, result.stdout) == (1, "")
    assert result.stderr.startswith("tdmread: error: ")


def test_an_outside_program_uses_the_installed_package(venv: Path, tmp_path: Path) -> None:
    program = tmp_path / "consumer.py"
    program.write_text(
        "import sys, tdmread\n"
        "d = tdmread.read_tdm(sys.argv[1])\n"
        "c = d.group('Time').channel('stamps')\n"
        "print(tdmread.__version__, tdmread.__file__)\n"
        "print(c.times()[0].isoformat(), sum(d.group('Wave').channel('ramp').numbers()))\n",
        encoding="utf-8",
    )
    result = _run([_python(venv), str(program), TYPES], cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    version_line, values = result.stdout.splitlines()
    assert version_line.startswith(__version__) and "site-packages" in version_line
    assert values == "2026-10-14T17:34:39.500000 499500"


def test_the_wheel_ships_type_information(venv: Path) -> None:
    probe = (
        "import importlib.resources as r; print(r.files('tdmread').joinpath('py.typed').is_file())"
    )
