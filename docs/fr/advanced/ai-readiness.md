# Préparation pour l'IA

Le chargement des métadonnées DDI-L (Data Documentation Initiative Lifecycle) dans Neo4j
transforme des archives XML statiques en un graphe de connaissances interrogeable : un format
qui ouvre de puissantes capacités d'IA et d'apprentissage automatique.

## Pourquoi la structure en graphe est importante pour l'IA

Les fichiers DDI-L traditionnels sont des documents XML profondément imbriqués. Bien que
complets, ce format pose des défis pour les systèmes d'IA :

| Format XML | Format graphe |
| ------------ | -------------- |
| Analyse séquentielle requise | Traversée directe des relations |
| Connexions implicites via les ID | Relations typées explicites |
| Difficile d'interroger les motifs | Correspondance de motifs native |
| Contexte enfoui dans la hiérarchie | Contexte visible dans la structure |

Lorsque DDI-L est chargé dans Neo4j, la structure en graphe inhérente des instruments
d'enquête devient explicite et traversable.

## Capacités clés pour l'IA

### 1. Génération augmentée par récupération (RAG)

Neo4j permet la recherche sémantique sur les métadonnées d'enquête pour les pipelines RAG :

```cypher
// Find questions related to a concept
MATCH (q:QuestionItem)-[:USES_CODELIST]->(cl:CodeList)
WHERE q.question_text CONTAINS 'employment'
RETURN q.name, q.question_text, cl.name
```

Cela permet aux LLM de fonder leurs réponses sur la structure réelle de l'enquête plutôt que
d'halluciner le contenu des questions ou les options de réponse.

### 2. Réponses aux questions contextuelles

La structure en graphe préserve le contexte du flux de l'enquête que les représentations
plates perdent :

```cypher
// Get full context for a question: what comes before, after, and why
MATCH path = (prev)-[:HAS_CONSTRUCT]->(seq:Sequence)-[:HAS_CONSTRUCT]->(qc:QuestionConstruct)
WHERE qc.fragment_id = $question_id
MATCH (qc)-[:ASKS_QUESTION]->(q:QuestionItem)
OPTIONAL MATCH (q)-[:USES_CODELIST]->(cl:CodeList)-[:HAS_CATEGORY]->(cat:Category)
RETURN path, q, collect(cat.category_label) AS response_options
```

Un assistant IA peut désormais expliquer non seulement ce que demande une question, mais aussi
sa position dans le flux de l'instrument et les réponses disponibles.

### 3. Compréhension des instruments d'enquête

Les LLM peuvent raisonner sur la logique de l'enquête grâce aux requêtes sur le graphe :

```cypher
// Analyze conditional branching
MATCH (ite:IfThenElse)-[:THEN]->(then_seq:Sequence)
MATCH (ite)-[:ELSE]->(else_seq:Sequence)
RETURN ite.condition,
       size((then_seq)-[:HAS_CONSTRUCT]->()) AS then_path_length,
       size((else_seq)-[:HAS_CONSTRUCT]->()) AS else_path_length
```

Cela permet à l'IA de comprendre les motifs de saut, la logique de filtre et le routage des
répondants.

### 4. Plongements de graphes de connaissances

La structure en graphe permet la génération de plongements (embeddings) pour :

- **Similarité des questions** : Trouver des questions sémantiquement liées entre les enquêtes
- **Comparaison d'instruments** : Identifier les différences structurelles entre les versions
  d'enquête
- **Regroupement de concepts** : Grouper les questions par concepts sous-jacents

```python
# Example: Generate embeddings from graph structure
from neo4j import GraphDatabase
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('all-MiniLM-L6-v2')

with driver.session() as session:
    questions = session.run("""
        MATCH (q:QuestionItem)
        RETURN q.fragment_id AS id, q.question_text AS text
    """)
    for q in questions:
        embedding = model.encode(q["text"])
        session.run("""
            MATCH (q:QuestionItem {fragment_id: $id})
            SET q.embedding = $embedding
        """, id=q["id"], embedding=embedding.tolist())
```

### 5. Flux de travail agentiques

Les agents IA peuvent naviguer dans le graphe de l'enquête pour accomplir des tâches
complexes :

- **Documentation d'enquête** : Générer des descriptions lisibles du flux de l'instrument
- **Assurance qualité** : Identifier les questions orphelines ou les branches inaccessibles
- **Aide à la traduction** : Trouver tous les éléments textuels nécessitant une localisation
- **Harmonisation** : Mettre en correspondance les questions entre les enquêtes avec des
  concepts communs

## Motifs d'IA natifs au graphe

### Recherche vectorielle + graphe

Combiner la similarité sémantique avec des contraintes structurelles :

