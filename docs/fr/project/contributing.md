# Contribuer à ddigraph

Les contributions sont les bienvenues ! Ce guide explique comment configurer un environnement
de développement, exécuter les vérifications et soumettre des modifications.

## Configuration du développement

```bash
# Cloner le dépôt
git clone https://github.com/pbisson44/ddigraph.git
cd ddigraph

# Installer avec toutes les dépendances de développement
pip install -e ".[dev,docs]"
```

Cela installe le paquet en mode éditable avec :

- **dev** : ruff, mypy, pytest, pytest-asyncio, psutil, types-lxml
- **docs** : mkdocs, mkdocs-material, mkdocs-static-i18n, pymdown-extensions

## Exécuter les vérifications

```bash
# Vérification du code et formatage
ruff check .
ruff format .

# Vérification des types
mypy .

# Tests
pytest

# Tout en une fois
ruff check . && ruff format . && mypy . && pytest
```

## Documentation

```bash
# Servir localement avec rechargement automatique
mkdocs serve

# Construire le site statique
mkdocs build
```

La documentation est bilingue (anglais/français). Les fichiers anglais sont dans `docs/en/`
et les fichiers français dans `docs/fr/`.

## Conventions de code

- **Formateur** : ruff avec une longueur de ligne de 100 caractères
- **Vérification des types** : mypy strict avec le plugin pydantic
- **Asynchrone** : toutes les opérations d'E/S utilisent `async`/`await`
- **Tests** : pytest avec pytest-asyncio (`asyncio_mode = "auto"`)
- **Imports** : isort via ruff avec `ddigraph` comme paquet interne

## Processus de pull request

1. Forkez le dépôt et créez une branche de fonctionnalité
2. Effectuez vos modifications avec des messages de commit clairs et descriptifs
3. Assurez-vous que toutes les vérifications passent : `ruff check . && ruff format . && mypy . && pytest`
4. Mettez à jour la documentation si votre modification affecte le comportement visible par l'utilisateur
5. Ouvrez une pull request avec une description de ce qui a changé et pourquoi

## Ajouter de nouveaux types d'entités DDI

Pour ajouter la prise en charge d'un nouveau type d'élément DDI :

1. **Définir le type de noeud** dans `src/ddigraph/schema/definitions/` -- ajoutez le label,
   les propriétés et les contraintes d'unicité
2. **Ajouter la logique d'analyse** dans l'analyseur approprié (`codebook_loader.py` ou
   `fragment_loader.py`)
3. **Ajouter les correspondances de relations** si l'élément référence d'autres éléments
4. **Mettre à jour l'amorçage du schéma** dans `DDISchema.generate_all_schema_queries()`
5. **Ajouter des tests** couvrant le nouveau type d'élément
6. **Mettre à jour la documentation** dans `docs/en/user-guide/relationships.md` et
   l'équivalent français

## Ajouter de nouveaux backends graphe

Les nouveaux backends implémentent le protocole `GraphWriteAdapter` :

```python
from ddigraph.schema import GraphWriteAdapter


class MyBackendAdapter(GraphWriteAdapter):
    async def write_batch(self, graph, **kwargs):
        """Écrire un lot de noeuds et de relations."""
        ...

    async def purge_dataset(self, dataset_id, **kwargs):
        """Supprimer toutes les données d'un jeu de données."""
        ...
```

Consultez les adaptateurs existants dans `demo/` pour des implémentations de référence :

- `demo/load_gremlin.py` -- Adaptateur Gremlin
- `demo/load_networkx.py` -- Adaptateur NetworkX
- `demo/load_pandas.py` -- Adaptateur pandas

## Signaler des problèmes

Ouvrez un ticket sur [github.com/pbisson44/ddigraph/issues](https://github.com/pbisson44/ddigraph/issues)
en incluant :

- Version de Python (`python --version`)
- Version de ddigraph (`pip show ddigraph`)
- Version de Neo4j (si applicable)
- Étapes minimales de reproduction
- Trace d'erreur complète

## Licence

En contribuant, vous acceptez que vos contributions soient licenciées sous la
[licence MIT](https://github.com/pbisson44/ddigraph/blob/main/LICENSE).
