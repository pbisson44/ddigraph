# Démarrage rapide

Ce guide vous montre la façon la plus rapide de charger un fichier DDI dans une base de données
graphe. Nous commençons avec **Neo4j** — la configuration la plus courante — puis montrons les
autres options.

Si vous n'avez pas encore installé ddigraph, commencez par [Installation](installation.md).

---

## Étape 1 — Choisissez votre base de données

Choisissez la base de données que vous voulez utiliser. Si vous n'êtes pas sûr, choisissez
Neo4j — c'est l'option la plus complète et la plus facile pour débuter.

=== "Neo4j"

    **Qu'est-ce que c'est ?** Neo4j est une base de données graphe qui stocke les données
    sous forme de nœuds et de relations. C'est le choix recommandé pour la plupart des utilisateurs.

    ```bash
    # Démarrer Neo4j avec Docker (une seule fois)
    docker run -d --name neo4j \
        -p 7474:7474 -p 7687:7687 \
        -e NEO4J_AUTH=neo4j/password \
        neo4j:latest

    # Indiquer à ddigraph où se trouve Neo4j
    export DDIGRAPH_NEO4J_URI=bolt://localhost:7687
    export DDIGRAPH_NEO4J_USER=neo4j
    export DDIGRAPH_NEO4J_PASSWORD=password

    # Initialiser le schéma de la base (une seule fois avant le premier chargement)
    ddigraph bootstrap

    # Charger votre fichier DDI
    ddigraph load survey.xml --dataset-id demo
    ```

    Après l'exécution, vos métadonnées DDI se trouvent dans Neo4j sous forme de graphe.
    Ouvrez `http://localhost:7474` dans votre navigateur pour l'explorer visuellement.

    **Que fait `bootstrap` ?**
    Il crée les index et contraintes dont Neo4j a besoin pour stocker correctement les
    données DDI. C'est sûr de l'exécuter plusieurs fois — si le schéma existe déjà, rien
    ne change.

=== "RDF/SPARQL"

    **Qu'est-ce que c'est ?** RDF (Resource Description Framework) est un format pour
    représenter les données sous forme de triplets liés. Utilisez ceci si vous travaillez
    avec des outils du web sémantique ou des triplestores comme Virtuoso, GraphDB ou Stardog.

    ```python
    import ddigraph

    # Un seul appel. Le vocabulaire, la conversion SKOS et les IRI sont
    # gérés pour vous ; voyez le guide RDF pour le détail de la sortie.
    result = ddigraph.export("survey.xml", "output.ttl", format="turtle")
    print(result.triples, "triples")
    ```

=== "NetworkX"

    **Qu'est-ce que c'est ?** NetworkX est une bibliothèque Python pour analyser des graphes
    en mémoire — aucune base de données séparée requise. Utilisez ceci pour des analyses
    locales rapides ou du prototypage.

    ```python
    import networkx as nx

    from ddigraph import iter_graph


    def node_id(node):
        return "|".join(str(v) for _k, v in sorted(node.identity.items()))


    G = nx.MultiDiGraph()

    for chunk in iter_graph("survey.xml"):
        for node in chunk.nodes:
            G.add_node(node_id(node), node_type=node.label, **node.properties)
        for edge in chunk.relationships:
            G.add_edge(node_id(edge.start), node_id(edge.end), key=edge.type)

    print(f"Chargé : {G.number_of_nodes()} nœuds, {G.number_of_edges()} arêtes")
    ```

=== "Gremlin"

    **Qu'est-ce que c'est ?** Gremlin est un langage de requête graphe pris en charge par
    des bases de données comme JanusGraph, Amazon Neptune et Azure Cosmos DB.

    ```python
    from gremlin_python.process.anonymous_traversal import traversal
    from gremlin_python.driver.driver_remote_connection import DriverRemoteConnection
    from ddigraph import iter_graph

    connection = DriverRemoteConnection("ws://localhost:8182/gremlin", "g")
    g = traversal().withRemote(connection)

    for chunk in iter_graph("survey.xml"):
        for node in chunk.nodes:
            node_id = next(iter(node.identity.values()))
            g.addV(node.label).property("id", node_id).property(
                "name", node.properties.get("label", "")
            ).iterate()

    connection.close()
    ```

---

## Étape 2 — Vérifier le format (optionnel)

ddigraph détecte automatiquement si votre fichier est DDI Codebook, DDI Lifecycle ou DDI-CDI.
Vous pouvez vérifier manuellement avec :

```python
from ddigraph import detect_ddi_format

format_type = detect_ddi_format("survey.xml")
print(format_type)  # "codebook", "lifecycle" ou "cdi"
```

**Que signifient ces formats ?**

