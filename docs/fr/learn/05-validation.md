# Leçon 5 — Prouver que c'est juste

!!! abstract "Ce que vous allez apprendre"
    - Vérifier un fichier DDI contre le XSD officiel avant de lui faire confiance
    - Vérifier un export RDF contre des formes SHACL après l'avoir produit
    - Distinguer les deux, et savoir lequel répond à quelle question

Cette leçon demande `pip install "ddigraph[shacl]"`.

## Deux questions différentes

Il y a deux moments où « est-ce juste ? » mérite d'être posé, et ils
appellent des outils différents.

**Avant.** Ce fichier est-il du DDI valide ? C'est une question sur le XML,
et la réponse vient du XSD que publie la DDI Alliance.

**Après.** Ce que j'ai produit est-il du RDF valide, avec les bonnes
classes et les propriétés requises ? C'est une question sur le graphe, et
la réponse vient des formes SHACL.

Aucun ne remplace l'autre. Un fichier DDI parfaitement valide peut produire
du RDF absurde si l'exportateur est faux. Un export parfait peut venir d'un
fichier qui n'a jamais été conforme.

## Avant : XSD

Le package livre les schémas officiels — 154 fichiers XSD couvrant Codebook
2.6, Lifecycle 3.1 à 3.3 et CDI 1.0. `ddigraph validate` choisit le bon :

<!-- runnable -->
```bash
ddigraph validate "$FIXTURE" --max-issues 3 || true
```

```text
File:   fragment_instance.xml
Flavor: lifecycle 3.3
Schema: instance_3_3.xsd
Result: invalid (3 issue(s))
  line 8: Element '{ddi:datacollection:3_3}Instrument', attribute 'id': The attribute 'id' is not allowed.
```

Il a choisi `instance_3_3.xsd` tout seul. La variante vient de l'élément
racine ; la *version* vient de l'espace de noms que le document déclare —
`ddi:datacollection:3_3`. Valider du DDI-L 3.3 contre le schéma 3.1
produirait une page d'absurdités : ce n'est donc pas à vous de vous en
souvenir.

La même chose depuis Python :

<!-- runnable -->
```python
import os

from ddigraph.validation import validate

result = validate(os.environ["FIXTURE"], max_issues=3)

print("valide :", result.valid)
print("schéma :", result.schema.name)
for issue in result.issues:
    print(" ", issue)
```

!!! warning "Ce fichier est réellement invalide, et c'est le propos"
    Tous les fichiers XML de ce dépôt échouent à la validation XSD. Ils
    sont synthétiques — écrits pour exercer les analyseurs, pas pour être
    conformes. Celui de Codebook est un `<codeBook>` nu, sans aucun espace
    de noms.

    Une bonne part du DDI publié est dans la même situation : il s'analyse,
    il se charge, il n'est pas strictement valide. C'est pourquoi
    `ddigraph load` ne valide pas sans qu'on le demande. Refuser des
    fichiers qui fonctionnent rendrait l'outil moins utile, pas plus.

Demandez la rigueur quand vous la voulez :

```bash
ddigraph load survey.xml --validate    # refuser le fichier s'il n'est pas conforme
ddigraph export survey.xml --validate -o out.ttl
```

`ddigraph validate` sort avec un code non nul en cas de violation : une
étape de CI tient donc en une ligne.

```bash
ddigraph validate survey.xml || exit 1
```

??? info "Une subtilité du schéma Codebook"
    Le schéma DDI-Codebook 2.6 publié par l'Alliance n'est lui-même pas du
    XSD valide. En 55 endroits, un `xs:attribute` place son `xs:annotation`
    *après* son `xs:simpleType`, alors que la spécification exige
    `(annotation?, simpleType?)`. Tout analyseur conforme le rejette.

    ddigraph répare l'ordre en mémoire avant la compilation : la validation
    Codebook fonctionne donc. Le fichier sur disque reste identique octet
    pour octet à ce que l'Alliance a publié — son empreinte figure dans
    `schemas/manifest.json` et doit continuer de correspondre. Le
    réordonnancement est sans risque car `xs:annotation` est de la
    documentation que rien ne lit.

