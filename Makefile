.PHONY: format format-check lint typecheck deadcode test test-fast coverage check

format:
	ruff format conlang tests

format-check:
	ruff format --check conlang tests

lint:
	ruff check .

typecheck:
	mypy conlang

deadcode:
	vulture conlang --min-confidence 80

test:
	python -m pytest

test-fast:
	python -m pytest -n auto

coverage:
	python -m pytest --cov=conlang --cov-report=term-missing

check: format-check lint typecheck deadcode test
