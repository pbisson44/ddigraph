# Leçon 8 — Laisser le modèle interroger le graphe

!!! abstract "Ce que vous allez apprendre"
    - Donner un outil à un modèle plutôt qu'un mur de contexte
    - Écrire un outil qui répond à une vraie question DDI
    - Savoir laquelle des deux approches convient à votre problème

## La limite du contexte entassé

La leçon 7 a mis des faits dans l'invite. Cela fonctionne, et cela cesse de
fonctionner toujours pour la même raison : il faut décider quoi inclure
*avant* de savoir ce qui sera demandé.

Récupérez trop peu et la réponse n'y est pas. Récupérez trop et vous le
payez à chaque requête. Et certaines questions demandent un parcours que
vous ne pouvez pas anticiper : « quelles variables proviennent de questions
utilisant cette liste de codes ? » fait trois sauts, et aucune recherche par
mot-clé ne la trouve.

L'alternative est d'arrêter de deviner. Donnez un outil au modèle et
laissez-le demander.

## Un outil, c'est une fonction plus une description

Un outil a trois parties : un nom, une description qui dit au modèle quand
l'appeler, et un schéma pour ses entrées.

La description est la partie dans laquelle on investit trop peu. C'est par
elle que le modèle décide si l'outil est pertinent : elle doit donc dire
*quand l'appeler*, pas seulement ce qu'il fait.

<!-- runnable -->
```python
ANSWER_OPTIONS_TOOL = {
    "name": "get_answer_options",
    "description": (
        "Return the answer options a respondent could choose for a survey "
        "question. Call this whenever the user asks what someone could answer, "
        "what a variable's values mean, or which categories a question uses. "
        "Matches on question text, case-insensitively."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "The question text, or any distinctive part of it.",
            }
        },
        "required": ["question"],
    },
}

print(ANSWER_OPTIONS_TOOL["name"], "->", sorted(ANSWER_OPTIONS_TOOL["input_schema"]["properties"]))
```

La description est rédigée en anglais : c'est la langue de l'invite et
celle des données du graphe.

## L'implémenter sur le graphe

Vient la fonction. C'est le parcours de la leçon 3, enveloppé pour prendre
une question et renvoyer des options :

<!-- runnable -->
```python
import json
import os

from ddigraph import iter_graph


def node_key(node):
    return "|".join(f"{k}={v}" for k, v in sorted(node.identity.items()))


nodes, edges = {}, []
for chunk in iter_graph(os.environ["FIXTURE"]):
    for node in chunk.nodes:
        nodes[node_key(node)] = node
    for edge in chunk.relationships:
        edges.append((node_key(edge.start), edge.type, node_key(edge.end)))


def follow(start, rel_type):
    """Tous les nœuds atteignables depuis `start` par un arc `rel_type`."""
    return [end for s, t, end in edges if s == start and t == rel_type]


def get_answer_options(question: str) -> dict:
    """L'implémentation de l'outil. Sa valeur de retour repart vers le modèle."""
    for key, node in nodes.items():
        if node.label != "QuestionItem":
            continue
        text = node.properties.get("question_text", "")
        if question.lower() not in text.lower():
            continue

        options = []
        for code_list in follow(key, "USES_CODELIST"):
            for category in follow(code_list, "HAS_CATEGORY"):
                found = nodes[category]
                options.append(found.properties.get("label"))
        return {"question": text, "options": options}

    return {"error": f"No question matching {question!r}"}


print(json.dumps(get_answer_options("age"), indent=2))
print(json.dumps(get_answer_options("income"), indent=2))
```

```text
{
  "question": "What is your age?",
  "options": [
    "Under 18"
  ]
}
{
  "error": "No question matching 'income'"
}
```

Ce second appel compte autant que le premier. **Renvoyez une erreur claire,
pas un résultat vide.** `{"options": []}` se lit, pour un modèle, comme
« cette question n'a pas d'options de réponse » — ce qui est faux, et ce
qu'il rapportera comme un fait. `error` lui dit que la recherche a échoué,
et il le dira.

