"""The served vocabulary document must describe the vocabulary we emit.

Every exported triple carries IRIs under the project namespace, and the
namespace is only meaningful if following it lands on a document that says
what the terms mean. A hand-maintained copy of a 249-class vocabulary drifts
the first time a label is added and nothing notices -- which is exactly how
this repo came to have a documented predicate mapping table that no code
implemented. So the document is generated, and these tests hold the
committed copy to the generator.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "generate_vocabulary.py"
COPIES = (
    REPO_ROOT / "docs" / "en" / "ns" / "vocabulary.ttl",
    REPO_ROOT / "docs" / "fr" / "ns" / "vocabulary.ttl",
)


def test_committed_document_is_up_to_date() -> None:
    """``--check`` is the gate; this is what runs it in CI."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--check"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )

    assert result.returncode == 0, (
        f"vocabulary.ttl is stale. Run: python scripts/generate_vocabulary.py\n{result.stderr}"
    )


@pytest.mark.parametrize("path", COPIES, ids=lambda p: p.parent.parent.name)
def test_both_language_trees_carry_the_document(path: Path) -> None:
    """Each language tree is built independently, sharing no static files.

    A single copy leaves whichever page it is missing from linking to a 404.
    """
    assert path.exists(), f"{path.relative_to(REPO_ROOT)} is missing"


def test_the_two_copies_are_identical() -> None:
    """It is RDF; there is nothing to translate."""
    first, second = (path.read_text(encoding="utf-8") for path in COPIES)

    assert first == second


def test_the_namespace_iri_resolves_to_a_real_page() -> None:
    """``vocabulary.py`` claims the IRI dereferences. Hold it to that.

    The namespace is ``.../ddigraph/ns/<version>/`` and the docs site is
    published at ``.../ddigraph/``, so the page has to be
    ``docs/<lang>/ns/<version>.md`` -- mkdocs serves that at the directory
    URL the IRI names. Bumping ``VOCABULARY_VERSION`` without moving the
    page would leave every exported triple pointing at a 404.
    """
    from ddigraph.rdf.vocabulary import DDIGRAPH, VOCABULARY_VERSION

    assert DDIGRAPH == f"https://pbisson44.github.io/ddigraph/ns/{VOCABULARY_VERSION}/"

    for language in ("en", "fr"):
        page = REPO_ROOT / "docs" / language / "ns" / f"{VOCABULARY_VERSION}.md"
        assert page.exists(), (
            f"{page.relative_to(REPO_ROOT)} is missing, so {DDIGRAPH} does not resolve"
        )


def test_document_parses_as_turtle() -> None:
    """A namespace document that does not parse is worse than none."""
    rdflib = pytest.importorskip("rdflib")

    graph = rdflib.Graph().parse(str(COPIES[0]), format="turtle")

    assert len(graph) > 1000


def test_every_emitted_class_is_defined() -> None:
    """Any label the exporter can emit must be findable in the document.

    This is the property that makes the namespace worth publishing: a
    consumer who meets ``ddigraph:SomeLabel`` in exported data can look it
    up and find out what it is.
    """
    rdflib = pytest.importorskip("rdflib")

    from ddigraph.rdf.vocabulary import project_class_iri
    from ddigraph.schema.definitions import DDISchema

    graph = rdflib.Graph().parse(str(COPIES[0]), format="turtle")
    defined = {str(subject) for subject in graph.subjects()}

    missing = sorted(
        project_class_iri(node.label)
        for node in DDISchema.get_all_nodes()
        if project_class_iri(node.label) not in defined
    )

    assert not missing, f"labels the exporter emits but the document omits: {missing[:10]}"


def test_every_emitted_predicate_is_defined() -> None:
    """Same guarantee for relationship predicates minted in our namespace."""
    rdflib = pytest.importorskip("rdflib")

    from ddigraph.rdf.vocabulary import (
        DDIGRAPH,
        _all_relationship_types,
        predicate_iri,
        project_predicate_iri,
    )

    graph = rdflib.Graph().parse(str(COPIES[0]), format="turtle")
    defined = {str(subject) for subject in graph.subjects()}

    emitted = {
        iri
        for rel_type in _all_relationship_types()
        for iri in (predicate_iri(rel_type), project_predicate_iri(rel_type))
        if iri.startswith(DDIGRAPH)
    }

    assert not sorted(emitted - defined)


def test_document_asserts_nothing_about_other_vocabularies() -> None:
    """Statements about DISCO or SKOS terms belong in their documents.

    Publishing ``disco:Question a owl:Class`` from here would be asserting
    facts about someone else's vocabulary, and a consumer merging both
    documents would get our version of their term.
    """
    rdflib = pytest.importorskip("rdflib")

    from ddigraph.rdf.vocabulary import DDIGRAPH

    graph = rdflib.Graph().parse(str(COPIES[0]), format="turtle")

    foreign = sorted(
        str(subject)
        for subject in set(graph.subjects())
        if isinstance(subject, rdflib.URIRef) and not str(subject).startswith(DDIGRAPH)
    )

    assert not foreign, f"document makes claims about foreign terms: {foreign}"


def test_inverted_predicates_are_declared_inverse_not_subproperty() -> None:
    """Direction is the one thing a reasoner cannot recover on its own.

    The graph models a code list container-first; SKOS models it
    member-first. Declaring ``ddigraph:hasCategory`` a subproperty of
    ``skos:inScheme`` would tell a reasoner the scheme is in the concept.
    """
    rdflib = pytest.importorskip("rdflib")

    from ddigraph.rdf.vocabulary import (
        DDIGRAPH,
        _all_relationship_types,
        is_inverted_predicate,
        project_predicate_iri,
    )

    graph = rdflib.Graph().parse(str(COPIES[0]), format="turtle")
    owl = rdflib.Namespace("http://www.w3.org/2002/07/owl#")

    inverted = [rel for rel in _all_relationship_types() if is_inverted_predicate(rel)]
    assert inverted, "guard the guard: the inverted set must not be empty"

    for rel_type in inverted:
        subject = rdflib.URIRef(project_predicate_iri(rel_type))
        assert (subject, owl.inverseOf, None) in graph, f"{rel_type} is not declared inverse"
        assert (subject, rdflib.RDFS.subPropertyOf, None) not in graph, (
            f"{rel_type} is declared a subproperty of the predicate it inverts"
        )

    assert DDIGRAPH  # the namespace the assertions above are scoped to
