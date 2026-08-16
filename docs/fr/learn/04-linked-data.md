# Leçon 4 — Rejoindre le monde extérieur

!!! abstract "Ce que vous allez apprendre"
    - Exporter un fichier DDI en RDF que d'autres systèmes lisent
    - Comprendre l'astuce des deux types qui rend l'export réversible
    - Interroger un export en SPARQL

Cette leçon demande l'extra RDF : `pip install "ddigraph[rdf]"`.

## Le problème d'un vocabulaire à soi

Un graphe dans votre base vous est utile. Un graphe auquel d'autres peuvent
se joindre est utile à tout le monde. C'est à cela que sert RDF : une façon
partagée de dire « cette chose est une question, et elle utilise cette
liste de codes », où *question* et *utilise* signifient la même chose pour
tout lecteur.

Le piège, c'est que « partagé » ne fonctionne que si vous employez des
termes que d'autres emploient déjà. Inventez les vôtres et vous avez du XML
avec des étapes en plus.

Le mode d'échec ressemble à ceci, et il est assez répandu pour mériter
d'être reconnu :

```text
ddi:USES_CODELIST      # un nom de relation Neo4j
ddi:question_text      # un nom d'attribut Python
```

Les deux laissent fuir une convention de nommage interne dans un format
dont le but même est d'être externe — l'une vient de la base, l'autre du
code source. Et un préfixe `ddi:` pointant vers un domaine que vous ne
contrôlez pas ne peut être consulté par personne. Une telle sortie ne se
joint à rien.

## Trois couches

Le correctif comporte trois parties, et tout vocabulaire RDF sérieux fait
quelque chose de semblable.

**Réutiliser les termes publiés.** La DDI Alliance publie des vocabulaires
RDF — DISCO pour les études, variables et questions ; XKOS pour les
classifications. Les listes de codes s'alignent sur SKOS, la norme des
vocabulaires contrôlés. Là où un terme existe, on l'utilise.

**Créer un seul espace de noms pour le reste.** DISCO définit 16 classes ;
DDI compte environ 250 concepts. Le reste a besoin de termes, et ils vivent
sous un espace de noms qui
[se résout vers une page les décrivant](../ns/1.0.md).

**Émettre les deux types.** Expliqué ci-dessous — c'est la partie
intéressante.

## Votre premier export

<!-- runnable -->
```python
import os

import ddigraph

result = ddigraph.export(os.environ["FIXTURE"], "survey.ttl", format="turtle")
print(result.nodes, "nœuds ->", result.triples, "triplets")
```

Voyez ce qui sort pour la question :

```turtle
<urn:ddi:test.org:q1:1.0> a disco:Question,
        ddigraph:QuestionItem ;
    rdfs:label "Question 1" ;
    dcterms:identifier "urn:ddi:test.org:q1:1.0" ;
    dcterms:publisher "test.org" ;
    disco:questionText "What is your age?" .
```

Trois choses à remarquer.

**Le sujet est l'URN DDI** de la leçon 1 — `urn:ddi:test.org:q1:1.0`. Pas
une URL inventée. Il est déjà unique au niveau mondial : il n'y a rien à
inventer.

**Les prédicats sont des termes publiés.** `disco:questionText`,
`dcterms:publisher`, `rdfs:label`. Aucun `USES_CODELIST` nulle part.

**Il y a deux types.** `disco:Question` *et* `ddigraph:QuestionItem`.

## Pourquoi deux types

Ce dernier point semble redondant. Il ne l'est pas, et la raison mérite
d'être comprise car c'est elle qui rend l'aller-retour possible.

L'alignement vers les classes standard est **multiple vers un** :

| Libellé ddigraph | Classe standard |
| ------------------ | ----------------- |
| `Question` | `disco:Question` |
| `QuestionItem` | `disco:Question` |
| `CodeScheme` | `skos:ConceptScheme` |
| `CodeList` | `skos:ConceptScheme` |
| `CategoryScheme` | `skos:ConceptScheme` |

