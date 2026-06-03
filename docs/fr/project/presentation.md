# Sommaire exécutif

**ddigraph** est un paquet Python qui transforme les métadonnées DDI (Data Documentation Initiative) d'archives XML statiques en un **graphe de connaissances interrogeable** dans Neo4j. Cela permet aux organisations de :

- **Comprendre** les instruments d'enquête complexes grâce à l'exploration visuelle
- **Intégrer** de manière transparente avec d'autres normes internationales comme SDMX
- **Exploiter** l'IA et l'apprentissage automatique pour la découverte de métadonnées
- **Mettre à l'échelle** les opérations de métadonnées au-delà de la documentation manuelle

---

## L'objectif : De l'archive à l'actif

### Le problème que nous résolvons

Les métadonnées d'enquête vivent aujourd'hui dans des fichiers XML qui sont :

- ✗ **Difficiles à naviguer** : Les hiérarchies profondément imbriquées nécessitent des outils spécialisés
- ✗ **Difficiles à intégrer** : Pas de moyen standardisé de se connecter à d'autres systèmes
- ✗ **Inaccessibles à l'IA** : Les formats actuels ne peuvent pas exploiter les capacités modernes d'apprentissage automatique
- ✗ **Longues à analyser** : Des questions comme « quelles variables utilisent cette liste de codes ? » nécessitent un travail manuel

### Ce que nous offrons

ddigraph convertit ceci :

```xml
<!-- 148 Ko de XML imbriqué -->
<Fragment>
  <QuestionItem>
    <QuestionReference>
      <ID>q-001</ID>
    </QuestionReference>
  </QuestionItem>
</Fragment>
```

En ceci :

```cypher
// Requête simple et visuelle
MATCH (q:QuestionItem)-[:USES_CODELIST]->(cl:CodeList)
WHERE cl.name = 'Age Groups'
RETURN q.question_text
```

---

## Avantages clés

### 1. Découverte instantanée des métadonnées

**Avant** : Les analystes parcourent manuellement le XML pour trouver quelles questions utilisent une liste de codes spécifique.

- Temps : 2 à 4 heures par requête
- Sujet aux erreurs : Facile de manquer des références dans les structures imbriquées
- Limité : Ne peut répondre qu'aux questions explicitement prévues

**Après** : Les requêtes graphe retournent des réponses en temps réel.

```cypher
// Trouver toutes les questions utilisant les codes « Statut d'emploi »
MATCH (q:QuestionItem)-[:USES_CODELIST]->(cl:CodeList {name: 'Employment Status'})
RETURN q.question_text, q.name
```

- Temps : < 1 seconde
- Complet : Retourne toutes les relations automatiquement
- Flexible : Peut explorer des connexions inattendues

**Impact métier** : Révisions de questionnaires plus rapides, réduction des erreurs de collecte de données, amélioration de la qualité des enquêtes.

### 2. Visualisation des instruments d'enquête

**Avant** : Le flux de l'enquête est documenté dans de longs documents Word ou des feuilles de calcul.

**Après** : La visualisation interactive du graphe montre la structure complète en un coup d'oeil.

```text
[Point d'entrée] → [Séquence : Démographie]
    ├→ [Question : Âge]
    ├→ [Si Âge ≥ 18]
    │   └→ [Séquence : Emploi]
    │       ├→ [Question : Statut d'emploi]
    │       └→ [Question : Heures travaillées]
    └→ [Si Âge < 18]
        └→ [Séquence : Éducation]
```

**Impact métier** : Les parties prenantes peuvent examiner la logique de l'enquête visuellement, détectant les défauts de conception avant le déploiement sur le terrain.

### 3. Analyse d'impact et assurance qualité

**Avant** : Modifier une liste de codes nécessite de vérifier manuellement des dizaines de fichiers XML pour trouver les dépendances.

**Après** : Les requêtes graphe montrent instantanément tous les éléments affectés.

```cypher
// Qu'est-ce qui sera affecté si nous changeons cette liste de codes ?
MATCH (cl:CodeList {name: 'Industry Codes'})
MATCH (cl)<-[:USES_CODELIST]-(q:QuestionItem)
MATCH (q)<-[:ASKS_QUESTION]-(qc:QuestionConstruct)
MATCH (qc)<-[:HAS_CONSTRUCT*]-(seq:Sequence)
RETURN DISTINCT seq.name AS sections_affectees, 
       count(q) AS nombre_questions
```

