# Interopérabilité des standards

!!! note "À qui s'adresse cette page ?"
    Cette page est destinée aux équipes qui utilisent **à la fois les métadonnées DDI et les
    structures de données SDMX** et souhaitent les relier dans le même graphe. Si vous ne
    travaillez pas avec SDMX, vous pouvez passer cette page.

    **SDMX** (Statistical Data and Metadata eXchange) est une norme internationale pour
    partager des statistiques entre organisations comme les banques centrales, les agences
    gouvernementales et Eurostat. Elle décrit les *structures de données* — quelles colonnes
    existent dans un jeu de données, quelles valeurs sont autorisées et comment elles se
    rapportent les unes aux autres.

    **DDI** décrit les *métadonnées* d'enquête — quelles questions ont été posées, quelles
    variables ont été collectées et ce que signifient les réponses. Ces deux standards décrivent
    les mêmes données sous des angles différents, et un graphe facilite leur liaison.

---

## Pourquoi les graphes pour l'interopérabilité ?

Les approches traditionnelles de la mise en correspondance des standards reposent sur des
scripts de transformation, des feuilles de style XSLT ou des schémas relationnels rigides.
Ces approches peinent avec :

- **Évolution du schéma** : L'ajout de nouvelles correspondances nécessite des modifications
  de code
- **Relations plusieurs-à-plusieurs** : Un seul concept DDI peut correspondre à plusieurs
  composants SDMX
- **Correspondances contextuelles** : Le même élément peut être mis en correspondance
  différemment selon le contexte
- **Traçabilité** : Difficile d'auditer pourquoi une correspondance a été établie

Les bases de données graphe répondent à ces défis grâce à leur schéma flexible et leur
modélisation explicite des relations.

### Avantages du graphe

| Défi | Approche relationnelle | Approche graphe |
| ----- | ---------------------- | --------------- |
| Modifications du schéma | ALTER TABLE, migrations | Ajout dynamique de nouveaux types de nœuds/relations |
| Plusieurs-à-plusieurs | Tables de jonction | Relations directes avec propriétés |
| Contexte | JOINs complexes | Traversée de chemins spécifiques |
| Traçabilité | Tables d'audit | Les propriétés des relations capturent la provenance |

## Motif d'intégration DDI-SDMX

La tâche principale est de relier les variables DDI aux composants de structure de données SDMX.

Dans SDMX, chaque variable dans un jeu de données joue l'un des deux rôles suivants :

- **Dimension** — une colonne qui *identifie* un point de données (ex. : pays, année, groupe
  d'âge). Les dimensions indiquent *à quoi* une valeur fait référence.
- **Mesure** — le nombre réel rapporté (ex. : taux de chômage, nombre de personnes).

Une variable DDI correspond au rôle qu'elle joue dans la structure SDMX.

Chaque variable a aussi un **domaine de valeurs** — l'ensemble des valeurs autorisées (ex. :
une liste de codes de pays, ou une plage numérique). Dans SDMX, cela est représenté par une
**liste de codes** (pour les valeurs catégorielles) ou un **type de données** (pour les
nombres/textes).

### Correspondance par identifiant

La façon la plus simple de relier DDI et SDMX est la **correspondance par identifiant** —
quand une variable DDI et un composant SDMX partagent le même identifiant, on peut les
relier automatiquement. Cela fonctionne pour la plupart des jeux de données structurés où
les identifiants ont été attribués de façon cohérente.

```uml
DDI Variable ──────────────────────> SDMX Component
     │                                      │
     ├── ID attribute ◄──── matches ────► ID attribute
     ├── User ID      ◄──── matches ────► User ID
     │                                      │
     └── Value Domain ─────────────────> Dimension Codelist
                       ─────────────────> Measure Data Type
```

Dans Neo4j, ce lien devient une relation explicite :

```cypher
// Variable as Dimension
(v:Variable)-[:MAPS_TO_DIMENSION]->(d:Dimension)
(v)-[:HAS_VALUE_DOMAIN]->(vd:ValueDomain)-[:ALIGNED_WITH]->(cl:Codelist)

// Variable as Measure
(v:Variable)-[:MAPS_TO_MEASURE]->(m:Measure)
(v)-[:HAS_VALUE_DOMAIN]->(vd:ValueDomain)-[:ALIGNED_WITH]->(dt:DataType)
```

### Schéma du graphe pour l'intégration

