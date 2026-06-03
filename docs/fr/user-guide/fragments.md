# Prise en charge de DDI-L FragmentInstance

ddigraph prend en charge les fichiers DDI Lifecycle 3.x FragmentInstance avec une **couverture
XSD complète** — chaque objet identifiable de manière indépendante défini dans le schéma
DDI-L 3.2 possède un type de nœud correspondant dans le graphe. Ce format est très différent
du DDI Codebook. Au lieu d'une structure plate centrée sur le jeu de données, DDI-L utilise
des fragments réutilisables qui se référencent mutuellement pour former un graphe orienté.

## Qu'est-ce que FragmentInstance ?

Dans le format DDI-L FragmentInstance :

- Chaque élément `<Fragment>` contient un composant DDI réutilisable (Instrument, Sequence,
  CodeList, QuestionItem, etc.)
- Les composants se référencent mutuellement via des éléments `*Reference` (par exemple,
  `ControlConstructReference`, `CodeListReference`)
- La structure forme naturellement un graphe, ce qui la rend idéale pour Neo4j

Exemple de structure :

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

## Démarrage rapide

```bash
# Détection automatique du format et chargement
ddigraph load questionnaire.xml

# Spécifier explicitement le format lifecycle
ddigraph load questionnaire.xml --format lifecycle

# Détecter le format sans charger
ddigraph detect questionnaire.xml
```

### API Python

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

## Types de nœuds pris en charge

Le chargeur FragmentInstance reconnaît chaque élément concret de type Maintainable, Versionable
ou Identifiable défini dans DDI-L 3.3 — 189 types de nœuds au total (même ensemble que 3.1/3.2),
organisés ci-dessous par module DDI. Les tableaux présentent le sous-ensemble le plus couramment
référencé ; la couverture des autres éléments concrets identifiables est vérifiée par
`scripts/xsd_coverage.py`.

### Instruments d'enquête et construits de contrôle

| Label du nœud | Élément DDI-L | Description |
| ---------------- | --------------- | ------------- |
| `Instrument` | `<Instrument>` | Point d'entrée de l'instrument d'enquête |
| `Sequence` | `<Sequence>` | Liste ordonnée de construits de contrôle |
| `IfThenElse` | `<IfThenElse>` | Branchement conditionnel (si/alors/sinon) |
| `Loop` | `<Loop>` | Répète un bloc un nombre fixé de fois |
| `QuestionConstruct` | `<QuestionConstruct>` | Lie une question au flux de contrôle |
| `StatementItem` | `<StatementItem>` | Affiche du texte au répondant |
| `ComputationItem` | `<ComputationItem>` | Calcule une valeur dérivée |
| `RepeatWhile` | `<RepeatWhile>` | Répète tant qu'une condition est vraie |
| `RepeatUntil` | `<RepeatUntil>` | Répète jusqu'à ce qu'une condition soit vraie |
| `Split` | `<Split>` | Divise le flux en branches parallèles |
| `SplitJoin` | `<SplitJoin>` | Rejoint des branches parallèles |
| `DevelopmentStep` | `<DevelopmentStep>` | Étape dans un processus de développement de questionnaire |
| `SamplingStage` | `<SamplingStage>` | Étape dans un plan de sondage |
| `SampleStep` | `<SampleStep>` | Étape individuelle dans une étape d'échantillonnage |
| `MeasurementConstruct` | `<MeasurementConstruct>` | Lie un item de mesure au flux de contrôle |

### Questions et mesures

| Label du nœud | Élément DDI-L | Description |
| ---------------- | --------------- | ------------- |
| `QuestionItem` | `<QuestionItem>` | Question individuelle avec un domaine de réponse |
| `QuestionGrid` | `<QuestionGrid>` | Grille ou tableau de questions liées |
| `QuestionBlock` | `<QuestionBlock>` | Bloc de questions réutilisable |
| `MeasurementItem` | `<MeasurementItem>` | Item d'un instrument de mesure |

### Schémas de collecte de données

Les types de schémas sont des conteneurs nommés qui regroupent des objets DDI de même nature.

