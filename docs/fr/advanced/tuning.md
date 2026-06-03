# Optimisation des performances

Ce guide couvre les paramètres de réglage pour l'ingestion DDI Codebook et DDI-L
FragmentInstance.

## Référence rapide

| Paramètre | Défaut | DDI Codebook | DDI-L FragmentInstance |
| ----------- | --------- | -------------- | ------------------------ |
| `chunk_size` | 200 | Enregistrements par lot | Fragments par lot |
| `queue_maxsize` | 2 | Lots en mémoire tampon | N/A (analyse synchrone) |
| `writer_concurrency` | 4 | Écritures parallèles | N/A (lots séquentiels) |
| `write_retry_attempts` | 3 | Nombre de réessais | Nombre de réessais |

## Taille des lots (`DDIGRAPH_CHUNK_SIZE`)

Contrôle le nombre d'enregistrements/fragments regroupés avant l'écriture dans Neo4j.

### DDI Codebook

Des lots plus grands réduisent le surcoût transactionnel mais augmentent la latence par
transaction. Le seuil compte tous les types d'enregistrements analysés ensemble (variables,
questions, catégories, etc.) :

```bash
# Lots plus grands pour une ingestion à haut débit
export DDIGRAPH_CHUNK_SIZE=1000

# Lots plus petits pour les environnements à mémoire limitée
export DDIGRAPH_CHUNK_SIZE=100
```

Pour les codebooks avec un mélange de métadonnées et de variables, 500-1000 enregistrements
combinés maintient l'efficacité des écritures.

### DDI-L FragmentInstance

Les fragments sont regroupés par type d'élément avant les écritures UNWIND :

```bash
# Pour les gros fichiers FragmentInstance (>5000 fragments)
ddigraph load questionnaire.xml --chunk-size 500

# Pour les fichiers plus petits ou le débogage
ddigraph load questionnaire.xml --chunk-size 50
```

**Recommandation** : Commencez avec 200-300 pour les fichiers FragmentInstance et ajustez en
fonction de la mémoire et de la latence d'écriture.

## Taille de la file d'attente (`DDIGRAPH_QUEUE_MAXSIZE`)

*S'applique uniquement au DDI Codebook.*

Contrôle la contre-pression entre l'analyse et l'écriture en limitant le nombre d'objets
`DDIBatch` en file d'attente :

```bash
# Maintenir l'écrivain occupé sur les systèmes rapides
export DDIGRAPH_QUEUE_MAXSIZE=4

# Réduire l'utilisation mémoire
export DDIGRAPH_QUEUE_MAXSIZE=1
```

Le chargeur FragmentInstance utilise une analyse synchrone par lots, donc la taille de la
file d'attente ne s'applique pas.

## Concurrence d'écriture (`DDIGRAPH_WRITER_CONCURRENCY`)

*S'applique uniquement au DDI Codebook.*

Définit le nombre de lots écrits en parallèle dans Neo4j :

```bash
# Concurrence plus élevée pour les clusters Neo4j rapides
export DDIGRAPH_WRITER_CONCURRENCY=4

# Écrivain unique pour le débogage ou les connexions limitées
export DDIGRAPH_WRITER_CONCURRENCY=1
```

Assurez-vous que `max_connection_pool_size` >= `writer_concurrency` pour éviter la famine
des écrivains.

## Pool de connexions du pilote

### Taille du pool de connexions

```bash
# Égaler ou dépasser la concurrence d'écriture
export DDIGRAPH_MAX_CONNECTION_POOL_SIZE=10
export DDIGRAPH_WRITER_CONCURRENCY=4
```

### Délais d'expiration

| Paramètre | Objectif | Recommandation |
| --------- | -------- | -------------- |
| `connection_timeout` | Temps pour établir la connexion | 5-30s |
| `max_connection_lifetime` | Recyclage des connexions inactives | 300-3600s |
| `session_timeout` | Durée de vie de la session | Adapter aux besoins transactionnels |
| `transaction_timeout` | Limite de transaction côté serveur | 30-120s |

```bash
# Défaillance rapide sur les problèmes de connexion
export DDIGRAPH_CONNECTION_TIMEOUT=5

# Transactions longues pour les gros lots
export DDIGRAPH_TRANSACTION_TIMEOUT=60
```

## Configuration des réessais

Les deux chargeurs prennent en charge le backoff exponentiel avec gigue pour les défaillances
transitoires :

```bash
# Réessais agressifs pour les réseaux instables
export DDIGRAPH_WRITE_RETRY_ATTEMPTS=5
export DDIGRAPH_WRITE_RETRY_BASE_DELAY=1.0
export DDIGRAPH_WRITE_RETRY_JITTER=0.5

# Défaillance rapide pour les environnements stables
export DDIGRAPH_WRITE_RETRY_ATTEMPTS=2
export DDIGRAPH_WRITE_RETRY_BASE_DELAY=0.1
export DDIGRAPH_WRITE_RETRY_JITTER=0
```

Équivalent CLI :

```bash
ddigraph load file.xml --dataset-id demo \
  --write-retry-attempts 5 \
  --write-retry-base-delay 1.0 \
  --write-retry-jitter 0.5
```

## Dry Run et Replace

### Mode validation

Analyser et planifier sans écrire :

