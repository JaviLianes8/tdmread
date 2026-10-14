# tdmread 1.0.0 certification report

Progress:
- [x] Branch `release/1.0.0` created from `main` (0.2.1, a646185)
- [x] Baseline gates run on 0.2.1
- [x] Real LabVIEW 2026 output and NI reader captures (item 7)
- [ ] API review and 1.0.0 API changes (item 1)
- [ ] Errors, typing, docstrings and doctests (items 2 to 5)
- [ ] Contract, fuzz and author mutation round (items 6, 9, 18)
- [ ] Docs: README, GUIDE, CHANGELOG (items 11, 12)
- [ ] Packaging, e2e and upgrade from PyPI 0.2.1 (items 8, 10, 13, 14)
- [ ] Independent reviewer and five QA lenses report PASS (items 16, 19)
- [ ] Gates (item 15)
- [ ] PR and trace guard CLEAN (item 17); merge and publish left to the maintainer

## Baseline on 0.2.1 (before any change)

| Command | Result |
| --- | --- |
| `ruff format --check .`, `ruff check .`, `mypy --strict src tests` | exit 0 |
| `pytest` | 43 passed (the fetched upstream samples present) |
| `pytest --doctest-modules src` | no doctests at all |
