# Glossaire

Définitions en langage clair de tous les termes techniques utilisés dans la documentation
de ddigraph. Si vous voyez un mot que vous ne comprenez pas, cherchez-le ici.

---

## A

### Adaptateur / Patron adaptateur

Un **adaptateur** est un bout de code qui relie deux choses qui ne « parlent » pas le même
langage. Dans ddigraph, un adaptateur prend les données produites par l'analyseur DDI et les
traduit dans le format compris par une base de données spécifique. Par exemple, le
`Neo4jGraphAdapter` écrit dans Neo4j, tandis que le `NetworkXAdapter` écrit dans un graphe
NetworkX en mémoire.

Le **patron adaptateur** est l'approche de conception qui rend cela possible : l'analyseur ne
se soucie pas de quelle base de données vous utilisez — il produit des données, et
l'adaptateur s'occupe du reste.

### Asynchrone (async)

**Asynchrone** signifie « faire plusieurs choses à la fois sans attendre que chacune soit
terminée avant de commencer la suivante ».

Dans ddigraph, l'analyseur lit le XML et l'adaptateur écrit dans la base de données en même
temps. C'est beaucoup plus rapide que d'attendre la confirmation de chaque écriture avant de
lire la prochaine partie du XML. Les mots-clés Python `async`/`await` contrôlent ce comportement.

---

## B

### Contre-pression (back-pressure)

La **contre-pression** est un régulateur qui ralentit une partie d'un système quand une autre
partie ne peut pas suivre.

Dans ddigraph, si la base de données écrit lentement, la contre-pression ralentit le lecteur
XML pour que la file d'attente entre les deux ne grossisse pas jusqu'à épuiser la mémoire.
Pensez-y comme un régulateur de débit d'eau : si le tuyau est bloqué en aval, il réduit le
débit en amont.

### Écriture par lots (batch writing)

L'**écriture par lots** consiste à envoyer beaucoup d'enregistrements à la base de données
en un seul voyage plutôt qu'un par un.

Imaginez envoyer 100 lettres : vous pourriez faire 100 voyages à la poste, ou les mettre
toutes dans une boîte et faire 1 seul voyage. L'écriture par lots est la deuxième approche.
ddigraph utilise la clause Cypher `UNWIND` pour les écritures par lots, ce qui peut être
10 à 100 fois plus rapide.

---

## C

### Codebook (DDI Codebook)

Le **DDI Codebook** est l'un des deux principaux formats DDI XML. C'est le format le plus
ancien et le plus simple. Il décrit un ensemble de données d'enquête avec un nœud `Dataset`
central connecté aux variables, questions et listes de codes.

Utilisez DDI Codebook si votre fichier XML a un élément racine comme `<codeBook>` ou
`<codebook>`.

### Cypher

**Cypher** est le langage de requête utilisé par Neo4j — similaire à SQL, mais conçu pour
les graphes plutôt que les tables.

En SQL vous écrivez `SELECT * FROM utilisateurs WHERE id = 1`. En Cypher vous écrivez
`MATCH (u:User {id: 1}) RETURN u`. Cypher utilise des motifs visuels comme
`(noeud)-[:RELATION]->(autre)` pour exprimer comment les données sont connectées. Vous n'avez
pas besoin de connaître Cypher pour utiliser la CLI de ddigraph, mais c'est utile quand vous
voulez explorer vos données dans Neo4j Browser.

---

## D

### DDI

**DDI** signifie *Data Documentation Initiative* (Initiative de documentation des données).
C'est une norme internationale pour décrire les données d'enquêtes en sciences sociales —
questionnaires, variables, listes de codes. Les fichiers DDI sont des fichiers XML qui
contiennent les métadonnées (descriptions) d'un ensemble de données, pas les données elles-mêmes.

### DDI-CDI

**DDI-CDI** (DDI Cross-Domain Integration) est la version la plus récente de la norme DDI.
Elle peut décrire une plus grande variété de types de données, y compris les données
administratives et les données liées. ddigraph charge les fichiers DDI-CDI avec la classe
`CDILoader`.

### DDI-L (DDI Cycle de vie)

**DDI-L** (DDI Lifecycle, version 3.x) est un format DDI plus complexe qui prend en charge
des composants réutilisables appelés *fragments*. Chaque fragment est une pièce indépendante
de métadonnées qui peut être référencée par d'autres fragments.

Utilisez DDI-L si votre fichier XML a un élément racine comme `<DDIInstance>` ou contient
des éléments `<Fragment>`.

---

## F

### Fragment / FragmentInstance

Un **fragment** en DDI-L est une seule unité réutilisable de métadonnées — par exemple,
une question, une variable ou un concept. Les fragments peuvent référencer d'autres
fragments par leur identifiant.

