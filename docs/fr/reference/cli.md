# Référence CLI

Le package installe une commande `ddigraph` avec des sous-commandes pour l'amorçage du schéma,
la détection de format et l'ingestion. Le CLI **détecte automatiquement le format DDI** par
défaut, prenant en charge les fichiers DDI Codebook, DDI-L FragmentInstance et DDI-CDI.

## Vue d'ensemble des commandes

| Commande | Description |
| --------- | ------------- |
| `bootstrap` | Créer les contraintes et index (Codebook + DDI-L par défaut ; ajoutez `--no-include-fragments` pour le codebook seul) |
| `load` | Charger en flux un fichier DDI XML dans Neo4j (détection automatique du format) |
| `detect` | Détecter le format DDI d'un fichier sans le charger |
| `version` | Afficher la version de ddigraph installée |

## Amorçage du schéma

`bootstrap` crée les index et contraintes dont Neo4j a besoin avant
votre premier chargement. Vous pouvez l'exécuter plusieurs fois sans
risque.

```bash
# Codebook + DDI-L FragmentInstance (par défaut)
ddigraph bootstrap --neo4j-uri bolt://db:7687 --neo4j-user neo4j --neo4j-password password

# Codebook seul
ddigraph bootstrap --no-include-fragments
```

## Chargement des données

La commande `load` détecte automatiquement le format DDI et utilise le chargeur approprié :

```bash
# Détection automatique du format (comportement par défaut)
ddigraph load /path/to/survey.xml --dataset-id demo

# Spécifier explicitement le format
ddigraph load /path/to/codebook.xml --format codebook --dataset-id demo
ddigraph load /path/to/questionnaire.xml --format lifecycle

# Pour DDI-L FragmentInstance, --dataset-id est optionnel
ddigraph load /path/to/fragments.xml
```

### Options de chargement

```bash
ddigraph load FILE [OPTIONS]
Options:
  --format {auto,codebook,lifecycle,cdi}  Format DDI (défaut : auto)
  --dataset-id ID                     Identifiant du jeu de données (requis pour Codebook)
  --dataset-name NAME                 Nom lisible du jeu de données
  --chunk-size N                      Enregistrements par lot (défaut : 200)
  --writer-concurrency N              Tâches d'écriture concurrentes
  --dry-run / --validate-only         Analyser sans écrire dans Neo4j
  --replace                           Effacer les données existantes avant le chargement
  --json                              Afficher les résultats en JSON
```

### Exemples

```bash
# Charger en flux un DDI Codebook avec réglage de l'ingestion
ddigraph load /path/to/codebook.xml --dataset-id demo --dataset-name "Demo Survey" \
  --chunk-size 500 --writer-concurrency 2 --batch-metrics --log-level DEBUG
# Valider un chargement sans écrire (analyse et plans Cypher uniquement)
ddigraph load /path/to/codebook.xml --dataset-id demo --dry-run

# Purger un jeu de données existant avant le rechargement
ddigraph load /path/to/codebook.xml --dataset-id demo --replace

# Charger un DDI-L FragmentInstance avec sortie JSON
ddigraph load /path/to/questionnaire.xml --json
```

## Détection de format

Détecter le format DDI d'un fichier sans le charger :

```bash
ddigraph detect /path/to/survey.xml

# Sortie :
# Format: lifecycle
# File: /path/to/survey.xml

ddigraph detect /path/to/survey.xml --json
# Sortie : {"path": "/path/to/survey.xml", "format": "lifecycle"}

ddigraph detect /path/to/cdi-metadata.xml
# Sortie :
# Format: cdi
# File: /path/to/cdi-metadata.xml
```

La fonction `detect_ddi_format()` retourne l'une des trois valeurs : `"codebook"`, `"lifecycle"` ou
`"cdi"`. La fonction utilitaire `is_cdi_format()` est également disponible pour la détection
spécifique au CDI.

## Variables d'environnement