```cypher
// DDI nodes (from ddigraph)
(:Variable {id, name, label, user_id})
(:ValueDomain {id, type})
(:CodeList {id, name})
(:Category {id, label, code_value})

// SDMX nodes
(:DataStructureDefinition {id, agency, version})
(:Dimension {id, position, concept_identity})
(:Measure {id, concept_identity})
(:Codelist {id, agency, version})  // SDMX codelist
(:Code {id, value, name})

// Integration relationships
(:Variable)-[:MAPS_TO_DIMENSION {match_type, confidence}]->(:Dimension)
(:Variable)-[:MAPS_TO_MEASURE {match_type, confidence}]->(:Measure)
(:CodeList)-[:ALIGNED_WITH {mapping_date, method}]->(:Codelist)
(:Category)-[:CORRESPONDS_TO]->(:Code)
```

### Création des correspondances

Exécutez ces requêtes Cypher pour créer les liens. La première requête correspond par
`user_id` (la correspondance la plus fiable) ; la seconde utilise le champ `id` brut
comme solution de repli :

```cypher
// Match DDI variables to SDMX dimensions by user_id
MATCH (v:Variable)
WHERE v.user_id IS NOT NULL
MATCH (d:Dimension)
WHERE d.id = v.user_id OR d.concept_identity = v.user_id
MERGE (v)-[m:MAPS_TO_DIMENSION]->(d)
SET m.match_type = 'user_id',
    m.matched_on = datetime(),
    m.confidence = 1.0
RETURN v.name, d.id, m.match_type
```

```cypher
// Match by ID attribute
MATCH (v:Variable)
MATCH (d:Dimension)
WHERE d.id = v.id
MERGE (v)-[m:MAPS_TO_DIMENSION]->(d)
SET m.match_type = 'id',
    m.matched_on = datetime(),
    m.confidence = 0.9
RETURN v.name, d.id, m.match_type
```

### Alignement des domaines de valeurs

Une fois les variables mises en correspondance avec les dimensions, leurs domaines de valeurs
doivent être alignés avec les listes de codes SDMX :

```cypher
// Find DDI CodeLists that should align with SDMX Codelists
MATCH (v:Variable)-[:MAPS_TO_DIMENSION]->(d:Dimension)
MATCH (v)-[:HAS_VALUE_DOMAIN]->(:ValueDomain)-[:USES_CODELIST]->(ddi_cl:CodeList)
MATCH (d)-[:HAS_LOCAL_REPRESENTATION]->(sdmx_cl:Codelist)
MERGE (ddi_cl)-[a:ALIGNED_WITH]->(sdmx_cl)
SET a.alignment_date = datetime()
RETURN ddi_cl.name, sdmx_cl.id
```

```cypher
// Map individual categories to codes
MATCH (ddi_cl:CodeList)-[:ALIGNED_WITH]->(sdmx_cl:Codelist)
MATCH (ddi_cl)-[:HAS_CATEGORY]->(cat:Category)
MATCH (sdmx_cl)-[:HAS_CODE]->(code:Code)
WHERE cat.code_value = code.value
MERGE (cat)-[:CORRESPONDS_TO]->(code)
RETURN cat.label, code.name
```

## Interrogation des données intégrées

### Trouver toutes les variables mises en correspondance

```cypher
MATCH (v:Variable)-[m:MAPS_TO_DIMENSION|MAPS_TO_MEASURE]->(component)
RETURN v.name AS variable,
       type(m) AS mapping_type,
       labels(component)[0] AS component_type,
       component.id AS component_id,
       m.confidence AS confidence
ORDER BY m.confidence DESC
```

### Tracer la lignée complète

```cypher
// From DDI question to SDMX dimension
MATCH path = (q:QuestionItem)<-[:ASKS_QUESTION]-(:QuestionConstruct)
             <-[:HAS_CONSTRUCT*]-(seq:Sequence),
      (v:Variable)-[:MAPS_TO_DIMENSION]->(d:Dimension)
WHERE v.question_id = q.fragment_id
RETURN q.name AS question,
       v.name AS variable,
       d.id AS sdmx_dimension,
       length(path) AS depth
```

### Trouver les variables non mises en correspondance

```cypher
MATCH (v:Variable)
WHERE NOT (v)-[:MAPS_TO_DIMENSION|MAPS_TO_MEASURE]->()
RETURN v.id, v.name, v.user_id
ORDER BY v.name
```

### Rapport d'alignement des listes de codes

```cypher
MATCH (ddi_cl:CodeList)-[:ALIGNED_WITH]->(sdmx_cl:Codelist)
OPTIONAL MATCH (ddi_cl)-[:HAS_CATEGORY]->(cat:Category)
OPTIONAL MATCH (cat)-[:CORRESPONDS_TO]->(code:Code)
WITH ddi_cl, sdmx_cl,
     count(DISTINCT cat) AS ddi_categories,
     count(DISTINCT code) AS mapped_codes
RETURN ddi_cl.name AS ddi_codelist,
       sdmx_cl.id AS sdmx_codelist,
       ddi_categories,
       mapped_codes,
       round(100.0 * mapped_codes / ddi_categories) AS pct_mapped
```

