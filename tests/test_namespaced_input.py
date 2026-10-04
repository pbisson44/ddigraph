"""Real DDI declares its namespace; the synthetic fixtures do not.

Every published DDI-Codebook file puts ``codeBook`` in ``ddi:codebook:2_5``
(or ``2_6``). The fixtures under ``tests/fixtures/`` leave it out, and the
demo corpus is all DDI-L, so until these tests existed no namespaced
codebook had ever been parsed in CI. It mattered: a dozen nested lookups
such as ``find("qstn")`` and ``findall(".//universe")`` used bare tag names,
which never match a namespaced element. The top-level dispatch strips
namespaces, so most nodes still appeared and nothing raised -- the parser
silently dropped universes, categories, concepts, series, groups and
collection events, 17 of 73 relationships, and every label read through
``_first_text``.

Each test injects the official namespace into a fixture and requires the
projected graph to be *identical*, properties included. Comparing counts
alone would miss a lookup that blanks a property without dropping a node.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ddigraph.graph.view import iter_graph
from ddigraph.schema.ddi_graph import Node

FIXTURES = Path(__file__).parent / "fixtures"


def _key(node: Node) -> tuple[str, str]:
    return node.label, repr(sorted(node.identity.items()))


def _canonical(path: Path) -> tuple[list[str], list[str]]:
    """The whole projected graph as sorted, comparable strings."""
    nodes: list[str] = []
    relationships: list[str] = []
    for chunk in iter_graph(path, dataset_id="ns-test"):
        nodes.extend(
            repr((*_key(node), sorted(node.properties.items(), key=str))) for node in chunk.nodes
        )
        relationships.extend(
            repr(
                (
                    rel.type,
                    _key(rel.start),
                    _key(rel.end),
                    sorted((rel.properties or {}).items(), key=str),
                )
            )
            for rel in chunk.relationships
        )
    return sorted(nodes), sorted(relationships)


def _with_default_namespace(source: Path, root: str, namespace: str, tmp_path: Path) -> Path:
    text = source.read_text(encoding="utf-8")
    assert f"<{root} " in text, f"{source.name} no longer opens with <{root} ...>"
    namespaced = tmp_path / source.name
    namespaced.write_text(
        text.replace(f"<{root} ", f'<{root} xmlns="{namespace}" ', 1), encoding="utf-8"
    )
    return namespaced


@pytest.mark.parametrize("fixture", ["codebook_sample.xml", "reusable_fragments.xml"])
@pytest.mark.parametrize("namespace", ["ddi:codebook:2_5", "ddi:codebook:2_6"])
def test_a_namespaced_codebook_projects_identically(
    fixture: str, namespace: str, tmp_path: Path
) -> None:
    source = FIXTURES / fixture
    namespaced = _with_default_namespace(source, "codeBook", namespace, tmp_path)

    expected_nodes, expected_relationships = _canonical(source)
    nodes, relationships = _canonical(namespaced)

    assert expected_nodes, "the fixture projected nothing; the comparison would be vacuous"
    assert nodes == expected_nodes
    assert relationships == expected_relationships


def test_a_cdi_document_in_the_published_namespace_projects_identically(
    tmp_path: Path,
) -> None:
    source = FIXTURES / "cdi_sample.xml"
    text = source.read_text(encoding="utf-8")
    namespaced = tmp_path / source.name
    namespaced.write_text(
        text.replace(
            'xmlns="http://ddi-cdi/1.0"',
            'xmlns="http://ddialliance.org/Specification/DDI-CDI/1.0/XMLSchema/"',
            1,
        ),
        encoding="utf-8",
    )

    assert _canonical(namespaced) == _canonical(source)
