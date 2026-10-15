"""Contracts from the fifth adversarial round: exit codes when the readers are gone."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
EVENT = str(REPO / "tests" / "fixtures" / "labview2026" / "Example Event File.tdm")


def _closed(args: list[str], close_stderr: bool) -> int:
    env = dict(os.environ)
    if (REPO / "src").is_dir():
        env["PYTHONPATH"] = str(REPO / "src")
    process = subprocess.Popen(
        [sys.executable, "-m", "tdmread", *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    assert process.stdout is not None and process.stderr is not None
    process.stdout.close()
    if close_stderr:
        process.stderr.close()
        return process.wait(timeout=60)
    err = process.stderr.read()
    process.stderr.close()
    code = process.wait(timeout=60)
    assert b"Errno" not in err and b"Exception ignored" not in err
    return code


@pytest.mark.parametrize("close_stderr", [False, True])
@pytest.mark.parametrize(
    ("args", "expected"),
    [
        (["--version"], 0),
        (["--help"], 0),
        ([], 0),
        (["dump", EVENT], 2),
        (["info", "missing.tdm"], 1),
        (["dump", EVENT, "-g", "nope", "-c", "x"], 1),
    ],
)
def test_exit_codes_hold_when_the_readers_are_gone(
    args: list[str], expected: int, close_stderr: bool
) -> None:
    assert _closed(args, close_stderr) == expected


@pytest.mark.parametrize(
    ("args", "expected"), [(["--version"], 0), (["info", EVENT], 1), (["bogus"], 2)]
)
def test_exit_codes_hold_with_both_descriptors_closed_inside_the_process(
    args: list[str], expected: int
) -> None:
    env = dict(os.environ)
    if (REPO / "src").is_dir():
        env["PYTHONPATH"] = str(REPO / "src")
    code = (
        "import os, runpy, sys; os.close(1); os.close(2); "
        f"sys.argv = ['tdmread', *{args!r}]; runpy.run_module('tdmread', run_name='__main__')"
    )
    done = subprocess.run([sys.executable, "-c", code], env=env, timeout=60)
    assert done.returncode == expected
