"""Tests for the ddigraph RDF vocabulary.

The vocabulary is the part of this release consumers will actually key
their queries on, so these tests care less about individual mappings than
about the properties that make the vocabulary usable at all: that it is
total, that it is unambiguous, and that nothing leaks a Neo4j
relationship name or a Python attribute name into predicate space.

``ddigraph.rdf.vocabulary`` imports no ``rdflib``, so all of this runs on
a base install.
"""

from __future__ import annotations

import pytest

from ddigraph.rdf import vocabulary as v
from ddigraph.schema.definitions import DDISchema

ALL_LABELS = sorted({node.label for node in DDISchema.get_all_nodes()})
ALL_REL_TYPES = sorted(set(DDISchema.FRAGMENT_RELATIONSHIP_TYPES.values()))


def test_namespace_is_versioned_independently_of_the_package() -> None:
    """The namespace must not move when the package version moves.

    Consumers key queries on these IRIs. A namespace carrying the release
    version would invalidate every one of them on each minor bump, which is
    the interoperability failure this vocabulary exists to end.
    """
    import ddigraph

    assert v.VOCABULARY_VERSION not in ddigraph.__version__ or ddigraph.__version__.startswith(
        "0.0.0"
    )
    assert v.DDIGRAPH.endswith(f"/ns/{v.VOCABULARY_VERSION}/")


def test_namespace_is_owned_by_this_project() -> None:
    """No squatting on ddialliance.org or example.org, as the demos did."""
    assert v.DDIGRAPH.startswith("https://pbisson44.github.io/ddigraph/")


@pytest.mark.parametrize("label", ALL_LABELS)
def test_every_schema_label_gets_exactly_one_project_class(label: str) -> None:
    """The mapping is total: no label falls through without a class IRI."""
    iris = v.class_iris(label)

    assert iris[-1] == v.DDIGRAPH + label
    assert len(iris) == len(set(iris))
    assert all(iri.startswith(("http://", "https://")) for iri in iris)


@pytest.mark.parametrize("label", ALL_LABELS)
def test_project_class_is_always_present(label: str) -> None:
    """Round-tripping must never depend on the alignment table.

    The standard alignment is many-to-one, so the project-namespace type is
    the only thing that can identify the original label. It is emitted for
    every node, aligned or not.
    """
    assert v.project_class_iri(label) in v.class_iris(label)


def test_aligned_labels_emit_both_types() -> None:
    """Standard class first for interop, project class last for identity."""
    assert v.class_iris("QuestionItem") == (v.DISCO + "Question", v.DDIGRAPH + "QuestionItem")
    assert v.class_iris("Category") == (v.SKOS + "Concept", v.DDIGRAPH + "Category")


def test_many_to_one_alignment_stays_distinguishable() -> None:
    """The reason the reader can round-trip a collapsed alignment.

    ``Question`` and ``QuestionItem`` share ``disco:Question``; ``CodeList``
    and ``CodeScheme`` share ``skos:ConceptScheme``. The project type is what
    keeps them apart.
    """
    for a, b in [("Question", "QuestionItem"), ("CodeList", "CodeScheme")]:
        assert v.standard_class_iri(a) == v.standard_class_iri(b)
        assert v.project_class_iri(a) != v.project_class_iri(b)


def test_standard_classes_only_use_published_namespaces() -> None:
    """A wrong alignment is worse than none, so pin the namespaces."""
    published = (v.DISCO, v.SKOS, v.XKOS, v.FOAF, v.PROV, v.DCTERMS)

    for label in ALL_LABELS:
        standard = v.standard_class_iri(label)
        if standard is not None:
            assert standard.startswith(published), f"{label} -> {standard}"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("USES_CODELIST", "usesCodelist"),
        ("HAS_CONSTRUCT", "hasConstruct"),
        ("IN_DATASET", "inDataset"),
        ("question_text", "questionText"),
        ("name", "name"),
        ("GROUPS", "groups"),
        ("PascalCase", "pascalCase"),
        ("", ""),
        # Separator-only input: the guard that stops an IndexError on the
        # empty head. Found by mutation testing, which changed the empty
        # return value and survived every other case.
        ("_", ""),
        ("__", ""),
        ("_leading", "leading"),
        ("trailing_", "trailing"),
    ],
)
def test_lower_camel_conversion(raw: str, expected: str) -> None:
    """The convention the docs always claimed and no code implemented."""
    assert v.to_lower_camel(raw) == expected