À partir du seul `disco:Question`, impossible de savoir si le point de
départ était une `Question` ou un `QuestionItem`. L'information a disparu.

Chaque nœud porte donc les deux : la classe standard pour les autres, et la
classe projet pour l'identité. Un consommateur orienté interopérabilité lit
`disco:Question` et ignore l'autre. Le lecteur ddigraph lit
`ddigraph:QuestionItem` et reconstruit le graphe d'origine à l'identique.

C'est pourquoi ceci fonctionne :

```bash
ddigraph export survey.xml --format turtle -o out.ttl
ddigraph load out.ttl        # et ça revient, sans rien perdre
```

## Les listes de codes deviennent du SKOS

Les vocabulaires contrôlés reçoivent un traitement particulier, car SKOS
est la norme la mieux outillée de tout ce domaine. Une `CodeList` devient
un `skos:ConceptScheme`, et chaque `Category` un `skos:Concept` :

<!-- runnable -->
```python
import os

import rdflib

import ddigraph

ddigraph.export(os.environ["FIXTURE"], "survey.ttl", format="turtle")

graph = rdflib.Graph().parse("survey.ttl", format="turtle")
rows = graph.query("""
    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
    SELECT ?concept ?label
    WHERE { ?concept a skos:Concept ; skos:prefLabel ?label }
""")
for concept, label in rows:
    print(concept, "->", label)
```

```text
urn:ddi:test.org:cat1:1.0 -> Under 18
```

C'est une requête SPARQL sur vos métadonnées d'enquête, avec un vocabulaire
que les outils de thésaurus, EuroVoc et tout l'écosystème SKOS parlent déjà.

!!! note "Le sens n'est pas décoratif"
    Le graphe dit `CodeList -HAS_CATEGORY-> Category`, car c'est ainsi que
    le XML s'imbrique. SKOS dit l'inverse : c'est le *concept* qui porte
    `skos:inScheme` vers son schéma, et `skos:member` appartient à
    `skos:Collection`, pas à `skos:ConceptScheme`.

    L'exportateur échange donc sujet et objet pour ces arcs. Émettre le
    sens du graphe tel quel produirait du SKOS que les validateurs
    rejettent — des triplets d'apparence correcte affirmant que le schéma
    est à l'intérieur du concept.

## Exercice

Exportez le fichier Codebook et comptez combien de types RDF distincts il
utilise. Puis comptez combien d'entre eux appartiennent à l'espace de noms
du projet plutôt qu'à un vocabulaire publié.

??? success "Solution"
    ```python
    import os

    import rdflib

    import ddigraph
    from ddigraph.rdf.vocabulary import DDIGRAPH

    ddigraph.export(os.environ["CODEBOOK_FIXTURE"], "cb.ttl", format="turtle")
    graph = rdflib.Graph().parse("cb.ttl", format="turtle")

    types = {str(t) for t in graph.objects(None, rdflib.RDF.type)}
    project = {t for t in types if t.startswith(DDIGRAPH)}

    print(len(types), "types,", len(project), "dans l'espace de noms projet")
    ```

    La plupart seront dans l'espace de noms du projet, et c'est attendu :
    DISCO couvre 16 classes contre environ 250 pour DDI. Les termes publiés
    portent les concepts qui intéressent les autres — études, variables,
    questions, listes de codes — et le reste est tout de même consigné
    plutôt qu'abandonné.

## Vérifiez-vous

- Pourquoi l'IRI de sujet est-il un URN DDI plutôt qu'une URL de votre domaine ?
- Que casse-t-on en n'émettant que le `rdf:type` standard ?
- Pourquoi l'exportateur inverse-t-il le sens de `HAS_CATEGORY` ?

---

Suivant : [Prouver que c'est juste](05-validation.md) — vérifier un export
contre des règles lisibles par machine.
