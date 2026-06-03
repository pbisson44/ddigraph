"""DDI ingestion loaders for Codebook, Lifecycle, and CDI formats."""

from ddigraph.ingest.cdi_loader import (
    CDIBatch,
    CDIBatchStream,
    is_cdi_format,
    parse_cdi_batches,
)
from ddigraph.ingest.fragment_loader import (
    AsyncFragmentGraphWriter,
    DDIFragmentLoader,
    DDIFragmentParser,
    Fragment,
    FragmentBatch,
    FragmentReference,
    detect_ddi_format,
)

__all__ = [
    "AsyncFragmentGraphWriter",
    "CDIBatch",
    "CDIBatchStream",
    "DDIFragmentLoader",
    "DDIFragmentParser",
    "Fragment",
    "FragmentBatch",
    "FragmentReference",
    "detect_ddi_format",
    "is_cdi_format",
    "parse_cdi_batches",
]
