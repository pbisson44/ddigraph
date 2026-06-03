# DDI-L FragmentInstance Support

ddigraph supports DDI Lifecycle 3.x FragmentInstance files with **full XSD coverage** — every
independently identifiable object defined in the DDI-L 3.2 schema has a matching graph node type.
This format is very different from DDI Codebook. Instead of a flat, dataset-centric structure,
DDI-L uses reusable fragments that link to each other and form a directed graph.

## What is FragmentInstance?

In DDI-L FragmentInstance format:

- Each `<Fragment>` element contains a reusable DDI component (Instrument, Sequence, CodeList,
  QuestionItem, etc.)
- Components reference each other via `*Reference` elements (e.g., `ControlConstructReference`,
  `CodeListReference`)
- The structure naturally forms a graph, making it ideal for Neo4j

Example structure:

```xml
<FragmentInstance>
  <TopLevelReference>
    <Agency>ie.cso</Agency>
    <ID>instrument-123</ID>
    <TypeOfObject>Instrument</TypeOfObject>
  </TopLevelReference>
  <Fragment>
    <Instrument>
      <Agency>ie.cso</Agency>
      <ID>instrument-123</ID>
      <ControlConstructReference>
        <Agency>ie.cso</Agency>
        <ID>sequence-456</ID>
        <TypeOfObject>Sequence</TypeOfObject>
      </ControlConstructReference>
    </Instrument>
  </Fragment>
  <Fragment>
    <Sequence>
      <Agency>ie.cso</Agency>
      <ID>sequence-456</ID>
      <!-- More references... -->
    </Sequence>
  </Fragment>
</FragmentInstance>
```

## Quick Start

```bash
# Auto-detect format and load
ddigraph load questionnaire.xml

# Explicitly specify lifecycle format
ddigraph load questionnaire.xml --format lifecycle

# Detect format without loading
ddigraph detect questionnaire.xml
```

### Python API

```python
from neo4j import AsyncGraphDatabase

from ddigraph import DDIFragmentLoader, detect_ddi_format
from ddigraph.config import Settings

async def load_fragments():
    settings = Settings()
    driver = AsyncGraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password.get_secret_value()),
    )
    loader = DDIFragmentLoader(driver, settings=settings)
    result = await loader.load("questionnaire.xml")
    print(result)
    # {'Instrument': 1, 'Sequence': 388, 'QuestionConstruct': 376,
    #  'QuestionItem': 373, 'CodeList': 196, 'Category': 1065, ...}
    await driver.close()
```

## Supported Node Types

The FragmentInstance loader recognises every concrete Maintainable, Versionable and Identifiable
element defined in DDI-L 3.3 — 189 node types in total (same set as 3.1/3.2), organised below by
DDI module. The tables highlight the most commonly referenced subset; coverage for the remaining
concrete identifiables is verified by `scripts/xsd_coverage.py`.

### Survey Instruments and Control Constructs

| Node Label | DDI-L Element | Description |
| ------------ | --------------- | ------------- |
| `Instrument` | `<Instrument>` | Survey instrument entry point |
| `Sequence` | `<Sequence>` | Ordered list of control constructs |
| `IfThenElse` | `<IfThenElse>` | Conditional branching (if/then/else) |
| `Loop` | `<Loop>` | Repeats a block a set number of times |
| `QuestionConstruct` | `<QuestionConstruct>` | Links a question into the flow |
| `StatementItem` | `<StatementItem>` | Displays text to the respondent |
| `ComputationItem` | `<ComputationItem>` | Calculates a derived value |
| `RepeatWhile` | `<RepeatWhile>` | Repeats while a condition is true |
| `RepeatUntil` | `<RepeatUntil>` | Repeats until a condition is true |
| `Split` | `<Split>` | Splits flow into parallel branches |
| `SplitJoin` | `<SplitJoin>` | Rejoins parallel branches |
| `DevelopmentStep` | `<DevelopmentStep>` | Step in a questionnaire development process |
| `SamplingStage` | `<SamplingStage>` | Stage in a sampling design |
| `SampleStep` | `<SampleStep>` | Single step within a sampling stage |
| `MeasurementConstruct` | `<MeasurementConstruct>` | Links a measurement item into the flow |