```cypher
// Find similar questions within the same survey section
MATCH (target:QuestionItem {fragment_id: $id})
MATCH (target)<-[:ASKS_QUESTION]-(qc:QuestionConstruct)<-[:HAS_CONSTRUCT]-(seq:Sequence)
MATCH (seq)-[:HAS_CONSTRUCT]->(other_qc:QuestionConstruct)-[:ASKS_QUESTION]->(similar:QuestionItem)
WHERE similar <> target
RETURN similar.name, similar.question_text,
       gds.similarity.cosine(target.embedding, similar.embedding) AS similarity
ORDER BY similarity DESC
LIMIT 5
```

### Fenêtres de contexte du graphe

Extraire des sous-graphes comme contexte pour les prompts des LLM :

```cypher
// Get 2-hop neighborhood for context
MATCH (q:QuestionItem {fragment_id: $id})
MATCH path = (q)-[*1..2]-(related)
RETURN path
```

Ce sous-graphe riche en contexte peut être sérialisé et inclus dans les prompts, offrant aux
LLM une conscience structurelle impossible avec la récupération de documents plats.

### Chaînes de raisonnement

Les chemins du graphe permettent un raisonnement en plusieurs étapes :

```cypher
// Trace how a respondent reaches a specific question
MATCH path = (entry:EntryPoint)-[:HAS_CONSTRUCT*]->(qc:QuestionConstruct)
WHERE (qc)-[:ASKS_QUESTION]->(:QuestionItem {fragment_id: $target})
RETURN [node IN nodes(path) | labels(node)[0]] AS node_types,
       length(path) AS steps
```

## Applications pratiques

### Chatbots d'enquête

Construire des interfaces conversationnelles qui comprennent la structure de l'enquête :

```bash
Utilisateur : "Quelles questions viennent après la section emploi ?"
Bot : [Interroge le graphe pour les séquences suivant les construits liés à l'emploi]
      "Après les questions sur l'emploi, les répondants répondent à 5 questions sur
       la satisfaction au travail, puis sont orientés selon leur statut d'emploi..."
```

### Documentation automatisée

Générer de la documentation à partir de la structure du graphe :

```python
def describe_instrument(instrument_id: str) -> str:
    """Generate natural language description of survey instrument."""
    with driver.session() as session:
        structure = session.run("""
            MATCH (i:Instrument {fragment_id: $id})-[:HAS_CONSTRUCT]->(seq:Sequence)
            MATCH (seq)-[:HAS_CONSTRUCT]->(c)
            RETURN seq.name AS section, labels(c)[0] AS type, count(*) AS count
            ORDER BY section
        """, id=instrument_id)
        # Feed to LLM for natural language generation
        return llm.generate(structure.data())
```

### Validation de la qualité

Validation des instruments d'enquête assistée par l'IA :

```cypher
// Find questions without response options
MATCH (q:QuestionItem)
WHERE NOT (q)-[:USES_CODELIST]->()
RETURN q.name, q.question_text AS potentially_missing_codelist

// Find unreachable constructs
MATCH (c)
WHERE c:Sequence OR c:QuestionConstruct
AND NOT ()-[:HAS_CONSTRUCT|THEN|ELSE]->(c)
AND NOT c:EntryPoint
RETURN labels(c)[0] AS type, c.fragment_id AS orphaned
```

## D'archive à actif IA

La transformation de DDI-L XML vers un graphe Neo4j représente un changement fondamental :

| Perspective d'archive | Perspective prête pour l'IA |
| -------------------- | --------------------------- |
| Format de stockage | Représentation des connaissances |
| Documentation | Structure interrogeable |
| Catalogue de métadonnées | Substrat de raisonnement |
| Référence statique | Source de contexte dynamique |

En chargeant DDI-L dans Neo4j, les métadonnées d'enquête deviennent un participant de premier
plan dans les pipelines d'IA -- non pas simplement des données à récupérer, mais une structure
sur laquelle raisonner.

## Pour commencer

1. Chargez vos fichiers DDI-L :

   ```bash
   ddigraph bootstrap
   ddigraph load instrument.xml
   ```

2. Ajoutez des plongements pour la recherche sémantique (optionnel) :

   ```cypher
   // After generating embeddings externally
   CALL db.index.vector.createNodeIndex(
     'question_embeddings', 'QuestionItem', 'embedding', 384, 'cosine'
   )
   ```

3. Interrogez pour les applications d'IA :

   ```cypher
   // RAG context retrieval
   MATCH (q:QuestionItem)
   WHERE q.question_text CONTAINS $search_term
   MATCH path = (q)<-[:ASKS_QUESTION]-(:QuestionConstruct)<-[:HAS_CONSTRUCT]-(s:Sequence)
   RETURN q, s, path
   ```

## Pour aller plus loin

- [Neo4j Graph Data Science](https://neo4j.com/docs/graph-data-science/current/)
- [Spécification DDI Lifecycle](https://ddialliance.org/Specification/DDI-Lifecycle/3.3/)
- [Intégration LangChain Neo4j](https://python.langchain.com/docs/integrations/graphs/neo4j_cypher)
- [Architecture](../user-guide/architecture.md) - Conception et composants de ddigraph
- [Relations](../user-guide/relationships.md) - Schéma du graphe et types de relations
