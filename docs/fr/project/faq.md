# Foire aux questions

## Général

### Quels formats DDI sont pris en charge ?

ddigraph prend en charge trois formats DDI :

- **DDI Codebook** (DDI-C 2.5 / 2.6) -- Format traditionnel à plat avec un noeud central Dataset
  reliant les variables, questions et métadonnées au niveau de l'étude. Largement utilisé
  par les archives d'enquêtes et les catalogues de données.
- **DDI-L FragmentInstance** (DDI Lifecycle 3.2/3.3) -- Format modulaire construit autour
  de fragments réutilisables. Prend en charge les flux de questionnaires, les instruments
  CAPI/CAWI et les conceptions d'études complexes.
- **DDI-CDI** (1.0) -- Modèle d'intégration cross-domaine. Capture les variables conceptuelles,
  représentées et d'instance ainsi que leurs relations pour l'harmonisation inter-études.

La CLI détecte automatiquement le format, ou vous pouvez le spécifier avec
`--format codebook` ou `--format lifecycle`.

### Ai-je besoin de Neo4j pour utiliser ddigraph ?

Non. Bien que Neo4j soit le backend principal, ddigraph prend en charge plusieurs backends :

- **NetworkX** -- Graphe Python en mémoire, aucune base de données requise
- **pandas** -- Basé sur les DataFrames, aucune base de données requise
- **RDF/SPARQL** -- Tout triplestore (Fuseki, Blazegraph, GraphDB)
- **Gremlin** -- JanusGraph, Amazon Neptune, Azure Cosmos DB

Consultez la section [Backends graphe](../backends/neo4j.md) pour les guides de configuration.

### Quelles versions de Python sont prises en charge ?

Python 3.12-3.14. Le paquet utilise des fonctionnalités Python modernes incluant
`asyncio`, les annotations de types et les instructions `match`.

### En quoi ddigraph diffère-t-il des autres outils DDI ?

La plupart des outils DDI se concentrent sur la validation, l'édition ou la conversion entre
versions DDI. ddigraph est spécifiquement conçu pour **transformer les métadonnées DDI en
structures de graphe** pour l'interrogation et l'analyse. Cela le rend adapté pour :

- Le suivi de la lignée à travers les instruments d'enquête
- L'analyse d'impact (quelles questions affectent quelles variables)
- La comparaison inter-études via la traversée de graphe
- L'intégration avec les écosystèmes de graphes de connaissances (RDF, SPARQL)

---

## Installation et configuration

### Comment installer ddigraph ?

```bash
pip install ddigraph
```

Pour le développement :

```bash
pip install -e ".[dev,docs]"
```

### Comment me connecter à Neo4j Aura (cloud) ?

Utilisez le schéma d'URI `neo4j+s://` fourni par Aura :

```bash
export DDIGRAPH_NEO4J_URI=neo4j+s://xxxx.databases.neo4j.io
export DDIGRAPH_NEO4J_USER=neo4j
export DDIGRAPH_NEO4J_PASSWORD=votre-mot-de-passe-aura
```

!!! tip
    Neo4j Aura utilise des connexions chiffrées par défaut. Le schéma `neo4j+s://` gère
    TLS automatiquement -- aucun drapeau `--neo4j-tls-*` supplémentaire n'est nécessaire.

### Comment migrer de neo4ddi à ddigraph ?

1. Mettez à jour vos imports :

    ```python
    # Avant
    from neo4ddi import DDILoader

    # Après
    from ddigraph import DDILoader
    ```

2. Mettez à jour les commandes CLI de `neo4ddi` à `ddigraph`

3. Mettez à jour les variables d'environnement de `NEO4DDI_*` à `DDIGRAPH_*` (l'ancien
   préfixe fonctionne toujours mais est obsolète)

---

## Performances

### Comment gérer les fichiers volumineux ?

ddigraph utilise l'analyse XML en flux, la consommation mémoire est donc bornée par
`chunk_size` plutôt que par la taille du fichier. Pour les fichiers volumineux :

