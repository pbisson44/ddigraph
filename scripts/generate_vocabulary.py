#!/usr/bin/env python3
"""Generate the served vocabulary document from ``ddigraph.rdf.vocabulary``.

Every exported triple carries IRIs under
``https://pbisson44.github.io/ddigraph/ns/1.0/``. A namespace that does not
dereference is the problem this release exists to fix, only moved one level
up: a consumer who follows the IRI has to land on something that says what
the term means.

The document is generated rather than hand-written for the same reason the
SHACL shapes are. A hand-maintained copy of a 270-class vocabulary drifts
from the code the first time a label is added, and nothing would notice --
which is exactly how this repo ended up with a documented predicate mapping
table no code implemented.

Usage::

    python scripts/generate_vocabulary.py            # write the file
    python scripts/generate_vocabulary.py --check    # fail if it is stale
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from ddigraph.rdf import vocabulary as vocab  # noqa: E402
from ddigraph.schema.ddi_graph import NODE_RECORD_FIELDS  # noqa: E402
from ddigraph.schema.definitions import DDISchema  # noqa: E402

#: Written under each language tree so mkdocs serves it beside the page that
#: links to it. The document itself is language-neutral -- it is RDF -- but
#: mkdocs-static-i18n builds the two trees independently and does not fall
#: back across them for static files, so a single copy would leave the
#: French page pointing at a 404. Both copies are generated and both are
#: drift-checked, so duplicating them costs nothing to maintain.
OUTPUTS = (
    REPO_ROOT / "docs" / "en" / "ns" / "vocabulary.ttl",
    REPO_ROOT / "docs" / "fr" / "ns" / "vocabulary.ttl",
)

_PREFIX_LINES = [
    f"@prefix {prefix}: <{iri}> ."
    for prefix, iri in sorted(
        {
            "ddigraph": vocab.DDIGRAPH,
            "dcterms": vocab.DCTERMS,
            "disco": vocab.DISCO,
            "foaf": vocab.FOAF,
            "owl": vocab.OWL,
            "prov": vocab.PROV,
            "rdf": vocab.RDF,
            "rdfs": vocab.RDFS,
            "skos": vocab.SKOS,
            "xkos": vocab.XKOS,
        }.items()
    )
]


def _term(iri: str) -> str:
    """Return the local name of a project-namespace IRI."""
    return iri.removeprefix(vocab.DDIGRAPH)


def _is_project(iri: str) -> bool:
    """Return True when an IRI belongs to this project's namespace."""
    return iri.startswith(vocab.DDIGRAPH)


def _classes() -> list[str]:
    """Emit one ``owl:Class`` per graph label.

    Every node carries its project class regardless of alignment (see
    ``class_iris``), so every label gets a term. Where a published class
    exists the project term is a *subclass* of it, not an equivalent one:
    the alignment is many-to-one, and ``Question`` and ``QuestionItem`` are
    both ``disco:Question`` without being each other.
    """
    blocks: list[str] = []
    for label in sorted({node.label for node in DDISchema.get_all_nodes()}):
        lines = [
            f"ddigraph:{_term(vocab.project_class_iri(label))} a owl:Class ;",
            f'    rdfs:label "{label}"@en ;',
        ]
        standard = vocab.standard_class_iri(label)
        if standard:
            lines.append(f"    rdfs:subClassOf <{standard}> ;")
        lines[-1] = lines[-1].removesuffix(" ;") + " ."
        blocks.append("\n".join(lines))
    return blocks


