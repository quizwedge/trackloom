.PHONY: all clean dev lint format test help

all: lint format test

clean:
	rm -rf .venv .pytest_cache __pycache__ *.egg-info


dev:
	python3 -m pip install -e .[dev]

lint:
	python3 -m ruff check .

format:
	python3 -m ruff format .

test:
	python3 -m pytest -q

help:
	@echo "Available targets:"
	@echo "  make dev    - install dev dependencies"
	@echo "  make lint   - run Ruff checks"
	@echo "  make format - apply Ruff formatting"
	@echo "  make test   - run pytest"
	@echo "  make all    - lint, format, test"
	@echo "  make clean  - remove local dev artifacts"
