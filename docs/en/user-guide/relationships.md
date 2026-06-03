# Graph Relationships and Reference Fields

ddigraph creates relationships in Neo4j from the DDI XML structure. The relationship
types differ between the DDI Codebook and DDI-L FragmentInstance formats. A
relationship is a labeled link between two graph nodes.

## DDI Codebook Relationships

The Codebook loader reads relationship types from `DDI_RELATIONSHIPS` in
`ddigraph.schema.ddi_graph`. Each entry holds:

- **Relationship type**: Neo4j relationship label
- **Start/End labels**: Graph node labels
- **Reference field**: Property used for lookups
- **Lookup field**: Optional embedded reference value

### Dataset-Scoped Relationships

Most entities attach to a Dataset via `IN_DATASET`:

| Relationship | Start Label | End Label | Description |
| -------------- | ------------- | ----------- | ------------- |
| `IN_DATASET` | Various | Dataset | Entity belongs to dataset |
| `DESCRIBES` | Study | Dataset | Study describes dataset |
| `DESCRIBES` | Citation | Dataset | Citation describes dataset |
| `ASSOCIATED_WITH` | Organization | Dataset | Organization associated |
| `COVERS` | Coverage | Dataset | Geographic/temporal coverage |
| `FUNDS` | Funding | Dataset | Funding source |
| `CONTRIBUTES_TO` | Contributor | Dataset | Contributor role |
| `INSTRUMENT_FOR` | CollectionInstrument | Dataset | Collection instrument |
| `USES_CONSTRUCT` | ControlConstruct | Dataset | Control construct usage |
| `REPRESENTS` | RepresentedVariable | Dataset | Variable representation |
| `HAS_COMPARISON` | Comparison | Dataset | Comparison information |
| `GOVERNED_BY` | AccessPolicy | Dataset | Access policy |

### Cross-Entity Relationships

| Relationship | Start Label | End Label | Lookup Field |
| -------------- | ------------- | ----------- | -------------- |
| `IN_SCHEME` | Category | CodeScheme | `code_scheme_id` |
| `USES_CONCEPT` | Variable | Concept | `concept` |
| `IN_FILE` | Variable | DataFile | `file_id` |
| `IN_UNIVERSE` | Variable | Universe | `universe_id` |
| `ASKED_AS` | Variable | Question | `question_id` |
| `USES_CATEGORY` | Variable | Category | `category_ids` |
| `USES_QUESTION_ITEM` | Variable | QuestionItem | - |
| `PART_OF` | QuestionItem | Question | `parent_question_id` |
| `IN_GRID` | QuestionItem | QuestionGrid | `parent_grid_id` |
| `IN_FLOW` | QuestionItem | QuestionFlow | `parent_flow_id` |
| `GROUPS` | VarGroup | Variable | `variable_ids` |
| `GROUPS` | CategoryGroup | Category | `category_ids` |
| `USES_CONSTRUCT` | CollectionInstrument | ControlConstruct | `referenced_construct_id` |
| `USES_CONCEPT` | RepresentedVariable | Concept | `concept` |

### DDI-C 2.6 Relationships

DDI Codebook 2.6 adds more entity types. These come with new relationships:

| Relationship | Start Label | End Label | Description |
| -------------- | ------------- | ----------- | ------------- |
| `IN_DATASET` | NCube | Dataset | N-dimensional data cube in dataset |
| `IN_DATASET` | NCubeGroup | Dataset | N-cube group in dataset |
| `IN_DATASET` | DocumentDescription | Dataset | Document description in dataset |
| `IN_DATASET` | SampleFrame | Dataset | Sample frame in dataset |
| `IN_DATASET` | QualityStatement | Dataset | Quality statement in dataset |
| `IN_DATASET` | StudyAuthorization | Dataset | Study authorization in dataset |
| `IN_DATASET` | StudyDevelopment | Dataset | Study development in dataset |
| `IN_DATASET` | ExPostEvaluation | Dataset | Ex-post evaluation in dataset |
| `GROUPS` | NCubeGroup | NCube | NCubeGroup groups NCube entities |

## DDI-L FragmentInstance Relationships

A fragment is a reusable, self-contained DDI object. The FragmentInstance loader
builds relationships from `*Reference` elements in the XML. The mapping lives in
`DDISchema.FRAGMENT_RELATIONSHIP_TYPES`:

### Control Flow Relationships