def _object_properties() -> list[str]:
    """Emit one ``owl:ObjectProperty`` per minted relationship predicate.

    Only project-namespace terms are defined here. Saying anything about
    ``disco:question`` in our own document would be asserting facts about
    someone else's vocabulary.

    Where the graph edge and the published predicate run in opposite
    directions -- SKOS models membership member-first, the graph models it
    container-first -- the relation is ``owl:inverseOf``, not
    ``rdfs:subPropertyOf``. Getting that backwards would tell a reasoner the
    scheme is in the concept.
    """
    seen: dict[str, tuple[str, str | None, bool]] = {}
    for rel_type in sorted(vocab._all_relationship_types()):
        standard = vocab.predicate_iri(rel_type)
        project = vocab.project_predicate_iri(rel_type)
        inverted = vocab.is_inverted_predicate(rel_type)

        # Every relationship type gets its project term defined, including
        # the aligned ones whose project term the writer never emits. That
        # makes this file the complete, machine-readable mapping: a consumer
        # who meets ``disco:question`` in the data can follow the
        # ``rdfs:subPropertyOf`` chain back to the DDI relationships that
        # produce it. A prose table claiming the same thing is what the
        # documentation used to have, and no code implemented it.
        for iri, parent in ((standard, None), (project, standard)):
            if not _is_project(iri):
                continue
            seen.setdefault(
                iri,
                (rel_type, parent if parent and not _is_project(parent) else None, inverted),
            )

    blocks: list[str] = []
    for iri, (rel_type, parent, inverted) in sorted(seen.items()):
        lines = [
            f"ddigraph:{_term(iri)} a owl:ObjectProperty ;",
            f'    rdfs:label "{rel_type}"@en ;',
        ]
        if parent:
            relation = "owl:inverseOf" if inverted else "rdfs:subPropertyOf"
            lines.append(f"    {relation} <{parent}> ;")
        lines[-1] = lines[-1].removesuffix(" ;") + " ."
        blocks.append("\n".join(lines))
    return blocks


def _datatype_properties() -> list[str]:
    """Emit one ``owl:DatatypeProperty`` per minted record attribute.

    Record fields become literal-valued predicates. Fields with a published
    equivalent (``dcterms:identifier`` for ``urn``, and the SKOS labelling
    predicates) resolve to that term instead and so mint nothing.
    """
    fields = sorted({field for _id, names in NODE_RECORD_FIELDS.values() for field in names})

    seen: dict[str, str] = {}
    for field in fields:
        for skos_typed in (False, True):
            iri = vocab.property_iri(field, skos_typed=skos_typed)
            if _is_project(iri):
                seen.setdefault(iri, field)

    return [
        "\n".join(
            [
                f"ddigraph:{_term(iri)} a owl:DatatypeProperty ;",
                f'    rdfs:label "{field}"@en .',
            ]
        )
        for iri, field in sorted(seen.items())
    ]


def render() -> str:
    """Return the full Turtle document."""
    classes = _classes()
    object_properties = _object_properties()
    datatype_properties = _datatype_properties()

    header = "\n".join(
        [
            "# The ddigraph DDI vocabulary.",
            "#",
            "# GENERATED FILE -- do not edit by hand.",
            "# Regenerate with: python scripts/generate_vocabulary.py",
            "#",
            "# Terms are derived from DDISchema, the same table that generates the",
            "# Neo4j constraints and the SHACL shapes, so this document cannot",
            "# describe a vocabulary the exporter does not actually emit.",
            "",
            *_PREFIX_LINES,
            "",
            f"<{vocab.DDIGRAPH}>",
            "    a owl:Ontology ;",
            '    dcterms:title "The ddigraph DDI vocabulary"@en ;',
            "    dcterms:description "
            '"Classes and predicates for DDI metadata exported by ddigraph. '
            "Terms with a published equivalent in DISCO, XKOS or SKOS are declared as "
            'subclasses or subproperties of it rather than redefined."@en ;',
            f'    owl:versionInfo "{vocab.VOCABULARY_VERSION}" ;',
            f"    rdfs:seeAlso <{vocab.DISCO}> , <{vocab.XKOS}> , <{vocab.SKOS}> .",
        ]
    )

    sections = [
        (f"Classes ({len(classes)})", classes),
        (f"Object properties ({len(object_properties)})", object_properties),
        (f"Datatype properties ({len(datatype_properties)})", datatype_properties),
    ]

    parts = [header]
    for title, blocks in sections:
        parts.append(f"\n\n{'#' * 70}\n# {title}\n{'#' * 70}\n")
        parts.append("\n\n".join(blocks))

    return "\n".join(parts).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    """Write or verify the vocabulary document."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if the committed file is out of date; write nothing",
    )
    args = parser.parse_args(argv)

    rendered = render()

    if args.check:
        stale = [
            path
            for path in OUTPUTS
            if not path.exists() or path.read_text(encoding="utf-8") != rendered
        ]
        if stale:
            names = ", ".join(str(path.relative_to(REPO_ROOT)) for path in stale)
            print(
                f"{names} out of date. Run: python scripts/generate_vocabulary.py",
                file=sys.stderr,
            )
            return 1
        print("vocabulary.ttl already up to date")
        return 0

    for path in OUTPUTS:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered, encoding="utf-8")
        print(f"Wrote {path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
