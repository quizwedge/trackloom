.PHONY: dev lint format test

dev:
	python3 -m pip install -e .[dev]

lint:
	python3 -m ruff check .

format:
	python3 -m ruff format .

test:
	python3 -m pytest -q
