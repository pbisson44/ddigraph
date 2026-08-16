"""The ddigraph RDF vocabulary: one namespace, one predicate convention.

Before 0.5.0 there was no vocabulary, only four competing guesses at one.
``demo/load_rdf.py`` minted ``http://ddialliance.org/ontology#``,
``demo/sdmx_from_physical_instance.py`` used
``http://ddialliance.org/ontology/ddi-l/3_3#``, and ``docs/backends/rdf.md``
used ``http://ddi.example.org/`` in one example and
``http://ddialliance.org/Specification/DDI-Lifecycle/3.3/`` in another --
none of them owned by this project. Predicates were equally unsettled:
Neo4j relationship names leaked out verbatim as ``ddi:USES_CODELIST`` while
the documentation promised ``ddi:usesCodeList``, and Python attribute names
leaked out as ``ddi:question_text``. Nothing produced that way can be joined
to anyone else's data.

This module fixes the vocabulary in three layers.

**Reuse a published standard where one exists.** The DDI Alliance publishes
two RDF vocabularies that cover much of this ground: DISCO, built directly
from DDI Codebook and DDI Lifecycle, and XKOS, which extends SKOS for
statistical classifications. Code lists and categories map onto SKOS itself.
Those alignments are hand-curated below and are the reason an exported graph
can join to anything else in the linked-data world.

**Mint one project namespace for the rest.** DISCO defines 16 classes;
``DDISchema`` carries roughly 250 node labels. Everything without a standard
equivalent gets a term under :data:`DDIGRAPH`, versioned independently of
the package (see :data:`VOCABULARY_VERSION`) because a namespace that
changed every release would recreate the problem this module exists to solve.

**Emit both types, always.** The standard alignment is many-to-one:
``Question`` and ``QuestionItem`` both map to ``disco:Question``;
``CodeScheme``, ``CodeList`` and ``CategoryScheme`` all map to
``skos:ConceptScheme``. A reader cannot recover the original label from the
standard type alone, so :func:`class_iris` returns *both* the standard class
and the project-namespace class. Interop consumers read the former and
ignore the latter; :mod:`ddigraph.rdf.reader` reads the latter and
round-trips exactly. This is why lossless round-tripping is possible at all.

No ``rdflib`` import appears here on purpose: these are plain strings, so the
tables can be imported and tested from a base install.
"""

from __future__ import annotations

from collections.abc import Sequence

from ddigraph.schema.definitions import DDISchema

# The vocabulary version is NOT the package version. Consumers key their
# queries on these IRIs; bumping the namespace every minor release would
# break every one of them. It changes only on a breaking vocabulary change.
VOCABULARY_VERSION = "1.0"

# Project namespace. Resolvable: the documentation site is published at this
# host, so the IRI dereferences to ``docs/<lang>/ns/1.0.md``, which describes
# the vocabulary and links the generated ``vocabulary.ttl`` beside it. Change
# VOCABULARY_VERSION and that page has to move with it, or every exported
# triple points at a 404 -- tests/test_vocabulary_document.py enforces this.
DDIGRAPH = f"https://pbisson44.github.io/ddigraph/ns/{VOCABULARY_VERSION}/"

# Published vocabularies we align to. DISCO and XKOS are the DDI Alliance's
# own RDF work; the rest are the usual linked-data furniture.
DISCO = "http://rdf-vocabulary.ddialliance.org/discovery#"
XKOS = "http://rdf-vocabulary.ddialliance.org/xkos#"
SKOS = "http://www.w3.org/2004/02/skos/core#"
DCTERMS = "http://purl.org/dc/terms/"
FOAF = "http://xmlns.com/foaf/0.1/"
PROV = "http://www.w3.org/ns/prov#"
OWL = "http://www.w3.org/2002/07/owl#"
RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
RDFS = "http://www.w3.org/2000/01/rdf-schema#"
XSD = "http://www.w3.org/2001/XMLSchema#"
SH = "http://www.w3.org/ns/shacl#"

#: Prefixes bound on every graph this package writes.
PREFIXES: dict[str, str] = {
    "ddigraph": DDIGRAPH,
    "disco": DISCO,
    "xkos": XKOS,
    "skos": SKOS,
    "dcterms": DCTERMS,
    "foaf": FOAF,
    "prov": PROV,
    "owl": OWL,
    "rdfs": RDFS,
    "xsd": XSD,
}