@pytest.mark.parametrize("rel_type", ALL_REL_TYPES)
def test_no_predicate_leaks_a_neo4j_relationship_name(rel_type: str) -> None:
    """No SCREAMING_SNAKE in predicate space.

    ``demo/load_rdf.py`` emitted ``ddi:USES_CODELIST`` verbatim while the
    documentation promised ``ddi:usesCodeList``. Whichever term wins, the
    local part must never be the raw Neo4j name.
    """
    iri = v.predicate_iri(rel_type)
    local = iri.rsplit("#", 1)[-1].rsplit("/", 1)[-1]

    assert "_" not in local
    assert not local.isupper()
    assert local[0].islower()


def test_single_word_lifecycle_types_recover_word_boundaries() -> None:
    """Uncurated ``*Reference`` tags flatten; the source tag still has them.

    ``AgencyOrganizationReference`` defaults to ``AGENCYORGANIZATION``, which
    camel-cases to an unreadable ``agencyorganization``. The tag is used
    instead, giving ``agencyOrganization``.
    """
    assert v.predicate_iri("AGENCYORGANIZATION") == v.DDIGRAPH + "agencyOrganization"
    assert v.predicate_iri("CODELISTGROUP") == v.DDIGRAPH + "codeListGroup"


def test_curated_predicates_win_over_the_mechanical_rule() -> None:
    """Where a published term exists it is used instead of a minted one."""
    assert v.predicate_iri("USES_CONCEPT") == v.DISCO + "concept"
    assert v.predicate_iri("IN_DATASET") == v.DCTERMS + "isPartOf"
    assert v.predicate_iri("HAS_CATEGORY") == v.SKOS + "inScheme"


def test_container_member_edges_are_inverted_for_skos() -> None:
    """SKOS models scheme membership from the member's side.

    The graph points ``CodeList -HAS_CATEGORY-> Category`` because that is
    how the XML nests. In SKOS the concept carries ``skos:inScheme``, and
    ``skos:member`` belongs to ``skos:Collection``, not
    ``skos:ConceptScheme`` -- emitting the graph direction verbatim would
    produce SKOS that tooling rejects.
    """
    for rel_type in ("HAS_CATEGORY", "HAS_CODE", "HAS_CONCEPT"):
        assert v.is_inverted_predicate(rel_type)
        assert v.predicate_iri(rel_type) == v.SKOS + "inScheme"

    # An edge already pointing member -> container needs no swap.
    assert not v.is_inverted_predicate("IN_SCHEME")
    assert v.predicate_iri("IN_SCHEME") == v.SKOS + "inScheme"


def test_uncertain_alignments_are_left_unmapped() -> None:
    """A wrong alignment is worse than none, because consumers act on it.

    ``GROUPS`` and ``USES_CATEGORY`` have no unambiguous SKOS equivalent --
    neither endpoint is reliably a concept scheme -- so they mint a project
    term rather than guess at ``skos:member``.
    """
    assert v.predicate_iri("GROUPS") == v.DDIGRAPH + "groups"
    assert v.predicate_iri("USES_CATEGORY") == v.DDIGRAPH + "usesCategory"


def test_skos_subjects_get_skos_labelling_predicates() -> None:
    """Mixing rdfs:label into a concept scheme upsets SKOS tooling."""
    assert v.property_iri("label", skos_typed=True) == v.SKOS + "prefLabel"
    assert v.property_iri("label", skos_typed=False) == v.RDFS + "label"
    assert v.property_iri("description", skos_typed=True) == v.SKOS + "definition"
    assert v.property_iri("description") == v.DCTERMS + "description"


