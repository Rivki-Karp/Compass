# Thin wrapper around tasks.py (the primary, cross-platform interface).
.PHONY: install data test lint fmt

install:
	uv run --project backend python tasks.py install

data:
	uv run --project backend python tasks.py data

test:
	uv run --project backend python tasks.py test

lint:
	uv run --project backend python tasks.py lint

fmt:
	uv run --project backend python tasks.py fmt
