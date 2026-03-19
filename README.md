# trackloom

[![Tests](https://github.com/quizwedge/trackloom/actions/workflows/tests.yml/badge.svg)](https://github.com/quizwedge/trackloom/actions/workflows/tests.yml)
[![Lint](https://github.com/quizwedge/trackloom/actions/workflows/lint.yml/badge.svg)](https://github.com/quizwedge/trackloom/actions/workflows/lint.yml)
[![License: GPL-3.0-or-later](https://img.shields.io/badge/License-GPL--3.0--or--later-blue.svg)](LICENSE)

`trackloom` is a safe CLI for comparing two music libraries and merging tracks
from library A into library B without overwriting existing files or deleting
data.

It extracts normalized `artist`, `album`, and `song` fields from file paths and
embedded tags, compares exact and fuzzy matches, builds a copy/add plan, lets
you review ambiguous matches, and applies the plan with dry-run and reporting
support.

## Why use it

- Safe by default: no overwrite, no delete, confirmation required for writes
- Workflow-oriented: `compare`, `plan`, `review`, `apply`
- Handles fuzzy matching and duplicate preference logic
- Supports dry-run, JSON output, reports, and quarantine-based replacement flow
- Works with common music formats via `mutagen`

## Install

From PyPI:

```bash
python3 -m pip install trackloom
```

From a source checkout:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip setuptools wheel
python3 -m pip install -e .
```

After install:

```bash
trackloom help
```

## Quickstart

```bash
trackloom compare /path/to/A /path/to/B --json > /tmp/compare.json
trackloom plan /path/to/A /path/to/B --write-plan-json /tmp/plan.json
trackloom review /path/to/A /path/to/B --decisions-file /tmp/decisions.json \
  --write-plan-json /tmp/reviewed-plan.json
trackloom apply /path/to/A /path/to/B --from-plan-json /tmp/reviewed-plan.json --dry-run
```

For a real run, replace the final command with `--yes` after checking the plan
and dry-run output.

## Commands

- `parse`: catalog parsed fields from one or two directories
- `compare`: find exact and fuzzy matches and recommended actions
- `plan`: build copy/add operations to bring A into B
- `review`: resolve `manual_review` items interactively
- `apply`: execute the plan safely, with dry-run and reports
- `doctor`: run environment and CLI diagnostics

## Safety model

- Existing destination files are never overwritten.
- Delete operations are never performed.
- Replacement cleanup is quarantine-only and only applies to
  `replace_in_b_with_a`.
- Real writes require confirmation by default.
- `apply` continues past per-file I/O failures and reports them.

## Docs

- CLI workflow and command details: `docs/CLI.md`
- Architecture overview: `docs/ARCHITECTURE.md`
- Troubleshooting: `docs/TROUBLESHOOTING.md`
- ADR index: `adr/README.md`
- Release checklist: `RELEASE.md`
- Contribution guide: `CONTRIBUTING.md`

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip setuptools wheel
python3 -m pip install -e .[dev]
python3 -m ruff check .
python3 -m ruff format .
python3 -m pytest -q
```

## License

This project is licensed under the GNU General Public License v3.0 or later
(`GPL-3.0-or-later`). See `LICENSE`.

Built by Dan Getz, Jr.