## Le câblage

L'appel d'API. Non exécuté par la suite de tests : il demande une clé.

```python
import anthropic

client = anthropic.Anthropic()

messages = [{"role": "user", "content": "What could someone answer for the age question?"}]

response = client.messages.create(
    model="claude-opus-5",
    max_tokens=1024,
    tools=[ANSWER_OPTIONS_TOOL],
    messages=messages,
)

if response.stop_reason == "tool_use":
    tool_call = next(block for block in response.content if block.type == "tool_use")
    result = get_answer_options(**tool_call.input)

    messages.append({"role": "assistant", "content": response.content})
    messages.append(
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_call.id,
                    "content": json.dumps(result),
                }
            ],
        }
    )

    response = client.messages.create(
        model="claude-opus-5",
        max_tokens=1024,
        tools=[ANSWER_OPTIONS_TOOL],
        messages=messages,
    )

for block in response.content:
    if block.type == "text":
        print(block.text)
```

Les noms de modèles changent. La
[liste des modèles](https://docs.claude.com/en/docs/about-claude/models)
donne ceux en cours.

Trois choses faciles à rater :

**Ajoutez tout le `response.content`**, pas seulement le texte. Il contient
le bloc `tool_use`, et la requête suivante en a besoin pour rattacher votre
résultat à l'appel.

**`tool_use_id` doit correspondre.** C'est ainsi que l'API apparie un
résultat à son appel, et ce n'est pas facultatif.

**Un tour n'est pas la boucle.** Un modèle peut appeler un outil, lire le
résultat et en appeler un autre. Du vrai code boucle jusqu'à ce que
`stop_reason` ne soit plus `tool_use`. Le SDK Anthropic fournit un *tool
runner* qui s'en charge.

## Laquelle choisir

| | Dossier d'ancrage (leçon 7) | Outils (cette leçon) |
| --- | --- | --- |
| Taille du graphe | Petite, ou réduite après filtrage | Quelconque |
| Forme des questions | Connue à l'avance | Ouverte |
| Allers-retours | Un | Deux ou plus |
| Échoue par | Omission de ce qu'il fallait | Appel du mauvais outil |

Les deux se combinent bien. Un petit dossier oriente le modèle — ce qu'est
cette enquête, quels types existent — et les outils lui permettent d'aller
chercher les détails. Le dossier devient bon marché parce qu'il n'a plus à
être complet.

## Exercice

Écrivez un second outil, `find_questions_about(concept)`, qui renvoie les
questions liées à un concept. Puis décidez : outil séparé, ou paramètre
supplémentaire du premier ?

??? success "Solution"
    ```python
    CONCEPT_TOOL = {
        "name": "find_questions_about",
        "description": (
            "Find survey questions that measure a given concept. Call this when "
            "the user asks which questions cover a topic or concept."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"concept": {"type": "string", "description": "The concept name."}},
            "required": ["concept"],
        },
    }
    ```

    Gardez-le séparé. Deux outils aux frontières nettes valent mieux qu'un
    outil à drapeau de mode, car le modèle choisit en lisant les
    descriptions — et « renvoie des options de réponse *ou* des questions,
    selon l'argument passé » ne décrit rien correctement.

    Le signe que vous êtes allé trop loin dans l'autre sens est un jeu
    d'outils où plusieurs descriptions pourraient plausiblement
    correspondre à la même demande. Le modèle devine alors, et la
    correction est de les fusionner ou d'affûter la frontière dans les
    descriptions.

## Vérifiez-vous

- Pourquoi la description est-elle la partie la plus importante d'un outil ?
- Pourquoi renvoyer une erreur plutôt qu'une liste vide ?
- Quand un dossier d'ancrage vaut-il mieux qu'un outil ?

---

C'est la fin du cours. L'[étude de cas RDF](../advanced/rdf-case-study.md)
l'applique de bout en bout, et
[Préparation pour l'IA](../advanced/ai-readiness.md) va plus loin dans le
filtrage et les schémas agentiques sur un graphe chargé.