**Impact métier** : Risque réduit de changements cassants, mises à jour d'enquêtes plus rapides, amélioration de la qualité des données.

### 4. Documentation automatisée

**Avant** : La documentation de l'enquête est rédigée manuellement et devient rapidement obsolète.

**Après** : La documentation est générée à partir du graphe, toujours synchronisée avec la structure réelle.

```python
# Générer une documentation en langage naturel
def document_survey(instrument_id):
    results = session.run("""
        MATCH (i:Instrument {id: $id})-[:HAS_CONSTRUCT]->(seq:Sequence)
        MATCH (seq)-[:HAS_CONSTRUCT]->(c)
        RETURN seq.name, labels(c)[0], count(*) as count
        ORDER BY seq.name
    """, id=instrument_id)
    
    # Alimenter le LLM pour la génération en langage naturel
    return generate_documentation(results)
```

**Résultat** : « L'Enquête sur la population active comprend 5 sections : Démographie (8 questions), Emploi (12 questions)... »

**Impact métier** : Documentation toujours à jour, effort manuel réduit, formatage cohérent.

---

## Interopérabilité avec les normes internationales (SDMX)

### Le défi de l'intégration

Les organisations doivent communiquer des données aux organismes internationaux (Eurostat, OCDE, ONU) en utilisant le format SDMX (Statistical Data and Metadata eXchange). La mise en correspondance des métadonnées DDI avec la structure SDMX est généralement :

### La solution graphe

ddigraph rend l'intégration DDI-SDMX **explicite et interrogeable** :

```cypher
// Mise en correspondance automatique via des identifiants partagés
MATCH (v:Variable)
WHERE v.user_id IS NOT NULL
MATCH (d:Dimension {id: v.user_id})
MERGE (v)-[m:MAPS_TO_DIMENSION]->(d)
SET m.match_type = 'user_id',
    m.confidence = 1.0,
    m.mapped_on = datetime()
```

**Ce que cela signifie** :

1. Les **variables DDI** (de votre enquête) sont liées directement aux **dimensions SDMX** (structure de rapport international)
2. La mise en correspondance est **documentée dans le graphe** avec des métadonnées sur la confiance et la méthode
3. Les deux directions sont interrogeables :
   - « Quels composants SDMX correspondent à cette variable ? »
   - « Quelles variables DDI alimentent cette dimension SDMX ? »

### Exemple concret

**Scénario** : Votre Enquête sur la population active doit être rapportée à Eurostat en utilisant leur modèle SDMX.

**Approche traditionnelle** :

1. Exporter les variables DDI vers Excel
2. Faire correspondre manuellement aux codes de dimension Eurostat
3. Maintenir un fichier de correspondance Excel
4. Espérer que rien ne change

**Approche ddigraph** :

1. Charger les métadonnées DDI : `ddigraph load survey.xml`
2. Charger la structure SDMX dans le même graphe
3. Exécuter la requête de mise en correspondance automatique
4. Examiner et valider les correspondances visuellement

**Impact métier** :

- Configuration **plus rapide** des rapports internationaux
- **Zéro maintenance** car les correspondances se mettent à jour automatiquement
- **Auditabilité complète** de quelles variables correspondent où et pourquoi
- **Réduction des erreurs** de transcription manuelle

### Rapports d'alignement

Générer des rapports d'alignement complets :

```cypher
// Afficher la couverture des correspondances
MATCH (v:Variable)
OPTIONAL MATCH (v)-[:MAPS_TO_DIMENSION]->(d:Dimension)
WITH count(v) as total, count(d) as mapped
RETURN total, mapped, 
       round(100.0 * mapped / total) AS couverture_pct
```

**Résultat** : « Couverture : 87 % des variables mises en correspondance (1 400 sur 1 609) »

---

## Préparation à l'IA : Libérer les capacités d'apprentissage automatique

### Pourquoi la structure graphe est importante pour l'IA

Les fichiers XML traditionnels ne sont **pas prêts pour l'IA** :

- Les LLM ne peuvent pas « voir » les relations enfouies dans les balises imbriquées
- Les systèmes de génération augmentée par récupération (RAG) ont besoin d'un contexte interrogeable
- Les embeddings ne capturent pas les connexions structurelles

**Les bases de données graphe rendent les métadonnées accessibles à l'IA** :

- Les relations sont explicites et parcourables
- Le contexte est préservé dans la structure du graphe
- La recherche de motifs est native, pas reconstruite

### Capacité 1 : Chatbots d'enquête intelligents

