"""ddigraph - DDI to Knowledge Graph transformation toolkit.

This package transforms DDI (Data Documentation Initiative) XML
metadata into a Neo4j knowledge graph. Streaming parsers also emit
records that can drive other backends through the parser tier --
see ``demo/load_rdf.py``, ``demo/load_gremlin.py``,
``demo/load_networkx.py``, and ``demo/load_pandas.py`` for examples.
The high-level entry points are:

* :func:`ddigraph.load` -- sync load of a DDI file into a Neo4j target.
* :func:`ddigraph.aload` -- async equivalent of ``load``.
* :func:`ddigraph.detect` -- identify the DDI flavor (codebook,
  lifecycle, cdi) of a file without loading.
* :func:`ddigraph.bootstrap` -- create the indexes/constraints DDI
  ingestion needs.

Typical usage::

    import ddigraph

    ddigraph.bootstrap(target="bolt://localhost:7687")
    result = ddigraph.load("survey.xml", target="bolt://localhost:7687")
    print(result.nodes_written, "nodes,", result.relationships_written, "relationships")

When ``target`` is omitted, connection details come from the env-driven
:class:`~ddigraph.config.Settings` model (``DDIGRAPH_NEO4J_URI``,
``DDIGRAPH_NEO4J_USER``, ``DDIGRAPH_NEO4J_PASSWORD``).

The public API surface ships in two tiers:

* **Supported** -- ``load``, ``aload``, ``detect``, ``bootstrap``,
  ``abootstrap``, ``LoadResult``, ``Settings``, ``__version__``.
  These names follow semantic versioning across minor releases.
* **Power-user** -- ``DDILoader``, ``DDIFragmentLoader``,
  ``DDIFragmentParser``, ``DDIBatch``, ``CDIBatch``,
  ``CDIBatchStream``, ``DDISchema``, ``Fragment``,
  ``FragmentReference``, ``FlavorName``, ``detect_ddi_format``,
  ``is_cdi_format``, ``parse_ddi_batches``, ``parse_cdi_batches``.
  Importable from ``ddigraph`` for fine-grained control, but they
  carry no stability guarantee across minor releases. Pin a version
  if you depend on them.
"""

from importlib.metadata import PackageNotFoundError, version

from ddigraph.api import (
    FlavorName,
    LoadResult,
    abootstrap,
    aload,
    bootstrap,
    detect,
    load,
)
from ddigraph.config import Settings
from ddigraph.ingest.cdi_loader import (
    CDIBatch,
    CDIBatchStream,
    is_cdi_format,
    parse_cdi_batches,
)
from ddigraph.ingest.fragment_loader import (
    DDIFragmentLoader,
    DDIFragmentParser,
    Fragment,
    FragmentReference,
    detect_ddi_format,
)
from ddigraph.ingest.loader import DDIBatch, DDILoader, parse_ddi_batches
from ddigraph.schema.definitions import DDISchema

try:
    __version__ = version("ddigraph")
except PackageNotFoundError:
    # Package not installed (development mode)
    __version__ = "0.4.0"

# Intentionally split into two tiers (supported / power-user) with a
# blank-line break instead of alphabetised; see the module docstring.
__all__ = [  # noqa: RUF022 (tier ordering is intentional)
    # Supported public API -- the 90 % case, semver-stable across
    # minor releases. See the module docstring for details.
    "LoadResult",
    "Settings",
    "__version__",
    "abootstrap",
    "aload",
    "bootstrap",
    "detect",
    "load",
    # Power-user surface -- the parser tier, batch types, and the
    # shared schema container. Importable from ``ddigraph`` but carries
    # no stability guarantee across minor releases.
    "CDIBatch",
    "CDIBatchStream",
    "DDIBatch",
    "DDIFragmentLoader",
    "DDIFragmentParser",
    "DDILoader",
    "DDISchema",
    "FlavorName",
    "Fragment",
    "FragmentReference",
    "detect_ddi_format",
    "is_cdi_format",
    "parse_cdi_batches",
    "parse_ddi_batches",
]