def test_is_skos_typed_matches_the_class_alignment() -> None:
    """The flag the writer branches on must follow the class table."""
    assert v.is_skos_typed("Category")
    assert v.is_skos_typed("CodeList")
    assert not v.is_skos_typed("Variable")


def test_property_predicates_never_leak_snake_case() -> None:
    """``ddi:question_text`` was the third convention in play. Not any more."""
    for field in ("question_text", "response_type", "dataset_id", "reusable_urn"):
        local = v.property_iri(field).rsplit("#", 1)[-1].rsplit("/", 1)[-1]
        assert "_" not in local


def test_external_references_map_to_the_interop_hook() -> None:
    """This is what joins a code list to EuroVoc or DBpedia."""
    assert v.property_iri("external_references") == v.SKOS + "exactMatch"


def test_subject_iri_prefers_the_ddi_urn() -> None:
    """A DDI URN is already globally unique; reuse beats reinvention."""
    urn = "urn:ddi:ie.cso:q-4711:1.0.0"

    assert v.subject_iri("QuestionItem", "anything", urn=urn) == urn


def test_subject_iri_preserves_urn_structure() -> None:
    """``demo/load_rdf.py`` flattened colons out, destroying the URN."""
    urn = "urn:ddi:ie.cso:q-4711:1.0.0"
    minted = v.subject_iri("QuestionItem", "q-4711", urn=urn)

    assert minted.count(":") == urn.count(":")
    assert "_" not in minted.removeprefix("urn:ddi:")


def test_subject_iri_uses_an_identity_that_is_already_a_urn() -> None:
    """Endpoint stubs carry a label and an identity, and no properties.

    ``make_node_key`` returns the DDI URN verbatim when the fragment has
    one, so DDI-L identity values are already URNs. Deriving the IRI from
    identity alone is what keeps a relationship endpoint on the same IRI as
    the full node it points at -- minting from ``properties["urn"]`` would
    put the two on different subjects and leave every edge dangling.
    """
    urn = "urn:ddi:ie.cso:inst1:1.0.0"

    assert v.subject_iri("Instrument", urn) == urn
    assert v.subject_iri("Instrument", urn) == v.subject_iri("Instrument", urn, urn=urn)


def test_subject_iri_falls_back_without_inventing_a_domain() -> None:
    """No default http:// namespace nobody owns."""
    minted = v.subject_iri("Variable", "v1")

    assert minted.startswith("urn:ddigraph:")
    assert "example.org" not in minted


def test_subject_iri_honours_a_caller_supplied_base() -> None:
    """Publishers pass their own namespace; a missing slash is tolerated."""
    assert (
        v.subject_iri("Variable", "v1", base="https://example.org/id")
        == "https://example.org/id/Variable/v1"
    )
    assert (
        v.subject_iri("Variable", "v1", base="https://example.org/id/")
        == "https://example.org/id/Variable/v1"
    )


def test_subject_iri_escapes_characters_that_break_iris() -> None:
    """Identity values are user data and may contain anything."""
    minted = v.subject_iri("Variable", "a b/c?d")

    assert " " not in minted
    assert minted.endswith("a%20b%2Fc%3Fd")


def test_distinct_nodes_never_collide_on_one_iri() -> None:
    """Label scoping keeps same-id records of different types apart."""
    assert v.subject_iri("Variable", "x1") != v.subject_iri("Question", "x1")


def test_every_bound_prefix_resolves_to_a_declared_namespace() -> None:
    """``PREFIXES`` is what gets bound on every emitted graph."""
    assert v.PREFIXES["ddigraph"] == v.DDIGRAPH
    assert v.PREFIXES["disco"] == v.DISCO
    assert v.PREFIXES["skos"] == v.SKOS
    assert all(ns.endswith(("#", "/")) for ns in v.PREFIXES.values())