### Questions and Measurements

| Node Label | DDI-L Element | Description |
| ------------ | --------------- | ------------- |
| `QuestionItem` | `<QuestionItem>` | Single question with a response domain |
| `QuestionGrid` | `<QuestionGrid>` | Matrix or grid of related questions |
| `QuestionBlock` | `<QuestionBlock>` | Reusable block of questions |
| `MeasurementItem` | `<MeasurementItem>` | A measurement instrument item |

### Data Collection Schemes

Scheme types are named containers that group related DDI objects of the same kind.

| Node Label | DDI-L Element | Description |
| ------------ | --------------- | ------------- |
| `QuestionScheme` | `<QuestionScheme>` | Container for question items |
| `ControlConstructScheme` | `<ControlConstructScheme>` | Container for control constructs |
| `InstrumentScheme` | `<InstrumentScheme>` | Container for instruments |
| `InterviewerInstructionScheme` | `<InterviewerInstructionScheme>` | Container for interviewer instructions |
| `ProcessingEventScheme` | `<ProcessingEventScheme>` | Container for processing events |
| `ProcessingInstructionScheme` | `<ProcessingInstructionScheme>` | Container for processing instructions |
| `DevelopmentActivityScheme` | `<DevelopmentActivityScheme>` | Container for development activities |
| `MeasurementScheme` | `<MeasurementScheme>` | Container for measurement items |
| `SamplingInformationScheme` | `<SamplingInformationScheme>` | Container for sampling information |

### Variables and Value Domains

| Node Label | DDI-L Element | Description |
| ------------ | --------------- | ------------- |
| `Variable` | `<Variable>` | Data variable |
| `ConceptualVariable` | `<ConceptualVariable>` | Conceptual variable definition |
| `RepresentedVariable` | `<RepresentedVariable>` | Variable with a value representation |
| `RepresentedVariableGroup` | `<RepresentedVariableGroup>` | Group of represented variables |
| `RepresentedVariableScheme` | `<RepresentedVariableScheme>` | Container for represented variables |
| `VariableGroup` | `<VariableGroup>` | Group of related variables |
| `VariableScheme` | `<VariableScheme>` | Container for variables |

### Codes and Categories

| Node Label | DDI-L Element | Description |
| ------------ | --------------- | ------------- |
| `CodeList` | `<CodeList>` | List of response codes |
| `Category` | `<Category>` | One category within a code list |
| `CategoryScheme` | `<CategoryScheme>` | Container for categories |
| `CategoryGroup` | `<CategoryGroup>` | Group of related categories |
| `CodeListScheme` | `<CodeListScheme>` | Container for code lists |
| `NCubeScheme` | `<NCubeScheme>` | Container for n-dimensional data cubes |

### Statistical Classifications

| Node Label | DDI-L Element | Description |
| ------------ | --------------- | ------------- |
| `ClassificationFamily` | `<ClassificationFamily>` | Family of related statistical classifications |
| `StatisticalClassification` | `<StatisticalClassification>` | A statistical classification system |
| `ClassificationItem` | `<ClassificationItem>` | One item within a classification |

### Concepts and Conceptual Components

| Node Label | DDI-L Element | Description |
| ------------ | --------------- | ------------- |
| `Concept` | `<Concept>` | A conceptual definition |
| `ConceptScheme` | `<ConceptScheme>` | Container for concepts |
| `ConceptGroup` | `<ConceptGroup>` | Group of related concepts |
| `ConceptualVariableScheme` | `<ConceptualVariableScheme>` | Container for conceptual variables |
| `ConceptualVariableGroup` | `<ConceptualVariableGroup>` | Group of conceptual variables |

### Universe and Geography

| Node Label | DDI-L Element | Description |
| ------------ | --------------- | ------------- |
| `Universe` | `<Universe>` | A population or universe definition |
| `UniverseScheme` | `<UniverseScheme>` | Container for universes |
| `UniverseGroup` | `<UniverseGroup>` | Group of related universes |
| `GeographicStructure` | `<GeographicStructure>` | Geographic classification structure |
| `GeographicStructureScheme` | `<GeographicStructureScheme>` | Container for geographic structures |
| `GeographicLocation` | `<GeographicLocation>` | A specific geographic location |
| `GeographicLocationScheme` | `<GeographicLocationScheme>` | Container for geographic locations |