**Cas d'utilisation** : Les parties prenantes posent des questions sur la conception de l'enquête en langage naturel.

```bash
Utilisateur : « Quelles questions viennent après la section emploi ? »
Bot : [Interroge le graphe pour les séquences suivant les construits d'emploi]
     « Après les questions sur l'emploi, les répondants répondent à 5 questions 
      sur la satisfaction au travail, puis bifurquent selon le statut d'emploi... »
```

**Comment ça fonctionne** :

1. Question de l'utilisateur → Le LLM convertit en requête graphe
2. Le graphe retourne des résultats structurés
3. Le LLM convertit les résultats en langage naturel

**Impact métier** : Les parties prenantes non techniques peuvent explorer la structure de l'enquête sans formation.

### Capacité 2 : Génération augmentée par récupération (RAG)

**Cas d'utilisation** : Générer la documentation de l'enquête ou répondre aux questions de politique fondées sur les métadonnées réelles.

```python
# Pipeline RAG avec contexte graphe
def answer_question(user_query):
    # 1. Convertir la requête en motif graphe
    graph_results = neo4j.run("""
        MATCH (q:QuestionItem)
        WHERE q.question_text CONTAINS $keywords
        MATCH path = (q)<-[:ASKS_QUESTION]-(:QuestionConstruct)
                        <-[:HAS_CONSTRUCT]-(seq:Sequence)
        RETURN q.question_text, seq.name, path
    """, keywords=extract_keywords(user_query))
    
    # 2. Alimenter le LLM avec le contexte graphe
    context = format_graph_results(graph_results)
    response = llm.generate(user_query, context=context)
    
    return response
```

**Exemple** :

- Requête : « Comment l'enquête mesure-t-elle le chômage ? »
- Le graphe récupère : Questions sur le statut d'emploi, les heures travaillées, la recherche d'emploi
- Le LLM génère : « L'enquête mesure le chômage à travers trois questions clés dans la section Emploi... »

**Impact métier** : Réponse automatisée aux demandes des parties prenantes, cohérente avec la conception réelle de l'enquête.

### Capacité 3 : Validation de la qualité avec l'IA

**Cas d'utilisation** : Détecter automatiquement les problèmes de conception d'enquête.

```cypher
// Trouver les questions sans options de réponse (erreur potentielle)
MATCH (q:QuestionItem)
WHERE NOT (q)-[:USES_CODELIST]->()
  AND q.response_type = 'code'
RETURN q.name, q.question_text AS liste_codes_potentiellement_manquante

// Trouver les construits inaccessibles (code mort dans l'enquête)
MATCH (c)
WHERE (c:Sequence OR c:QuestionConstruct)
  AND NOT ()-[:HAS_CONSTRUCT|THEN|ELSE]->(c)
  AND NOT c:EntryPoint
RETURN labels(c)[0] AS type, c.name AS construit_orphelin
```

**Amélioration IA** : Entraîner des modèles d'apprentissage automatique pour prédire les problèmes courants basés sur les motifs du graphe.

**Impact métier** : Détecter les erreurs de conception d'enquête avant le déploiement sur le terrain, réduisant les révisions coûteuses.

### Capacité 4 : Recherche sémantique et recommandations

**Cas d'utilisation** : Trouver des questions similaires à travers différentes enquêtes pour l'harmonisation.

```python
# Générer des embeddings pour toutes les questions
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

**Requête de questions similaires** :

```cypher
// Trouver les questions sémantiquement similaires à « Quel est votre âge ? »
MATCH (target:QuestionItem {fragment_id: 'q-age'})
MATCH (similar:QuestionItem)
WHERE similar <> target
WITH similar, 
     gds.similarity.cosine(target.embedding, similar.embedding) AS similarity
