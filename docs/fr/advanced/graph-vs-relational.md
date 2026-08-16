# Graphe vs Relationnel

Ce document explique pourquoi ddigraph utilise une base de données graphe (Neo4j) plutôt
qu'une base de données relationnelle traditionnelle, les avantages que cela apporte pour les
métadonnées DDI, et les considérations pour les équipes évaluant cette approche.

## Le défi : la complexité inhérente du DDI

DDI (Data Documentation Initiative) décrit les instruments d'enquête, les questionnaires, les
variables et leurs relations. Cela crée une structure naturellement interconnectée :

- Les questions référencent des listes de codes et des catégories
- Les variables sont liées aux questions, concepts et univers
- Les construits de flux de contrôle (séquences, conditionnels, boucles) forment des chemins
  d'exécution
- Les instruments contiennent des hiérarchies imbriquées de construits

### Une requête DDI typique

Considérez cette question : *"Quelles questions utilisent une liste de codes particulière, et
quelles variables sont dérivées de ces questions ?"*

Cela nécessite de traverser :

```text
CodeList → QuestionItem → QuestionConstruct → Variable
```

## Approche base de données relationnelle

### Conception du schéma relationnel

Dans une base de données relationnelle, vous pourriez modéliser cela avec des tables
normalisées :

```sql
CREATE TABLE code_lists (
    id VARCHAR PRIMARY KEY,
    agency VARCHAR,
    version VARCHAR,
    label TEXT
);

CREATE TABLE question_items (
    id VARCHAR PRIMARY KEY,
    agency VARCHAR,
    version VARCHAR,
    label TEXT,
    question_text TEXT,
    code_list_id VARCHAR REFERENCES code_lists(id)
);

CREATE TABLE question_constructs (
    id VARCHAR PRIMARY KEY,
    question_item_id VARCHAR REFERENCES question_items(id)
);

CREATE TABLE variables (
    id VARCHAR PRIMARY KEY,
    label TEXT,
    question_construct_id VARCHAR REFERENCES question_constructs(id)
);
```

### Le problème des requêtes

Trouver toutes les variables utilisant une liste de codes spécifique nécessite plusieurs
JOINs :

```sql
SELECT v.*
FROM variables v
JOIN question_constructs qc ON v.question_construct_id = qc.id
JOIN question_items qi ON qc.question_item_id = qi.id
WHERE qi.code_list_id = 'cl-age-groups';
```

Cela semble gérable, mais la complexité du DDI croît rapidement :

1. **Chemins de profondeur variable** : Le flux d'enquête peut s'imbriquer arbitrairement
   (Sequence -> Sequence -> IfThenElse -> Sequence -> QuestionConstruct)
2. **Types de relations multiples** : Une seule entité peut avoir de nombreuses relations
   différentes
3. **Références polymorphes** : ControlConstructReference peut pointer vers Sequence,
   QuestionConstruct, IfThenElse, Loop, etc.
4. **Préoccupations transversales** : Trouver tous les construits affectés par un changement
   de liste de codes nécessite de traverser plusieurs chemins

### Limitations du relationnel

| Défi | Impact relationnel |
| ----- | ------------------ |
| Traversée de profondeur variable | Nécessite des CTE récursifs ou plusieurs requêtes |
| Recherche de chemins | Auto-jointures complexes, difficiles à optimiser |
| Évolution du schéma | L'ajout de types de relations nécessite ALTER TABLE |
| Références polymorphes | Nécessite des colonnes de type ou des clés étrangères multiples |
| Analyse d'impact | Scans multi-tables coûteux |

#### Exemple : requête de profondeur variable en SQL

Trouver tous les construits atteignables depuis un instrument :

```sql
WITH RECURSIVE reachable AS (
    -- Base case: start from instrument
    SELECT child_id, child_type, 1 as depth
    FROM control_construct_refs
    WHERE parent_id = 'instrument-1'

    UNION ALL

    -- Recursive case: follow references
    SELECT ccr.child_id, ccr.child_type, r.depth + 1
    FROM control_construct_refs ccr
    JOIN reachable r ON ccr.parent_id = r.child_id
    WHERE r.depth < 20  -- Safety limit
)
SELECT * FROM reachable;
```

Cette requête :

- Devient lente à mesure que la profondeur augmente
- Nécessite un réglage minutieux des index
- Peut atteindre les limites de récursion de la base de données
- Ne filtre pas facilement par type de relation

## Approche base de données graphe

### Conception du schéma graphe

Dans Neo4j, la même structure est exprimée sous forme de nœuds et de relations :

```cypher
// Nodes
(:CodeList {fragment_id: "cl-1", label: "Age Groups"})
(:QuestionItem {fragment_id: "q-1", question_text: "What is your age?"})
(:QuestionConstruct {fragment_id: "qc-1"})
(:Variable {fragment_id: "v-1", label: "Age"})

// Relationships
(q:QuestionItem)-[:USES_CODELIST]->(cl:CodeList)
(qc:QuestionConstruct)-[:ASKS_QUESTION]->(q:QuestionItem)
(v:Variable)-[:DERIVED_FROM]->(qc:QuestionConstruct)
```

