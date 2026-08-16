# Référence de configuration

ddigraph utilise une configuration hiérarchique : les options CLI ont la priorité la plus
élevée, suivies des variables d'environnement, puis des valeurs par défaut. Un fichier `.env`
est automatiquement chargé s'il est présent dans le répertoire de travail.

## Ordre de précédence

1. **Options CLI** -- priorité la plus élevée
2. **Variables d'environnement** (`DDIGRAPH_*`)
3. **Fichier `.env`** dans le répertoire courant
4. **Valeurs par défaut** -- priorité la plus basse

!!! info "Fichier `.env`"
    ddigraph charge automatiquement un fichier `.env` situé dans le répertoire de travail
    courant. Chaque ligne doit suivre le format `CLÉ=valeur`. Les lignes vides et les
    commentaires commençant par `#` sont ignorés.

## Variables d'environnement

### Connexion Neo4j

| Variable | Option CLI | Description | Défaut |
| -------- | ---------- | ----------- | ------ |
| `DDIGRAPH_NEO4J_URI` | `--neo4j-uri` | URI bolt Neo4j | `bolt://localhost:7687` |
| `DDIGRAPH_NEO4J_USER` | `--neo4j-user` | Nom d'utilisateur Neo4j | `neo4j` |
| `DDIGRAPH_NEO4J_PASSWORD` | `--neo4j-password` | Mot de passe Neo4j | **requis** |
| `DDIGRAPH_NEO4J_DATABASE` | `--neo4j-database` | Base de données cible | `neo4j` |

```bash
export DDIGRAPH_NEO4J_URI=bolt://localhost:7687
export DDIGRAPH_NEO4J_USER=neo4j
export DDIGRAPH_NEO4J_PASSWORD=secret
export DDIGRAPH_NEO4J_DATABASE=neo4j
```

### Réglage de l'ingestion

| Variable | Option CLI | Description | Défaut |
| -------- | ---------- | ----------- | ------ |
| `DDIGRAPH_CHUNK_SIZE` | `--chunk-size` | Enregistrements par lot | `200` |
| `DDIGRAPH_DRY_RUN` | `--dry-run` | Valider sans écrire dans Neo4j | `false` |
| `DDIGRAPH_REPLACE` | `--replace` | Effacer les données existantes avant le chargement | `false` |
| `DDIGRAPH_MAX_QUEUE_SIZE` | -- | Taille maximale de la file d'attente asynchrone | `1000` |

```bash
# Lots plus grands pour un débit élevé
export DDIGRAPH_CHUNK_SIZE=500

# Mode validation uniquement
export DDIGRAPH_DRY_RUN=true

# Rechargement complet
export DDIGRAPH_REPLACE=true
```

!!! warning "Mode dry-run"
    Lorsque `DDIGRAPH_DRY_RUN=true`, l'option `--replace` est ignorée. Aucune donnée n'est
    modifiée en mode validation.

### Configuration des réessais

| Variable | Option CLI | Description | Défaut |
| -------- | ---------- | ----------- | ------ |
| `DDIGRAPH_WRITE_RETRY_ATTEMPTS` | `--write-retry-attempts` | Tentatives de réessai | `3` |
| `DDIGRAPH_WRITE_RETRY_BASE_DELAY` | `--write-retry-base-delay` | Délai de base en secondes (backoff exponentiel) | `0.5` |
| `DDIGRAPH_WRITE_RETRY_JITTER` | `--write-retry-jitter` | Gigue maximale en secondes | `0.2` |

Le mécanisme de réessai utilise un backoff exponentiel avec gigue. La formule est :

```text
délai = base_delay * (2 ^ tentative) + random(0, jitter)
```

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

### Options TLS

| Variable | Option CLI | Description | Défaut |
| -------- | ---------- | ----------- | ------ |
| `DDIGRAPH_ENCRYPTED` | `--encrypted` | Exiger les connexions TLS | `false` |
| `DDIGRAPH_VERIFY_HOSTNAME` | `--verify-hostname` | Vérifier le nom d'hôte TLS | `false` |
| `DDIGRAPH_TRUSTED_CERTIFICATES` | `--trusted-certificates` | Politique de confiance des certificats | -- |
| `DDIGRAPH_TRUSTED_CERTIFICATES_FILE` | `--trusted-certificates-file` | Chemin vers le fichier PEM des certificats | -- |

```bash
# Connexion chiffrée avec vérification du nom d'hôte
export DDIGRAPH_ENCRYPTED=true
export DDIGRAPH_VERIFY_HOSTNAME=true

# Certificat auto-signé
export DDIGRAPH_ENCRYPTED=true
export DDIGRAPH_TRUSTED_CERTIFICATES_FILE=/etc/ssl/certs/private-ca.pem

# AuraDB (le schéma neo4j+s:// active TLS automatiquement)
export DDIGRAPH_NEO4J_URI=neo4j+s://xxxx.databases.neo4j.io
```

!!! tip "AuraDB et TLS"
    Lorsque vous utilisez une URI avec le schéma `neo4j+s://` ou `bolt+s://`, le chiffrement
    TLS est activé automatiquement. Il n'est pas nécessaire de définir `DDIGRAPH_ENCRYPTED`
    séparément.

