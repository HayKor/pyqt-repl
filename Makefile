.PHONY: install run test lint build clean

install:
	uv sync

run:
	./run.sh $(ARGS)

test:
	QT_QPA_PLATFORM=offscreen uv run pytest -q

lint:
	uv run ruff check

build:
	uv build

clean:
	rm -rf dist .pytest_cache .ruff_cache
	find . -name __pycache__ -prune -exec rm -rf {} +