# Fallback IRI stem for subjects whose record carries no DDI URN and where
# the caller supplied no --base-uri. A URN-style identifier is used rather
# than inventing an http:// domain nobody owns -- the mistake the old demo
# namespaces made. Callers publishing data should pass their own base.
DEFAULT_BASE_URI = "urn:ddigraph:"

# ---------------------------------------------------------------------------
# Class alignment
# ---------------------------------------------------------------------------

#: Labels that denote a controlled vocabulary container.
SCHEME_LABELS: frozenset[str] = frozenset(
    {"CodeScheme", "CodeList", "CategoryScheme", "ConceptScheme"}
)

#: Labels that denote a member of a controlled vocabulary.
CONCEPT_LABELS: frozenset[str] = frozenset({"Category", "Concept"})

# Hand-curated alignment to published vocabularies. Only terms with a genuine
# standard equivalent belong here -- a wrong alignment is worse than none,
# because consumers act on it. Everything absent falls through to DDIGRAPH.
_STANDARD_CLASSES: dict[str, str] = {
    # DISCO -- the DDI Alliance's own discovery vocabulary.
    "Study": DISCO + "Study",
    "StudyUnit": DISCO + "Study",
    "Group": DISCO + "StudyGroup",
    "Series": DISCO + "StudyGroup",
    "Variable": DISCO + "Variable",
    "RepresentedVariable": DISCO + "RepresentedVariable",
    "Question": DISCO + "Question",
    "QuestionItem": DISCO + "Question",
    "QuestionScheme": DISCO + "Questionnaire",
    "Universe": DISCO + "Universe",
    "DataFile": DISCO + "DataFile",
    "LogicalRecord": DISCO + "LogicalDataSet",
    "Instrument": DISCO + "Instrument",
    "CollectionInstrument": DISCO + "Instrument",
    "Representation": DISCO + "Representation",
    "AnalysisUnit": DISCO + "AnalysisUnit",
    # SKOS -- code lists and their members, the highest-value interop surface.
    "CodeScheme": SKOS + "ConceptScheme",
    "CodeList": SKOS + "ConceptScheme",
    "CategoryScheme": SKOS + "ConceptScheme",
    "ConceptScheme": SKOS + "ConceptScheme",
    "Category": SKOS + "Concept",
    "Concept": SKOS + "Concept",
    # XKOS -- statistical classification structure on top of SKOS.
    "CategoryGroup": XKOS + "ClassificationLevel",
    "ConceptGroup": XKOS + "ClassificationLevel",
    # General-purpose vocabularies.
    "Organization": FOAF + "Organization",
    "Individual": FOAF + "Person",
    "Dataset": DCTERMS + "Dataset",
    "ProcessingEvent": PROV + "Activity",
    "DataCollectionEvent": PROV + "Activity",
    "Software": PROV + "SoftwareAgent",
    # DDI-CDI curated entities that share the same concepts.
    "CDIConcept": SKOS + "Concept",
    "CDIConceptSystem": SKOS + "ConceptScheme",
    "CDICategory": SKOS + "Concept",
    "CDICodeList": SKOS + "ConceptScheme",
    "CDIInstanceVariable": DISCO + "Variable",
    "CDIRepresentedVariable": DISCO + "RepresentedVariable",
    "CDIConceptualVariable": DISCO + "RepresentedVariable",
    "CDIUniverse": DISCO + "Universe",
    "CDIPopulation": DISCO + "Universe",
    "CDILogicalRecord": DISCO + "LogicalDataSet",
    "CDIStatisticalClassification": XKOS + "ClassificationLevel",
    "CDIActivity": PROV + "Activity",
    "CDIAgent": PROV + "Agent",
    "CDIProcessingAgent": PROV + "SoftwareAgent",
}

# ---------------------------------------------------------------------------
# Property alignment
# ---------------------------------------------------------------------------