### Unit Types

| Node Label | DDI-L Element | Description |
| ------------ | --------------- | ------------- |
| `UnitType` | `<UnitType>` | Type of unit being observed or measured |
| `UnitTypeScheme` | `<UnitTypeScheme>` | Container for unit types |
| `UnitTypeGroup` | `<UnitTypeGroup>` | Group of unit types |

### Study and Data Management

| Node Label | DDI-L Element | Description |
| ------------ | --------------- | ------------- |
| `StudyUnit` | `<StudyUnit>` | Study or survey metadata |
| `DataCollection` | `<DataCollection>` | Data collection process metadata |
| `DataCollectionMethodology` | `<DataCollectionMethodology>` | Collection methodology details |
| `SamplingProcedure` | `<SamplingProcedure>` | Sampling procedure description |
| `DevelopmentActivity` | `<DevelopmentActivity>` | A design or development activity |
| `Methodology` | `<Methodology>` | Methodology description |
| `ResourcePackage` | `<ResourcePackage>` | Package of reusable DDI resources |
| `PhysicalInstance` | `<PhysicalInstance>` | Reference to a physical data file |
| `DataRelationship` | `<DataRelationship>` | Relationship between data elements |
| `LogicalRecord` | `<LogicalRecord>` | Logical record layout |
| `RecordLayout` | `<RecordLayout>` | Physical record layout description |
| `OtherMaterial` | `<OtherMaterial>` | Reference to supplementary material |

### Module-Level Wrappers

These node types act as top-level containers that hold groups of related DDI content.

| Node Label | DDI-L Element | Description |
| ------------ | --------------- | ------------- |
| `ConceptualComponent` | `<ConceptualComponent>` | Module grouping conceptual content |
| `LogicalProduct` | `<LogicalProduct>` | Module grouping logical product content |
| `PhysicalDataProduct` | `<PhysicalDataProduct>` | Module grouping physical data content |
| `Archive` | `<Archive>` | Module grouping archive content |
| `DDIProfile` | `<DDIProfile>` | Profile defining which DDI elements are used |
| `LocalHoldingPackage` | `<LocalHoldingPackage>` | Local holding of DDI resources |

### Archive and Organisation

| Node Label | DDI-L Element | Description |
| ------------ | --------------- | ------------- |
| `Individual` | `<Individual>` | A named person in the archive |
| `Collection` | `<Collection>` | An archival collection |
| `Access` | `<Access>` | Access conditions and restrictions |

## Relationship Types

Relationships are derived from DDI-L `*Reference` elements. The most commonly used types are
listed below; the full mapping is in `DDISchema.FRAGMENT_RELATIONSHIP_TYPES`.

### Control Flow

| Reference Element | Relationship | Description |
| ------------------- | ------------ | ------------- |
| `ControlConstructReference` | `HAS_CONSTRUCT` | Sequence or instrument contains a construct |
| `ThenConstructReference` | `THEN` | IfThenElse true branch |
| `ElseConstructReference` | `ELSE` | IfThenElse false branch |
| `UntilConstructReference` | `UNTIL` | RepeatUntil loop body |
| `WhileConstructReference` | `WHILE` | RepeatWhile loop body |

### Questions, Codes, and Categories

| Reference Element | Relationship | Description |
| ------------------- | ------------ | ------------- |
| `QuestionItemReference` | `ASKS_QUESTION` | Construct asks a question |
| `QuestionGridReference` | `ASKS_QUESTION` | Construct asks a question grid |
| `QuestionBlockReference` | `ASKS_QUESTION` | Construct uses a question block |
| `CodeListReference` | `USES_CODELIST` | Question uses a code list |
| `CategoryReference` | `HAS_CATEGORY` | Code list contains a category |

### Variables, Concepts, and Universe

