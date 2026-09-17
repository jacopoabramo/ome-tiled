---
allowed-tools: Bash(uv:*)
description: Run the full local validation suite
---

`uv run tox` runs every environment: `lint`, `mypy`, `tests`. Run that, then
report a one-line result per environment.

On failure, show the failing output, fix it, and re-run only that environment
with `uv run tox -e <name>`.

`uv run mypy` against the project `.venv` is not a substitute: the `.venv`
holds every group any `uv sync` has installed, while each `tox` environment
installs exactly what `uv.lock` resolves, which is what CI runs.
