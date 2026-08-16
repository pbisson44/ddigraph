# Leçon 1 — Les métadonnées sont déjà un graphe

!!! abstract "Ce que vous allez apprendre"
    - Ce qu'est DDI et quel problème il résout
    - Pourquoi les métadonnées d'enquête tiennent mieux dans un graphe
    - Ce que sont les trois variantes DDI et pourquoi il y en a trois

## Le problème que DDI résout

Une enquête produit deux choses. Les données — des lignes de réponses. Et
tout ce qu'il faut pour donner un sens à ces lignes : ce qui a été demandé,
à qui, dans quel ordre, ce que signifient les codes, qui a mené l'enquête,
comment elle a été pondérée.

Cette seconde partie, ce sont les métadonnées. Perdez-les et les données ne
sont plus qu'un tableur de chiffres illisible. Une colonne nommée `Q4A`
contenant la valeur `3` ne dit rien en soi.

DDI (Data Documentation Initiative) est une norme pour écrire ces
métadonnées. C'est du XML, maintenu par une alliance internationale
d'archives de données, et c'est ce qu'utilisent la plupart des archives en
sciences sociales.

## Pourquoi un graphe

Regardez ce que disent réellement les métadonnées :

- Une **question** utilise une **liste de codes**
- Une **liste de codes** contient des **catégories**
- Une **question** porte sur un **concept**
- Une **question** s'applique à un **univers** — les personnes interrogées
- Une **variable** provient d'une **question**
- Une **séquence** contient des **questions**, et les séquences s'imbriquent

Chacune de ces phrases est un lien entre deux choses. C'est cela, un
graphe : des choses et les liens entre elles.

Vous pouvez ranger cela dans des tables. Certains le font. Mais les
questions que l'on veut vraiment poser sont des questions de chemins :

> Quelles variables remontent à des questions utilisant cette liste de codes ?

En SQL, c'est une chaîne de jointures dont la longueur dépend de la
profondeur d'imbrication — et il faut connaître cette profondeur à
l'avance. Dans une base graphe, c'est un seul motif :

```cypher
MATCH (v:Variable)-[*]->(c:CodeList {fragment_id: 'cl-employment'})
RETURN v.name
```

Le `*` signifie « autant de sauts qu'il faudra ». C'est là toute la
différence. Ce n'est pas que les graphes sont plus rapides : c'est que la
question devient exprimable.

!!! note "Quand une table est la bonne réponse"
    Si vous demandez seulement « donne-moi toutes les variables de cette
    étude », une table est plus simple et vous devriez l'utiliser. Les
    graphes gagnent leur place quand les questions intéressantes portent
    sur les *connexions* — et dans les métadonnées d'enquête, c'est
    généralement le cas.

## Trois variantes, une norme

DDI existe sous trois formes. Vous les rencontrerez toutes.

| Variante | Ce que c'est | Élément racine |
| ---------- | -------------- | ---------------- |
| **Codebook** (DDI-C 2.x) | L'ancienne, la plus simple. Tout dépend d'une seule étude. | `<codeBook>` |
| **Lifecycle** (DDI-L 3.x) | Métadonnées découpées en *fragments* réutilisables qui se référencent. | `<FragmentInstance>` |
| **CDI** (DDI-CDI 1.0) | La plus récente. Décrit des données inter-domaines, pas seulement des enquêtes. | Espace de noms CDI |

Il y en a trois parce qu'elles ont été conçues à des époques différentes
pour des usages différents, et que les archives détiennent des fichiers
dans les trois. Un outil qui n'en lit qu'une est un outil que vous
dépasserez.

Lifecycle est celle qui est *manifestement* un graphe : un fragment qui en
référence un autre est un arc, écrit comme un arc. Codebook et CDI
expriment la même idée par imbrication et par références.

## Voyons cela

Assez de théorie. Demandons au package quelle variante est un fichier :

<!-- runnable -->
```python
import os

import ddigraph

for name in ("FIXTURE", "CODEBOOK_FIXTURE", "CDI_FIXTURE"):
    path = os.environ[name]
    print(ddigraph.detect(path))
```

Cela affiche `lifecycle`, `codebook`, `cdi`. La détection lit l'élément XML
racine — aucune configuration, aucune supposition de votre part.

## Exercice

Ouvrez `tests/fixtures/fragment_instance.xml` dans un éditeur. Il est
court. Trouvez l'élément `<r:CodeListReference>` dans la question, et le
fragment `<l:CodeList>` qu'il désigne.

Qu'est-ce qui les relie ? Notez les informations qui font fonctionner le
lien.

??? success "Solution"
    La référence porte une **agence**, un **ID** et une **version**, et le
    fragment de liste de codes déclare les mêmes trois :

    ```xml
    <r:CodeListReference>
        <r:Agency>test.org</r:Agency>
        <r:ID>cl1</r:ID>
        <r:Version>1.0</r:Version>
        <r:TypeOfObject>CodeList</r:TypeOfObject>
    </r:CodeListReference>
    ```

    ```xml
    <l:CodeList id="cl1" agency="test.org" version="1.0">
    ```

    Agence plus ID plus version forment un **URN** —
    `urn:ddi:test.org:cl1:1.0` — unique au niveau mondial. C'est pourquoi
    les fragments DDI-L peuvent vivre dans des fichiers séparés et se
    relier quand même, et c'est l'identifiant que ddigraph utilise comme
    sujet lorsqu'il écrit du RDF. Vous le reverrez en leçon 4.

    `TypeOfObject` est le quatrième élément. Il dit quel type de chose est
    référencé, ce qui permet à un analyseur de savoir que l'arc est
    `USES_CODELIST` et non autre chose.

## Vérifiez-vous

- Pourquoi une question sur les *chemins* favorise-t-elle un graphe ?
- Quelle variante DDI stocke ses arcs explicitement, et pourquoi pas les autres ?
- Quelles informations rendent une référence DDI-L résoluble ?

---

Suivant : [Regarder avant de charger](02-first-look.md) — inspecter un
fichier jamais vu, sans rien installer.
