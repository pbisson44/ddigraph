# Apprendre ddigraph

Un cours en huit leçons. Il enseigne deux choses à la fois : les idées
derrière les métadonnées d'enquête vues comme un graphe, et l'outil qui
fait le travail.

Vous n'avez besoin de connaître ni DDI, ni Neo4j, ni RDF. Vous devez savoir
lire du Python et utiliser un terminal.

## Pourquoi un cours et pas seulement les guides

Le reste de ce site répond à « comment faire X ? ». Cette section répond à
« que se passe-t-il, et pourquoi est-ce construit ainsi ? ». L'ordre
compte : chaque leçon s'appuie sur ce que la précédente a bâti.

Si vous voulez seulement charger un fichier et passer à autre chose,
utilisez plutôt le [Démarrage rapide](../getting-started/quickstart.md).
Revenez ici quand quelque chose vous surprendra.

## Les huit leçons

| # | Leçon | Vous saurez | Durée |
| --- | ------- | ------------- | ------- |
| 1 | [Les métadonnées sont déjà un graphe](01-metadata-as-a-graph.md) | Dire ce qu'est DDI et pourquoi un graphe lui convient | 15 min |
| 2 | [Regarder avant de charger](02-first-look.md) | Inspecter un fichier DDI sans base de données | 15 min |
| 3 | [Nœuds, arcs, identité](03-the-graph-model.md) | Diffuser tout fichier DDI en nœuds et arcs | 25 min |
| 4 | [Rejoindre le monde extérieur](04-linked-data.md) | Exporter du RDF que d'autres systèmes lisent | 30 min |
| 5 | [Prouver que c'est juste](05-validation.md) | Valider un export avec des formes SHACL | 20 min |
| 6 | [Construire votre pipeline](06-your-own-pipeline.md) | Envoyer DDI vers le magasin de votre choix | 25 min |
| 7 | [Ancrer un modèle dans le graphe](07-grounding-an-llm.md) | Empêcher un modèle d'inventer votre enquête | 25 min |
| 8 | [Des outils sur le graphe](08-tools-over-the-graph.md) | Donner à un modèle un outil sur vos métadonnées | 25 min |

Environ trois heures au total. Les leçons 1 à 6 se tiennent seules ; les
leçons 7 et 8 s'appuient sur la leçon 3 et peuvent se lire juste après elle
si c'est ce qui vous amène ici.

## Installation

Les leçons 1 à 3 ne demandent que l'installation de base. Les leçons 4 et 5
demandent les extras RDF. Aucune leçon n'a besoin d'une base de données.

Les leçons 7 et 8 construisent tout localement : tous leurs exercices
s'exécutent sans clé d'API. Les deux exemples qui appellent un modèle sont
signalés comme tels et sont le seul code du cours que la suite de tests
n'exécute pas.

```bash
pip install "ddigraph[shacl]"
```

Chaque leçon travaille sur des fichiers livrés avec le dépôt source : il
n'y a donc rien à télécharger.

```bash
git clone https://github.com/pbisson44/ddigraph
cd ddigraph
```

Les fichiers sont dans `tests/fixtures/`. Ils sont petits volontairement —
assez petits pour être ouverts dans un éditeur et lus, ce qui est bien
l'intérêt quand on apprend la forme des données.

| Fichier | Variante |
| --------- | ---------- |
| `codebook_sample.xml` | DDI Codebook |
| `fragment_instance.xml` | DDI Lifecycle 3.3 |
| `cdi_sample.xml` | DDI-CDI 1.0 |

!!! tip "Les exemples ici sont testés"
    Chaque commande et chaque script de ces leçons s'exécute dans la suite
    de tests à chaque commit. Si l'un d'eux casse, la construction échoue.
    Ce ne sont pas des illustrations : c'est la sortie réelle d'exécutions
    réelles.

## Comment utiliser les exercices

Chaque leçon se termine par un exercice et une solution masquée. Essayez
avant d'ouvrir la solution ; la réponse est bien moins utile que la
tentative.

## Ensuite

Après la leçon 8, vous aurez vu chaque partie du package.
L'[étude de cas RDF](../advanced/rdf-case-study.md) mène ensuite une liste
de codes de DDI jusqu'aux données liées validées : tout le cours appliqué à
un seul problème réaliste, et
[Préparation pour l'IA](../advanced/ai-readiness.md) va plus loin dans le
filtrage et les schémas agentiques sur un graphe chargé.
