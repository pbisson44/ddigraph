# RDF / SPARQL

ddigraph peut exporter les métadonnées DDI sous forme de triplets RDF pour une utilisation avec des
points d'accès SPARQL et des outils du web sémantique.

## Vue d'ensemble

Le backend RDF convertit les entités DDI en triplets RDF en utilisant des vocabulaires standards :

- **DDI-RDF** : Vocabulaire RDF de l'Alliance DDI (lorsque disponible)
- **Dublin Core** : Termes de métadonnées standards
- **SKOS** : Pour les listes de codes et les catégories
- **Espace de noms personnalisé** : Pour les propriétés spécifiques à DDI

## Dépendances

RDFLib est inclus avec ddigraph :

```bash
pip install ddigraph  # inclut rdflib
```

Pour les points d'accès SPARQL distants, vous pourriez avoir besoin de pilotes supplémentaires :

```bash
pip install sparqlwrapper  # pour les requêtes SPARQL distantes
```

## Utilisation de base

### Convertir DDI en RDF

```python
from rdflib import Graph, Namespace, Literal, URIRef
from rdflib.namespace import RDF, RDFS, SKOS, DCTERMS
from ddigraph import DDIFragmentParser

# Définir les espaces de noms
DDI = Namespace("http://ddi.example.org/")
DATA = Namespace("http://data.example.org/")

g = Graph()
g.bind("ddi", DDI)
g.bind("data", DATA)
g.bind("skos", SKOS)
g.bind("dcterms", DCTERMS)

# Analyser DDI et créer les triplets
parser = DDIFragmentParser()
for fragment in parser.parse("survey.xml"):
    subj = DATA[fragment.fragment_id]

    # Triplet de type
    g.add((subj, RDF.type, DDI[fragment.element_type]))

    # Libellé
    if fragment.label:
        g.add((subj, RDFS.label, Literal(fragment.label)))

    # URN comme identifiant
    if fragment.urn:
        g.add((subj, DCTERMS.identifier, Literal(fragment.urn)))

    # Relations
    for rel_type, ref in fragment.references:
        obj = DATA[ref.id]
        g.add((subj, DDI[rel_type], obj))

# Sérialiser
print(g.serialize(format="turtle"))
```

### Formats d'export

```python
# Turtle (lisible par l'humain)
g.serialize("output.ttl", format="turtle")

# N-Triples (traitement en flux)
g.serialize("output.nt", format="nt")

# RDF/XML
g.serialize("output.rdf", format="xml")

# JSON-LD
g.serialize("output.jsonld", format="json-ld")
```

## Exemple complet

Consultez `demo/load_rdf.py` pour un exemple complet :

```python
"""Load DDI into RDF graph and perform SPARQL queries."""

from pathlib import Path
from rdflib import Graph, Namespace, Literal, URIRef
from rdflib.namespace import RDF, RDFS, SKOS, XSD

from ddigraph.ingest.fragment_loader import DDIFragmentParser

DDI = Namespace("http://ddialliance.org/Specification/DDI-Lifecycle/3.3/")
DATA = Namespace("http://example.org/data/")


def load_ddi_to_rdf(ddi_path: str) -> Graph:
    """Parse DDI-L file and create RDF graph."""
    g = Graph()
    g.bind("ddi", DDI)
    g.bind("data", DATA)
    g.bind("skos", SKOS)

    parser = DDIFragmentParser()

    for fragment in parser.parse(ddi_path):
        subj = DATA[fragment.fragment_id]

        # Node type
        g.add((subj, RDF.type, DDI[fragment.element_type]))

        # Properties
        if fragment.label:
            g.add((subj, RDFS.label, Literal(fragment.label)))
        if fragment.urn:
            g.add((subj, DDI.urn, Literal(fragment.urn)))

        # Special handling for QuestionItems
        if fragment.element_type == "QuestionItem":
            props = fragment.to_dict()
            if props.get("question_text"):
                g.add((subj, DDI.questionText, Literal(props["question_text"])))

        # Categories as SKOS concepts
        if fragment.element_type == "Category":
            g.add((subj, RDF.type, SKOS.Concept))
            props = fragment.to_dict()
            if props.get("category_label"):
                g.add((subj, SKOS.prefLabel, Literal(props["category_label"])))

        # Relationships
        for rel_type, ref in fragment.references:
            obj = DATA[ref.id]
            g.add((subj, DDI[rel_type], obj))

    return g


def main():
    ddi_file = "data/Ireland_LabourSurvey.xml"

    g = load_ddi_to_rdf(ddi_file)
    print(f"Created {len(g)} triples")

    # Export
    g.serialize("output.ttl", format="turtle")

    # Query
    query = """
    PREFIX ddi: <http://ddialliance.org/Specification/DDI-Lifecycle/3.3/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT ?item ?label ?text
    WHERE {
        ?item a ddi:QuestionItem .
        OPTIONAL { ?item rdfs:label ?label }
        OPTIONAL { ?item ddi:questionText ?text }
    }
    LIMIT 10
    """

    for row in g.query(query):
        print(f"{row.label}: {row.text}")


if __name__ == "__main__":
    main()
```