WHERE similarity > 0.8
RETURN similar.question_text, similarity
ORDER BY similarity DESC
LIMIT 5
```

**Impact métier** : Harmonisation des enquêtes plus rapide, meilleure réutilisation des questions existantes, meilleure comparabilité dans le temps.

### L'avantage IA

| Capacité | Archive XML | Graphe + IA |
| ------------ | ------------- | ------------ |
| Réponse aux questions | Recherche manuelle | Chatbot automatisé |
| Documentation | Documents Word statiques | Générée à la demande |
| Contrôles qualité | Revue manuelle | Validation par l'IA |
| Harmonisation | Comparaison de tableurs | Recherche sémantique |
| Découverte | Limitée aux requêtes connues | Analyse exploratoire |

**En résumé** : ddigraph + IA = Des métadonnées qui travaillent pour vous, et non l'inverse.

## Atténuation des risques

### Risques techniques

| Risque | Atténuation |
| ------ | ------------ |
| Courbe d'apprentissage | Requêtes pré-construites, outils visuels, documentation |
| Complexité de l'infrastructure | Utiliser Neo4j Aura géré, Docker pour le développement |
| Migration des données | Déploiement incrémental, garder le XML comme source de vérité |
| Intégration d'outils | Le patron adaptateur supporte l'export vers CSV/JSON/pandas |

### Risques organisationnels

| Risque | Atténuation |
| ------ | ------------ |
| Résistance au changement | Commencer par une preuve de concept, démontrer des gains rapides |
| Lacunes en compétences | Plan de formation, support externe disponible |
| Contraintes budgétaires | Noyau open source, mise à l'échelle cloud optionnelle |

---

## Comparaison : Graphe vs approches traditionnelles

### vs. Bases de données relationnelles (SQL)

| Caractéristique | Base relationnelle | Base graphe (ddigraph) |
| --------- | --------------- | --------------------- |
| Complexité des requêtes | JOINs complexes | Recherche de motifs naturelle |
| Requêtes à profondeur variable | CTE récursives (lent) | Parcours natif (rapide) |
| Flexibilité du schéma | Migrations ALTER TABLE | Ajouter des relations dynamiquement |
| Modélisation des relations | Clés étrangères + tables de jonction | Relations directes |
| Visualisation | Non native | Navigateur graphe intégré |

**Verdict** : Les bases de données graphe sont conçues pour les données connectées comme les métadonnées DDI.

### vs. Scripts d'analyse XML

| Caractéristique | Scripts personnalisés | ddigraph |
| --------- | ---------------- | --------- |
| Maintenance | Les scripts cassent avec les changements de schéma | Schéma déclaratif, s'adapte automatiquement |
| Réutilisabilité | Scripts à usage unique | Bibliothèque de requêtes pour tous les usages |
| Performance | Re-analyser le fichier à chaque fois | Interroger le graphe en millisecondes |
| Collaboration | Revues de code | Exploration visuelle |

**Verdict** : ddigraph élimine la dette technique des scripts d'analyse fragiles.

### vs. Documentation manuelle

| Caractéristique | Documents Word/Excel | ddigraph |
| --------- | ----------------- | --------- |
| Précision | Obsolète immédiatement | Reflète toujours la structure actuelle |
| Découverte | Limitée aux chemins documentés | Explorer n'importe quelle relation |
| Mises à jour | Édition manuelle | Automatique à partir des données |
| Intégration | Copier-coller | Accès API/requête |

**Verdict** : Les données graphe sont auto-documentées et toujours à jour.

---

## Questions et discussion

### Pour les gestionnaires techniques

- **Q** : Comment cela s'intègre-t-il avec notre infrastructure de données existante ?
  - **R** : ddigraph exporte vers CSV/JSON/pandas pour l'intégration avec n'importe quel outil. Le graphe complète, ne remplace pas.

- **Q** : Que faire si Neo4j devient un goulot d'étranglement ?
  - **R** : Neo4j peut gérer des milliards de noeuds. Les volumes de métadonnées actuels sont minuscules en comparaison.

### Pour les gestionnaires non techniques

- **Q** : Le personnel doit-il apprendre la programmation ?
  - **R** : Non. Navigateur graphe visuel + requêtes pré-construites pour les tâches courantes. Les utilisateurs avancés peuvent apprendre Cypher (plus simple que SQL).

---

## Conclusion : Les métadonnées comme actif stratégique

Les métadonnées d'enquête ont historiquement été un **centre de coûts** — une documentation nécessaire qui requiert un effort manuel pour être maintenue et interrogée.

**ddigraph transforme les métadonnées en actif stratégique** en les rendant :

- ✓ **Interrogeables** en temps réel
- ✓ **Intégrées** avec les normes internationales
- ✓ **Prêtes pour l'IA** pour les capacités modernes
- ✓ **Évolutives** à travers l'organisation

**L'opportunité** : Les organisations qui traitent les métadonnées comme une infrastructure obtiennent des avantages compétitifs en qualité des données, conformité et efficacité opérationnelle.

**Le choix** : Continuer avec des processus manuels, ou exploiter la technologie graphe moderne pour travailler plus intelligemment.

---

**Merci. Des questions ?**