| Label du nœud | Élément DDI-L | Description |
| ---------------- | --------------- | ------------- |
| `QuestionScheme` | `<QuestionScheme>` | Conteneur d'items de questions |
| `ControlConstructScheme` | `<ControlConstructScheme>` | Conteneur de construits de contrôle |
| `InstrumentScheme` | `<InstrumentScheme>` | Conteneur d'instruments |
| `InterviewerInstructionScheme` | `<InterviewerInstructionScheme>` | Conteneur d'instructions pour enquêteurs |
| `ProcessingEventScheme` | `<ProcessingEventScheme>` | Conteneur d'événements de traitement |
| `ProcessingInstructionScheme` | `<ProcessingInstructionScheme>` | Conteneur d'instructions de traitement |
| `DevelopmentActivityScheme` | `<DevelopmentActivityScheme>` | Conteneur d'activités de développement |
| `MeasurementScheme` | `<MeasurementScheme>` | Conteneur d'items de mesure |
| `SamplingInformationScheme` | `<SamplingInformationScheme>` | Conteneur d'informations d'échantillonnage |

### Variables et domaines de valeurs

| Label du nœud | Élément DDI-L | Description |
| ---------------- | --------------- | ------------- |
| `Variable` | `<Variable>` | Variable de données |
| `ConceptualVariable` | `<ConceptualVariable>` | Définition de variable conceptuelle |
| `RepresentedVariable` | `<RepresentedVariable>` | Variable avec une représentation de valeur |
| `RepresentedVariableGroup` | `<RepresentedVariableGroup>` | Groupe de variables représentées |
| `RepresentedVariableScheme` | `<RepresentedVariableScheme>` | Conteneur de variables représentées |
| `VariableGroup` | `<VariableGroup>` | Groupe de variables liées |
| `VariableScheme` | `<VariableScheme>` | Conteneur de variables |

### Codes et catégories

| Label du nœud | Élément DDI-L | Description |
| ---------------- | --------------- | ------------- |
| `CodeList` | `<CodeList>` | Liste de codes de réponse |
| `Category` | `<Category>` | Une catégorie dans une liste de codes |
| `CategoryScheme` | `<CategoryScheme>` | Conteneur de catégories |
| `CategoryGroup` | `<CategoryGroup>` | Groupe de catégories liées |
| `CodeListScheme` | `<CodeListScheme>` | Conteneur de listes de codes |
| `NCubeScheme` | `<NCubeScheme>` | Conteneur de cubes de données n-dimensionnels |

### Classifications statistiques

| Label du nœud | Élément DDI-L | Description |
| ---------------- | --------------- | ------------- |
| `ClassificationFamily` | `<ClassificationFamily>` | Famille de classifications statistiques liées |
| `StatisticalClassification` | `<StatisticalClassification>` | Un système de classification statistique |
| `ClassificationItem` | `<ClassificationItem>` | Un item dans une classification |

### Concepts et composantes conceptuelles

| Label du nœud | Élément DDI-L | Description |
| ---------------- | --------------- | ------------- |
| `Concept` | `<Concept>` | Une définition conceptuelle |
| `ConceptScheme` | `<ConceptScheme>` | Conteneur de concepts |
| `ConceptGroup` | `<ConceptGroup>` | Groupe de concepts liés |
| `ConceptualVariableScheme` | `<ConceptualVariableScheme>` | Conteneur de variables conceptuelles |
| `ConceptualVariableGroup` | `<ConceptualVariableGroup>` | Groupe de variables conceptuelles |

### Univers et géographie

| Label du nœud | Élément DDI-L | Description |
| ---------------- | --------------- | ------------- |
| `Universe` | `<Universe>` | Définition d'une population ou d'un univers |
| `UniverseScheme` | `<UniverseScheme>` | Conteneur d'univers |
| `UniverseGroup` | `<UniverseGroup>` | Groupe d'univers liés |
| `GeographicStructure` | `<GeographicStructure>` | Structure de classification géographique |
| `GeographicStructureScheme` | `<GeographicStructureScheme>` | Conteneur de structures géographiques |
| `GeographicLocation` | `<GeographicLocation>` | Un emplacement géographique précis |
| `GeographicLocationScheme` | `<GeographicLocationScheme>` | Conteneur d'emplacements géographiques |

### Types d'unités

