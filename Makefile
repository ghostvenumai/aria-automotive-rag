.PHONY: install install-ai run test lint

install:
	pip install -e ".[dev]"

install-ai:
	pip install -e ".[dev,ai]"

run:
	uvicorn app.main:app --reload

test:
	pytest

lint:
	python -m py_compile $(shell find app tests -name '*.py' -print)
