.PHONY: setup dev preview build test ingest index evaluate

setup:
	uv sync --extra cognee
	npm --prefix frontend ci

dev:
	uv run --extra cognee python -m scripts.dev

preview: build
	uv run --extra cognee uvicorn backend.app:app --host 127.0.0.1 --port 8000

build:
	npm --prefix frontend run build

test:
	uv run --extra cognee pytest
	npm --prefix frontend run typecheck

ingest:
	uv run --extra cognee python -m scripts.ingest

index:
	uv run --extra cognee python -m scripts.index_cognee

evaluate:
	uv run --extra cognee python -m scripts.evaluate
