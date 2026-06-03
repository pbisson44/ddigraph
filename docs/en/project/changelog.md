# Changelog

All notable changes to ddigraph are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## Unreleased

### Added

**Real XSD-Driven 100 % Coverage for Every DDI Flavor**

`scripts/xsd_coverage.py` now parses the bundled XSDs directly and verifies
that the package registers a handler for every concrete, non-abstract element.
Coverage is enforced by the `TestRealXSDCoverage` pytest guardrail:

| Flavor      | Scope                                                                 | Target | Covered |
| ----------- | --------------------------------------------------------------------- | -----: | ------: |
| DDI-L 3.x   | Concrete Maintainable + Versionable + Identifiable elements           |    189 |  100 %  |
| DDI-C 2.x   | Codebook elements with the `GLOBALS` attribute group (no layout tags) |     73 |  100 %  |
| DDI-CDI 1.0 | Concrete top-level entity elements (associations excluded)            |    210 |  100 %  |

Implementation highlights:

- 106 new DDI-L identifiable `NodeDefinition` entries and matching `NAME_TAGS`
  entries covering every remaining concrete element in DDI-L 3.3.
- `BatchBuilder.ingest_generic_identifiable()` + `GenericIdentifiableRecord`
  capture every concrete codebook element that carries the `GLOBALS`
  attribute group without a bespoke record class, while still letting
  enclosing bespoke handlers (e.g. `stdyDscr`) read nested children.
- `CDIGenericRecord` + the `generic_entities` collection on `CDIBatch`
  round-trip every DDI-CDI concrete entity beyond the ~35 hand-tuned record
  types.
- `CDIBatchStream` only processes root-level elements, preventing reusable
  nested types (e.g. `Identifier`, `ObjectName`) from being cleared before
  their parent entity finishes parsing.

---

## v0.1.0

### Added

**DDI Format Support**

- **DDI Codebook** (DDI-C 2.5 and 2.6) support with streaming XML parsing for files of any size
- **DDI Lifecycle** (DDI-L 3.2/3.3) FragmentInstance support with batched writes and full async I/O
- **DDI-CDI 1.0** support with a streaming parser for 32 entity types and 20 relationship types
- **Format auto-detection** -- `detect_ddi_format()` inspects the XML root element and namespace to
  pick the right parser automatically
- DDI-C 2.6 entity types: NCube, NCubeGroup, DocumentDescription, SampleFrame, QualityStatement,
  StudyAuthorization, StudyDevelopment, ExPostEvaluation

**Multi-Backend Architecture**

- **`GraphWriteAdapter` protocol** (`ddigraph.schema.adapter`) for pluggable backend implementations
  supporting both synchronous and asynchronous adapters
- **Neo4j backend** -- Bolt driver, schema bootstrap, UNWIND batching, retry with exponential backoff
- **RDF/SPARQL backend** -- via rdflib and SPARQLWrapper
- **Gremlin backend** -- via gremlinpython (JanusGraph, Neptune, Cosmos DB)
- **NetworkX backend** -- in-memory graph for local analysis and prototyping
- **pandas backend** -- tabular analysis and CSV/Excel export
- Demo scripts for all backends (`demo/load_rdf.py`, `demo/load_gremlin.py`,
  `demo/load_networkx.py`, `demo/load_pandas.py`)

**CLI**

- `load` command with format auto-detection, `--dry-run`, `--replace`, and configurable batching
- `ensure-schema` and `ensure-fragment-schema` commands for database constraint and index setup
- `detect` command to identify the DDI format of a file without loading it
- `audit` command for graph content verification
- Credential source auditing at startup

**Core Engine**

- Streaming `iterparse`-based XML parsing -- memory usage stays constant regardless of file size
- Async write pipeline with `asyncio.Queue` back-pressure and configurable writer concurrency
- UNWIND-based batched writes reducing Neo4j round-trips by 10--100x
- Retry logic with exponential backoff and jitter for transient write failures
- Unified schema definitions in `ddigraph.schema.definitions` as single source of truth
- Shared parsing utilities in `ddigraph.utils.parsing`
- Shared retry logic in `ddigraph.utils.retry.retry_transient`
- Configuration via environment variables with `.env` file support (pydantic-settings v2)
- Structured logging with configurable log levels
- Python 3.12--3.14 support

