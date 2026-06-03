# Modèle relationnel et champs de référence

ddigraph crée des relations dans Neo4j en se basant sur la structure XML DDI. Les types de
relations diffèrent entre les formats DDI Codebook et DDI-L FragmentInstance.

## Relations DDI Codebook

Le chargeur Codebook dérive les types de relations à partir de `DDI_RELATIONSHIPS` défini dans
`ddigraph.schema.ddi_graph`. Chaque entrée capture :

- **Type de relation** : label de la relation Neo4j
- **Labels début/fin** : labels des nœuds du graphe
- **Champ de référence** : propriété utilisée pour les recherches
- **Champ de recherche** : valeur de référence intégrée optionnelle

### Relations au niveau du jeu de données

La plupart des entités sont rattachées à un Dataset via `IN_DATASET` :

| Relation | Label de départ | Label d'arrivée | Description |
| ---------- | ----------------- | ----------------- | ------------- |
| `IN_DATASET` | Divers | Dataset | L'entité appartient au jeu de données |
| `DESCRIBES` | Study | Dataset | L'étude décrit le jeu de données |
| `DESCRIBES` | Citation | Dataset | La citation décrit le jeu de données |
| `ASSOCIATED_WITH` | Organization | Dataset | Organisation associée |
| `COVERS` | Coverage | Dataset | Couverture géographique/temporelle |
| `FUNDS` | Funding | Dataset | Source de financement |
| `CONTRIBUTES_TO` | Contributor | Dataset | Rôle de contributeur |
| `INSTRUMENT_FOR` | CollectionInstrument | Dataset | Instrument de collecte |
| `USES_CONSTRUCT` | ControlConstruct | Dataset | Utilisation de construit de contrôle |
| `REPRESENTS` | RepresentedVariable | Dataset | Représentation de variable |
| `HAS_COMPARISON` | Comparison | Dataset | Information de comparaison |
| `GOVERNED_BY` | AccessPolicy | Dataset | Politique d'accès |

### Relations inter-entités

| Relation | Label de départ | Label d'arrivée | Champ de recherche |
| ---------- | ----------------- | ----------------- | -------------------- |
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

### Relations DDI-C 2.6

DDI Codebook 2.6 introduit des types d'entités supplémentaires avec de nouvelles relations :

| Relation | Label de départ | Label d'arrivée | Description |
| ---------- | ----------------- | ----------------- | ------------- |
| `IN_DATASET` | NCube | Dataset | Cube de données N-dimensionnel dans le jeu de données |
| `IN_DATASET` | NCubeGroup | Dataset | Groupe de nCubes dans le jeu de données |
| `IN_DATASET` | DocumentDescription | Dataset | Description de document dans le jeu de données |
| `IN_DATASET` | SampleFrame | Dataset | Cadre d'échantillonnage dans le jeu de données |
| `IN_DATASET` | QualityStatement | Dataset | Déclaration de qualité dans le jeu de données |
| `IN_DATASET` | StudyAuthorization | Dataset | Autorisation d'étude dans le jeu de données |
| `IN_DATASET` | StudyDevelopment | Dataset | Développement d'étude dans le jeu de données |
| `IN_DATASET` | ExPostEvaluation | Dataset | Évaluation ex-post dans le jeu de données |
| `GROUPS` | NCubeGroup | NCube | NCubeGroup regroupe les entités NCube |

## Relations DDI-L FragmentInstance

Le chargeur FragmentInstance dérive les relations à partir des éléments `*Reference` du XML.
La correspondance est définie dans `DDISchema.FRAGMENT_RELATIONSHIP_TYPES` :

### Relations de flux de contrôle

| Élément de référence | Relation | Description |
| ---------------------- | ---------- | ------------- |
| `ControlConstructReference` | `HAS_CONSTRUCT` | La séquence/l'instrument contient un construit |
| `ThenConstructReference` | `THEN` | Branche vraie de IfThenElse |
| `ElseConstructReference` | `ELSE` | Branche fausse de IfThenElse |
| `ElseIf/ThenConstructReference` | `ELSE_IF` | Branche sinon-si de IfThenElse |
| `UntilConstructReference` | `UNTIL` | Corps de la boucle RepeatUntil |
| `WhileConstructReference` | `WHILE` | Corps de la boucle RepeatWhile |
| `LoopVariableReference` | `LOOP_VARIABLE` | Variable d'itération de boucle |

### Relations code/catégorie