```bash
# Augmenter la taille des lots pour moins d'allers-retours avec la base
ddigraph load gros-fichier.xml --dataset-id demo --chunk-size 500
```

!!! tip
    La valeur par défaut de `--chunk-size` (200) fonctionne bien pour la plupart des fichiers.
    Augmentez-la pour les fichiers avec de nombreux petits fragments. Diminuez-la si vous
    constatez une pression mémoire.

### Pourquoi l'ingestion est-elle lente ?

Causes courantes :

1. **Latence réseau** vers Neo4j -- Utilisez une instance locale ou augmentez `--chunk-size`
   pour réduire les allers-retours
2. **Index manquants** -- Exécutez `ddigraph bootstrap` avant le
   chargement
3. **Taille de lot trop petite** -- Essayez `--chunk-size 500` ou plus
4. **Surcoût des réessais** -- Si les connexions sont instables, ajustez les paramètres :

    ```bash
    ddigraph load fichier.xml --dataset-id demo \
      --write-retry-attempts 3 \
      --write-retry-base-delay 0.5 \
      --write-retry-jitter 0.2
    ```

Consultez [Optimisation des performances](../advanced/tuning.md) pour des conseils détaillés.

---

## Dépannage

### Connexion refusée / Impossible de se connecter à Neo4j

Vérifiez que Neo4j est en cours d'exécution et accessible :

```bash
# Vérifier si Neo4j écoute
curl -s http://localhost:7474 | head -1

# Vérifier les variables d'environnement
echo $DDIGRAPH_NEO4J_URI
echo $DDIGRAPH_NEO4J_USER
```

Corrections courantes :

- Assurez-vous que Neo4j est démarré : `docker ps` ou vérifiez le service Neo4j
- Vérifiez le schéma d'URI : utilisez `bolt://` en local, `neo4j+s://` pour Aura
- Vérifiez que les identifiants correspondent à ce que Neo4j attend

### Erreur de mémoire ou processus tué

Pour les fichiers très volumineux, réduisez l'utilisation mémoire :

```bash
# Des lots plus petits utilisent moins de mémoire
ddigraph load gros-fichier.xml --dataset-id demo --chunk-size 50
```

Si le processus Python est tué par le système, augmentez la mémoire disponible ou traitez
le fichier en sections.

### Erreurs de contraintes de schéma

Si vous voyez des erreurs concernant des contraintes manquantes ou des clés dupliquées :

```bash
# Ré-exécuter l'amorçage du schéma (idempotent)
ddigraph bootstrap
```

### Erreur "Format inconnu"

Si `ddigraph detect` signale un format inconnu, le fichier n'est peut-être pas un format DDI
pris en charge. ddigraph requiert :

- DDI Codebook : élément racine `<codeBook>` avec l'espace de noms DDI 2.x
- DDI-L FragmentInstance : élément racine `<FragmentInstance>` avec l'espace de noms DDI Lifecycle 3.x

### Puis-je utiliser ddigraph sans programmation asynchrone ?

La CLI gère l'exécution asynchrone en interne -- vous exécutez simplement `ddigraph load`
comme une commande normale.

Pour l'API Python, encapsulez les appels asynchrones avec `asyncio.run()` :

```python
import asyncio
from ddigraph import DDILoader
from ddigraph.config import Settings

async def charger():
    settings = Settings()
    # ... configurer le pilote et le chargeur
    result = await loader.load(path, dataset_id="demo")
    return result

result = asyncio.run(charger())
```

### Comment ajouter un backend graphe personnalisé ?

Implémentez le protocole `GraphWriteAdapter` :

```python
from ddigraph.schema import GraphWriteAdapter

class MonAdaptateur(GraphWriteAdapter):
    async def write_batch(self, graph, **kwargs):
        ...
    async def purge_dataset(self, dataset_id, **kwargs):
        ...
```

Consultez [Patron adaptateur](../user-guide/adapter.md) pour le guide complet.
