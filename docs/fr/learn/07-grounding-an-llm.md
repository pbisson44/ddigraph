# Leçon 7 — Ancrer un modèle dans le graphe

!!! abstract "Ce que vous allez apprendre"
    - Pourquoi un modèle de langage se trompe sur la structure d'une enquête
    - Construire un dossier d'ancrage à partir d'un fichier DDI
    - Ne récupérer que la partie du graphe dont une question a besoin

## Ce qu'un modèle ne sait pas

Demandez à un modèle de langage quelles réponses proposait une question
d'enquête : il vous donnera une liste plausible. Le plausible est
justement le problème. Il a lu quantité d'enquêtes, il sait donc à quoi
ressemble d'ordinaire une tranche d'âge — et c'est exactement pour cela
qu'il en produira une qui se lit correctement et qui n'est pas la vôtre.

Rien dans le modèle ne sait que *votre* instrument plaçait `Under 18` en
premier, ni qu'une question n'a été posée qu'à une partie des répondants.
Cela vit dans vos métadonnées.

Le travail n'est donc pas de rendre le modèle plus intelligent. Il est de
lui mettre les faits sous les yeux et de dire clairement que ce sont les
faits.

## Un dossier d'ancrage

La chose utile la plus simple est une description factuelle et compacte du
graphe, envoyée dans la requête à côté de la question. La leçon 3 vous a
déjà donné tout ce qu'il faut pour la construire :

<!-- runnable -->
```python
import os

from ddigraph import iter_graph


def node_key(node):
    return "|".join(f"{k}={v}" for k, v in sorted(node.identity.items()))


def name_of(node):
    return node.properties.get("label") or node.properties.get("name") or node_key(node)


nodes, edges = {}, []
for chunk in iter_graph(os.environ["FIXTURE"]):
    for node in chunk.nodes:
        nodes[node_key(node)] = node
    for edge in chunk.relationships:
        edges.append((node_key(edge.start), edge.type, node_key(edge.end)))

lines = ["The survey contains these items. Do not invent items that are not listed."]
for key, node in sorted(nodes.items(), key=lambda item: item[1].label):
    text = node.properties.get("question_text")
    lines.append(f"- {node.label}: {name_of(node)}" + (f' — asks "{text}"' if text else ""))

lines.append("")
lines.append("Links between them:")
for start, rel_type, end in edges:
    lines.append(f"- {name_of(nodes[start])} --{rel_type}--> {name_of(nodes[end])}")

pack = "\n".join(lines)
print(pack)
```

```text
The survey contains these items. Do not invent items that are not listed.
- Category: Under 18
- CodeList: Age Groups
- Instrument: Test Instrument
- QuestionConstruct: fragment_id=urn:ddi:test.org:qc1:1.0
- QuestionItem: Question 1 — asks "What is your age?"
- Sequence: Main Sequence

Links between them:
- Test Instrument --HAS_CONSTRUCT--> Main Sequence
- Main Sequence --HAS_CONSTRUCT--> fragment_id=urn:ddi:test.org:qc1:1.0
- fragment_id=urn:ddi:test.org:qc1:1.0 --REFERENCES_QUESTION--> Question 1
- Question 1 --USES_CODELIST--> Age Groups
- Age Groups --HAS_CATEGORY--> Under 18
```

Moins de 600 caractères, et cela répond à des questions que le modèle
devinerait autrement. Notez que les liens sont inclus, pas seulement les
éléments : « quelle liste de codes utilise la question sur l'âge ? » est
une question sur un arc.

Le dossier est rédigé en anglais parce que c'est la langue des données :
inutile de traduire des libellés que le modèle devra relier à des chaînes
anglaises.

## L'utiliser

Placez le dossier dans l'invite système et posez la question normalement.
Cet exemple n'est pas exécuté par la suite de tests : il demande une clé
d'API.

```python
import anthropic

client = anthropic.Anthropic()

response = client.messages.create(
    model="claude-opus-5",
    max_tokens=1024,
    system=(
        "Answer questions about this survey using only the structure below. "
        "If the answer is not there, say so rather than guessing.\n\n" + pack
    ),
    messages=[{"role": "user", "content": "What could a respondent answer for age?"}],
)

for block in response.content:
    if block.type == "text":
        print(block.text)
```

