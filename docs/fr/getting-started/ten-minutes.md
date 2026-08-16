# 10 minutes avec ddigraph

Ce tutoriel vous présente l'essentiel de **ddigraph** en une dizaine de minutes. À l'issue de cette lecture, vous aurez chargé un fichier DDI XML dans une base de données graphe et exécuté vos premières requêtes.

## Qu'est-ce que DDI ?

La [Data Documentation Initiative (DDI)](https://ddialliance.org/) est un standard international destiné à décrire les données d'enquête, les questionnaires et les métadonnées statistiques. Les fichiers DDI sont des documents XML qui capturent les variables, les questions, les listes de codes, les concepts et les relations qui les unissent -- exactement le type de métadonnées richement connectées qui prennent toute leur valeur dans une base de données graphe.

ddigraph analyse le XML DDI et le transforme en graphe de connaissances, avec une prise en charge privilégiée de Neo4j et des backends supplémentaires incluant RDF, Gremlin et NetworkX.

---

## Installer ddigraph

```bash
pip install ddigraph
```

!!! tip "Version de Python"
    ddigraph nécessite **Python 3.12-3.14**. Vérifiez votre version avec `python --version`.

Le paquet installe automatiquement toutes les dépendances requises (lxml, pilote neo4j, pydantic-settings, networkx, rdflib, gremlinpython, etc.).

---

## Démarrer Neo4j

La méthode la plus rapide pour obtenir une instance Neo4j locale est d'utiliser Docker :

```bash
docker run --rm --name neo4j-demo \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:5
```

Après quelques secondes, la base de données est accessible sur `bolt://localhost:7687` et l'interface web est disponible à l'adresse <http://localhost:7474>.

!!! note "Neo4j Aura"
    Si vous préférez une instance gérée dans le cloud, créez gratuitement une
    base Neo4j Aura à l'adresse <https://neo4j.com/cloud/aura-free/> et
    utilisez l'URI `neo4j+s://` qui vous sera fournie.

!!! tip "Docker non installé ?"
    Si Docker n'est pas installé sur votre machine, vous pouvez également
    utiliser [Neo4j Desktop](https://neo4j.com/download/) qui fournit une
    interface graphique pour gérer vos bases de données locales.

---

## Variables d'environnement

Indiquez à ddigraph comment se connecter à Neo4j :

```bash
export DDIGRAPH_NEO4J_URI=bolt://localhost:7687
export DDIGRAPH_NEO4J_USER=neo4j
export DDIGRAPH_NEO4J_PASSWORD=password
```

Vous pouvez aussi placer ces valeurs dans un fichier `.env` dans votre répertoire de travail -- ddigraph le détecte automatiquement.

```ini
# .env
DDIGRAPH_NEO4J_URI=bolt://localhost:7687
DDIGRAPH_NEO4J_USER=neo4j
DDIGRAPH_NEO4J_PASSWORD=password
```

!!! warning "Sécurité"
    Ne versionnez jamais le fichier `.env` dans votre dépôt Git. Ajoutez-le
    à votre `.gitignore`.

---

## Amorcer le schéma

Avant de charger des données, créez les contraintes d'unicité et les index dont le chargeur a besoin :

```bash
# Schéma Codebook uniquement
ddigraph bootstrap

# Inclure également le schéma DDI-L FragmentInstance
ddigraph bootstrap
```

La commande est idempotente : l'exécuter plusieurs fois est sans danger.

!!! info "Que fait cette commande ?"
    `bootstrap` crée des contraintes d'unicité sur les identifiants de
    noeuds et des index sur les propriétés couramment interrogées. Cela
    garantit l'intégrité des données et accélère les requêtes.

---

## Charger un fichier DDI

### Via la CLI

La CLI auto-détecte si le fichier utilise le format DDI Codebook ou DDI-L FragmentInstance :

```bash
# DDI Codebook -- un identifiant de jeu de données est requis
ddigraph load codebook_survey.xml --dataset-id my-survey

# DDI-L FragmentInstance -- pas besoin d'identifiant de jeu de données
ddigraph load questionnaire.xml
```

Un chargement réussi affiche un récapitulatif :

```text
Ingestion complete: Category=45, CodeList=12, Instrument=1, QuestionItem=120, Sequence=30
```

!!! tip "Exécution à blanc"
    Ajoutez `--dry-run` pour valider le XML sans rien écrire dans Neo4j :
    ```bash
    ddigraph load survey.xml --dataset-id demo --dry-run
    ```

### Via l'API Python

```python
import asyncio
from neo4j import AsyncGraphDatabase
from ddigraph import DDILoader, DDIFragmentLoader, detect_ddi_format, Settings


async def main():
    settings = Settings()
    driver = AsyncGraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password.get_secret_value()),
    )

    path = "survey.xml"

    # Auto-détection du format
    fmt = detect_ddi_format(path)
    print(f"Format détecté : {fmt}")

    if fmt == "lifecycle":
        loader = DDIFragmentLoader(driver, settings=settings)
        result = await loader.load(path)
    else:
        loader = DDILoader(driver, settings=settings)
        result = loader.load(
            path,
            dataset_id="my-survey",
            dataset_name="Mon enquête",
        )

    print(result)
    await driver.close()


asyncio.run(main())
```

!!! note "Async/await"
    ddigraph utilise des E/S asynchrones pour l'écriture dans Neo4j. Le
    chargeur Codebook (`DDILoader`) propose une méthode synchrone `load()`,
    tandis que le chargeur Lifecycle (`DDIFragmentLoader`) est entièrement
    asynchrone.

---

## Explorer le graphe avec Cypher

Ouvrez le navigateur Neo4j à l'adresse <http://localhost:7474> et essayez quelques requêtes.

**Compter les noeuds par type :**

```cypher
CALL db.labels() YIELD label
RETURN label, count { MATCH (n) WHERE label IN labels(n) RETURN n } AS count
ORDER BY count DESC
```

**Lister tous les jeux de données :**

```cypher
MATCH (d:Dataset) RETURN d.id, d.name
```

**Trouver les variables liées à une question :**

```cypher
MATCH (v:Variable)-[:ASKS]->(q:Question)
RETURN v.label AS variable, q.text AS texte_question
LIMIT 10
```

**Explorer le flux de contrôle d'un instrument DDI-L :**

```cypher
MATCH path = (i:Instrument)-[:HAS_CONSTRUCT*1..3]->(n)
RETURN path
LIMIT 50
```

**Trouver les questions qui référencent une liste de codes :**

```cypher
MATCH (q:QuestionItem)-[:USES_CODELIST]->(cl:CodeList)
RETURN q.name AS question, cl.name AS liste_de_codes, cl.code_count
ORDER BY cl.code_count DESC
LIMIT 10
```

---

## Auto-détection du format DDI

ddigraph peut vous indiquer le format d'un fichier sans le charger :

```bash
ddigraph detect survey.xml
# Format: codebook
# File: survey.xml

ddigraph detect questionnaire.xml --json
# {"path":"questionnaire.xml","format":"lifecycle"}
```

En Python :

```python
from ddigraph import detect_ddi_format

fmt = detect_ddi_format("my_file.xml")
print(fmt)  # "codebook" ou "lifecycle"
```

La détection ne lit que l'élément racine du XML : elle est donc rapide même sur les fichiers volumineux.

---

## Utiliser des backends alternatifs

Neo4j est le backend principal, mais ddigraph peut écrire vers d'autres systèmes graphe grâce à son patron adaptateur. Voici un exemple rapide avec NetworkX qui ne nécessite aucune base de données :

```python
import asyncio
from pathlib import Path
import networkx as nx
from ddigraph.ingest.fragment_loader import DDIFragmentParser


async def load_to_networkx(path: str) -> nx.MultiDiGraph:
    G = nx.MultiDiGraph()
    parser = DDIFragmentParser(Path(path))

    for batch in parser.parse_batches():
        # Ajouter les noeuds
        for element_type, fragments in batch.fragments_by_type.items():
            for fragment in fragments:
                props = fragment.to_dict()
                node_id = props.pop("fragment_id")
                G.add_node(node_id, node_type=element_type, **props)

        # Ajouter les arêtes
        for from_id, rel_type, to_id in batch.relationships:
            G.add_edge(from_id, to_id, key=rel_type, type=rel_type)

    return G


G = asyncio.run(load_to_networkx("questionnaire.xml"))
print(f"Noeuds : {G.number_of_nodes()}, Arêtes : {G.number_of_edges()}")
```

!!! tip "Autres backends"
    RDF est fourni avec le package : utilisez `ddigraph export`. Voyez le
    [guide du backend RDF](../backends/rdf.md).

    Pour les autres, le répertoire `demo/` propose des exemples pour
    [Gremlin](https://github.com/pbisson44/ddigraph/blob/main/demo/load_gremlin.py) et
    [pandas](https://github.com/pbisson44/ddigraph/blob/main/demo/load_pandas.py).
    Ce sont des exemples, pas des adaptateurs fournis.

---

## Prochaines étapes

Vous maîtrisez désormais le flux de travail principal : installer, connecter, amorcer, charger, interroger. Voici quelques pistes pour aller plus loin :

- **[Référence de configuration](../reference/configuration.md)** -- toutes les variables d'environnement et options CLI en un seul endroit.
- **[Référence CLI](../reference/cli.md)** -- documentation complète des commandes, y compris les réglages d'ingestion et les options TLS.
- **[Architecture](../user-guide/architecture.md)** -- comment l'analyse en flux continu, le traitement par lots et les écritures asynchrones s'articulent.
- **[Guide DDI-L FragmentInstance](../user-guide/fragments.md)** -- exploration approfondie de la prise en charge de DDI Lifecycle.
- **[Patron adaptateur](../user-guide/adapter.md)** -- écrire votre propre adaptateur de backend.
- **[Optimisation des performances](../advanced/tuning.md)** -- taille des lots, concurrence et paramètres de nouvelle tentative.
- **[FAQ](../project/faq.md)** -- questions fréquentes et dépannage.

Bonne exploration !