| Reference Element | Relationship | Description |
| ------------------- | ------------ | ------------- |
| `VariableReference` | `REFERENCES_VARIABLE` | Reference to a variable |
| `RepresentedVariableReference` | `USES_REPRESENTED_VARIABLE` | Reference to a represented variable |
| `ConceptReference` | `USES_CONCEPT` | Reference to a concept |
| `UniverseReference` | `IN_UNIVERSE` | Object belongs to a universe |
| `BasedOnReference` | `BASED_ON` | Object is derived from another |
| `ValueDomainReference` | `HAS_VALUE_DOMAIN` | Object has a value domain |

### Scheme Containment

These relationships link individual DDI objects to the scheme that contains them.

| Reference Element | Relationship | Description |
| ------------------- | ------------ | ------------- |
| `QuestionSchemeReference` | `IN_QUESTION_SCHEME` | Question belongs to a question scheme |
| `ControlConstructSchemeReference` | `IN_CONTROL_CONSTRUCT_SCHEME` | Construct belongs to a control construct scheme |
| `InstrumentSchemeReference` | `IN_INSTRUMENT_SCHEME` | Instrument belongs to an instrument scheme |
| `CodeListSchemeReference` | `IN_CODELIST_SCHEME` | Code list belongs to a code list scheme |
| `VariableSchemeReference` | `IN_VARIABLE_SCHEME` | Variable belongs to a variable scheme |
| `ConceptSchemeReference` | `IN_CONCEPT_SCHEME` | Concept belongs to a concept scheme |
| `UniverseSchemeReference` | `IN_UNIVERSE_SCHEME` | Universe belongs to a universe scheme |
| `GeographicStructureSchemeReference` | `IN_GEOGRAPHIC_STRUCTURE_SCHEME` | Geographic structure belongs to a scheme |
| `GeographicLocationSchemeReference` | `IN_GEOGRAPHIC_LOCATION_SCHEME` | Geographic location belongs to a scheme |
| `UnitTypeSchemeReference` | `IN_UNIT_TYPE_SCHEME` | Unit type belongs to a unit type scheme |
| `ClassificationFamilyReference` | `IN_CLASSIFICATION_FAMILY` | Classification belongs to a family |

### Parameter Flow

| Reference Element | Relationship | Description |
| ------------------- | ------------ | ------------- |
| `SourceParameterReference` | `SOURCE_PARAM` | Parameter data source |
| `TargetParameterReference` | `TARGET_PARAM` | Parameter data target |
| `InParameterReference` | `IN_PARAM` | Input parameter |
| `OutParameterReference` | `OUT_PARAM` | Output parameter |

Any unrecognized `*Reference` element is converted to an uppercase relationship type by removing
the "Reference" suffix. For example, `CustomReference` becomes `CUSTOM`.

## Node Properties

Each fragment node includes:

| Property | Description |
| ---------- | ------------- |
| `fragment_id` | Unique identifier (from `<ID>` element) |
| `agency` | Maintaining agency (from `<Agency>` element) |
| `version` | Version string (from `<Version>` element) |
| `urn` | Full DDI URN if present |
| `label` | Human-readable label (from `<Label>` element) |
| `name` | Element name (element-type-specific) |

### Type-Specific Properties

| Node Type | Additional Properties |
| ----------- | ---------------------- |
| `CodeList` | `code_count` - number of codes |
| `Category` | `category_label` - category name |
| `QuestionItem` | `question_text` - question text (truncated to 1000 chars) |
| `IfThenElse` | `condition` - condition expression (truncated to 500 chars) |
| `Sequence` | `construct_count` - number of child constructs |

## Entry Point Marking

The fragment at `<TopLevelReference>` receives an additional `EntryPoint` label, making it easy
to find the survey instrument's starting point:

```cypher
MATCH (n:EntryPoint)
RETURN n
```

## Schema Bootstrap

Before loading FragmentInstance files, ensure the schema is created:

```bash
# Codebook + DDI-L FragmentInstance (default)
ddigraph bootstrap
```

This creates:

- **Unique constraints** on `fragment_id` for each node type
- **Secondary indexes** on `name`, `label`, and type-specific fields

## Performance