## Avantages de l'approche graphe

### 1. Cardinalité flexible des correspondances

Une seule variable DDI peut correspondre à plusieurs composants SDMX (ou inversement) sans
modification du schéma :

```cypher
// Variable maps to both dimension and attribute
(v:Variable)-[:MAPS_TO_DIMENSION]->(d:Dimension)
(v:Variable)-[:MAPS_TO_ATTRIBUTE]->(a:Attribute)
```

### 2. Métadonnées de correspondance riches

Les relations portent des propriétés qui documentent la correspondance :

```cypher
[:MAPS_TO_DIMENSION {
  match_type: 'user_id',      // How the match was made
  confidence: 0.95,           // Confidence score
  matched_on: datetime(),     // When
  matched_by: 'auto',         // Who/what
  notes: 'Verified by SME'    // Documentation
}]
```

### 3. Enrichissement incrémental

Ajoutez de nouveaux types de correspondance sans modifier les données existantes :

```cypher
// Later: add semantic similarity mappings
MATCH (v:Variable), (d:Dimension)
WHERE gds.similarity.cosine(v.embedding, d.embedding) > 0.8
MERGE (v)-[m:MAPS_TO_DIMENSION]->(d)
SET m.match_type = 'semantic',
    m.confidence = gds.similarity.cosine(v.embedding, d.embedding)
```

### 4. Navigation bidirectionnelle

Interrogez depuis la perspective de chaque standard :

```cypher
// DDI-first: What SDMX components does this variable map to?
MATCH (v:Variable {name: 'AGE'})-[:MAPS_TO_DIMENSION|MAPS_TO_MEASURE]->(c)
RETURN c

// SDMX-first: What DDI variables feed this dimension?
MATCH (d:Dimension {id: 'AGE'})<-[:MAPS_TO_DIMENSION]-(v:Variable)
RETURN v
```

### 5. Analyse d'impact

Comprendre les effets en aval des modifications :

```cypher
// If we change this CodeList, what SDMX structures are affected?
MATCH (cl:CodeList {id: 'CL_SEX'})-[:ALIGNED_WITH]->(sdmx_cl:Codelist)
      <-[:HAS_LOCAL_REPRESENTATION]-(d:Dimension)
      <-[:HAS_DIMENSION]-(dsd:DataStructureDefinition)
RETURN dsd.id AS affected_structure, d.id AS via_dimension
```

## Implémentation avec ddigraph

### Étape 1 : Charger les données DDI

```bash
ddigraph load survey.xml --format lifecycle
```

### Étape 2 : Charger la structure SDMX

Créer les nœuds SDMX (exemple en Cypher) :

```cypher
// Load DSD
CREATE (dsd:DataStructureDefinition {
  id: 'DSD_LFS',
  agency: 'EUROSTAT',
  version: '1.0'
})

// Load Dimensions
CREATE (d:Dimension {id: 'FREQ', position: 1, concept_identity: 'FREQ'})
CREATE (d:Dimension {id: 'GEO', position: 2, concept_identity: 'GEO'})
// ... etc
```

### Étape 3 : Exécuter les requêtes de correspondance

Lancez les requêtes de poignée de main pour créer les relations d'intégration.

### Étape 4 : Valider et rapporter

```cypher
// Summary statistics
MATCH (v:Variable)
OPTIONAL MATCH (v)-[m:MAPS_TO_DIMENSION]->(d)
OPTIONAL MATCH (v)-[m2:MAPS_TO_MEASURE]->(measure)
RETURN count(v) AS total_variables,
       count(d) AS mapped_to_dimension,
       count(measure) AS mapped_to_measure,
       count(v) - count(d) - count(measure) AS unmapped
```

## Conclusion

Les bases de données graphe transforment l'interopérabilité des standards, d'un processus
fragile et lourd en code, en un modèle de données flexible et interrogeable. La représentation
explicite des correspondances sous forme de relations permet :

- Une logique d'intégration auto-documentée
- Une extension facile vers de nouveaux types de correspondance
- Des requêtes puissantes de lignée et d'impact
- Un raffinement incrémental des correspondances au fil du temps

Pour l'intégration DDI-SDMX en particulier, le modèle en graphe représente naturellement la
"poignée de main" entre les identifiants de variables et les identifiants de composants, tout
en préservant le contexte complet nécessaire pour comprendre et maintenir les correspondances.
