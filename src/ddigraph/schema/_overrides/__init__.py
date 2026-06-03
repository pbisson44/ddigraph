"""Schema overrides applied on top of XSD-derived data.

This package holds the bridge between the XSD-derived metadata under
``ddigraph.schema._generated`` and the runtime ``NodeDefinition`` /
``RelationshipDefinition`` tuples exported from
``ddigraph.schema.definitions``. Items declared in
``schema_overrides.toml`` are merged with the generated data to produce
the final runtime tables.

This module is private: nothing outside ``ddigraph.schema`` should
import from here.
"""

__all__: list[str] = []