```bash
# Valider avant l'ingestion en production
ddigraph load file.xml --dataset-id demo --dry-run

# Ou via variable d'environnement
DDIGRAPH_DRY_RUN=true ddigraph load file.xml --dataset-id demo
```

### Mode remplacement

Purger les données existantes avant le chargement :

```bash
# Réingérer un jeu de données depuis zéro
ddigraph load file.xml --dataset-id demo --replace

# Replace est ignoré pendant le dry-run
ddigraph load file.xml --dataset-id demo --dry-run --replace  # Aucune purge n'a lieu
```

## Réglage spécifique au format

### DDI-C

Optimiser pour le pipeline producteur/consommateur :

```bash
# Configuration à haut débit
export DDIGRAPH_CHUNK_SIZE=1000
export DDIGRAPH_QUEUE_MAXSIZE=4
export DDIGRAPH_WRITER_CONCURRENCY=4
export DDIGRAPH_MAX_CONNECTION_POOL_SIZE=10
```

### DDI-L FragmentInstance

Optimiser pour les écritures UNWIND par lots :

```bash
# Gros fichiers FragmentInstance
export DDIGRAPH_CHUNK_SIZE=500
export DDIGRAPH_TRANSACTION_TIMEOUT=60
# Environnements à mémoire limitée
export DDIGRAPH_CHUNK_SIZE=100
```

## Surveillance

Activez les métriques par lot pour la visibilité :

```bash
ddigraph load file.xml --dataset-id demo --batch-metrics
```

Cela émet des métriques de chronométrage et de comptage pouvant être capturées par les
systèmes d'observabilité.

### Métriques utiles

| Métrique | Description |
| -------- | ----------- |
| `batch_duration_seconds` | Durée par écriture de lot |
| `batch_size` | Enregistrements/fragments par lot |
| `batches` | Nombre total de lots traités |
| `batch_write_retries` | Nombre de réessais |

## Exemples pratiques

### Grand DDI Codebook (10K+ variables)

```bash
export DDIGRAPH_NEO4J_URI=bolt://cluster:7687
export DDIGRAPH_MAX_CONNECTION_POOL_SIZE=20
export DDIGRAPH_CHUNK_SIZE=1000
export DDIGRAPH_QUEUE_MAXSIZE=4
export DDIGRAPH_WRITER_CONCURRENCY=4
export DDIGRAPH_TRANSACTION_TIMEOUT=60
ddigraph bootstrap
ddigraph load large_codebook.xml --dataset-id survey2024 --batch-metrics
```

### Grand DDI-L FragmentInstance (5K+ fragments)

```bash
export DDIGRAPH_NEO4J_URI=bolt://cluster:7687
export DDIGRAPH_CHUNK_SIZE=500
export DDIGRAPH_TRANSACTION_TIMEOUT=60
export DDIGRAPH_WRITE_RETRY_ATTEMPTS=5
ddigraph bootstrap
ddigraph load large_questionnaire.xml --batch-metrics --json
```

### Instance cloud AuraDB

```bash
export DDIGRAPH_NEO4J_URI=neo4j+s://xxxx.databases.neo4j.io
export DDIGRAPH_ENCRYPTED=true
export DDIGRAPH_CONNECTION_TIMEOUT=10
export DDIGRAPH_CHUNK_SIZE=200  # Lots plus petits pour la latence cloud
export DDIGRAPH_WRITE_RETRY_ATTEMPTS=5
export DDIGRAPH_WRITE_RETRY_BASE_DELAY=2.0
ddigraph bootstrap
ddigraph load file.xml --dataset-id demo
```

### Environnement à mémoire limitée

```bash
export DDIGRAPH_CHUNK_SIZE=50
export DDIGRAPH_QUEUE_MAXSIZE=1
export DDIGRAPH_WRITER_CONCURRENCY=1
ddigraph load file.xml --dataset-id demo
```

## Comparaison des performances

### Performances DDI-L FragmentInstance

Pour `Ireland_LabourSurvey.xml` (148K lignes, 2 762 fragments) :

| Métrique | Valeur |
| -------- | ------ |
| Requêtes Neo4j | ~30 |
| Profil mémoire | O(chunk_size) |
| Opérations async | Toutes les écritures |
| Requêtes par fragment | ~0.01 |

Le faible nombre de requêtes provient du regroupement UNWIND par type de fragment.

## Dépannage

### Ingestion lente

1. Augmentez `chunk_size` pour réduire le surcoût transactionnel
2. Augmentez `writer_concurrency` (Codebook) si le pool a de la capacité
3. Vérifiez les ressources du serveur Neo4j et les index

### Problèmes de mémoire

1. Diminuez `chunk_size` pour réduire les données en cours de traitement
2. Diminuez `queue_maxsize` (Codebook) pour limiter la mise en mémoire tampon
3. Assurez-vous que l'analyse XML utilise le traitement en flux (`iterparse`)

### Erreurs de connexion

1. Augmentez `connection_timeout` pour les réseaux lents
2. Augmentez `write_retry_attempts` pour les défaillances transitoires
3. Vérifiez les paramètres TLS pour les instances cloud

### Délais de transaction dépassés

1. Diminuez `chunk_size` pour réduire le travail par transaction
2. Augmentez `transaction_timeout` pour les gros lots
3. Vérifiez la configuration du serveur Neo4j

Voir [Architecture](../user-guide/architecture.md) pour le contexte de conception et
[Référence CLI](../reference/cli.md) pour toutes les options.
