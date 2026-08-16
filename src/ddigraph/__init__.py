"""ddigraph - DDI to Knowledge Graph transformation toolkit.

This package transforms DDI (Data Documentation Initiative) XML
metadata into a Neo4j knowledge graph, and reads and writes RDF. Any DDI
flavor can also be streamed as backend-neutral nodes and relationships
through :func:`ddigraph.iter_graph`, which is how you drive a store this
package does not ship an adapter for; ``demo/load_gremlin.py``,
``demo/load_networkx.py`` and ``demo/load_pandas.py`` are worked examples.
The high-level entry points are:

* :func:`ddigraph.load` -- sync load of a DDI file into a Neo4j target.
* :func:`ddigraph.aload` -- async equivalent of ``load``.
* :func:`ddigraph.detect` -- identify the DDI flavor (codebook,
  lifecycle, cdi) of a file without loading.
* :func:`ddigraph.bootstrap` -- create the indexes/constraints DDI
  ingestion needs.
* :func:`ddigraph.export` -- write a DDI file out as RDF, JSON or CSV.
  Needs no database.
* :func:`ddigraph.iter_graph` -- stream any DDI flavor as
  backend-neutral :class:`ddigraph.GraphChunk` values, for building your
  own consumer.
* :func:`ddigraph.preview` -- summarise a DDI file's graph shape as
  text, Mermaid or a self-contained HTML page. Needs no database.

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
  ``abootstrap``, ``export``, ``iter_graph``, ``preview``,
  ``LoadResult``, ``ExportResult``, ``GraphChunk``, ``Settings``,
  ``__version__``.
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
from ddigraph.exporter import ExportResult, export
from ddigraph.graph.view import GraphChunk, iter_graph
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
from ddigraph.previewer import preview
from ddigraph.schema.definitions import DDISchema

try:
    __version__ = version("ddigraph")
except PackageNotFoundError:
    # Running from a source tree that was never installed. Deliberately not
    # a real release number: a hard-coded fallback silently goes stale (it
    # sat at "0.4.0" through three patch releases), and a version that
    # cannot be trusted should look untrustworthy.
    __version__ = "0.0.0.dev0"

# Intentionally split into two tiers (supported / power-user) with a
# blank-line break instead of alphabetised; see the module docstring.
__all__ = [  # noqa: RUF022 (tier ordering is intentional)
    # Supported public API -- the 90 % case, semver-stable across
    # minor releases. See the module docstring for details.
    "ExportResult",
    "GraphChunk",
    "LoadResult",
    "Settings",
    "__version__",
    "abootstrap",
    "aload",
    "bootstrap",
    "detect",
    "export",
    "iter_graph",
    "load",
    "preview",
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