# Record attribute -> standard predicate. ``label`` is handled by
# :func:`property_iri` instead, because its correct predicate depends on
# whether the subject is SKOS-typed.
_STANDARD_PROPERTIES: dict[str, str] = {
    "description": DCTERMS + "description",
    "urn": DCTERMS + "identifier",
    "agency": DCTERMS + "publisher",
    "version": OWL + "versionInfo",
    "code": SKOS + "notation",
    "name": DCTERMS + "title",
    "title": DCTERMS + "title",
    "rationale": SKOS + "scopeNote",
    "purpose": DISCO + "purpose",
    "question_text": DISCO + "questionText",
    "start_date": DISCO + "startDate",
    "end_date": DISCO + "endDate",
    "external_references": SKOS + "exactMatch",
}

# ---------------------------------------------------------------------------
# Relationship alignment
# ---------------------------------------------------------------------------

_STANDARD_PREDICATES: dict[str, str] = {
    "USES_CONCEPT": DISCO + "concept",
    "USES_CONCEPT_SCHEME": DISCO + "concept",
    "ASKS_QUESTION": DISCO + "question",
    "USES_QUESTION_ITEM": DISCO + "question",
    "ASKED_AS": DISCO + "question",
    "USES_CODELIST": DISCO + "responseDomain",
    "IN_UNIVERSE": DISCO + "universe",
    "IN_FILE": DISCO + "dataFile",
    "REPRESENTS": DISCO + "representation",
    "BASED_ON": DISCO + "basedOn",
    "INSTRUMENT_FOR": DISCO + "instrument",
    "IN_DATASET": DCTERMS + "isPartOf",
    "PART_OF": DCTERMS + "isPartOf",
    "IN_SCHEME": SKOS + "inScheme",
    # Container -> member edges. SKOS models this from the member's side:
    # ``skos:inScheme`` is the property a concept carries, and ``skos:member``
    # belongs to ``skos:Collection``, not ``skos:ConceptScheme``. These are
    # therefore emitted with subject and object swapped -- see
    # :func:`is_inverted_predicate`.
    "HAS_CATEGORY": SKOS + "inScheme",
    "HAS_CODE": SKOS + "inScheme",
    "HAS_CONCEPT": SKOS + "inScheme",
}

# Relationship types whose RDF form runs opposite to the graph edge. The
# graph points container -> member; SKOS wants member -> container.
_INVERTED_PREDICATES: frozenset[str] = frozenset({"HAS_CATEGORY", "HAS_CODE", "HAS_CONCEPT"})


def to_lower_camel(name: str) -> str:
    """Convert an identifier to ``lowerCamelCase``.

    Handles the two shapes that reach RDF predicates: ``SCREAMING_SNAKE``
    relationship types (``USES_CODELIST``) and ``snake_case`` record
    attributes (``question_text``). A name already free of separators is
    lowercased only in its first character, so ``PascalCase`` survives.

    Args:
        name: The identifier to convert.

    Returns:
        The ``lowerCamelCase`` form, or an empty string for empty input.
    """
    if not name:
        return ""
    if "_" in name:
        # The emptiness check has to come before the unpack, not after it:
        # a separator-only name such as ``"_"`` leaves no parts at all, and
        # ``head, *tail = []`` raises ValueError rather than reaching a
        # guard on ``head``.
        parts = [part for part in name.split("_") if part]
        if not parts:
            return ""
        head, *tail = parts
        return head.lower() + "".join(part.capitalize() for part in tail)
    if name.isupper():
        return name.lower()
    return name[0].lower() + name[1:]


def _lifecycle_terms() -> dict[str, str]:
    """Recover word boundaries for single-word lifecycle relationship types.

    ``FRAGMENT_RELATIONSHIP_TYPES`` defaults an uncurated ``*Reference`` tag
    to ``tag.replace("Reference", "").upper()``, which flattens
    ``AgencyOrganizationReference`` to ``AGENCYORGANIZATION``. Camel-casing
    that yields ``agencyorganization`` -- correct but unreadable, and it
    throws away structure the schema still holds. The source tag keeps the
    boundaries, so it is used instead wherever the rel type carries no
    underscore of its own.

    Where several tags collapse onto one rel type the candidates are sorted
    so the choice is deterministic across runs.
    """
    candidates: dict[str, set[str]] = {}
    for tag, rel_type in DDISchema.FRAGMENT_RELATIONSHIP_TYPES.items():
        if "_" in rel_type:
            # A curated name: the rel type is the deliberate wording and
            # already camel-cases well (ASKS_QUESTION -> asksQuestion).
            continue
        stem = tag[: -len("Reference")] if tag.endswith("Reference") else tag
        if stem:
            candidates.setdefault(rel_type, set()).add(to_lower_camel(stem))
    return {rel: sorted(terms)[0] for rel, terms in candidates.items() if terms}


