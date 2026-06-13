---
hide:
  - navigation
  - toc
title: ddigraph
---

<!-- markdownlint-disable MD033 -->
<div align="center" markdown>

## **ddigraph**

### Transformez vos métadonnées DDI en graphes de connaissances

Boîte à outils Python moderne pour convertir les métadonnées XML
[DDI](https://ddialliance.org/) (Data Documentation Initiative)
en graphes de connaissances interrogeables. Analysez les formats Codebook,
Lifecycle et CDI grâce au traitement XML en flux continu, puis chargez les résultats
dans Neo4j, un triplestore RDF, une base Gremlin, NetworkX ou pandas -- le
tout via une interface unique et cohérente.

[Pour commencer](getting-started/quickstart.md){ .md-button .md-button--primary }
[Voir sur GitHub](https://github.com/pbisson44/ddigraph){ .md-button }

</div>
<!-- markdownlint-enable MD033 -->

---

## Pourquoi ddigraph ?

<!-- markdownlint-disable MD033 -->
<div class="grid cards" markdown>

- **Analysez une fois, écrivez partout**

    ---

    Le parseur en flux émet des enregistrements typés que vous
    pouvez persister dans Neo4j d'emblée, ou vers des triplestores
    RDF/SPARQL, des bases Gremlin, NetworkX ou pandas grâce à de
    petits adaptateurs spécifiques au backend. Le code d'analyse ne
    change pas ; seul l'écrivain change. Voir les scripts
    `demo/load_*.py`.

- **Traitement XML en flux continu**

    ---

    L'analyse basée sur `iterparse` est bornée en mémoire et traite des
    fichiers de toute taille. Les nœuds et les relations sont produits de
    manière incrémentale : la consommation de RAM reste constante quel que
    soit le volume d'entrée.

- **E/S asynchrones avec contre-pression**

    ---

    L'analyse concurrente et les écritures par lots sont coordonnées via des
    files d'attente asynchrones avec contre-pression configurable, ce qui
    maintient un débit élevé tout en évitant les pics de mémoire.

- **Auto-détection du format**

    ---

    Pointez ddigraph vers n'importe quel fichier DDI : il détermine
    automatiquement s'il s'agit du format Codebook, Lifecycle ou DDI-CDI, puis
    sélectionne le bon analyseur -- aucune configuration manuelle requise.

- **Schéma unifié**

    ---

    Les étiquettes de nœuds, les clés de propriétés, les types de relations
    et les contraintes sont définis dans un seul module de schéma. Chaque
    backend reçoit la même structure canonique, garantissant la cohérence
    entre les cibles de graphe.

- **Prêt pour la production**

    ---

    Logique de nouvelle tentative avec recul exponentiel, journalisation
    structurée, contrôles de santé et points d'observabilité compatibles
    OpenTelemetry font de ddigraph un outil adapté aux pipelines automatisés
    et aux workflows CI/CD.

</div>
<!-- markdownlint-enable MD033 -->

---

## Qu'est-ce que DDI ?

La [Data Documentation Initiative (DDI)](https://ddialliance.org/) est un
standard international pour la description des données d'enquête, des
questionnaires et des métadonnées statistiques. Largement adopté par les
archives de données, les instituts nationaux de statistique et les
organismes de recherche, DDI fournit un vocabulaire XML riche pour décrire
les variables, les questions, les listes de codes, les concepts et les liens
qui les unissent.

Ces métadonnées richement connectées se prêtent naturellement à la
représentation sous forme de graphe. C'est exactement ce que fait ddigraph :
il transforme le XML DDI en un graphe de connaissances exploitable, que vous
pouvez interroger, visualiser et intégrer dans vos pipelines de données.

---

## Installation

=== "pip"

    ```bash
    pip install ddigraph
    ```

=== "Développement"

    ```bash
    pip install -e ".[dev,docs]"
    ```

!!! tip "Extras pour les backends"
    L'installation de base inclut le pilote Neo4j. Pour les autres backends,
    installez les extras correspondants :

    ```bash
    pip install ddigraph[rdf]      # RDFLib + SPARQLWrapper
    pip install ddigraph[gremlin]   # Gremlin-Python
    ```

---

## Exemple rapide

```bash
# 1. Configurez votre connexion Neo4j
export DDIGRAPH_NEO4J_URI=bolt://localhost:7687
export DDIGRAPH_NEO4J_USER=neo4j
export DDIGRAPH_NEO4J_PASSWORD=secret

# 2. Créez les index et les contraintes
ddigraph bootstrap

# 3. Chargez n'importe quel fichier DDI (le format est auto-détecté)
ddigraph load path/to/survey.xml --dataset-id my-survey

# 4. Vérifiez ce qui a été chargé (utilisez Cypher dans le navigateur Neo4j)
#    MATCH (n) RETURN labels(n) AS type, count(*) AS n ORDER BY n DESC
```

!!! note "API Python"
    Le même flux de travail est disponible par programmation. Consultez le
    [guide de démarrage rapide](getting-started/quickstart.md) pour un exemple
    Python complet utilisant `DDILoader` et `DDIFragmentLoader`.

---

## Documentation

<!-- markdownlint-disable MD007 MD033 -->
<div class="grid cards" markdown>

- **Pour commencer**

    ---

    Installez ddigraph, effectuez votre premier chargement et explorez le
    graphe en moins de dix minutes.

    - [Installation](getting-started/installation.md)
    - [Démarrage rapide](getting-started/quickstart.md)
    - [10 minutes avec ddigraph](getting-started/ten-minutes.md)

- **Guide d'utilisation**

    ---

    Comprenez l'architecture, découvrez comment les éléments DDI sont
    transposés en structures de graphe, et étendez ddigraph avec des
    adaptateurs personnalisés.

    - [Architecture](user-guide/architecture.md)
    - [DDI-L FragmentInstance](user-guide/fragments.md)
    - [Modèle relationnel](user-guide/relationships.md)
    - [Patron adaptateur](user-guide/adapter.md)

- **Bases de données graphe**

    ---

    Guides détaillés pour chaque backend pris en charge : configuration de la
    connexion, amorçage du schéma et exemples de requêtes.

    - [Neo4j](backends/neo4j.md)
    - [RDF / SPARQL](backends/rdf.md)
    - [Gremlin](backends/gremlin.md)
    - [NetworkX](backends/networkx.md)

- **Référence**

    ---

    Référence complète des commandes CLI et catalogue de toutes les options
    de configuration.

    - [Référence CLI](reference/cli.md)
    - [Configuration](reference/configuration.md)

- **Avancé**

    ---

    Optimisez les performances, intégrez ddigraph aux pipelines IA/LLM et
    comprenez sa place dans l'écosystème DDI.

    - [Optimisation des performances](advanced/tuning.md)
    - [Préparation pour l'IA](advanced/ai-readiness.md)
    - [Interopérabilité des standards](advanced/interoperability.md)
    - [Graphe vs Relationnel](advanced/graph-vs-relational.md)

- **Projet**

    ---

    Contribuez à ddigraph, consultez le journal des modifications ou trouvez
    des réponses aux questions fréquentes.

    - [Contribuer](project/contributing.md)
    - [Journal des modifications](project/changelog.md)
    - [FAQ](project/faq.md)

</div>
<!-- markdownlint-enable MD007 MD033 -->

---

## Formats DDI pris en charge

| Format | Version | Élément racine | Description |
| ------ | ------- | -------------- | ----------- |
| **DDI Codebook** | 2.5 / 2.6 | `<codeBook>` | Structure traditionnelle à plat avec un nœud Dataset central reliant les variables, les questions et les métadonnées de niveau étude. Largement utilisé par les archives d'enquêtes et les catalogues de données. |
| **DDI Lifecycle** | 3.2 / 3.3 | `<FragmentInstance>` | Format modulaire construit autour de fragments réutilisables. Prend en charge les flux de questionnaires, les instruments CAPI/CAWI et les plans d'étude complexes avec versionnage fin. |
| **DDI-CDI** | 1.0 | `<Wrapper>` | Modèle d'intégration cross-domaine. Capture les variables conceptuelles, représentées et d'instance ainsi que leurs relations pour l'harmonisation inter-études. |

!!! info "Détection du format"
    Il n'est pas nécessaire de spécifier le format d'un fichier. La fonction
    `detect_ddi_format()` inspecte l'élément racine et l'espace de noms pour
    sélectionner automatiquement l'analyseur correct.

---

## Backends graphe pris en charge

| Backend | Bibliothèque | Cas d'usage | Protocole |
| ------- | ------------ | ----------- | --------- |
| **Neo4j** | `neo4j` (pilote Bolt) | Déploiements en production, traversées complexes, recherche plein texte | Bolt |
| **RDF / SPARQL** | `rdflib`, `SPARQLWrapper` | Publication de données liées, alignement d'ontologies, requêtes fédérées | HTTP / SPARQL 1.1 |
| **Gremlin** | `gremlinpython` | JanusGraph, Amazon Neptune, Azure Cosmos DB | WebSocket |
| **NetworkX** | `networkx` | Analyse locale, prototypage, tests unitaires | En mémoire |
| **pandas** | `pandas` | Analyse tabulaire, export CSV/Excel, validation de données | En mémoire |

Neo4j est branché via le protocole `GraphWriteAdapter` dans
`ddigraph.schema.adapter`. Les autres backends listés ci-dessus ne
passent pas par cet adaptateur ; ils consomment le parseur (`DDILoader`,
`DDIFragmentLoader`, `DDIFragmentParser`) et écrivent via leur propre
petit adaptateur spécifique. Les scripts `demo/load_*.py` montrent le
motif.

---

<!-- markdownlint-disable MD033 -->
<div align="center" markdown>

**ddigraph** est distribué sous la [licence MIT](https://github.com/pbisson44/ddigraph/blob/main/LICENSE).

[GitHub](https://github.com/pbisson44/ddigraph) |
[PyPI](https://pypi.org/project/ddigraph/) |
[Issues](https://github.com/pbisson44/ddigraph/issues)

</div>
<!-- markdownlint-enable MD033 -->