The FragmentInstance loader uses streaming and batched writes:

| Aspect | Implementation |
| -------- | ---------------- |
| Parsing | Streaming `iterparse` - memory bounded |
| Batching | Groups fragments by type |
| Writes | UNWIND-based Cypher |
| Async | Full async with `AsyncDriver` |
| Retry | Exponential backoff with jitter |

For a 148K-line DDI-L file with 2,762 fragments:

| Metric | Value |
| -------- | ------- |
| Neo4j queries | ~30 |
| Memory usage | O(chunk_size) |
| Async operations | All writes |

## Configuration

The same settings apply to both loaders:

```bash
# Adjust batch size
ddigraph load questionnaire.xml --chunk-size 300

# Enable dry-run validation
ddigraph load questionnaire.xml --dry-run

# Clear existing fragments before loading
ddigraph load questionnaire.xml --replace

# Full verbose output
ddigraph load questionnaire.xml --log-level DEBUG --batch-metrics --json
```

## Example Queries

After loading, explore the graph:

```cypher
-- Find all instruments
MATCH (i:Instrument)
RETURN i.fragment_id, i.name, i.label
-- Trace questionnaire flow from entry point
MATCH path = (entry:EntryPoint)-[:HAS_CONSTRUCT*1..5]->(construct)
RETURN path
-- Find questions with their code lists
MATCH (qc:QuestionConstruct)-[:ASKS_QUESTION]->(q:QuestionItem)
OPTIONAL MATCH (q)-[:USES_CODELIST]->(cl:CodeList)
RETURN q.name, q.question_text, cl.name, cl.code_count
-- Count constructs by type in a sequence
MATCH (s:Sequence)-[:HAS_CONSTRUCT]->(c)
RETURN s.name, labels(c)[0] AS construct_type, count(*) AS count
ORDER BY s.name, count DESC
-- Find conditional branches
MATCH (ite:IfThenElse)-[:THEN]->(then_branch)
OPTIONAL MATCH (ite)-[:ELSE]->(else_branch)
RETURN ite.condition, then_branch.fragment_id, else_branch.fragment_id
```

## Worked Example: Ireland Labour Survey

The Ireland Labour Force Survey (`Ireland_LabourSurvey.xml`) is a real-world DDI-L file with:

- 148,479 lines of XML
- 2,762 fragments
- 1 Instrument, 388 Sequences, 376 QuestionConstructs, 373 QuestionItems
- 357 IfThenElse branching constructs
- 196 CodeLists with 1,065 Categories

Loading this file:

```bash
ddigraph bootstrap
ddigraph load Ireland_LabourSurvey.xml --json
```

Output:

```json
{
  "Instrument": 1,
  "Sequence": 388,
  "IfThenElse": 357,
  "QuestionConstruct": 376,
  "QuestionItem": 373,
  "CodeList": 196,
  "Category": 1065,
  "relationships": 767,
  "batches": 14
}
```

## API Reference

### `DDIFragmentLoader`

```python
class DDIFragmentLoader:
    def __init__(
        self,
        driver: Driver | AsyncDriver,
        settings: Settings | None = None,
        *,
        metrics: MetricsEmitter | None = None,
    ): ...
    async def load(
        self,
        path: Path | str,
        *,
        clear_first: bool | None = None,
    ) -> dict[str, int]: ...
```

### `DDIFragmentParser`

```python
class DDIFragmentParser:
    def __init__(
        self,
        path: Path,
        *,
        chunk_size: int = 200,
        metrics: MetricsEmitter | None = None,
        recover: bool = True,
    ): ...
    def parse_batches(self) -> Iterator[FragmentBatch]: ...
```

### `detect_ddi_format`

```python
def detect_ddi_format(path: Path | str) -> str:
    """Returns 'codebook' or 'lifecycle'."""
```

## Limitations

Current limitations of the FragmentInstance loader:

1. **No cross-file references**: References to fragments in other files are not resolved
2. **Deferred relationship resolution**: Only relationships between fragments in the same file
   are created
3. **Limited property extraction**: Not all DDI-L elements have specialized property extraction

Future versions may address these limitations.