### La même requête, simplifiée

Trouver toutes les variables utilisant une liste de codes spécifique :

```cypher
MATCH (cl:CodeList {fragment_id: 'cl-age-groups'})
      <-[:USES_CODELIST]-(q:QuestionItem)
      <-[:ASKS_QUESTION]-(qc:QuestionConstruct)
      <-[:DERIVED_FROM]-(v:Variable)
RETURN v
```

### Traversée de profondeur variable

Trouver tous les construits atteignables depuis un instrument :

```cypher
MATCH (inst:Instrument {fragment_id: 'instrument-1'})
      -[:HAS_CONSTRUCT*]->(construct)
RETURN construct
```

L'opérateur `*` gère la profondeur arbitraire naturellement, sans limites de récursion ni CTE
complexes.

## Avantages des bases de données graphe pour le DDI

### 1. Modèle de données naturel

Les métadonnées DDI *sont* un graphe. La structure XML définit explicitement des nœuds
(fragments) et des arêtes (références) :

```xml
<QuestionConstruct>
    <QuestionReference>           <!-- This IS an edge -->
        <ID>question-1</ID>
    </QuestionReference>
</QuestionConstruct>
```

Les bases de données graphe représentent cela directement, tandis que les bases relationnelles
doivent l'encoder indirectement.

### 2. Performance des requêtes pour les traversées

| Opération | Relationnel | Graphe |
| --------- | ----------- | ------ |
| JOIN unique | Rapide | Rapide |
| 3-4 JOINs | Modéré | Rapide |
| Traversée de profondeur variable | Lent/Complexe | Rapide |
| Recherche de chemins | Très lent | Optimisé |
| Correspondance de motifs | Codage manuel | Support natif |

Les bases de données graphe utilisent l'adjacence sans index, ce qui signifie que chaque nœud
référence directement ses voisins. Le temps de traversée est proportionnel à la taille du
résultat, pas à la taille totale des données.

### 3. Flexibilité du schéma

Ajouter un nouveau type de relation dans une base relationnelle :

```sql
ALTER TABLE question_items
ADD COLUMN instruction_id VARCHAR REFERENCES instructions(id);
-- Plus migration scripts, ORM updates, etc.
```

Ajouter un nouveau type de relation dans Neo4j :

```cypher
MATCH (q:QuestionItem {fragment_id: 'q-1'})
MATCH (i:Instruction {fragment_id: 'inst-1'})
CREATE (q)-[:HAS_INSTRUCTION]->(i)
```

Aucune migration de schéma requise. Les nouveaux types de relations peuvent coexister avec les
données existantes.

### 4. Langage de requête expressif

Cypher exprime les motifs de graphe directement :

```cypher
// Find questions with conditional branching that use a specific code list
MATCH (cl:CodeList {fragment_id: 'cl-yes-no'})
      <-[:USES_CODELIST]-(q:QuestionItem)
      <-[:ASKS_QUESTION]-(qc:QuestionConstruct)
      <-[:HAS_CONSTRUCT]-(seq:Sequence)
      <-[:THEN|ELSE]-(ite:IfThenElse)
RETURN q.fragment_id, q.question_text, ite.condition
```

### 5. Analyse d'impact

Comprendre ce qui est affecté par un changement :

```cypher
// Find everything that depends on a code list
MATCH (cl:CodeList {fragment_id: 'cl-occupation'})
MATCH path = (cl)<-[*1..5]-(dependent)
RETURN DISTINCT labels(dependent)[0] as type,
       dependent.fragment_id as id,
       length(path) as distance
ORDER BY distance
```

## Inconvénients potentiels et considérations

### 1. Courbe d'apprentissage

**Défi** : Les équipes habituées au SQL doivent apprendre Cypher et la pensée en graphe.

**Atténuation** :

- La syntaxe Cypher est intuitive pour la correspondance de motifs
- ddigraph fournit des requêtes prêtes à l'emploi dans les scripts d'audit
- La documentation inclut les motifs de requête courants

### 2. Complexité opérationnelle

**Défi** : L'exécution de Neo4j nécessite une infrastructure supplémentaire.

**Atténuation** :

- Neo4j Aura fournit un hébergement cloud géré
- Docker simplifie le déploiement local
- Neo4j Community Edition est gratuit pour un usage mono-instance

### 3. Écosystème d'outils

**Défi** : Moins d'outils de BI prennent en charge nativement les bases de données graphe.

**Atténuation** :

- Neo4j dispose de connecteurs JDBC/ODBC pour les outils de BI
- Le motif adaptateur de ddigraph permet l'export vers pandas, JSON, CSV
- Les résultats graphe peuvent être aplatis pour le reporting traditionnel

### 4. Sémantique transactionnelle

**Défi** : Les bases de données graphe optimisent les lectures ; les charges d'écriture
intensives peuvent différer.

**Atténuation** :

