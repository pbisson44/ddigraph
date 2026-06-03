# Journal des modifications

Toutes les modifications notables de ddigraph sont documentées ici. Ce projet suit les conventions
[Keep a Changelog](https://keepachangelog.com/fr/1.1.0/).

---

## Non publié

### Ajouté

**Couverture XSD réelle à 100 % pour chaque variante DDI**

`scripts/xsd_coverage.py` analyse désormais directement les XSD fournis et
vérifie que le paquet enregistre un gestionnaire pour chaque élément concret
et non abstrait. La couverture est garantie par `TestRealXSDCoverage` :

| Variante    | Portée                                                                 | Cible | Couvert |
| ----------- | ---------------------------------------------------------------------- | ----: | ------: |
| DDI-L 3.x   | Éléments concrets Maintainable + Versionable + Identifiable            |   189 |  100 %  |
| DDI-C 2.x   | Éléments Codebook portant le groupe d'attributs `GLOBALS`              |    73 |  100 %  |
| DDI-CDI 1.0 | Éléments d'entité concrets de niveau supérieur (associations exclues) |   210 |  100 %  |

Points forts de l'implémentation :

- 106 nouvelles entrées `NodeDefinition` et `NAME_TAGS` pour DDI-L couvrant
  tous les éléments concrets restants de DDI-L 3.3.
- `BatchBuilder.ingest_generic_identifiable()` et `GenericIdentifiableRecord`
  capturent chaque élément Codebook concret portant `GLOBALS` sans classe
  d'enregistrement dédiée, tout en laissant les gestionnaires parents
  (ex. `stdyDscr`) lire les enfants imbriqués.
- `CDIGenericRecord` et la collection `generic_entities` de `CDIBatch`
  préservent chaque entité DDI-CDI concrète au-delà des ~35 types à la main.
- `CDIBatchStream` ne traite que les éléments de niveau racine, empêchant
  les types imbriqués réutilisables (ex. `Identifier`, `ObjectName`) d'être
  effacés avant la fin du parsing de leur parent.

---

## v0.1.0

### Ajouté

**Prise en charge des formats DDI**

- **DDI Codebook** (DDI-C 2.5 et 2.6) avec analyse XML en flux pour les fichiers de toute taille
- **DDI Lifecycle** (DDI-L 3.2/3.3) FragmentInstance avec écritures par lots et E/S asynchrones
  complètes
- **DDI-CDI 1.0** avec un analyseur en flux pour 32 types d'entités et 20 types de relations
- **Détection automatique du format** -- `detect_ddi_format()` inspecte l'élément racine XML et
  l'espace de noms pour choisir automatiquement le bon analyseur
- Types d'entités DDI-C 2.6 : NCube, NCubeGroup, DocumentDescription, SampleFrame,
  QualityStatement, StudyAuthorization, StudyDevelopment, ExPostEvaluation

**Architecture multi-backend**

- **Protocole `GraphWriteAdapter`** (`ddigraph.schema.adapter`) pour les implémentations de backend
  personnalisées prenant en charge les adaptateurs synchrones et asynchrones
- **Backend Neo4j** -- pilote Bolt, amorçage du schéma, traitement par lots UNWIND, réessai avec
  délai exponentiel
- **Backend RDF/SPARQL** -- via rdflib et SPARQLWrapper
- **Backend Gremlin** -- via gremlinpython (JanusGraph, Neptune, Cosmos DB)
- **Backend NetworkX** -- graphe en mémoire pour l'analyse locale et le prototypage
- **Backend pandas** -- analyse tabulaire et export CSV/Excel
- Scripts de démonstration pour tous les backends (`demo/load_rdf.py`, `demo/load_gremlin.py`,
  `demo/load_networkx.py`, `demo/load_pandas.py`)

**CLI**

- Commande `load` avec détection automatique du format, `--dry-run`, `--replace` et traitement par
  lots configurable
- Commandes `ensure-schema` et `ensure-fragment-schema` pour la création des contraintes et des
  index de la base de données
- Commande `detect` pour identifier le format DDI d'un fichier sans le charger
- Commande `audit` pour la vérification du contenu du graphe
- Audit de la source des identifiants au démarrage

**Moteur principal**

- Analyse XML en flux basée sur `iterparse` -- la consommation mémoire reste constante quelle que
  soit la taille du fichier
- Pipeline d'écriture asynchrone avec contre-pression `asyncio.Queue` et concurrence d'écriture
  configurable
- Écritures par lots basées sur UNWIND réduisant les allers-retours Neo4j de 10 à 100 fois
- Logique de réessai avec délai exponentiel et gigue pour les erreurs d'écriture transitoires
- Définitions de schéma unifiées dans `ddigraph.schema.definitions` comme source unique de vérité
- Utilitaires d'analyse partagés dans `ddigraph.utils.parsing`
- Logique de réessai partagée dans `ddigraph.utils.retry.retry_transient`
- Configuration par variables d'environnement avec prise en charge des fichiers `.env`
  (pydantic-settings v2)
- Journalisation structurée avec niveaux de journalisation configurables
- Prise en charge de Python 3.12 à 3.14

**Couverture XSD complète pour DDI-L FragmentInstance**

- **80 types de nœuds de fragments** couvrant chaque maintainable et membre de schéma
  identifiable de manière indépendante défini dans le XSD DDI-L 3.2 :
  - 9 schémas de collecte de données (`QuestionScheme`, `ControlConstructScheme`,
    `InstrumentScheme`, `InterviewerInstructionScheme`, `ProcessingEventScheme`,
    `ProcessingInstructionScheme`, `DevelopmentActivityScheme`, `MeasurementScheme`,
    `SamplingInformationScheme`)
  - 3 schémas de produit logique (`CodeListScheme`, `NCubeScheme`, `VariableScheme`)
  - 6 schémas de composante conceptuelle (`ConceptScheme`, `UniverseScheme`,
    `ConceptualVariableScheme`, `GeographicStructureScheme`, `GeographicLocationScheme`,
    `UnitTypeScheme`)
  - 5 sous-types de construits de contrôle (`Split`, `SplitJoin`, `DevelopmentStep`,
    `SamplingStage`, `SampleStep`)
  - Types de classifications (`ClassificationFamily`, `StatisticalClassification`,
    `ClassificationItem`)
  - Types géographiques (`GeographicStructure`, `GeographicLocation`)
  - Groupes et types d'unités (`ConceptGroup`, `UniverseGroup`, `ConceptualVariableGroup`,
    `UnitType`, `UnitTypeGroup`, `VariableGroup`)
  - Conteneurs au niveau des modules (`ConceptualComponent`, `LogicalProduct`,
    `PhysicalDataProduct`, `Archive`, `DDIProfile`, `LocalHoldingPackage`)
  - Types archivistiques (`Individual`, `Collection`, `Access`)
  - Types de développement et de méthodologie (`DevelopmentActivity`, `RecordLayout`,
    `QuestionBlock`)
