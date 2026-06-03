"""Generated schema definitions derived from the bundled DDI XSDs.

This package holds the output of ``scripts/generate_schema_definitions.py``.
Modules under this directory are **regenerated** from the XSD files in
``schemas/``; do not edit them by hand. Edit
``src/ddigraph/schema/_overrides/schema_overrides.toml`` to adjust the
generator's output.

The generator and these artefacts are part of an in-progress migration to
make XSDs the single source of truth for ``NodeDefinition`` and
``RelationshipDefinition`` data. While the migration is in flight the
runtime continues to import from
``ddigraph.schema.definitions``; once the snapshot test in
``tests/test_generated_schema.py`` is green for every flavor, the
literals there will be replaced by re-exports from this package.

This module is private. Importers outside ``ddigraph.schema`` should not
depend on the names defined here.
"""

__all__: list[str] = []