## Après : SHACL

SHACL décrit ce à quoi un *graphe* doit ressembler : telle classe doit
porter telle propriété, tel lien doit viser tel type de nœud.
`ddigraph shapes` génère les formes depuis `DDISchema` — la table qui
construit aussi les contraintes Neo4j — elles ne peuvent donc pas diverger
de ce que l'exportateur émet.

<!-- runnable -->
```python
import os

import pyshacl
import rdflib

import ddigraph
from ddigraph.rdf.shacl import shapes_graph

ddigraph.export(os.environ["FIXTURE"], "survey.ttl", format="turtle")

data = rdflib.Graph().parse("survey.ttl", format="turtle")
conforms, _graph, _text = pyshacl.validate(data, shacl_graph=shapes_graph(flavor="lifecycle"))
print("conforme :", conforms)
```

```text
conforme : True
```

L'export est conforme alors même que le fichier source ne passe pas le XSD.
Ce n'est pas une contradiction : ce sont les deux questions qui sont
réellement différentes. L'analyseur est tolérant, il lit donc un fichier
légèrement non conforme et produit malgré tout un graphe bien formé.

Ou depuis la ligne de commande :

```bash
ddigraph shapes -o shapes.ttl --flavor lifecycle
```

## Pourquoi `--flavor` compte ici

Utilisez `--flavor` pour valider des données réelles. Vingt et un noms de
types DDI apparaissent dans plusieurs variantes — `Category`, `CodeList`,
`Universe` — avec des champs d'identité différents. Sans variante, les
formes des trois sont émises, et toute contrainte sur laquelle elles
divergent est omise plutôt que devinée.

Vous avez rencontré ce point en leçon 2, sous la forme du préfixe `CDI` sur
chaque nom de type CDI. Même collision, traitée de deux façons.

## Exercice

Validez le fichier CDI contre son XSD, puis exportez-le et validez l'export
contre les formes CDI. Les deux sont-ils d'accord ?

??? success "Solution"
    ```python
    import os

    import pyshacl
    import rdflib

    import ddigraph
    from ddigraph.rdf.shacl import shapes_graph
    from ddigraph.validation import validate

    xsd = validate(os.environ["CDI_FIXTURE"], max_issues=1)
    print("XSD valide :", xsd.valid)

    ddigraph.export(os.environ["CDI_FIXTURE"], "cdi.ttl", format="turtle")
    data = rdflib.Graph().parse("cdi.ttl", format="turtle")
    conforms, _g, _t = pyshacl.validate(data, shacl_graph=shapes_graph(flavor="cdi"))
    print("SHACL conforme :", conforms)
    ```

    Ils divergent : le XSD dit non, SHACL dit oui. Le fichier déclare
    l'espace de noms `http://ddi-cdi/1.0`, qui n'est pas celui du schéma
    publié ; le XSD n'a donc aucune déclaration correspondant à l'élément
    racine. L'analyseur ne s'en soucie pas, produit un graphe correct, et
    l'export est conforme.

    Un désaccord entre les deux est informatif, pas un bogue. Il vous dit
    que le problème est dans le *document d'entrée*, pas dans ce que vous
    en avez construit.

## Vérifiez-vous

- Lequel des deux repérerait une faute de frappe dans un nom d'élément du XML source ?
- Lequel repérerait un exportateur ayant oublié d'émettre `skos:prefLabel` ?
- Pourquoi `ddigraph load` ne valide-t-il pas par défaut ?

---

Suivant : [Construire votre pipeline](06-your-own-pipeline.md) — envoyer du
DDI vers un endroit dont ce package n'a jamais entendu parler.