Un **FragmentInstance** est un fichier DDI-L XML qui regroupe de nombreux fragments.
ddigraph charge ces fichiers avec la classe `DDIFragmentLoader`.

---

## G

### Base de données graphe

Une **base de données graphe** stocke les données sous forme de nœuds (des choses) et de
relations (des connexions entre les choses), au lieu de tables et de lignes.

Une base de données relationnelle dit : « Une enquête a de nombreuses variables » en
utilisant une clé étrangère. Une base de données graphe dit : « Le nœud `Survey` est
connecté à un nœud `Variable` via une flèche `HAS_VARIABLE`. » Les bases de données graphe
rendent les requêtes complexes beaucoup plus rapides et simples.

ddigraph prend en charge Neo4j (une base de données graphe), mais aussi RDF, Gremlin et
NetworkX.

---

## I

### iterparse

**iterparse** est un analyseur XML en flux continu. Au lieu de charger l'intégralité d'un
fichier XML en mémoire d'un coup, iterparse lit un élément à la fois, le traite, puis le
supprime.

C'est important pour les grands fichiers. Un fichier DDI de 5 Go ferait planter un programme
qui le charge entièrement. Avec iterparse, ddigraph peut traiter un fichier de n'importe
quelle taille en utilisant seulement une petite quantité de mémoire constante. ddigraph
utilise en interne `iterparse` de lxml.

---

## K

### Graphe de connaissances (knowledge graph)

Un **graphe de connaissances** est une base de données graphe qui représente des faits sur
un domaine — qui est connecté à quoi, et pourquoi. Dans ddigraph, vos métadonnées DDI
deviennent un graphe de connaissances : vous pouvez poser des questions comme « quels
concepts sont couverts par cet instrument ? » ou « quelles variables partagent la même
liste de codes ? ».

---

## M

### MERGE (Neo4j)

**MERGE** est une opération Cypher qui signifie « trouve ce nœud/relation s'il existe,
ou crée-le s'il n'existe pas ». C'est comme un *upsert* en SQL.

ddigraph utilise MERGE pour que charger le même fichier deux fois ne crée pas de nœuds
en double. Le deuxième chargement trouve les nœuds existants et les met à jour au lieu
d'en créer de nouveaux.

---

## N

### Nœud (Node)

Dans un graphe, un **nœud** est un élément ou une entité unique — comme une ligne dans
une table. Dans ddigraph, les exemples de nœuds incluent `Variable`, `QuestionItem`,
`Concept` et `Dataset`. Chaque nœud a des propriétés (comme `name`, `label`, `id`)
qui le décrivent.

### Relation (Relationship)

Dans un graphe, une **relation** est une connexion nommée et directionnelle entre deux
nœuds — comme une clé étrangère, mais avec une direction et un nom.
Par exemple : `(Question)-[:BELONGS_TO]->(Instrument)` signifie « cette question
appartient à cet instrument ».

---

## P

### Protocole (Python Protocol)

En Python, un **protocole** est une façon de définir quelles méthodes une classe doit avoir,
sans obliger cette classe à hériter de quoi que ce soit.

Pensez-y comme une fiche de poste : « Pour être un adaptateur graphe, votre classe doit
avoir une méthode `write_batch()`. » N'importe quelle classe qui a cette méthode est
qualifiée — elle n'a pas besoin d'être une sous-classe de quoi que ce soit.

Dans ddigraph, `GraphWriteAdapter` est un protocole qui définit l'interface que chaque
adaptateur doit implémenter.

---

## S

### Schéma / Initialisation du schéma

Un **schéma** dans Neo4j est l'ensemble des index et contraintes qui rendent les requêtes
rapides et les données cohérentes. Par exemple, une contrainte pourrait dire « chaque nœud
`Variable` doit avoir un `id` unique ».

L'**initialisation du schéma** est le processus de création de ces index et contraintes avant
de commencer à charger des données. Dans ddigraph, vous exécutez `ddigraph bootstrap`
pour le faire. C'est sûr de l'exécuter plusieurs fois — si le schéma existe déjà, rien ne change.

### Analyseur en flux (streaming parser)

Un **analyseur en flux** traite un fichier pièce par pièce, plutôt que de charger tout le
fichier en mémoire à la fois. Voir aussi : **iterparse**.

---

## U

### UNWIND (Cypher)

**UNWIND** est une clause Cypher qui prend une liste d'éléments et traite chacun comme
une ligne séparée. ddigraph utilise UNWIND pour envoyer de nombreux enregistrements à
Neo4j en une seule requête (« voici 500 variables, créez-les toutes en même temps »)
au lieu d'envoyer une requête par enregistrement.

C'est la principale raison pour laquelle l'écriture par lots de ddigraph est rapide.
Au lieu de 500 allers-retours vers la base de données, il n'y en a qu'1.