### Pool de connexions du pilote

| Variable | Option CLI | Description | Défaut |
| -------- | ---------- | ----------- | ------ |
| `DDIGRAPH_MAX_CONNECTION_POOL_SIZE` | `--max-connection-pool-size` | Nombre max de connexions dans le pool | -- |
| `DDIGRAPH_CONNECTION_TIMEOUT` | `--connection-timeout` | Délai d'ouverture de connexion (secondes) | -- |
| `DDIGRAPH_MAX_CONNECTION_LIFETIME` | `--max-connection-lifetime` | Durée de vie des connexions du pool (secondes) | -- |
| `DDIGRAPH_SESSION_TIMEOUT` | `--session-timeout` | Durée de vie de la session (secondes) | -- |
| `DDIGRAPH_TRANSACTION_TIMEOUT` | `--transaction-timeout` | Délai de transaction côté serveur (secondes) | -- |

### Journalisation et métriques

| Variable | Option CLI | Description | Défaut |
| -------- | ---------- | ----------- | ------ |
| `DDIGRAPH_LOG_LEVEL` | `--log-level` | Niveau de verbosité (`DEBUG`, `INFO`, `WARNING`, `ERROR`) | `INFO` |
| `DDIGRAPH_BATCH_METRICS` | `--batch-metrics` | Émettre les métriques par lot | `false` |
| `DDIGRAPH_METRICS_NAMESPACE` | `--metrics-namespace` | Préfixe des métriques | -- |

## Classe Settings

La configuration est gérée par la classe `Settings` basée sur Pydantic. Vous pouvez
l'utiliser directement dans votre code Python :

```python
from ddigraph.config import Settings

# Charger depuis les variables d'environnement et le fichier .env
settings = Settings()

# Accéder aux valeurs
print(settings.neo4j_uri)  # bolt://localhost:7687
print(settings.chunk_size)  # 200
print(settings.dry_run)  # False
```

Les champs de la classe `Settings` correspondent directement aux variables d'environnement :

```python
from ddigraph.config import Settings

# Surcharger des valeurs programmatiquement
settings = Settings(
    neo4j_uri="bolt://custom-host:7687",
    neo4j_password="secret",
    chunk_size=500,
    dry_run=True,
)
```

## Exemple de fichier `.env`

```bash
# Connexion Neo4j
DDIGRAPH_NEO4J_URI=bolt://localhost:7687
DDIGRAPH_NEO4J_USER=neo4j
DDIGRAPH_NEO4J_PASSWORD=mon_mot_de_passe_secret
DDIGRAPH_NEO4J_DATABASE=neo4j

# Réglage de l'ingestion
DDIGRAPH_CHUNK_SIZE=500
DDIGRAPH_DRY_RUN=false
DDIGRAPH_REPLACE=false

# Réessais
DDIGRAPH_WRITE_RETRY_ATTEMPTS=3
DDIGRAPH_WRITE_RETRY_BASE_DELAY=0.5
DDIGRAPH_WRITE_RETRY_JITTER=0.2

# TLS (décommenter si nécessaire)
# DDIGRAPH_ENCRYPTED=true
# DDIGRAPH_TRUSTED_CERTIFICATES_FILE=/path/to/cert.pem
```

!!! danger "Sécurité"
    Ne versionnez jamais votre fichier `.env` dans le contrôle de source. Ajoutez `.env` à
    votre `.gitignore` pour protéger vos identifiants.

## Référence rapide

| Variable | Défaut | Description |
| -------- | ------ | ----------- |
| `DDIGRAPH_NEO4J_URI` | `bolt://localhost:7687` | URI bolt Neo4j |
| `DDIGRAPH_NEO4J_USER` | `neo4j` | Nom d'utilisateur Neo4j |
| `DDIGRAPH_NEO4J_PASSWORD` | -- | Mot de passe Neo4j (requis) |
| `DDIGRAPH_NEO4J_DATABASE` | `neo4j` | Base de données cible |
| `DDIGRAPH_CHUNK_SIZE` | `200` | Enregistrements par lot |
| `DDIGRAPH_DRY_RUN` | `false` | Valider sans écrire |
| `DDIGRAPH_REPLACE` | `false` | Effacer les données existantes |
| `DDIGRAPH_MAX_QUEUE_SIZE` | `1000` | Taille max de la file d'attente async |
| `DDIGRAPH_WRITE_RETRY_ATTEMPTS` | `3` | Tentatives de réessai |
| `DDIGRAPH_WRITE_RETRY_BASE_DELAY` | `0.5` | Délai de base (secondes) |
| `DDIGRAPH_WRITE_RETRY_JITTER` | `0.2` | Gigue maximale (secondes) |
| `DDIGRAPH_ENCRYPTED` | `false` | Exiger TLS |
| `DDIGRAPH_VERIFY_HOSTNAME` | `false` | Vérifier le nom d'hôte TLS |

Voir [Référence CLI](cli.md) pour la liste complète des commandes et options.