| Format | Élément XML racine | À utiliser quand |
|---|---|---|
| `codebook` | `<codeBook>` ou `<codebook>` | Archives d'enquêtes traditionnelles |
| `lifecycle` | `<FragmentInstance>` | Outils de conception de questionnaires (DDI-L 3.2 / 3.3) |
| `cdi` | Espace de noms DDI-CDI | Projets d'intégration inter-domaines |

Si vous n'êtes pas sûr du format de votre fichier, exécutez `detect_ddi_format` et il vous
le dira.

Le format n'est que la première question. Pour voir ce que contient
vraiment le fichier, affichez-en un aperçu. Aucune base n'est requise :

<!-- runnable -->
```bash
ddigraph preview "$FIXTURE"
```

La commande affiche un décompte par type de nœud et par relation : vous
savez donc ce qu'un chargement produirait avant de le lancer.
`--format html -o preview.html` écrit le même résumé sous forme de page
à ouvrir dans un navigateur. Voyez la
[référence CLI](../reference/cli.md#apercu-dun-fichier) pour les autres
formats.

---

## Étape 3 — Charger depuis Python

L'API Python reflète la CLI. Un seul appel charge un fichier. Il
détecte le format, initialise le schéma et écrit vers votre cible :

```python
import ddigraph

result = ddigraph.load(
    "survey.xml",
    target="neo4j://localhost:7687",
    dataset_id="my-survey",
)
print(result.flavor, result.nodes_written, result.relationships_written)
```

`target` est une URL Neo4j (`bolt://...` ou `neo4j://...`). Omettez-la
pour utiliser la connexion de votre environnement. Il existe aussi une
forme asynchrone, `ddigraph.aload(...)`, avec les mêmes arguments.
Pour les autres backends (RDF, Gremlin, NetworkX, pandas), utilisez le
parseur plus un adaptateur — voir les pages
[Backends](../backends/neo4j.md) et les exemples par backend
ci-dessus.

Détecter le format d'un fichier sans le charger :

```python
import ddigraph

print(ddigraph.detect("survey.xml"))  # 'codebook', 'lifecycle' ou 'cdi'
```

### Plus de contrôle (avancé)

Si vous devez piloter vous-même les loaders, les classes de plus bas
niveau restent disponibles :

```python
import asyncio
from neo4j import AsyncGraphDatabase
from ddigraph import DDILoader, DDIFragmentLoader, detect_ddi_format, iter_graph
from ddigraph.config import Settings
from ddigraph.graph.bootstrap import ensure_schema


async def load_ddi(path: str, dataset_id: str = "default"):
    settings = Settings()
    driver = AsyncGraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password.get_secret_value()),
    )

    try:
        # Initialiser le schéma (sûr à exécuter à chaque fois)
        await ensure_schema(driver, include_fragments=True)

        # Choisir le bon chargeur selon le format
        fmt = detect_ddi_format(path)
        if fmt == "lifecycle":
            loader = DDIFragmentLoader(driver, settings=settings)
            result = await loader.load(path)
        elif fmt == "cdi":
            # DDI-CDI has no dedicated loader class. Stream it through the
            # backend-neutral view instead, which every flavor supports.
            from ddigraph.graph.writer import GraphChunkWriter

            writer = GraphChunkWriter(driver, database=settings.neo4j_database)
            result = await writer.write(iter_graph(path))
        else:
            loader = DDILoader(driver, settings=settings)
            result = await loader.load(path, dataset_id=dataset_id)

        return result
    finally:
        await driver.close()


result = asyncio.run(load_ddi("survey.xml", "my-survey"))
print(f"Chargé : {result}")
```

---

## Étape 4 — Explorer vos données

Maintenant que vos données sont chargées, exécutez quelques requêtes pour voir ce qu'il y a.

### Dans Neo4j Browser (`http://localhost:7474`)

```cypher
-- Compter tous les nœuds par type
MATCH (n) RETURN labels(n) AS type, count(n) AS nombre ORDER BY nombre DESC

-- Lister toutes les variables d'un jeu de données
MATCH (d:Dataset {id: 'demo'})<-[:IN_DATASET]-(v:Variable)
RETURN v.name, v.label

-- Questions avec leurs listes de réponses
MATCH (q:QuestionItem)-[:USES_CODELIST]->(cl:CodeList)
RETURN q.name, q.question_text, cl.name
```

### En Python (NetworkX)

```python
import networkx as nx

# Trouver des chemins entre deux nœuds
paths = list(nx.all_simple_paths(G, source="instrument-1", target="question-5", cutoff=5))

# Exporter pour la visualisation
nx.write_graphml(G, "ddi_graph.graphml")
```

---

## Et ensuite ?

- **[Vos premières requêtes](first-queries.md)** — guide étape par étape pour explorer vos données
- **[Modèle relationnel](../user-guide/relationships.md)** — tous les types de nœuds et relations
- **[Optimisation des performances](../advanced/tuning.md)** — optimiser pour les grands fichiers
- **[Référence CLI](../reference/cli.md)** — toutes les commandes disponibles
