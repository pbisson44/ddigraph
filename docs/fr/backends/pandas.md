# Backend pandas

pandas range le graphe dans deux tableaux : une ligne par nœud, une ligne
par relation. Utilisez-le quand l'étape suivante est un tableur, un rapport
ou une jointure avec d'autres données.

## Dépendances

pandas est un extra optionnel :

```bash
pip install "ddigraph[pandas]"
```

## Utilisation de base

<!-- runnable -->
```python
import os

from ddigraph.backends.pandas import to_dataframes

frames = to_dataframes(os.environ["FIXTURE"])

print(len(frames.nodes), "nœuds,", len(frames.relationships), "relations")
print(frames.nodes["node_label"].value_counts())
```

La source peut être du DDI XML de n'importe quelle variante, ou un export
RDF comme `survey.ttl`. Vous pouvez aussi passer des blocs déjà obtenus avec
`ddigraph.iter_graph()`.

## Les deux tableaux

`frames.nodes` a une ligne par nœud :

- `node_label` est le type du nœud, par exemple `Variable`.
- `node_id` est sa clé. Elle est unique au sein de son type.
- Chaque autre colonne est un champ. Les types n'ont pas les mêmes champs :
  le tableau en contient l'union, et la plupart des cellules d'une ligne
  sont vides.

`frames.relationships` a une ligne par relation, avec cinq colonnes :
`start_label`, `start_id`, `type`, `end_label` et `end_id`.

Les colonnes sont celles de `ddigraph export --format csv` : fichiers et
tableaux sont interchangeables.

## Un type à la fois

`frames.of(label)` renvoie les nœuds d'un type, avec seulement les colonnes
que ce type utilise :

<!-- runnable -->
```python
import os

from ddigraph.backends.pandas import to_dataframes

frames = to_dataframes(os.environ["FIXTURE"])

questions = frames.of("QuestionItem")
print(questions.columns.tolist())
```

## Joindre les tableaux

Une relation désigne ses deux extrémités par type et clé. Joignez sur les
deux pour récupérer ce qu'il vous faut de chaque extrémité :

<!-- runnable -->
```python
import os

from ddigraph.backends.pandas import to_dataframes

frames = to_dataframes(os.environ["FIXTURE"])
ends = frames.nodes[["node_label", "node_id", "label"]]

linked = frames.relationships.merge(
    ends,
    left_on=["start_label", "start_id"],
    right_on=["node_label", "node_id"],
).merge(
    ends,
    left_on=["end_label", "end_id"],
    right_on=["node_label", "node_id"],
    suffixes=("_start", "_end"),
)
print(linked[["label_start", "type", "label_end"]])
```

## Enregistrer

```python
import pandas as pd

frames.nodes.to_csv("nodes.csv", index=False)
frames.relationships.to_csv("relationships.csv", index=False)

with pd.ExcelWriter("survey.xlsx") as writer:  # requiert openpyxl, inclus dans l'extra
    frames.nodes.to_excel(writer, sheet_name="nodes", index=False)
    frames.relationships.to_excel(writer, sheet_name="relationships", index=False)
```

## Voir aussi

- [NetworkX](networkx.md) - Le même graphe, pour les algorithmes de graphes
- [Gremlin](gremlin.md) - Le même graphe, dans une base de données
- [Export en ligne de commande](../reference/cli.md) - Les mêmes tableaux, en fichiers CSV