| Élément de référence | Relation | Description |
| ---------------------- | ---------- | ------------- |
| `CodeListReference` | `USES_CODELIST` | La question utilise une liste de codes |
| `CategoryReference` | `HAS_CATEGORY` | La CodeList contient une catégorie |

### Relations de questions

| Élément de référence | Relation | Description |
| ---------------------- | ---------- | ------------- |
| `QuestionReference` | `ASKS_QUESTION` | Le construit pose une question |
| `QuestionItemReference` | `ASKS_QUESTION` | Référence à un item de question |
| `QuestionGridReference` | `ASKS_QUESTION` | Référence à une grille de questions |
| `QuestionBlockReference` | `ASKS_QUESTION` | Référence à un bloc de questions |

### Relations de mesure

| Élément de référence | Relation | Description |
| ---------------------- | ---------- | ------------- |
| `MeasurementReference` | `USES_MEASUREMENT` | Le construit utilise une mesure |
| `MeasurementItemReference` | `USES_MEASUREMENT` | Référence à un item de mesure |

### Relations d'instructions

| Élément de référence | Relation | Description |
| ---------------------- | ---------- | ------------- |
| `InterviewerInstructionReference` | `HAS_INSTRUCTION` | Instruction pour l'enquêteur |
| `InstructionReference` | `HAS_INSTRUCTION` | Instruction générale |

### Relations de variables

| Élément de référence | Relation | Description |
| ---------------------- | ---------- | ------------- |
| `VariableReference` | `REFERENCES_VARIABLE` | Référence de variable |
| `RepresentedVariableReference` | `USES_REPRESENTED_VARIABLE` | Variable représentée |
| `AssignedVariableReference` | `ASSIGNS_VARIABLE` | Affectation de variable |

### Relations de flux de paramètres

| Élément de référence | Relation | Description |
| ---------------------- | ---------- | ------------- |
| `SourceParameterReference` | `SOURCE_PARAM` | Source des données du paramètre |
| `TargetParameterReference` | `TARGET_PARAM` | Cible des données du paramètre |
| `InParameterReference` | `IN_PARAM` | Paramètre d'entrée |
| `OutParameterReference` | `OUT_PARAM` | Paramètre de sortie |

### Autres relations

| Élément de référence | Relation | Description |
| ---------------------- | ---------- | ------------- |
| `BasedOnReference` | `BASED_ON` | Source de dérivation |
| `UniverseReference` | `IN_UNIVERSE` | Référence de population |
| `ConceptReference` | `USES_CONCEPT` | Référence de concept |
| `InstrumentReference` | `USES_INSTRUMENT` | Référence d'instrument |
| `ValueDomainReference` | `HAS_VALUE_DOMAIN` | Domaine de valeurs |
| `ManagedRepresentationReference` | `HAS_REPRESENTATION` | Représentation |

### Relations d'appartenance aux schémas

Ces relations rattachent chaque objet DDI au schéma qui le contient, facilitant les requêtes
sur l'ensemble des membres d'un schéma.

| Élément de référence | Relation | Description |
| ---------------------- | ---------- | ------------- |
| `QuestionSchemeReference` | `IN_QUESTION_SCHEME` | La question appartient à un schéma de questions |
| `ControlConstructSchemeReference` | `IN_CONTROL_CONSTRUCT_SCHEME` | Le construit appartient à un schéma de construits |
| `InstrumentSchemeReference` | `IN_INSTRUMENT_SCHEME` | L'instrument appartient à un schéma d'instruments |
| `InterviewerInstructionSchemeReference` | `IN_INSTRUCTION_SCHEME` | L'instruction appartient à un schéma d'instructions |
| `ProcessingEventSchemeReference` | `IN_PROCESSING_EVENT_SCHEME` | L'événement de traitement appartient à son schéma |
| `ProcessingInstructionSchemeReference` | `IN_PROCESSING_INSTRUCTION_SCHEME` | L'instruction de traitement appartient à son schéma |
| `DevelopmentActivitySchemeReference` | `IN_DEVELOPMENT_ACTIVITY_SCHEME` | L'activité de développement appartient à son schéma |
| `MeasurementSchemeReference` | `IN_MEASUREMENT_SCHEME` | L'item de mesure appartient à un schéma de mesures |
| `SamplingInformationSchemeReference` | `IN_SAMPLING_INFORMATION_SCHEME` | L'information d'échantillonnage appartient à son schéma |
| `CodeListSchemeReference` | `IN_CODELIST_SCHEME` | La liste de codes appartient à un schéma |
| `VariableSchemeReference` | `IN_VARIABLE_SCHEME` | La variable appartient à un schéma de variables |
| `ConceptSchemeReference` | `IN_CONCEPT_SCHEME` | Le concept appartient à un schéma de concepts |
| `UniverseSchemeReference` | `IN_UNIVERSE_SCHEME` | L'univers appartient à un schéma d'univers |
| `ConceptualVariableSchemeReference` | `IN_CONCEPTUAL_VARIABLE_SCHEME` | La variable conceptuelle appartient à son schéma |
| `GeographicStructureSchemeReference` | `IN_GEOGRAPHIC_STRUCTURE_SCHEME` | La structure géographique appartient à son schéma |
| `GeographicLocationSchemeReference` | `IN_GEOGRAPHIC_LOCATION_SCHEME` | L'emplacement géographique appartient à son schéma |
| `UnitTypeSchemeReference` | `IN_UNIT_TYPE_SCHEME` | Le type d'unité appartient à son schéma |
| `ClassificationFamilyReference` | `IN_CLASSIFICATION_FAMILY` | La classification appartient à une famille |
| `OrganizationReference` | `REFERENCES_ORGANIZATION` | Référence à une organisation |
| `IndividualReference` | `REFERENCES_INDIVIDUAL` | Référence à une personne nommée |
| `SamplingProcedureReference` | `USES_SAMPLING_PROCEDURE` | L'objet utilise une procédure d'échantillonnage |

