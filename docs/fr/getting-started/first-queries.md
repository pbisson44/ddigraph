# Vos premières requêtes

Vous venez de charger un fichier DDI dans Neo4j. Et maintenant ?

Cette page vous montre comment explorer les données que vous venez de charger. Vous allez
exécuter vos premières requêtes Cypher, voir les résultats et comprendre ce que chaque
requête fait — étape par étape. Aucune expérience préalable en base de données n'est requise.

---

## Que s'est-il passé lors du chargement ?

Quand ddigraph a chargé votre fichier DDI XML, il l'a transformé en **graphe** — un ensemble
de **nœuds** (des choses) reliés par des **relations** (des liens entre les choses).

Imaginez ceci :

- Un **nœud** ressemble à une ligne dans un tableur. Il représente une chose précise,
  comme une question, une variable ou un concept.
- Une **relation** est une flèche qui relie deux nœuds. Elle indique comment ils sont liés
  (par exemple, « La question A *appartient à* l'instrument B »).

Pour un fichier DDI Codebook, ddigraph crée des nœuds comme :

| Type de nœud | Ce qu'il représente |
|---|---|
| `Dataset` | Votre enquête ou étude |
| `Variable` | Une colonne dans vos données (ex. : âge, revenu) |
| `QuestionItem` | Une question d'enquête |
| `ConceptScheme` | Un groupe de concepts liés |
| `Concept` | Un sujet ou une idée précis |
| `CodeList` | Une liste de choix de réponses |
| `Category` | Un seul choix de réponse dans une liste |

---

## Ouvrir Neo4j Browser

Neo4j Browser est une interface web où vous pouvez exécuter des requêtes Cypher et voir les
résultats sous forme de tableaux ou de graphes visuels.

1. Ouvrez votre navigateur et allez à : `http://localhost:7474`
2. Connectez-vous avec votre nom d'utilisateur et mot de passe Neo4j
   (par défaut : `neo4j` / `password`).
3. Vous verrez une zone de texte en haut. C'est là que vous tapez vos requêtes.
4. Appuyez sur **Ctrl+Entrée** (ou **Cmd+Entrée** sur Mac) pour exécuter une requête.

---

## Vos 8 premières requêtes

### 1. Combien de nœuds y a-t-il dans le graphe ?

```cypher
MATCH (n) RETURN count(n) AS total_noeuds
```

**Ce que ça fait :**

- `MATCH (n)` — trouve tous les nœuds dans la base de données. La lettre `n` est juste
  un nom de variable (vous pouvez utiliser n'importe quelle lettre).
- `RETURN count(n)` — les compte et retourne le nombre.
- `AS total_noeuds` — donne un nom lisible à la colonne de résultat.

**Ce que vous voyez :** Un seul nombre — le total de tous les nœuds.

---

### 2. Quels types de nœuds existent ?

```cypher
MATCH (n) RETURN labels(n) AS type, count(n) AS nombre
ORDER BY nombre DESC
```

**Ce que ça fait :**

- `labels(n)` — obtient le « type » de chaque nœud (ex. : Variable, Question).
- `ORDER BY nombre DESC` — trie avec les groupes les plus grands en premier.

**Ce que vous voyez :** Un tableau listant chaque type de nœud et combien il en existe.

---

### 3. Lister vos variables

```cypher
MATCH (v:Variable)
RETURN v.name AS nom, v.label AS libelle
LIMIT 20
```

**Ce que ça fait :**

- `(v:Variable)` — trouve uniquement les nœuds de type `Variable`. La partie `:Variable`
  est le filtre.
- `v.name` et `v.label` — lit des propriétés spécifiques (comme des colonnes) de chaque nœud.
- `LIMIT 20` — retourne seulement les 20 premiers résultats.

**Ce que vous voyez :** Un tableau des noms de variables et leurs libellés.

---

### 4. Trouver une question par mot-clé

```cypher
MATCH (q:QuestionItem)
WHERE toLower(q.question_text) CONTAINS 'age'
RETURN q.question_text AS question
```

**Ce que ça fait :**

- `WHERE` — filtre les résultats, comme une condition de recherche.
- `toLower(...)` — convertit le texte en minuscules pour que la recherche fonctionne
  quelle que soit la casse.
- `CONTAINS 'age'` — garde uniquement les questions qui contiennent le mot « age ».

**Ce que vous voyez :** Toutes les questions dont le texte contient le mot « age ».

---

### 5. Voir ce à quoi une variable est connectée

```cypher
MATCH (v:Variable {name: 'AGE'})-[r]->(autre)
RETURN type(r) AS relation, labels(autre) AS connecte_a, autre.name AS nom
```

**Ce que ça fait :**

- `{name: 'AGE'}` — trouve la variable spécifique nommée AGE. Remplacez par n'importe
  quel nom de variable de vos données.
- `-[r]->` — suit toute relation sortante depuis cette variable. `r` capture la relation.
- `type(r)` — obtient le nom de la relation (ex. : `HAS_QUESTION`, `BELONGS_TO`).

**Ce que vous voyez :** Tout ce à quoi la variable AGE est connectée, et comment.

---

### 6. Afficher le jeu de données et sa structure de premier niveau

```cypher
MATCH (d:Dataset)-[r]->(enfant)
RETURN d.id AS dataset, type(r) AS lien, labels(enfant) AS type_enfant, enfant.name AS nom
LIMIT 30
```

**Ce que ça fait :**

- Part du nœud `Dataset` (la racine de vos données).
- Suit une étape vers l'extérieur pour montrer tout ce qui y est directement connecté.

**Ce que vous voyez :** Les enfants immédiats de votre dataset — ce qu'il contient au premier niveau.

---

### 7. Compter les choix de réponses dans les listes de codes

```cypher
MATCH (cl:CodeList)-[:HAS_CATEGORY]->(cat:Category)
RETURN cl.name AS liste_codes, count(cat) AS nb_choix
ORDER BY nb_choix DESC
LIMIT 10
```

**Ce que ça fait :**

- `[:HAS_CATEGORY]` — suit uniquement les relations de type `HAS_CATEGORY`.
- Regroupe les résultats par liste de codes et compte combien de catégories chacune possède.

**Ce que vous voyez :** Vos listes de codes les plus longues (plus de choix de réponses) en tête.

---

### 8. Trouver toutes les questions liées à un concept

```cypher
MATCH (c:Concept {label: 'Age'})<-[:ABOUT_CONCEPT]-(q:QuestionItem)
RETURN c.label AS concept, q.question_text AS question
```

**Ce que ça fait :**

- Part d'un nœud `Concept` libellé « Age ».
- Suit les relations `ABOUT_CONCEPT` *en sens inverse* (la flèche `<-` pointe à gauche)
  pour trouver les questions qui référencent ce concept.
- Remplacez `'Age'` par n'importe quel libellé de concept dans vos données.

**Ce que vous voyez :** Toutes les questions étiquetées avec un concept donné.

---

## Et ensuite ?

Maintenant que vous pouvez explorer vos données, voici quelques bonnes prochaines étapes :

- **[Modèle relationnel](../user-guide/relationships.md)** — voir la liste complète des types
  de nœuds et de relations dans votre graphe.
- **[Backend Neo4j](../backends/neo4j.md)** — en savoir plus sur la connexion et les requêtes Neo4j.
- **[Référence CLI](../reference/cli.md)** — toutes les commandes disponibles pour charger,
  purger et gérer vos données.
- **[Glossaire](../reference/glossary.md)** — définitions en langage clair de tous les termes
  utilisés dans cette documentation.