- Les métadonnées DDI sont dominées par la lecture (charger une fois, interroger souvent)
- ddigraph utilise des écritures par lots avec UNWIND pour une ingestion efficace
- Neo4j prend en charge les transactions ACID

### 5. Requêtes d'agrégation

**Défi** : Certaines opérations d'agrégation sont plus naturelles en SQL.

**Exemple** : Compter les variables par jeu de données est plus simple en SQL :

```sql
SELECT dataset_id, COUNT(*) FROM variables GROUP BY dataset_id;
```

**Équivalent Cypher** :

```cypher
MATCH (d:Dataset)<-[:IN_DATASET]-(v:Variable)
RETURN d.id, count(v)
```

Les deux fonctionnent, mais le GROUP BY de SQL peut sembler plus familier.

### 6. Considérations de volume de données

**Défi** : Les très grands jeux de données (millions de nœuds) nécessitent un réglage.

**Atténuation** :

- ddigraph crée des index sur les champs clés
- Les tailles de lots sont configurables
- Neo4j Enterprise offre le clustering pour la montée en charge

## Quand utiliser chaque approche

### La base de données graphe (Neo4j) est préférable quand

- Les requêtes traversent fréquemment des relations
- L'analyse de chemins est importante (accessibilité, impact)
- Le schéma évolue avec de nouveaux types de relations
- Vous devez visualiser la structure des métadonnées
- Intégration avec d'autres données graphe (SDMX, ontologies)

### La base de données relationnelle peut être préférable quand

- Les requêtes sont principalement des agrégations et des comptages
- L'équipe n'a aucune expérience des bases de données graphe et un temps d'apprentissage limité
- L'infrastructure existante est purement relationnelle
- Le volume de données est faible et les requêtes sont simples
- La conformité exige des technologies de base de données spécifiques

## Approches hybrides

Vous n'avez pas à choisir exclusivement. Les motifs courants incluent :

### 1. Graphe pour la navigation, relationnel pour le reporting

Utilisez Neo4j pour les requêtes structurelles et l'analyse de chemins, mais synchronisez les
résumés vers un entrepôt de données relationnel pour les tableaux de bord BI.

### 2. Graphe comme couche de métadonnées

Conservez les données de réponse aux enquêtes dans une base relationnelle, mais utilisez Neo4j
pour les métadonnées qui décrivent ces données. Liez-les via les identifiants de jeu de
données/variable.

### 3. Export pour l'analyse

Utilisez le motif adaptateur de ddigraph pour exporter les données graphe vers des DataFrames
pandas ou des fichiers CSV pour les équipes plus à l'aise avec ces outils :

```bash
ddigraph export survey.xml --format json -o survey.json
ddigraph export survey.xml --format csv -o out-dir/   # nodes.csv + relationships.csv
python demo/load_pandas.py                            # DataFrames (script de démo)
```

## Référence de comparaison des requêtes

| Tâche | SQL | Cypher |
| ----- | --- | ------ |
| Recherche par ID | `SELECT * FROM questions WHERE id = 'q1'` | `MATCH (q:QuestionItem {fragment_id: 'q1'}) RETURN q` |
| JOIN simple | `SELECT * FROM questions q JOIN code_lists cl ON q.code_list_id = cl.id` | `MATCH (q:QuestionItem)-[:USES_CODELIST]->(cl) RETURN q, cl` |
| Profondeur variable | CTE récursif (complexe) | `MATCH path = (a)-[*1..5]->(b) RETURN path` |
| Plus court chemin | Non natif | `MATCH p = shortestPath((a)-[*]-(b)) RETURN p` |
| Tous les chemins | Très complexe | `MATCH p = allShortestPaths((a)-[*]-(b)) RETURN p` |
| Correspondance de motifs | JOINs multiples + conditions | `MATCH (a)-[:R1]->(b)-[:R2]->(c) WHERE ...` |

## Conclusion

Pour les métadonnées DDI, les bases de données graphe offrent des avantages significatifs en
expressivité des requêtes, performance de traversée et flexibilité du schéma. Les compromis
(courbe d'apprentissage, complexité opérationnelle) sont gérables, notamment grâce à :

1. La structure intrinsèquement graphe du DDI
2. L'importance de la traversée des relations dans les cas d'usage des métadonnées
3. Les outils matures et les options cloud de Neo4j
4. Le motif adaptateur de ddigraph pour la flexibilité d'intégration

Les équipes devraient évaluer en fonction de leurs motifs de requête spécifiques, de leur
infrastructure existante et de leur volonté d'investir dans les compétences en bases de données
graphe.

## Pour aller plus loin

- [Concepts des bases de données graphe Neo4j](https://neo4j.com/docs/getting-started/)
- [Langage de requête Cypher](https://neo4j.com/docs/cypher-manual/)
- [Spécification DDI Lifecycle](https://ddialliance.org/Specification/DDI-Lifecycle/)
- [Architecture ddigraph](../user-guide/architecture.md)
- [Interopérabilité des standards](interoperability.md)
