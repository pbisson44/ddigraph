.PHONY: lint format typecheck test update-schemas check-schemas schemas check-schema-definitions vocabulary check-vocabulary docs docs-serve lint-md fix-md check-readability mutation mutation-results clean

# Code quality
lint:
	ruff check .

format:
	ruff format .

typecheck:
	mypy .

test:
	pytest

# Markdown linting (markdownlint-cli2 via npx)
lint-md:
	npx --yes markdownlint-cli2@0.18.1 "**/*.md" "!**/site-packages/**" "!**/.venv/**"

fix-md:
	npx --yes markdownlint-cli2@0.18.1 --fix "**/*.md" "!**/site-packages/**" "!**/.venv/**"

# Advisory Flesch-Kincaid grade-level audit of the English docs tree.
# Requires the ``docs`` extra (textstat). Prints a per-page grade and
# exits 0; pass --threshold N --fail-on-error to enforce a ceiling.
check-readability:
	python scripts/check_readability.py docs/en

# Schema management
update-schemas:
	python scripts/update_schemas.py

check-schemas:
	python scripts/update_schemas.py --check

# XSD-derived schema definitions (under src/ddigraph/schema/_generated/)
schemas:
	python scripts/generate_schema_definitions.py

check-schema-definitions:
	python scripts/generate_schema_definitions.py --check

# The served RDF vocabulary (docs/{en,fr}/ns/vocabulary.ttl), generated
# from the same schema tables so it cannot describe terms we do not emit.
vocabulary:
	python scripts/generate_vocabulary.py

check-vocabulary:
	python scripts/generate_vocabulary.py --check

# Mutation testing (scoped -- see [tool.mutmut] in pyproject.toml).
# Requires the dev extra. Takes a few minutes; not a CI gate.
mutation:
	.venv/bin/mutmut run --max-children 4

mutation-results:
	.venv/bin/mutmut results

# Documentation
docs:
	mkdocs build

docs-serve:
	mkdocs serve

# Demo
demo-load:
	cd demo && python load_ddi.py

demo-audit:
	cd demo && python audit_graph.py

# Cleanup
clean:
	rm -rf dist/ build/ *.egg-info/ .pytest_cache/ .mypy_cache/ .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# All checks (for CI)
check: lint typecheck test check-schemas
