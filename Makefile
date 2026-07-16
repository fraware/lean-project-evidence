.PHONY: install test schemas examples check demo

install:
	python -m pip install -e ".[dev]"

test:
	pytest -q

schemas:
	python scripts/export_schemas.py
	python scripts/validate_examples.py

examples:
	python scripts/validate_examples.py

check: schemas test
	python -m compileall -q src

demo:
	bash scripts/demo.sh
