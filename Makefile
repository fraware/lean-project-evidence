.PHONY: install test schemas examples check demo lint typecheck coverage inventory

install:
	python -m pip install -e ".[dev]"

test:
	pytest -q

schemas:
	python scripts/export_schemas.py
	python scripts/validate_examples.py

examples:
	python scripts/validate_examples.py

# Spec §19.4 full static gate (may flag pre-existing style debt outside Phase C).
lint:
	ruff format --check .
	ruff check src/lpe scripts

typecheck:
	mypy src/lpe

# Coverage targets (CLOSURE-017 / spec §19.3): overall lines >=90%;
# policy/gate/review/ledger/TPPR/protocol >=95%; branch >=85%.
# Local `make coverage` uses a soft --cov-fail-under=80 line floor for fast feedback.
# CI hard-gates via scripts/check_coverage_gates.py --fail-under=90 --require-critical --require-branch.
coverage:
	pytest -q --cov=lpe --cov-report=term-missing --cov-fail-under=80 -m "not slow and not lean and not docker" tests/unit tests/security

# CLOSURE-032: regenerate REPOSITORY_TREE.txt + MANIFEST.sha256 from git inventory.
inventory:
	python scripts/sync_repository_inventory.py --write

sbom:
	python scripts/generate_sbom.py --skip-image

# Practical merge gate: schema drift + version sync + inventory + tests + bytecode.
# Full ruff/mypy merge-gated via `make lint` / `make typecheck` and CI (`ruff check src/lpe`, `mypy src/lpe`).
# Wheel build+smoke lives in CI (`python -m build` + scripts/verify_wheel.py).
check: schemas
	python scripts/export_schemas.py --check
	python scripts/check_version_sync.py
	python scripts/check_milestone_status.py
	python scripts/sync_repository_inventory.py --check
	python scripts/validate_compatibility_matrix.py
	python scripts/check_doc_links.py
	pytest -q
	python -m compileall -q src

demo:
	bash scripts/demo.sh
