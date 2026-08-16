"""File export for DDI graphs: RDF serialisations, JSON, and CSV.

Before 0.5.0 the package could load a DDI file into Neo4j and nothing else.
Writing a file meant running ``demo/export_files.py``, which ships in
neither the wheel nor the sdist and understands only the DDI-L parser tier.
This module is the shipped equivalent, and because it consumes
:class:`~ddigraph.graph.view.GraphChunk` it works for DDI Codebook,
DDI-Lifecycle and DDI-CDI alike.

Output shape differs by format, which the CLI help states plainly:

* ``turtle``, ``ntriples``, ``jsonld``, ``rdfxml`` and ``json`` write a
  single file to ``destination``.
* ``csv`` writes ``nodes.csv`` and ``relationships.csv`` into
  ``destination``, treated as a directory, because a graph does not fit one
  rectangle.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

from ddigraph.graph.view import GraphChunk, iter_graph
from ddigraph.logging import get_logger
from ddigraph.schema.ddi_graph import Node, Relationship

logger = get_logger(__name__)

#: Export format -> the ``rdflib`` serializer name it corresponds to.
RDF_FORMATS: dict[str, str] = {
    "turtle": "turtle",
    "ntriples": "nt",
    "jsonld": "json-ld",
    "rdfxml": "xml",
}

#: Formats that do not go through ``rdflib`` and need no optional extra.
PLAIN_FORMATS: tuple[str, ...] = ("json", "csv")

#: Every value accepted by ``--format``.
FORMATS: tuple[str, ...] = (*RDF_FORMATS, *PLAIN_FORMATS)

#: Conventional file extension per format, used to suggest an output name.
EXTENSIONS: dict[str, str] = {
    "turtle": ".ttl",
    "ntriples": ".nt",
    "jsonld": ".jsonld",
    "rdfxml": ".rdf",
    "json": ".json",
}


@dataclass(slots=True)
class ExportResult:
    """Summary of one :func:`export` call.

    Attributes:
        path: Where the output was written -- a file, or a directory for CSV.
        format: The format written.
        nodes: Number of nodes projected from the source document.
        relationships: Number of relationships projected.
        triples: Number of RDF triples emitted, or ``None`` for JSON and CSV.
    """

    path: Path
    format: str
    nodes: int
    relationships: int
    triples: int | None = None


def export(
    source: str | Path,
    destination: str | Path,
    *,
    format: str = "turtle",
    base: str | None = None,
    flavor: str | None = None,
    dataset_id: str | None = None,
    dataset_name: str | None = None,
    chunk_size: int = 200,
) -> ExportResult:
    """Export a DDI file to disk.

    Args:
        source: Path to a DDI Codebook, DDI-L FragmentInstance or DDI-CDI file.
        destination: Output file, or output directory when ``format`` is
            ``"csv"``.
        format: One of :data:`FORMATS`.
        base: IRI stem for subjects whose identity is not already a DDI URN.
            RDF formats only.
        flavor: Force a DDI flavor instead of sniffing the file.
        dataset_id: Dataset identifier for the codebook flavor; defaults to
            the source file stem.
        dataset_name: Human-readable dataset name for the codebook flavor.
        chunk_size: Records to accumulate per streamed chunk.

    Returns:
        ExportResult: What was written, and how much of it.

    Raises:
        ValueError: If ``format`` is not one of :data:`FORMATS`.
        ImportError: If an RDF format is requested without ``rdflib``.
    """
    if format not in FORMATS:
        raise ValueError(f"Unknown export format {format!r}. Expected one of: {', '.join(FORMATS)}")

    out = Path(destination)
    chunks = iter_graph(
        source,
        flavor=flavor,
        dataset_id=dataset_id,
        dataset_name=dataset_name,
        chunk_size=chunk_size,
    )

    if format in RDF_FORMATS:
        result = _export_rdf(chunks, out, format=format, base=base)
    elif format == "json":
        result = _export_json(chunks, out)
    else:
        result = _export_csv(chunks, out)

    logger.info(
        "Exported DDI graph",
        extra={
            "source": str(source),
            "destination": str(result.path),
            "format": format,
            "nodes": result.nodes,
            "relationships": result.relationships,
        },
    )
    return result


def _counted(chunks: Iterable[GraphChunk], tally: dict[str, int]) -> Iterator[GraphChunk]:
    """Pass chunks through while counting, so nothing is buffered twice."""
    for chunk in chunks:
        tally["nodes"] += len(chunk.nodes)
        tally["relationships"] += len(chunk.relationships)
        yield chunk


def _export_rdf(
    chunks: Iterable[GraphChunk],
    destination: Path,
    *,
    format: str,
    base: str | None,
) -> ExportResult:
    """Serialise through ``rdflib`` in the requested syntax."""
    from ddigraph.rdf.writer import build_graph

    tally = {"nodes": 0, "relationships": 0}
    graph = build_graph(_counted(chunks, tally), base=base)

    destination.parent.mkdir(parents=True, exist_ok=True)
    graph.serialize(destination=str(destination), format=RDF_FORMATS[format])

    return ExportResult(
        path=destination,
        format=format,
        nodes=tally["nodes"],
        relationships=tally["relationships"],
        triples=len(graph),
    )


def _node_record(node: Node) -> dict[str, object]:
    """Flatten a node for JSON or CSV."""
    record: dict[str, object] = {"label": node.label}
    record.update(node.identity)
    record.update(node.properties)
    return record


def _relationship_record(relationship: Relationship) -> dict[str, object]:
    """Flatten a relationship for JSON or CSV."""
    start = next(iter(relationship.start.identity.values()), "")
    end = next(iter(relationship.end.identity.values()), "")
    return {
        "start_label": relationship.start.label,
        "start_id": start,
        "type": relationship.type,
        "end_label": relationship.end.label,
        "end_id": end,
    }


def _export_json(chunks: Iterable[GraphChunk], destination: Path) -> ExportResult:
    """Write one JSON document holding nodes, relationships and a summary."""
    nodes: list[dict[str, object]] = []
    relationships: list[dict[str, object]] = []

    for chunk in chunks:
        nodes.extend(_node_record(node) for node in chunk.nodes)
        relationships.extend(_relationship_record(rel) for rel in chunk.relationships)

    by_label: dict[str, int] = {}
    for record in nodes:
        label = str(record["label"])
        by_label[label] = by_label.get(label, 0) + 1
    by_type: dict[str, int] = {}
    for record in relationships:
        rel_type = str(record["type"])
        by_type[rel_type] = by_type.get(rel_type, 0) + 1

    payload = {
        "summary": {
            "nodes": len(nodes),
            "relationships": len(relationships),
            "nodes_by_label": dict(sorted(by_label.items())),
            "relationships_by_type": dict(sorted(by_type.items())),
        },
        "nodes": nodes,
        "relationships": relationships,
    }

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(payload, indent=2, default=str, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    return ExportResult(
        path=destination,
        format="json",
        nodes=len(nodes),
        relationships=len(relationships),
    )


def _export_csv(chunks: Iterable[GraphChunk], destination: Path) -> ExportResult:
    """Write ``nodes.csv`` and ``relationships.csv`` into a directory.

    Node types do not share a column set, so the header is the sorted union
    of every key seen. That needs all rows in hand before the first is
    written, which is why this path buffers where the RDF path streams.
    """
    nodes: list[dict[str, object]] = []
    relationships: list[dict[str, object]] = []

    for chunk in chunks:
        nodes.extend(_node_record(node) for node in chunk.nodes)
        relationships.extend(_relationship_record(rel) for rel in chunk.relationships)

    destination.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for record in nodes for key in record})

    with (destination / "nodes.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for record in nodes:
            writer.writerow({key: _csv_value(record.get(key)) for key in fields})

    rel_fields = ["start_label", "start_id", "type", "end_label", "end_id"]
    with (destination / "relationships.csv").open("w", newline="", encoding="utf-8") as handle:
        rel_writer = csv.DictWriter(handle, fieldnames=rel_fields)
        rel_writer.writeheader()
        rel_writer.writerows(relationships)

    return ExportResult(
        path=destination,
        format="csv",
        nodes=len(nodes),
        relationships=len(relationships),
    )


def _csv_value(value: object) -> str:
    """Render a property value for a CSV cell."""
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        return "|".join(str(item) for item in value)
    return str(value)


__all__ = ["EXTENSIONS", "FORMATS", "PLAIN_FORMATS", "RDF_FORMATS", "ExportResult", "export"]