### Comportement par défaut

Tout élément `*Reference` non reconnu est converti en type de relation en :

1. Supprimant le suffixe "Reference"
2. Convertissant en majuscules

Par exemple, `CustomReference` -> `CUSTOM`

## Accès aux définitions du schéma

Les définitions de relations sont accessibles via la classe `DDISchema` :

```python
from ddigraph.schema import DDISchema

# Obtenir le type de relation pour un element de reference
rel_type = DDISchema.get_fragment_relationship_type("ControlConstructReference")
# Retourne : "HAS_CONSTRUCT"

# Afficher toutes les correspondances de relations de fragments
print(DDISchema.FRAGMENT_RELATIONSHIP_TYPES)
```

## Exemples pratiques

### Enquête irlandaise sur l'emploi (DDI-L FragmentInstance)

Le fichier `Ireland_LabourSurvey.xml` illustre les relations DDI-L typiques :

**Liaison de construits de contrôle :**

```xml
<Instrument>
  <ID>e274cbba-78ea-4a7b-bf06-e6fef1e570e1</ID>
  <ControlConstructReference>
    <ID>cdbc61f8-5a7d-4c04-bf3a-75eaf9f919ab</ID>
    <TypeOfObject>Sequence</TypeOfObject>
  </ControlConstructReference>
</Instrument>
```

Crée : `(Instrument)-[:HAS_CONSTRUCT]->(Sequence)`

**Liaison question/CodeList :**

```xml
<QuestionItem>
  <ID>97cb6944-1704-483a-b32d-3e4965bd25aa</ID>
  <CodeListReference>
    <ID>20a3c76d-a966-4c32-a908-83f8a2ba341d</ID>
    <TypeOfObject>CodeList</TypeOfObject>
  </CodeListReference>
</QuestionItem>
```

Crée : `(QuestionItem)-[:USES_CODELIST]->(CodeList)`

**Branchement conditionnel :**

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

Crée :

- `(IfThenElse)-[:THEN]->(Sequence)`
- `(IfThenElse)-[:ELSE]->(Sequence)`

## Interrogation des relations

### Requêtes DDI Codebook

```cypher
-- Trouver toutes les variables d'un jeu de donnees
MATCH (d:Dataset {id: 'demo'})<-[:IN_DATASET]-(v:Variable)
RETURN v.name, v.label
-- Variables avec leurs concepts
MATCH (v:Variable)-[:USES_CONCEPT]->(c:Concept)
RETURN v.name, c.name
-- Questions regroupees par variable
MATCH (v:Variable)-[:ASKED_AS]->(q:Question)
RETURN v.name, q.text
```

### Requêtes DDI-L FragmentInstance

```cypher
-- Tracer le flux du questionnaire
MATCH path = (i:Instrument)-[:HAS_CONSTRUCT*1..5]->(c)
RETURN path
-- Trouver les branches conditionnelles
MATCH (ite:IfThenElse)-[:THEN]->(then_branch)
OPTIONAL MATCH (ite)-[:ELSE]->(else_branch)
RETURN ite.fragment_id, then_branch.fragment_id, else_branch.fragment_id
-- Questions avec leurs listes de codes
MATCH (qc:QuestionConstruct)-[:ASKS_QUESTION]->(q:QuestionItem)
       -[:USES_CODELIST]->(cl:CodeList)
RETURN q.name, q.question_text, cl.name
-- Toutes les categories d'une liste de codes
MATCH (cl:CodeList)-[:HAS_CATEGORY]->(cat:Category)
RETURN cl.name, collect(cat.category_label) AS categories
```