| Label du nœud | Élément DDI-L | Description |
| ---------------- | --------------- | ------------- |
| `UnitType` | `<UnitType>` | Type d'unité observée ou mesurée |
| `UnitTypeScheme` | `<UnitTypeScheme>` | Conteneur de types d'unités |
| `UnitTypeGroup` | `<UnitTypeGroup>` | Groupe de types d'unités |

### Étude et gestion des données

| Label du nœud | Élément DDI-L | Description |
| ---------------- | --------------- | ------------- |
| `StudyUnit` | `<StudyUnit>` | Métadonnées de l'étude ou de l'enquête |
| `DataCollection` | `<DataCollection>` | Métadonnées du processus de collecte de données |
| `DataCollectionMethodology` | `<DataCollectionMethodology>` | Détails de la méthodologie de collecte |
| `SamplingProcedure` | `<SamplingProcedure>` | Description de la procédure d'échantillonnage |
| `DevelopmentActivity` | `<DevelopmentActivity>` | Activité de conception ou de développement |
| `Methodology` | `<Methodology>` | Description de la méthodologie |
| `ResourcePackage` | `<ResourcePackage>` | Ensemble de ressources DDI réutilisables |
| `PhysicalInstance` | `<PhysicalInstance>` | Référence à un fichier de données physique |
| `DataRelationship` | `<DataRelationship>` | Relation entre éléments de données |
| `LogicalRecord` | `<LogicalRecord>` | Structure d'enregistrement logique |
| `RecordLayout` | `<RecordLayout>` | Description de la structure d'enregistrement physique |
| `OtherMaterial` | `<OtherMaterial>` | Référence à du matériel complémentaire |

### Conteneurs au niveau des modules

Ces types de nœuds servent de conteneurs de premier niveau regroupant du contenu DDI de même nature.

| Label du nœud | Élément DDI-L | Description |
| ---------------- | --------------- | ------------- |
| `ConceptualComponent` | `<ConceptualComponent>` | Module regroupant le contenu conceptuel |
| `LogicalProduct` | `<LogicalProduct>` | Module regroupant le contenu du produit logique |
| `PhysicalDataProduct` | `<PhysicalDataProduct>` | Module regroupant les données physiques |
| `Archive` | `<Archive>` | Module regroupant le contenu archivistique |
| `DDIProfile` | `<DDIProfile>` | Profil définissant les éléments DDI utilisés |
| `LocalHoldingPackage` | `<LocalHoldingPackage>` | Conservation locale de ressources DDI |

### Archives et organisations

| Label du nœud | Élément DDI-L | Description |
| ---------------- | --------------- | ------------- |
| `Individual` | `<Individual>` | Une personne nommée dans les archives |
| `Collection` | `<Collection>` | Une collection archivistique |
| `Access` | `<Access>` | Conditions et restrictions d'accès |

## Types de relations

Les relations sont dérivées des éléments `*Reference` de DDI-L. Les types les plus courants
sont listés ci-dessous ; la correspondance complète se trouve dans
`DDISchema.FRAGMENT_RELATIONSHIP_TYPES`.

### Flux de contrôle

| Élément de référence | Relation | Description |
| ---------------------- | --------- | ------------- |
| `ControlConstructReference` | `HAS_CONSTRUCT` | La séquence ou l'instrument contient un construit |
| `ThenConstructReference` | `THEN` | Branche vraie de IfThenElse |
| `ElseConstructReference` | `ELSE` | Branche fausse de IfThenElse |
| `UntilConstructReference` | `UNTIL` | Corps de la boucle RepeatUntil |
| `WhileConstructReference` | `WHILE` | Corps de la boucle RepeatWhile |

### Questions, codes et catégories

| Élément de référence | Relation | Description |
| ---------------------- | --------- | ------------- |
| `QuestionItemReference` | `ASKS_QUESTION` | Le construit pose une question |
| `QuestionGridReference` | `ASKS_QUESTION` | Le construit pose une grille de questions |
| `QuestionBlockReference` | `ASKS_QUESTION` | Le construit utilise un bloc de questions |
| `CodeListReference` | `USES_CODELIST` | La question utilise une liste de codes |
| `CategoryReference` | `HAS_CATEGORY` | La liste de codes contient une catégorie |

