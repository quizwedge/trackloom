.PHONY: all clean dev lint format test

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