_LIFECYCLE_TERMS: dict[str, str] = _lifecycle_terms()


def _all_relationship_types() -> frozenset[str]:
    """Every relationship type any DDI flavor can produce."""
    from ddigraph.ingest.cdi_loader import _CDI_RELATIONSHIP_MAP
    from ddigraph.schema.ddi_graph import DDI_RELATIONSHIPS

    return frozenset(
        set(DDISchema.FRAGMENT_RELATIONSHIP_TYPES.values())
        | {rel.type for rel in DDI_RELATIONSHIPS}
        | {entry[0] for entry in _CDI_RELATIONSHIP_MAP.values()}
    )


def project_predicate_iri(rel_type: str) -> str:
    """Return the project-namespace predicate for a relationship type.

    Always minted, never a published term, so it is unique per relationship
    type and therefore reversible.

    Args:
        rel_type: A relationship type such as ``"HAS_CATEGORY"``.

    Returns:
        The IRI under :data:`DDIGRAPH`.
    """
    term = _LIFECYCLE_TERMS.get(rel_type) or to_lower_camel(rel_type)
    return DDIGRAPH + term


def _ambiguous_predicates() -> frozenset[str]:
    """Return published predicates that more than one relationship type uses.

    Three of them, covering nine of 369 relationship types:
    ``disco:question`` (from ``ASKED_AS``, ``ASKS_QUESTION`` and
    ``USES_QUESTION_ITEM``), ``skos:inScheme`` (from ``HAS_CATEGORY``,
    ``HAS_CODE``, ``HAS_CONCEPT`` and ``IN_SCHEME``, which also disagree on
    direction) and ``dcterms:isPartOf`` (from ``IN_DATASET`` and
    ``PART_OF``).

    Alignment is what makes the output interoperable, but for these the
    original relationship type cannot be recovered from the triple. The
    writer emits a project-namespace companion alongside them so the reader
    can, exactly as every node carries a project ``rdf:type`` beside its
    standard one. The other published predicates are one-to-one and need no
    companion, which keeps the extra triples to the cases that need them.
    """
    grouped: dict[str, set[str]] = {}
    for rel_type in _all_relationship_types():
        grouped.setdefault(predicate_iri(rel_type), set()).add(rel_type)
    return frozenset(iri for iri, types in grouped.items() if len(types) > 1)


def is_ambiguous_predicate(iri: str) -> bool:
    """Return True when a predicate cannot identify its relationship type.

    Args:
        iri: A predicate IRI.

    Returns:
        True when the writer emits a project-namespace companion for it and
        the reader should therefore ignore this triple as a duplicate.
    """
    return iri in _AMBIGUOUS_PREDICATES


def label_for_class_iri(iri: str) -> str | None:
    """Recover a graph label from a project-namespace class IRI.

    Args:
        iri: A class IRI.

    Returns:
        The label, or ``None`` when the IRI is not a project class -- which
        is how the reader ignores the standard ``rdf:type`` alongside it.
    """
    if iri.startswith(DDIGRAPH):
        return iri[len(DDIGRAPH) :]
    return None


def relationship_type_for(iri: str) -> str | None:
    """Recover a relationship type from a predicate IRI.

    Args:
        iri: A predicate IRI.

    Returns:
        The relationship type, or ``None`` when the predicate names no
        relationship this vocabulary emits.
    """
    return _REVERSE_PREDICATES.get(iri)


def property_field_for(iri: str) -> str | None:
    """Recover a record attribute from a property predicate IRI.

    Falls back to reversing the ``lowerCamelCase`` rule for project-namespace
    predicates, so properties parsed out of DDI-L fragments -- whose names
    are not enumerable from the schema -- still round-trip.

    Args:
        iri: A predicate IRI.

    Returns:
        The record attribute name, or ``None`` when the IRI is unknown and
        outside the project namespace.
    """
    known = _REVERSE_PROPERTIES.get(iri)
    if known is not None:
        return known
    if iri.startswith(DDIGRAPH):
        return _to_snake(iri[len(DDIGRAPH) :])
    return None