### Variables, concepts et univers

| Élément de référence | Relation | Description |
| ---------------------- | --------- | ------------- |
| `VariableReference` | `REFERENCES_VARIABLE` | Référence à une variable |
| `RepresentedVariableReference` | `USES_REPRESENTED_VARIABLE` | Référence à une variable représentée |
| `ConceptReference` | `USES_CONCEPT` | Référence à un concept |
| `UniverseReference` | `IN_UNIVERSE` | L'objet appartient à un univers |
| `BasedOnReference` | `BASED_ON` | L'objet est dérivé d'un autre |
| `ValueDomainReference` | `HAS_VALUE_DOMAIN` | L'objet possède un domaine de valeurs |

### Appartenance aux schémas

Ces relations rattachent chaque objet DDI au schéma qui le contient.

| Élément de référence | Relation | Description |
| ---------------------- | --------- | ------------- |
| `QuestionSchemeReference` | `IN_QUESTION_SCHEME` | La question appartient à un schéma de questions |
| `ControlConstructSchemeReference` | `IN_CONTROL_CONSTRUCT_SCHEME` | Le construit appartient à un schéma de construits |
| `InstrumentSchemeReference` | `IN_INSTRUMENT_SCHEME` | L'instrument appartient à un schéma d'instruments |
| `CodeListSchemeReference` | `IN_CODELIST_SCHEME` | La liste de codes appartient à un schéma |
| `VariableSchemeReference` | `IN_VARIABLE_SCHEME` | La variable appartient à un schéma de variables |
| `ConceptSchemeReference` | `IN_CONCEPT_SCHEME` | Le concept appartient à un schéma de concepts |
| `UniverseSchemeReference` | `IN_UNIVERSE_SCHEME` | L'univers appartient à un schéma d'univers |
| `GeographicStructureSchemeReference` | `IN_GEOGRAPHIC_STRUCTURE_SCHEME` | La structure géographique appartient à son schéma |
| `GeographicLocationSchemeReference` | `IN_GEOGRAPHIC_LOCATION_SCHEME` | L'emplacement géographique appartient à son schéma |
| `UnitTypeSchemeReference` | `IN_UNIT_TYPE_SCHEME` | Le type d'unité appartient à son schéma |
| `ClassificationFamilyReference` | `IN_CLASSIFICATION_FAMILY` | La classification appartient à une famille |

### Flux de paramètres

| Élément de référence | Relation | Description |
| ---------------------- | --------- | ------------- |
| `SourceParameterReference` | `SOURCE_PARAM` | Source des données du paramètre |
| `TargetParameterReference` | `TARGET_PARAM` | Cible des données du paramètre |
| `InParameterReference` | `IN_PARAM` | Paramètre d'entrée |
| `OutParameterReference` | `OUT_PARAM` | Paramètre de sortie |

Tout élément `*Reference` non reconnu est converti en un type de relation en majuscules en
supprimant le suffixe "Reference". Par exemple, `CustomReference` devient `CUSTOM`.

## Propriétés des nœuds

Chaque nœud de fragment inclut :