| Reference Element | Relationship | Description |
| ------------------- | -------------- | ------------- |
| `ControlConstructReference` | `HAS_CONSTRUCT` | Sequence/Instrument contains construct |
| `ThenConstructReference` | `THEN` | IfThenElse true branch |
| `ElseConstructReference` | `ELSE` | IfThenElse false branch |
| `ElseIf/ThenConstructReference` | `ELSE_IF` | IfThenElse else-if branch |
| `UntilConstructReference` | `UNTIL` | RepeatUntil loop body |
| `WhileConstructReference` | `WHILE` | RepeatWhile loop body |
| `LoopVariableReference` | `LOOP_VARIABLE` | Loop iteration variable |

### Code/Category Relationships

| Reference Element | Relationship | Description |
| ------------------- | -------------- | ------------- |
| `CodeListReference` | `USES_CODELIST` | Question uses code list |
| `CategoryReference` | `HAS_CATEGORY` | CodeList contains category |

### Question Relationships

| Reference Element | Relationship | Description |
| ------------------- | -------------- | ------------- |
| `QuestionReference` | `ASKS_QUESTION` | Construct asks question |
| `QuestionItemReference` | `ASKS_QUESTION` | Reference to question item |
| `QuestionGridReference` | `ASKS_QUESTION` | Reference to question grid |
| `QuestionBlockReference` | `ASKS_QUESTION` | Reference to question block |

### Measurement Relationships

| Reference Element | Relationship | Description |
| ------------------- | -------------- | ------------- |
| `MeasurementReference` | `USES_MEASUREMENT` | Construct uses measurement |
| `MeasurementItemReference` | `USES_MEASUREMENT` | Reference to measurement item |

### Instruction Relationships

| Reference Element | Relationship | Description |
| ------------------- | -------------- | ------------- |
| `InterviewerInstructionReference` | `HAS_INSTRUCTION` | Interviewer instruction |
| `InstructionReference` | `HAS_INSTRUCTION` | General instruction |

### Variable Relationships

| Reference Element | Relationship | Description |
| ------------------- | -------------- | ------------- |
| `VariableReference` | `REFERENCES_VARIABLE` | Variable reference |
| `RepresentedVariableReference` | `USES_REPRESENTED_VARIABLE` | Represented variable |
| `AssignedVariableReference` | `ASSIGNS_VARIABLE` | Variable assignment |

### Parameter Flow Relationships

| Reference Element | Relationship | Description |
| ------------------- | -------------- | ------------- |
| `SourceParameterReference` | `SOURCE_PARAM` | Parameter data source |
| `TargetParameterReference` | `TARGET_PARAM` | Parameter data target |
| `InParameterReference` | `IN_PARAM` | Input parameter |
| `OutParameterReference` | `OUT_PARAM` | Output parameter |

### Other Relationships

| Reference Element | Relationship | Description |
| ------------------- | -------------- | ------------- |
| `BasedOnReference` | `BASED_ON` | Derivation source |
| `UniverseReference` | `IN_UNIVERSE` | Population reference |
| `ConceptReference` | `USES_CONCEPT` | Concept reference |
| `InstrumentReference` | `USES_INSTRUMENT` | Instrument reference |
| `ValueDomainReference` | `HAS_VALUE_DOMAIN` | Value domain |
| `ManagedRepresentationReference` | `HAS_REPRESENTATION` | Representation |

### Scheme Containment Relationships

A scheme is a named container that holds related DDI objects of one kind. These
relationships link each object back to its scheme. So you can find every member of
a scheme in one query.