## Statistiques sur les relations

Après le chargement de `Ireland_LabourSurvey.xml` :

```cypher
-- Compter les relations par type
MATCH ()-[r]->()
RETURN type(r) AS relationship_type, count(*) AS count
ORDER BY count DESC
```

Sortie typique :

| Type de relation | Nombre |
| ------------------ | -------- |
| HAS_CONSTRUCT | 450 |
| USES_CODELIST | 180 |
| HAS_CATEGORY | 120 |
| ASKS_QUESTION | 17 |

## Relations DDI-CDI 1.0

Le chargeur CDI extrait les relations à partir des éléments d'association dans les fichiers XML
DDI-CDI. Ces relations connectent les 210 types d'entités CDI concrets de niveau supérieur
(associations exclues). Le tableau ci-dessous liste les types de relations capturés avec un
label dédié ; les autres éléments d'association passent par le chemin d'entité générique.

| Relation | Label de départ | Label d'arrivée | Description |
| ---------- | ----------------- | ----------------- | ------------- |
| `HAS_CONCEPT` | ConceptualVariable | Concept | La variable utilise un concept |
| `MEASURES` | InstanceVariable | ConceptualVariable | L'instance mesure la variable conceptuelle |
| `HAS_CATEGORY` | CodeList | Category | La liste de codes contient une catégorie |
| `HAS_CODE` | CodeList | Code | La liste de codes contient un code |
| `DENOTES` | Code | Category | Le code dénote une catégorie |
| `HAS_CLASSIFICATION_ITEM` | StatisticalClassification | ClassificationItem | La classification contient un item |
| `HAS_COMPONENT` | WideDataStructure | InstanceVariable | La structure possède une variable composante |
| `IS_STRUCTURED_BY` | WideDataSet | WideDataStructure | Le jeu de données est structuré par la structure |
| `HAS_LOGICAL_RECORD` | WideDataSet | LogicalRecord | Le jeu de données possède un enregistrement logique |
| `CORRESPONDS_TO` | RepresentedVariable | ConceptualVariable | La variable représentée correspond à la variable conceptuelle |
| `PERFORMS` | Agent | Activity | L'agent effectue l'activité |
| `MAPS_TO` | CorrespondenceTable | ClassificationItem | La table de correspondance est reliée à un item de classification |
| `IS_BASED_ON` | RepresentedVariable | ConceptualVariable | La variable représentée est dérivée d'une variable conceptuelle |
| `IS_BASED_ON` | InstanceVariable | RepresentedVariable | La variable d'instance est dérivée d'une variable représentée |
| `TAKES_CONCEPT_FROM` | ConceptualVariable | Concept | La variable conceptuelle tire son concept de |
| `HAS_POPULATION` | Universe | Population | L'univers inclut cette population |
| `IS_DEFINED_BY` | DataStructureComponent | InstanceVariable | La composante de structure est définie par une variable |
| `HAS_SENTINEL_VALUE` | ValueDomain | Category | Le domaine de valeurs possède une valeur sentinelle ou manquante |
| `USES` | Activity | Activity | Une activité utilise ou dépend d'une autre activité |
| `HAS_DATA_STORE` | DataSet | DataStore | Le jeu de données contient un entrepôt de données |

### Requêtes CDI

```cypher
-- Trouver toutes les variables mesurant un concept
MATCH (iv:InstanceVariable)-[:MEASURES]->(cv:ConceptualVariable)-[:HAS_CONCEPT]->(c:Concept)
RETURN iv.name, cv.name, c.name

-- Explorer la structure d'un jeu de donnees
MATCH (ds:WideDataSet)-[:IS_STRUCTURED_BY]->(str:WideDataStructure)
       -[:HAS_COMPONENT]->(iv:InstanceVariable)
RETURN ds.name, str.name, collect(iv.name) AS variables

-- Hierarchie de classification
MATCH (sc:StatisticalClassification)-[:HAS_CLASSIFICATION_ITEM]->(ci:ClassificationItem)
RETURN sc.name, ci.name
```

Consultez [Architecture](architecture.md) pour comprendre comment les relations transitent à
travers le pipeline d'ingestion.