Exportez les informations de connexion Neo4j depuis votre shell ou un fichier `.env` :

```bash
export DDIGRAPH_NEO4J_URI=bolt://localhost:7687
export DDIGRAPH_NEO4J_USER=neo4j
export DDIGRAPH_NEO4J_PASSWORD=secret
export DDIGRAPH_NEO4J_DATABASE=neo4j  # optionnel, défaut : "neo4j"
```

### Correspondance complète des options et variables d'environnement

Chaque option CLI correspond 1:1 à une variable d'environnement `DDIGRAPH_`. Les booléens
acceptent les chaînes vrai/faux (`true/false`, `1/0`).

#### Options de connexion

| Option CLI | Variable d'environnement | Description |
| ---------- | --------------------- | ------------- |
| `--neo4j-uri` | `DDIGRAPH_NEO4J_URI` | URI bolt/s Neo4j |
| `--neo4j-user` | `DDIGRAPH_NEO4J_USER` | Nom d'utilisateur Neo4j |
| `--neo4j-password` | `DDIGRAPH_NEO4J_PASSWORD` | Mot de passe Neo4j |
| `--neo4j-database` | `DDIGRAPH_NEO4J_DATABASE` | Base de données cible (défaut : `neo4j`) |

#### Pool de connexions du pilote

| Option CLI | Variable d'environnement | Description |
| ---------- | --------------------- | ------------- |
| `--max-connection-pool-size` | `DDIGRAPH_MAX_CONNECTION_POOL_SIZE` | Nombre max de connexions dans le pool |
| `--connection-timeout` | `DDIGRAPH_CONNECTION_TIMEOUT` | Délai d'ouverture de connexion (secondes) |
| `--max-connection-lifetime` | `DDIGRAPH_MAX_CONNECTION_LIFETIME` | Durée de vie du pool (secondes) |
| `--session-timeout` | `DDIGRAPH_SESSION_TIMEOUT` | Durée de vie de la session (secondes) |
| `--transaction-timeout` | `DDIGRAPH_TRANSACTION_TIMEOUT` | Délai de transaction côté serveur |

#### Options TLS

| Option CLI | Variable d'environnement | Description |
| ---------- | --------------------- | ------------- |
| `--encrypted` | `DDIGRAPH_ENCRYPTED` | Exiger les connexions TLS |
| `--verify-hostname` | `DDIGRAPH_VERIFY_HOSTNAME` | Vérifier le nom d'hôte TLS |
| `--trusted-certificates` | `DDIGRAPH_TRUSTED_CERTIFICATES` | Politique de confiance (ex. `TRUST_ALL_CERTIFICATES`) |
| `--trusted-certificates-file` | `DDIGRAPH_TRUSTED_CERTIFICATES_FILE` | Chemin du fichier PEM |

#### Réglage de l'ingestion

| Option CLI | Variable d'environnement | Description |
| ---------- | --------------------- | ------------- |
| `--queue-maxsize` | `DDIGRAPH_QUEUE_MAXSIZE` | Seuil de contre-pression (lots) |
| `--chunk-size` | `DDIGRAPH_CHUNK_SIZE` | Enregistrements par lot |
| `--writer-concurrency` | `DDIGRAPH_WRITER_CONCURRENCY` | Tâches d'écriture concurrentes |
| `--batch-metrics` | `DDIGRAPH_BATCH_METRICS` | Émettre les métriques par lot |
| `--strict-parsing` | `DDIGRAPH_STRICT_PARSING` | Échouer sur les erreurs de syntaxe XML |
| `--dry-run` / `--validate-only` | `DDIGRAPH_DRY_RUN` | Analyser sans écrire |
| `--replace` | `DDIGRAPH_REPLACE` | Purger le jeu de données avant le chargement |

#### Paramètres de réessai