| Propriété | Description |
| ----------- | ------------- |
| `fragment_id` | Identifiant unique (provenant de l'élément `<ID>`) |
| `agency` | Agence responsable (provenant de l'élément `<Agency>`) |
| `version` | Chaîne de version (provenant de l'élément `<Version>`) |
| `urn` | URN DDI complet si présent |
| `label` | Libellé lisible (provenant de l'élément `<Label>`) |
| `name` | Nom de l'élément (spécifique au type d'élément) |

### Propriétés spécifiques au type

| Type de nœud | Propriétés supplémentaires |
| --------------- | ---------------------------- |
| `CodeList` | `code_count` - nombre de codes |
| `Category` | `category_label` - nom de la catégorie |
| `QuestionItem` | `question_text` - texte de la question (tronqué à 1000 caractères) |
| `IfThenElse` | `condition` - expression de condition (tronquée à 500 caractères) |
| `Sequence` | `construct_count` - nombre de construits enfants |

## Marquage du point d'entrée

Le fragment désigné par `<TopLevelReference>` reçoit un label supplémentaire `EntryPoint`,
facilitant ainsi la localisation du point de départ de l'instrument d'enquête :

```cypher
MATCH (n:EntryPoint)
RETURN n
```

## Amorçage du schéma

Avant de charger des fichiers FragmentInstance, assurez-vous que le schéma est créé :

```bash
# Codebook + DDI-L FragmentInstance (par défaut)
ddigraph bootstrap
```

Cela crée :

- Des **contraintes d'unicité** sur `fragment_id` pour chaque type de nœud
- Des **index secondaires** sur `name`, `label` et les champs spécifiques au type

## Performances

Le chargeur FragmentInstance utilise le traitement en flux et les écritures par lots :

| Aspect | Implémentation |
| -------- | ---------------- |
| Analyse | `iterparse` en flux - mémoire bornée |
| Traitement par lots | Regroupement des fragments par type |
| Écritures | Cypher basé sur UNWIND |
| Asynchrone | Entièrement asynchrone avec `AsyncDriver` |
| Réessai | Backoff exponentiel avec gigue (jitter) |

Pour un fichier DDI-L de 148 000 lignes contenant 2 762 fragments :

| Métrique | Valeur |
| ---------- | ------- |
| Requêtes Neo4j | ~30 |
| Utilisation mémoire | O(chunk_size) |
| Opérations asynchrones | Toutes les écritures |

## Configuration

Les mêmes paramètres s'appliquent aux deux chargeurs :

```bash
# Ajuster la taille des lots
ddigraph load questionnaire.xml --chunk-size 300

# Activer la validation en mode simulation (dry-run)
ddigraph load questionnaire.xml --dry-run

# Supprimer les fragments existants avant le chargement
ddigraph load questionnaire.xml --replace

# Sortie détaillée complète
ddigraph load questionnaire.xml --log-level DEBUG --batch-metrics --json
```

## Exemples de requêtes

Après le chargement, explorez le graphe :

```cypher
-- Trouver tous les instruments
MATCH (i:Instrument)
RETURN i.fragment_id, i.name, i.label
-- Tracer le flux du questionnaire depuis le point d'entree
MATCH path = (entry:EntryPoint)-[:HAS_CONSTRUCT*1..5]->(construct)
RETURN path
-- Trouver les questions avec leurs listes de codes
MATCH (qc:QuestionConstruct)-[:ASKS_QUESTION]->(q:QuestionItem)
OPTIONAL MATCH (q)-[:USES_CODELIST]->(cl:CodeList)
RETURN q.name, q.question_text, cl.name, cl.code_count
-- Compter les construits par type dans une sequence
MATCH (s:Sequence)-[:HAS_CONSTRUCT]->(c)
RETURN s.name, labels(c)[0] AS construct_type, count(*) AS count
ORDER BY s.name, count DESC
-- Trouver les branches conditionnelles
MATCH (ite:IfThenElse)-[:THEN]->(then_branch)
OPTIONAL MATCH (ite)-[:ELSE]->(else_branch)
RETURN ite.condition, then_branch.fragment_id, else_branch.fragment_id
```

## Exemple pratique : enquête irlandaise sur l'emploi

L'enquête irlandaise sur la population active (`Ireland_LabourSurvey.xml`) est un fichier DDI-L
réel contenant :

- 148 479 lignes de XML
- 2 762 fragments
- 1 Instrument, 388 Sequences, 376 QuestionConstructs, 373 QuestionItems
- 357 construits de branchement IfThenElse
- 196 CodeLists avec 1 065 Categories

Chargement de ce fichier :

```bash
ddigraph bootstrap
ddigraph load Ireland_LabourSurvey.xml --json
```

Sortie :

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

## Référence de l'API

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
    """Retourne 'codebook' ou 'lifecycle'."""
```

## Limitations

Limitations actuelles du chargeur FragmentInstance :

1. **Pas de références inter-fichiers** : les références à des fragments situés dans d'autres
   fichiers ne sont pas résolues
2. **Résolution différée des relations** : seules les relations entre fragments du même fichier
   sont créées
3. **Extraction limitée des propriétés** : tous les éléments DDI-L ne disposent pas d'une
   extraction de propriétés spécialisée

Les versions futures pourront remédier à ces limitations.