def _to_snake(name: str) -> str:
    """Invert :func:`to_lower_camel` for ``snake_case`` inputs."""
    out: list[str] = []
    for char in name:
        if char.isupper():
            out.append("_")
            out.append(char.lower())
        else:
            out.append(char)
    return "".join(out)


def project_class_iri(label: str) -> str:
    """Return the project-namespace class IRI for a graph label.

    This is the identity type: it is emitted for every node regardless of
    whether a standard alignment also exists, and it is what the reader keys
    on to reconstruct the original label.

    Args:
        label: A graph node label, e.g. ``"QuestionItem"``.

    Returns:
        The IRI under :data:`DDIGRAPH`.
    """
    return DDIGRAPH + label


def standard_class_iri(label: str) -> str | None:
    """Return the published-vocabulary class for a label, if one exists.

    Args:
        label: A graph node label.

    Returns:
        A DISCO, SKOS, XKOS, FOAF, PROV or DCTERMS class IRI, or ``None``
        when the label has no standard equivalent.
    """
    return _STANDARD_CLASSES.get(label)


def class_iris(label: str) -> tuple[str, ...]:
    """Return every ``rdf:type`` a node with this label should carry.

    Args:
        label: A graph node label.

    Returns:
        ``(standard_iri, project_iri)`` when an alignment exists, otherwise
        ``(project_iri,)``. The project IRI is always present and always
        last, so round-tripping never depends on the alignment table.
    """
    standard = standard_class_iri(label)
    project = project_class_iri(label)
    return (standard, project) if standard else (project,)


def predicate_iri(rel_type: str) -> str:
    """Return the RDF predicate for a graph relationship type.

    Args:
        rel_type: A relationship type such as ``"USES_CODELIST"``.

    Returns:
        A published-vocabulary predicate where one is curated, otherwise a
        ``lowerCamelCase`` term under :data:`DDIGRAPH` -- the convention the
        documentation always claimed and no code previously implemented.
    """
    standard = _STANDARD_PREDICATES.get(rel_type)
    if standard:
        return standard
    term = _LIFECYCLE_TERMS.get(rel_type) or to_lower_camel(rel_type)
    return DDIGRAPH + term


def is_inverted_predicate(rel_type: str) -> bool:
    """Return True when the RDF triple runs opposite to the graph edge.

    The graph models controlled vocabularies container-first
    (``CodeList -HAS_CATEGORY-> Category``) because that is how the XML nests.
    SKOS models them member-first: a concept carries ``skos:inScheme``, and
    ``skos:member`` belongs to ``skos:Collection`` rather than
    ``skos:ConceptScheme``. Emitting the graph direction verbatim would
    produce SKOS that validators and tooling reject.

    Args:
        rel_type: A relationship type such as ``"HAS_CATEGORY"``.

    Returns:
        True when the writer should swap subject and object.
    """
    return rel_type in _INVERTED_PREDICATES


def property_iri(field: str, *, skos_typed: bool = False) -> str:
    """Return the RDF predicate for a record attribute.

    Args:
        field: A record attribute name such as ``"question_text"``.
        skos_typed: True when the subject is a ``skos:Concept`` or
            ``skos:ConceptScheme``. SKOS defines its own labelling
            predicates, and mixing ``rdfs:label`` into a concept scheme is
            the sort of thing that makes downstream SKOS tooling unhappy.

    Returns:
        The predicate IRI.
    """
    if field == "label":
        return SKOS + "prefLabel" if skos_typed else RDFS + "label"
    if field == "description" and skos_typed:
        return SKOS + "definition"
    standard = _STANDARD_PROPERTIES.get(field)
    if standard:
        return standard
    return DDIGRAPH + to_lower_camel(field)


def is_skos_typed(label: str) -> bool:
    """Return True when a label maps onto a SKOS concept or scheme.

    Args:
        label: A graph node label.

    Returns:
        True when :func:`standard_class_iri` resolves into the SKOS
        namespace, which is what decides labelling predicates.
    """
    standard = standard_class_iri(label)
    return bool(standard and standard.startswith(SKOS))


