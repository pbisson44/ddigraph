"""DDI-CDI 1.0 ``NodeDefinition`` data.

The literal table was lifted into
``ddigraph.schema._overrides.schema_overrides.toml`` so future schema
edits happen there (not in this Python file). The TOML is the single
source of truth and is round-trip verified against
``tests/fixtures/cdi_nodes_snapshot.json``.

Validation of the curated label list against the XSD-derived entity
set in ``ddigraph.schema._generated.cdi`` lives in
``tests/test_cdi_generator.py``.
"""

from __future__ import annotations

from ddigraph.schema._overrides._loader import cdi_nodes
from ddigraph.schema.definitions._dataclasses import NodeDefinition

CDI_NODES: tuple[NodeDefinition, ...] = cdi_nodes()


__all__ = ["CDI_NODES"]