| Reference Element | Relationship | Description |
| ------------------- | -------------- | ------------- |
| `QuestionSchemeReference` | `IN_QUESTION_SCHEME` | Question belongs to a question scheme |
| `ControlConstructSchemeReference` | `IN_CONTROL_CONSTRUCT_SCHEME` | Construct belongs to a control construct scheme |
| `InstrumentSchemeReference` | `IN_INSTRUMENT_SCHEME` | Instrument belongs to an instrument scheme |
| `InterviewerInstructionSchemeReference` | `IN_INSTRUCTION_SCHEME` | Instruction belongs to an instruction scheme |
| `ProcessingEventSchemeReference` | `IN_PROCESSING_EVENT_SCHEME` | Processing event belongs to a processing event scheme |
| `ProcessingInstructionSchemeReference` | `IN_PROCESSING_INSTRUCTION_SCHEME` | Processing instruction belongs to its scheme |
| `DevelopmentActivitySchemeReference` | `IN_DEVELOPMENT_ACTIVITY_SCHEME` | Development activity belongs to its scheme |
| `MeasurementSchemeReference` | `IN_MEASUREMENT_SCHEME` | Measurement item belongs to a measurement scheme |
| `SamplingInformationSchemeReference` | `IN_SAMPLING_INFORMATION_SCHEME` | Sampling information belongs to its scheme |
| `CodeListSchemeReference` | `IN_CODELIST_SCHEME` | Code list belongs to a code list scheme |
| `VariableSchemeReference` | `IN_VARIABLE_SCHEME` | Variable belongs to a variable scheme |
| `ConceptSchemeReference` | `IN_CONCEPT_SCHEME` | Concept belongs to a concept scheme |
| `UniverseSchemeReference` | `IN_UNIVERSE_SCHEME` | Universe belongs to a universe scheme |
| `ConceptualVariableSchemeReference` | `IN_CONCEPTUAL_VARIABLE_SCHEME` | Conceptual variable belongs to its scheme |
| `GeographicStructureSchemeReference` | `IN_GEOGRAPHIC_STRUCTURE_SCHEME` | Geographic structure belongs to its scheme |
| `GeographicLocationSchemeReference` | `IN_GEOGRAPHIC_LOCATION_SCHEME` | Geographic location belongs to its scheme |
| `UnitTypeSchemeReference` | `IN_UNIT_TYPE_SCHEME` | Unit type belongs to a unit type scheme |
| `ClassificationFamilyReference` | `IN_CLASSIFICATION_FAMILY` | Classification belongs to a classification family |
| `OrganizationReference` | `REFERENCES_ORGANIZATION` | Reference to an organization |
| `IndividualReference` | `REFERENCES_INDIVIDUAL` | Reference to a named individual |
| `SamplingProcedureReference` | `USES_SAMPLING_PROCEDURE` | Object uses a sampling procedure |

### Fallback Behavior

ddigraph turns any unknown `*Reference` element into a relationship type. It does
this by:

1. Stripping the "Reference" suffix
2. Converting to uppercase

For example, `CustomReference` → `CUSTOM`

## Schema Definition Access

You can reach the relationship definitions through the `DDISchema` class:

```python
from ddigraph.schema import DDISchema

# Get relationship type for a reference element
rel_type = DDISchema.get_fragment_relationship_type("ControlConstructReference")
# Returns: "HAS_CONSTRUCT"

# View all fragment relationship mappings
print(DDISchema.FRAGMENT_RELATIONSHIP_TYPES)
```

## Worked Examples

### Ireland Labour Survey (DDI-L FragmentInstance)

The `Ireland_LabourSurvey.xml` file shows typical DDI-L relationships:

**Control construct linkage:**

```xml
<Instrument>
  <ID>e274cbba-78ea-4a7b-bf06-e6fef1e570e1</ID>
  <ControlConstructReference>
    <ID>cdbc61f8-5a7d-4c04-bf3a-75eaf9f919ab</ID>
    <TypeOfObject>Sequence</TypeOfObject>
  </ControlConstructReference>
</Instrument>
```

Creates: `(Instrument)-[:HAS_CONSTRUCT]->(Sequence)`

**Question/CodeList linkage:**

```xml
<QuestionItem>
  <ID>97cb6944-1704-483a-b32d-3e4965bd25aa</ID>
  <CodeListReference>
    <ID>20a3c76d-a966-4c32-a908-83f8a2ba341d</ID>
    <TypeOfObject>CodeList</TypeOfObject>
  </CodeListReference>
</QuestionItem>
```

Creates: `(QuestionItem)-[:USES_CODELIST]->(CodeList)`

**Conditional branching:**

```xml
<IfThenElse>
  <ID>conditional-123</ID>
  <ThenConstructReference>
    <ID>sequence-then</ID>
    <TypeOfObject>Sequence</TypeOfObject>
  </ThenConstructReference>
  <ElseConstructReference>
    <ID>sequence-else</ID>
    <TypeOfObject>Sequence</TypeOfObject>
  </ElseConstructReference>
</IfThenElse>
```

Creates:

- `(IfThenElse)-[:THEN]->(Sequence)`
- `(IfThenElse)-[:ELSE]->(Sequence)`

## Querying Relationships

### DDI Codebook Queries

```cypher
-- Find all variables in a dataset
MATCH (d:Dataset {id: 'demo'})<-[:IN_DATASET]-(v:Variable)
RETURN v.name, v.label
-- Variables with their concepts
MATCH (v:Variable)-[:USES_CONCEPT]->(c:Concept)
RETURN v.name, c.name
-- Questions grouped by variable
MATCH (v:Variable)-[:ASKED_AS]->(q:Question)
RETURN v.name, q.text
```

### DDI-L FragmentInstance Queries