def subject_iri(
    label: str,
    identity: str | Sequence[str],
    *,
    urn: str | None = None,
    base: str | None = None,
) -> str:
    """Mint a stable subject IRI for a graph node.

    A DDI URN is preferred whenever the record carries one: it is already a
    globally unique, agency-scoped identifier, so reusing it keeps exported
    data joinable to anything else describing the same object. Note that
    ``demo/load_rdf.py`` flattened colons out of the URN, destroying exactly
    that property; this does not.

    Args:
        label: The node's graph label, used to scope minted IRIs.
        identity: The node's identity value, or the ordered parts of a
            composite identity. A composite is never treated as a URN, since
            no single part identifies the node on its own.
        urn: The record's DDI URN when present.
        base: IRI stem for records with no URN. Defaults to
            :data:`DEFAULT_BASE_URI`.

    Returns:
        An absolute IRI.
    """
    if urn and urn.startswith("urn:"):
        return urn

    if isinstance(identity, str):
        parts = [identity]
    else:
        parts = [str(part) for part in identity]

    if len(parts) == 1 and parts[0].startswith("urn:"):
        # DDI-L identity *is* the URN: ``make_node_key`` returns it verbatim
        # when present. Deriving the IRI from identity alone is what keeps a
        # relationship endpoint -- which carries no properties, only a label
        # and an identity -- on the same IRI as the full node.
        return parts[0]

    stem = base or DEFAULT_BASE_URI
    if not stem.endswith(("/", "#", ":")):
        stem += "/"
    separator = ":" if stem.endswith(":") else ""
    local = ".".join(_escape(part) for part in parts)
    return f"{stem}{label}{separator or '/'}{local}"


def _escape(value: str) -> str:
    """Percent-escape the characters that cannot appear bare in an IRI."""
    out = []
    for char in str(value):
        if char.isalnum() or char in "-._~:":
            out.append(char)
        else:
            out.append("%" + format(ord(char), "02X"))
    return "".join(out)


def _reverse_predicates() -> dict[str, str]:
    """Build predicate IRI -> relationship type.

    Project predicates are registered first and are always unique. An
    unambiguous published predicate is registered too, so a graph written
    before its companion existed -- or by hand -- still reads back.
    """
    reverse: dict[str, str] = {}
    for rel_type in sorted(_all_relationship_types()):
        reverse.setdefault(project_predicate_iri(rel_type), rel_type)
    for rel_type in sorted(_all_relationship_types()):
        iri = predicate_iri(rel_type)
        if iri not in _AMBIGUOUS_PREDICATES:
            reverse.setdefault(iri, rel_type)
    return reverse


def _reverse_properties() -> dict[str, str]:
    """Build property predicate IRI -> record attribute.

    ``_STANDARD_PROPERTIES`` is not injective: ``name`` and ``title`` both
    map to ``dcterms:title``. Insertion order decides, so ``name`` wins --
    DDI records carry it far more often -- and the choice is stable because
    the declaration order is.
    """
    reverse: dict[str, str] = {
        RDFS + "label": "label",
        SKOS + "prefLabel": "label",
        SKOS + "definition": "description",
    }
    for field, iri in _STANDARD_PROPERTIES.items():
        reverse.setdefault(iri, field)
    return reverse


_AMBIGUOUS_PREDICATES: frozenset[str] = _ambiguous_predicates()
_REVERSE_PREDICATES: dict[str, str] = _reverse_predicates()
_REVERSE_PROPERTIES: dict[str, str] = _reverse_properties()


__all__ = [
    "CONCEPT_LABELS",
    "DCTERMS",
    "DDIGRAPH",
    "DEFAULT_BASE_URI",
    "DISCO",
    "FOAF",
    "OWL",
    "PREFIXES",
    "PROV",
    "RDF",
    "RDFS",
    "SCHEME_LABELS",
    "SH",
    "SKOS",
    "VOCABULARY_VERSION",
    "XKOS",
    "XSD",
    "class_iris",
    "is_ambiguous_predicate",
    "is_inverted_predicate",
    "is_skos_typed",
    "label_for_class_iri",
    "predicate_iri",
    "project_class_iri",
    "project_predicate_iri",
    "property_field_for",
    "property_iri",
    "relationship_type_for",
    "standard_class_iri",
    "subject_iri",
    "to_lower_camel",
]
