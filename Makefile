# Thin wrapper around tasks.py (the primary, cross-platform interface).
.PHONY: install data test lint fmt

install:
	uv run python tasks.py install

data:
	uv run python tasks.py data

test:
	uv run python tasks.py test

lint:
	uv run python tasks.py lint

fmt:
	uv run python tasks.py fmt
