# Contributing to Trackloom

Thanks for contributing.

## Development setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip setuptools wheel
python3 -m pip install -e .[dev]
```

## Run tests

```bash
python3 -m pytest -q
```

## Lint and format

```bash
python3 -m ruff check .
python3 -m ruff format .
```

## Makefile shortcuts

```bash
make dev
make lock
make lint
make format
make test
make all
make clean
make help
```

## Optional pre-commit hooks

```bash
pre-commit install
```

## Dependency lockfile

`requirements.txt` is the pinned runtime lockfile generated from
`pyproject.toml`.

Regenerate it with:

```bash
make lock
```

## Local CLI smoke checks

```bash
trackloom help
trackloom parse /path/to/library_a
trackloom compare /path/to/library_a /path/to/library_b --json
```

## Pull request expectations

- Keep PRs focused and small when possible.
- Include tests for behavior changes.
- Update `README.md` if flags, outputs, or workflow behavior changes.
- Changes under `tests/fixtures/contracts/` are treated as contract changes and
  must be reviewed alongside matching docs, ADR, and contract-test updates.
- Preserve safety guarantees (`no overwrite`, `no delete`) unless explicitly changed.
- Keep licensing headers in Python files:
  - `SPDX-License-Identifier: GPL-3.0-or-later`
  - `Built by Dan Getz, Jr.`

## Reporting issues

Use the issue templates and include exact commands, flags, and relevant output.
