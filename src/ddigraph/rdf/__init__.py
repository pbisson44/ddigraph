"""RDF tier for ddigraph: vocabulary, export, validation, and parsing.

Everything in this package that touches ``rdflib`` imports it *inside*
functions. ``ddigraph.rdf.vocabulary`` deliberately imports nothing from
``rdflib`` at all -- it is pure string data, so the mapping tables stay
importable, testable, and documentable with only a base install.
"""

from ddigraph.rdf.reader import read_graph
from ddigraph.rdf.vocabulary import (
    DDIGRAPH,
    PREFIXES,
    VOCABULARY_VERSION,
    class_iris,
    predicate_iri,
    property_iri,
    subject_iri,
)

__all__ = [
    "DDIGRAPH",
    "PREFIXES",
    "VOCABULARY_VERSION",
    "class_iris",
    "predicate_iri",
    "property_iri",
    "read_graph",
    "subject_iri",
]