**Full XSD Coverage for DDI-L FragmentInstance**

- **80 fragment node types** covering every independently identifiable maintainable and scheme
  member defined in the DDI-L 3.2 XSD:
  - 9 Data Collection schemes (`QuestionScheme`, `ControlConstructScheme`, `InstrumentScheme`,
    `InterviewerInstructionScheme`, `ProcessingEventScheme`, `ProcessingInstructionScheme`,
    `DevelopmentActivityScheme`, `MeasurementScheme`, `SamplingInformationScheme`)
  - 3 Logical Product schemes (`CodeListScheme`, `NCubeScheme`, `VariableScheme`)
  - 6 Conceptual Component schemes (`ConceptScheme`, `UniverseScheme`,
    `ConceptualVariableScheme`, `GeographicStructureScheme`, `GeographicLocationScheme`,
    `UnitTypeScheme`)
  - 5 control construct subtypes (`Split`, `SplitJoin`, `DevelopmentStep`,
    `SamplingStage`, `SampleStep`)
  - Classification types (`ClassificationFamily`, `StatisticalClassification`,
    `ClassificationItem`)
  - Geographic types (`GeographicStructure`, `GeographicLocation`)
  - Group and unit types (`ConceptGroup`, `UniverseGroup`, `ConceptualVariableGroup`,
    `UnitType`, `UnitTypeGroup`, `VariableGroup`)
  - Module-level wrappers (`ConceptualComponent`, `LogicalProduct`, `PhysicalDataProduct`,
    `Archive`, `DDIProfile`, `LocalHoldingPackage`)
  - Archive types (`Individual`, `Collection`, `Access`)
  - Development and methodology types (`DevelopmentActivity`, `RecordLayout`, `QuestionBlock`)
- 21 scheme-containment and archive `FRAGMENT_RELATIONSHIP_TYPES`
  (e.g., `IN_QUESTION_SCHEME`, `IN_CONCEPT_SCHEME`, `IN_CLASSIFICATION_FAMILY`,
  `REFERENCES_INDIVIDUAL`)
- `NAME_TAGS` entries for all 80 fragment node types in `DDIFragmentParser`

**Full XSD Coverage for DDI-CDI 1.0**

- **32 CDI entity types**, including `CDIVariableRelationship`, `CDIConceptMap`,
  `CDIConceptSystemCorrespondence`, `CDIPhysicalRecordSegment`, `CDIClassificationFamily`,
  `CDIClassificationIndex`, `CDIClassificationSeries`
- **20 CDI relationship types**, including `IS_BASED_ON`, `TAKES_CONCEPT_FROM`,
  `HAS_POPULATION`, `IS_DEFINED_BY`, `HAS_SENTINEL_VALUE`, `USES`, `HAS_DATA_STORE`
- `CDIBatch` collection fields and record dataclasses for all entity types

**XSD Coverage Audit**

- `scripts/xsd_coverage.py` audits package coverage against curated DDI-L and CDI target sets;
  exits with code 1 when coverage falls below a configurable threshold
- `tests/test_xsd_coverage.py` with 95+ assertions verifying all node types, NAME_TAGS entries,
  CDI tags, CDI relationships, and CDIBatch collections

**Documentation and Project**

- Bilingual documentation (English and French) built with mkdocs-material and mkdocs-static-i18n
- SECURITY.md with vulnerability reporting policy
- CODE_OF_CONDUCT.md (Contributor Covenant v2.1)
- `.pre-commit-config.yaml` for local linting enforcement
- GitHub issue/PR templates and Dependabot configuration
- `pytest-cov` with 70 % branch-coverage gate in CI
- PyPI package publication -- installable via `pip install ddigraph`
- MIT License

---

See [Contributing](contributing.md) for development setup and the [FAQ](faq.md) for common
questions.