```cypher
-- Trace questionnaire flow
MATCH path = (i:Instrument)-[:HAS_CONSTRUCT*1..5]->(c)
RETURN path
-- Find conditional branches
MATCH (ite:IfThenElse)-[:THEN]->(then_branch)
OPTIONAL MATCH (ite)-[:ELSE]->(else_branch)
RETURN ite.fragment_id, then_branch.fragment_id, else_branch.fragment_id
-- Questions with their code lists
MATCH (qc:QuestionConstruct)-[:ASKS_QUESTION]->(q:QuestionItem)
       -[:USES_CODELIST]->(cl:CodeList)
RETURN q.name, q.question_text, cl.name
-- All categories in a code list
MATCH (cl:CodeList)-[:HAS_CATEGORY]->(cat:Category)
RETURN cl.name, collect(cat.category_label) AS categories
```

## Relationship Statistics

After loading `Ireland_LabourSurvey.xml`:

```cypher
-- Count relationships by type
MATCH ()-[r]->()
RETURN type(r) AS relationship_type, count(*) AS count
ORDER BY count DESC
```

Typical output:

| Relationship Type | Count |
| ------------------- | ------- |
| HAS_CONSTRUCT | 450 |
| USES_CODELIST | 180 |
| HAS_CATEGORY | 120 |
| ASKS_QUESTION | 17 |

## DDI-CDI 1.0 Relationships

The CDI loader reads relationships from association elements in DDI-CDI XML files.
These relationships connect the 210 concrete top-level CDI entity types. (This count
does not include associations.) The table below lists the relationship types that
get their own labels. Other association elements pass through the generic-entity
path instead.

| Relationship | Start Label | End Label | Description |
| -------------- | ------------- | ----------- | ------------- |
| `HAS_CONCEPT` | ConceptualVariable | Concept | Variable uses concept |
| `MEASURES` | InstanceVariable | ConceptualVariable | Instance measures conceptual variable |
| `HAS_CATEGORY` | CodeList | Category | Code list contains category |
| `HAS_CODE` | CodeList | Code | Code list contains code |
| `DENOTES` | Code | Category | Code denotes category |
| `HAS_CLASSIFICATION_ITEM` | StatisticalClassification | ClassificationItem | Classification contains item |
| `HAS_COMPONENT` | WideDataStructure | InstanceVariable | Structure has component variable |
| `IS_STRUCTURED_BY` | WideDataSet | WideDataStructure | Dataset is structured by structure |
| `HAS_LOGICAL_RECORD` | WideDataSet | LogicalRecord | Dataset has logical record |
| `CORRESPONDS_TO` | RepresentedVariable | ConceptualVariable | Represented variable corresponds to conceptual variable |
| `PERFORMS` | Agent | Activity | Agent performs activity |
| `MAPS_TO` | CorrespondenceTable | ClassificationItem | Correspondence table maps to classification item |
| `IS_BASED_ON` | RepresentedVariable | ConceptualVariable | Represented variable is derived from a conceptual variable |
| `IS_BASED_ON` | InstanceVariable | RepresentedVariable | Instance variable is derived from a represented variable |
| `TAKES_CONCEPT_FROM` | ConceptualVariable | Concept | Conceptual variable takes its concept from |
| `HAS_POPULATION` | Universe | Population | Universe includes this population |
| `IS_DEFINED_BY` | DataStructureComponent | InstanceVariable | Data structure component is defined by a variable |
| `HAS_SENTINEL_VALUE` | ValueDomain | Category | Value domain has a sentinel or missing value |
| `USES` | Activity | Activity | One activity uses or depends on another activity |
| `HAS_DATA_STORE` | DataSet | DataStore | Dataset contains a data store |

### CDI Relationship Queries

```cypher
-- Find all variables measuring a concept
MATCH (iv:InstanceVariable)-[:MEASURES]->(cv:ConceptualVariable)-[:HAS_CONCEPT]->(c:Concept)
RETURN iv.name, cv.name, c.name

-- Explore dataset structure
MATCH (ds:WideDataSet)-[:IS_STRUCTURED_BY]->(str:WideDataStructure)
       -[:HAS_COMPONENT]->(iv:InstanceVariable)
RETURN ds.name, str.name, collect(iv.name) AS variables

-- Classification hierarchy
MATCH (sc:StatisticalClassification)-[:HAS_CLASSIFICATION_ITEM]->(ci:ClassificationItem)
RETURN sc.name, ci.name
```

See [Architecture](architecture.md) to learn how relationships flow through the
ingestion pipeline.