## Requêtes SPARQL

### Requêtes locales

```python
# Comptage par type
query = """
SELECT ?type (COUNT(?s) AS ?count)
WHERE { ?s a ?type }
GROUP BY ?type
ORDER BY DESC(?count)
"""

for row in g.query(query):
    print(f"{row.type}: {row.count}")
```

### Trouver les questions avec des listes de codes

```sparql
PREFIX ddi: <http://ddialliance.org/Specification/DDI-Lifecycle/3.3/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?question ?questionText ?codeList
WHERE {
    ?question a ddi:QuestionItem ;
              ddi:questionText ?questionText ;
              ddi:USES_CODELIST ?codeList .
}
```

### Traverser le flux de contrôle

```sparql
PREFIX ddi: <http://ddialliance.org/Specification/DDI-Lifecycle/3.3/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?instrument ?construct ?constructType
WHERE {
    ?instrument a ddi:Instrument ;
                ddi:HAS_CONSTRUCT+ ?construct .
    ?construct a ?constructType .
}
```

## Points d'accès SPARQL distants

### Chargement dans un triplestore

```python
from SPARQLWrapper import SPARQLWrapper

# Exemple avec Virtuoso
sparql = SPARQLWrapper("http://localhost:8890/sparql")
sparql.setMethod("POST")

# Insérer les données
insert_query = """
INSERT DATA {
    GRAPH <http://example.org/ddi/> {
        %s
    }
}
""" % g.serialize(format="nt")

sparql.setQuery(insert_query)
sparql.query()
```

### Interroger des points d'accès distants

```python
from SPARQLWrapper import SPARQLWrapper, JSON

sparql = SPARQLWrapper("http://localhost:8890/sparql")
sparql.setReturnFormat(JSON)

sparql.setQuery("""
    SELECT ?s ?p ?o
    FROM <http://example.org/ddi/>
    WHERE { ?s ?p ?o }
    LIMIT 100
""")

results = sparql.query().convert()
for result in results["results"]["bindings"]:
    print(result)
```

## Vocabulaire DDI-RDF

ddigraph utilise des types de relations sémantiques qui correspondent aux concepts DDI :

| Relation ddigraph | Propriété RDF | Description |
| ----------------- | ------------- | ----------- |
| `HAS_CONSTRUCT` | `ddi:hasConstruct` | La séquence contient un construct |
| `USES_CODELIST` | `ddi:usesCodeList` | La question utilise une liste de codes |
| `HAS_CATEGORY` | `ddi:hasCategory` | La CodeList contient une catégorie |
| `ASKS_QUESTION` | `ddi:asksQuestion` | Le construct référence une question |
| `USES_CONCEPT` | `ddi:usesConcept` | L'entité référence un concept |

## Intégration avec le Linked Data

### Liaison avec des vocabulaires externes

```python
from rdflib import OWL

# Lier les catégories à des vocabulaires externes
g.add((DATA["category-1"], OWL.sameAs, URIRef("http://eurovoc.europa.eu/123")))

# Utiliser des ontologies standards
g.add((DATA["variable-1"], DCTERMS.subject, URIRef("http://dbpedia.org/resource/Employment")))
```

### Publication en tant que Linked Data

```python
# Ajouter une description de jeu de données VoID
VOID = Namespace("http://rdfs.org/ns/void#")

dataset = DATA["dataset"]
g.add((dataset, RDF.type, VOID.Dataset))
g.add((dataset, DCTERMS.title, Literal("DDI Survey Metadata")))
g.add((dataset, VOID.sparqlEndpoint, URIRef("http://example.org/sparql")))
```

## Voir aussi

- [Architecture des adaptateurs](../user-guide/adapter.md) - Construction d'adaptateurs personnalisés
- [Modèle de relations](../user-guide/relationships.md) - Types de relations DDI
- [Vocabulaire DDI-RDF](https://ddi-alliance.atlassian.net/wiki/spaces/DDI4/pages/932085774/RDF) - Spécification officielle DDI-RDF