- 21 `FRAGMENT_RELATIONSHIP_TYPES` pour l'appartenance aux schémas et les références
  archivistiques (ex. `IN_QUESTION_SCHEME`, `IN_CONCEPT_SCHEME`, `IN_CLASSIFICATION_FAMILY`,
  `REFERENCES_INDIVIDUAL`)
- Entrées `NAME_TAGS` pour les 80 types de nœuds de fragments dans `DDIFragmentParser`

**Couverture XSD complète pour DDI-CDI 1.0**

- **32 types d'entités CDI**, dont `CDIVariableRelationship`, `CDIConceptMap`,
  `CDIConceptSystemCorrespondence`, `CDIPhysicalRecordSegment`, `CDIClassificationFamily`,
  `CDIClassificationIndex`, `CDIClassificationSeries`
- **20 types de relations CDI**, dont `IS_BASED_ON`, `TAKES_CONCEPT_FROM`, `HAS_POPULATION`,
  `IS_DEFINED_BY`, `HAS_SENTINEL_VALUE`, `USES`, `HAS_DATA_STORE`
- Champs de collection `CDIBatch` et classes d'enregistrement pour tous les types d'entités

**Audit de la couverture XSD**

- `scripts/xsd_coverage.py` vérifie la couverture du paquet par rapport à des ensembles cibles
  DDI-L et CDI ; retourne le code 1 si la couverture passe sous un seuil configurable
- `tests/test_xsd_coverage.py` avec plus de 95 assertions vérifiant tous les types de nœuds,
  entrées NAME_TAGS, balises CDI, relations CDI et collections CDIBatch

**Documentation et projet**

- Documentation bilingue (anglais et français) construite avec mkdocs-material et
  mkdocs-static-i18n
- SECURITY.md avec politique de signalement des vulnérabilités
- CODE_OF_CONDUCT.md (Contributor Covenant v2.1)
- `.pre-commit-config.yaml` pour l'application locale des règles de linting
- Modèles de tickets et de pull requests GitHub et configuration Dependabot
- `pytest-cov` avec seuil de couverture de branches de 70 % en CI
- Publication du paquet sur PyPI -- installable via `pip install ddigraph`
- Licence MIT

---

Consultez [Contribuer](contributing.md) pour la configuration du développement et la
[FAQ](faq.md) pour les questions fréquentes.