| Option CLI | Variable d'environnement | Description |
| ---------- | --------------------- | ------------- |
| `--write-retry-attempts` | `DDIGRAPH_WRITE_RETRY_ATTEMPTS` | Nombre total de tentatives |
| `--write-retry-base-delay` | `DDIGRAPH_WRITE_RETRY_BASE_DELAY` | Délai de base du backoff (secondes) |
| `--write-retry-jitter` | `DDIGRAPH_WRITE_RETRY_JITTER` | Gigue maximale (secondes) |

#### Journalisation

| Option CLI | Variable d'environnement | Description |
| ---------- | --------------------- | ------------- |
| `--log-level` | `DDIGRAPH_LOG_LEVEL` | Niveau de verbosité (`DEBUG`, `INFO`, etc.) |
| `--metrics-namespace` | `DDIGRAPH_METRICS_NAMESPACE` | Préfixe des métriques |

## Exemples de configuration TLS

```bash
# AuraDB (chiffrement activé ; utiliser les CA système/plateforme)
DDIGRAPH_NEO4J_URI=neo4j+s://<your-aura-host>:7687 \
  ddigraph bootstrap --encrypted

# Certificat auto-signé depuis un déploiement Neo4j privé
DDIGRAPH_ENCRYPTED=true \
DDIGRAPH_TRUSTED_CERTIFICATES_FILE=/etc/ssl/certs/private-ca.pem \
  ddigraph load /path/to/codebook.xml --dataset-id demo
```

## Configuration des réessais

Ajustez le comportement des réessais selon les conditions réseau :

```bash
# Réessais serrés pour une défaillance rapide lorsque le cluster est sain
ddigraph load /path/to/codebook.xml --dataset-id demo \
  --write-retry-attempts 2 --write-retry-base-delay 0.1 --write-retry-jitter 0

# Réessais souples pour survivre aux pertes de paquets intermittentes
DDIGRAPH_WRITE_RETRY_ATTEMPTS=5 \
DDIGRAPH_WRITE_RETRY_BASE_DELAY=1.0 \
DDIGRAPH_WRITE_RETRY_JITTER=0.5 \
  ddigraph load /path/to/codebook.xml --dataset-id demo
```

## Exemples combinés

Extraits prêts à copier-coller pour les configurations opérationnelles courantes :

```bash
# Limiter la durée des transactions et réessayer avec gigue
ddigraph load /path/to/codebook.xml --dataset-id demo \
  --transaction-timeout 15 --write-retry-attempts 5 \
  --write-retry-base-delay 0.5 --write-retry-jitter 0.25

# Observabilité au niveau des lots avec analyse stricte
DDIGRAPH_BATCH_METRICS=true \
  ddigraph load /path/to/codebook.xml --dataset-id demo \
  --strict-parsing --chunk-size 500 --queue-maxsize 4

# Charger un DDI-L FragmentInstance avec amorçage complet du schéma
ddigraph bootstrap
ddigraph load /path/to/questionnaire.xml --chunk-size 300

# Valider un fichier DDI-L sans écrire
ddigraph load /path/to/questionnaire.xml --dry-run --json
```

## Notes de comportement

- **Détection automatique du format** : Lorsque `--format auto` (par défaut), le CLI inspecte
  l'élément racine XML pour déterminer le format Codebook, FragmentInstance ou CDI.
- **Validation de l'identifiant du jeu de données** : Pour le format Codebook, `--dataset-id`
  est requis. Pour FragmentInstance, il est optionnel (les fragments sont auto-identifiants).
- **Dry-run et replace** : Lorsque `--dry-run` est activé, `--replace` est ignoré (aucune
  donnée n'est modifiée).
- **Analyse stricte vs permissive** : Le mode permissif par défaut active la récupération XML
  pour passer les balises malformées. Activez `--strict-parsing` pour échouer rapidement sur
  les erreurs de syntaxe.

Voir [Architecture](../user-guide/architecture.md) et [DDI-L FragmentInstance](../user-guide/fragments.md) pour le contexte de conception.