Les noms de modèles changent. La
[liste des modèles](https://docs.claude.com/en/docs/about-claude/models)
donne ceux en cours.

Deux détails sont faciles à rater.

**`response.content` est une liste de blocs, pas une chaîne.** Vérifiez
`block.type` avant de lire `block.text` : une réponse peut contenir
d'autres types de blocs, et indexer `content[0].text` casse la première
fois que cela arrive.

**Dites-lui quoi faire quand la réponse est absente.** Sans cette phrase,
un modèle interrogé sur ce que le dossier ne couvre pas produira souvent
une réponse d'apparence raisonnable. Avec elle, vous obtenez « les
métadonnées ne le disent pas », qui est la réponse que vous vouliez.

## Quand le graphe est trop gros

Six nœuds tiennent dans une invite. Soixante mille, non — et les y entasser
serait un gaspillage même si c'était possible : l'essentiel du graphe est
hors sujet pour une question donnée.

Filtrez donc d'abord. Nul besoin d'une base vectorielle pour commencer :
chercher dans le texte déjà présent dans le graphe mène assez loin.

<!-- runnable -->
```python
import os

from ddigraph import iter_graph


def relevant(path, question, limit=5):
    """Renvoie les nœuds dont le texte recoupe la question."""
    words = {word.lower().strip("?.,") for word in question.split() if len(word) > 3}
    hits = []

    for chunk in iter_graph(path):
        for node in chunk.nodes:
            haystack = " ".join(
                str(value) for value in node.properties.values() if isinstance(value, str)
            ).lower()
            score = sum(1 for word in words if word in haystack)
            if score:
                hits.append((score, node))

    hits.sort(key=lambda item: -item[0])
    return [node for _score, node in hits[:limit]]


for node in relevant(os.environ["FIXTURE"], "What are the age groups?"):
    print(node.label, "-", node.properties.get("label"))
```

```text
QuestionItem - Question 1
CodeList - Age Groups
```

Deux nœuds au lieu de six. Sur un fichier réel, c'est deux cents au lieu de
soixante mille, et c'est ce qui rend la requête abordable.

Les deux résultats obtiennent ici le score 1 — `Question 1` correspond à
« what », `Age Groups` à « groups » — et le tri de Python est stable : une
égalité conserve donc l'ordre d'analyse. C'est acceptable pour une première
passe, et c'est aussi la première chose à améliorer : donnez plus de poids
à une correspondance dans `question_text` qu'à une correspondance dans un
champ interne, et le classement se met à vouloir dire quelque chose.

!!! tip "Récupérez aussi les voisins"
    Un nœud seul n'est qu'une demi-réponse. Une fois vos correspondances
    obtenues, suivez leurs arcs sur un saut et incluez ce que vous trouvez :
    la `CodeList` ci-dessus n'est utile qu'avec ses catégories. La leçon 8
    fait exactement cela, et confie le travail au modèle plutôt que de le
    deviner à l'avance.

## Exercice

Le dossier ci-dessus utilise `label` comme nom d'un nœud et retombe sur sa
clé d'identité. Regardez la ligne `QuestionConstruct` dans la sortie.
Pourquoi est-elle laide, et qu'en feriez-vous ?

??? success "Solution"
    `QuestionConstruct` n'a ni propriété `label` ni `name` : `name_of`
    retombe donc sur la clé d'identité et affiche un URN. C'est du bruit :
    le construct est un élément de câblage du déroulé du questionnaire, et
    le modèle n'a pas besoin de son nom.

    Deux corrections raisonnables. Lui donner un meilleur repli —
    `Question 1` est à un saut de là via `REFERENCES_QUESTION`. Ou exclure
    complètement les types de nœuds structurels du dossier et replier la
    chaîne, pour que `Instrument → Sequence → Question 1` remplace quatre
    lignes par une.

    La seconde est en général meilleure. Chaque ligne du dossier coûte de
    l'argent à chaque requête, et un nœud sur lequel le lecteur ne pose
    jamais de question est une ligne qui ne le rentabilise jamais.

## Vérifiez-vous

- Pourquoi une réponse plausible d'un modèle non ancré aggrave-t-elle les choses ?
- Pourquoi inclure les arcs et pas seulement les nœuds ?
- Qu'est-ce qui casse si vous lisez `response.content[0].text` directement ?

---

Suivant : [Des outils sur le graphe](08-tools-over-the-graph.md) — lui
donner un outil plutôt qu'un mur de texte.
