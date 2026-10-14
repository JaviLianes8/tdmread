"""Every documented example runs and prints what it shows; links are absolute."""

from __future__ import annotations

import doctest
import importlib
import inspect
import pkgutil
import re
from pathlib import Path

import pytest

import tdmread

REPO = Path(__file__).resolve().parent.parent
MODULES = sorted(
    f"tdmread.{info.name}"
    for info in pkgutil.iter_modules(tdmread.__path__)
    if info.name != "__main__"
)


@pytest.mark.parametrize("name", MODULES)
def test_module_doctests_pass(name: str) -> None:
    module = importlib.import_module(name)
    result = doctest.testmod(module, optionflags=doctest.ELLIPSIS)
    assert result.failed == 0


def _members(obj: object) -> list[tuple[str, object]]:
    if not inspect.isclass(obj):
        return [("", obj)]
    found: list[tuple[str, object]] = [("", obj)]
    for attr, value in vars(obj).items():
        if attr.startswith("_") and attr not in ("__len__", "__iter__"):
            continue
        target = value.fget if isinstance(value, property) else value
        if callable(target) or isinstance(value, property):
            found.append((attr, target))
    return found


@pytest.mark.parametrize("name", tdmread.__all__)
def test_every_public_name_and_method_has_a_runnable_example(name: str) -> None:
    for attr, member in _members(getattr(tdmread, name)):
        doc = inspect.getdoc(member) or ""
        assert ">>>" in doc, f"{name}.{attr} has no example"


def test_public_doctests_pass_when_run_from_the_package() -> None:
    finder = doctest.DocTestFinder()
    runner = doctest.DocTestRunner(optionflags=doctest.ELLIPSIS)
    for name in tdmread.__all__:
        for test in finder.find(getattr(tdmread, name), name, globs={}):
            runner.run(test)
    assert runner.failures == 0 and runner.tries > 20


@pytest.mark.parametrize("document", ["README.md", "GUIDE.md"])
def test_document_examples_run_and_print_what_they_show(document: str) -> None:
    text = (REPO / document).read_text(encoding="utf-8")
    blocks = re.findall(r"```pycon\n(.*?)```", text, re.S)
    if document == "GUIDE.md":
        assert len(blocks) >= 2
    for block in blocks:
        test = doctest.DocTestParser().get_doctest(block, {}, document, document, 0)
        runner = doctest.DocTestRunner()
        runner.run(test)
        assert runner.failures == 0


def test_readme_python_example_compiles_and_uses_only_public_names() -> None:
    text = (REPO / "README.md").read_text(encoding="utf-8")
    for block in re.findall(r"```python\n(.*?)```", text, re.S):
        compile(block, "README.md", "exec")
        for imported in re.findall(r"from tdmread import (.+)", block):
            assert {n.strip() for n in imported.split(",")} <= set(tdmread.__all__)


def test_readme_links_are_absolute() -> None:
    text = (REPO / "README.md").read_text(encoding="utf-8")
    for target in re.findall(r"\]\(([^)]+)\)", text):
        assert target.startswith("https://"), target


def test_no_em_dash_anywhere_in_the_project() -> None:
    dash = chr(0x2014)
    for path in [*REPO.glob("*.md"), *REPO.glob("src/**/*.py"), *REPO.glob("tests/*.py")]:
        assert dash not in path.read_text(encoding="utf-8"), path
    for path in REPO.glob("scripts/*.p*"):
        assert dash not in path.read_text(encoding="utf-8"), path
