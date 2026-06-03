# DSL de composition Codebook — conception

Cette page est la référence de conception pour la refonte de la
composition Codebook :
regrouper les gestionnaires DDI-Codebook écrits à la main dans
`src/ddigraph/ingest/loader.py` derrière un extracteur déclaratif,
piloté par un fichier de surcharges. Lisez-la avant la mise en place
du runtime ; les choix de syntaxe présentés ici sont la partie qui
mérite une relecture.

## Pourquoi

`loader.py` fait environ 4 300 lignes. Environ 40 de ses ~44 méthodes
`ingest_*` sont quasi identiques : résoudre un identifiant, le
dédupliquer, extraire quelques champs d'éléments enfants, construire
un enregistrement, l'ajouter. Cette répétition représente l'essentiel
du fichier. Des refontes antérieures ont déjà déplacé chaque *nom*
de nœud et de relation vers le générateur dérivé du XSD plus
`schema_overrides.toml` ; cette refonte fait de même pour la *recette
d'extraction*, afin que les XSD (plus une petite surcharge
déclarative) deviennent l'unique source de vérité sur ce que chaque
élément du codebook apporte au graphe.

## Portée honnête

Tous les gestionnaires ne peuvent pas — et ne devraient pas —
devenir déclaratifs.

- **~33 gestionnaires plats** (`ingest_organization`, `ingest_series`,
  `ingest_group`, `ingest_methodology`, `ingest_software`,
  `ingest_funding`, `ingest_coverage`, …) ne font que id + dédup +
  extraction de champs superficiels + ajout. Ceux-ci se réduisent
  entièrement au DSL. C'est là que se trouve le gain en nombre de
  lignes.
- **~7 gestionnaires récursifs** — `ingest_variable` (115 lignes),
  `ingest_contributor_role` (94), `ingest_question_item` (65),
  `ingest_question` (55), `ingest_study` (48), plus
  `ingest_var_group` et `ingest_category_group` — créent des
  enregistrements *enfants* à partir d'éléments imbriqués (une `var`
  engendre des enregistrements `Question`, `Universe`, `Category` et
  `Concept`, chacun avec son propre ensemble de déduplication et la
  sémantique « lever une erreur sur variable en double »). Forcer
  cette récursion dans du TOML produirait un langage de configuration
  plus complexe que le Python qu'il remplace, ce qui irait à
  l'encontre de l'objectif de simplicité. **Ceux-ci restent en Python**, mais réécrits
  pour appeler les mêmes primitives de sélection partagées qu'utilise
  le runtime du DSL, afin que la logique d'extraction soit définie une
  seule fois.

Effet net : `loader.py` passe d'environ 4 300 à environ 1 400–1 700
lignes (pas l'estimation initiale de ~900). La masse restante est
constituée des sept gestionnaires récursifs exprimés en Python court,
composé de primitives, plus la colle de répartition. Le chiffre de
~900 supposait que les gestionnaires récursifs pouvaient être
entièrement déclaratifs ; cette conception échange consciemment cela
contre la lisibilité.

## Primitives de sélection

Un seul module, `src/ddigraph/ingest/_compose.py`, expose des
fonctions pures qui prennent un élément `lxml` et renvoient un
scalaire / une liste / un sous-élément. Elles remplacent les
fonctions auxiliaires ad hoc dispersées dans `loader.py`
(`_first_text`, `_first_text_any`, `_common_metadata`,
`_textual_metadata`, `_reference_values_by_suffix`, …). Chacune est
testée individuellement par des tests unitaires sur des fixtures
synthétiques.

| Primitive | Signature | Remplace |
|---|---|---|
| `text` | `text(elem, path) -> str \| None` | `_first_text(elem, path)` |
| `text_any` | `text_any(elem, *paths) -> str \| None` | `_first_text_any` |
| `nested_text` | `nested_text(elem, *path) -> str \| None` | `get_nested_text` (utils.parsing) |
| `attr` | `attr(elem, child, name) -> str \| None` | motifs `location.get("fileid")` |
| `count` | `count(elem, child_tag) -> int` | `len(findall())` manuel |
| `metadata` | `metadata(elem) -> dict[str, str \| None]` | `_common_metadata` (agency/version/urn) |
| `textual` | `textual(elem) -> dict[str, str \| None]` | `_textual_metadata` (name/label/description/rationale/language) |
| `refs_by_suffix` | `refs_by_suffix(elem, suffix) -> list[str]` | `_reference_values_by_suffix` |
| `lookup` | `lookup(elem, table, child_tag) -> str \| None` | `RESPONSE_DOMAIN_TYPES.get(...)` |
| `truncate` | `truncate(value, n) -> str \| None` | `text[:n]` |
| `coerce` | `coerce(value, xsd_type) -> object` | analyse de dates/entiers dispersée |

`coerce` est indexé par le type simple XSD que le générateur
enregistre déjà pour chaque propriété (le générateur l'émet dans
`src/ddigraph/schema/_generated/codebook.py`). Il réside dans un
module voisin `src/ddigraph/ingest/_coerce.py` afin d'être testable
indépendamment.

Toutes les primitives sont privées (modules `_compose`, `_coerce`) —
elles n'élargissent pas la surface publique, donc
`tests/test_public_api.py` reste vert.

## Registre de gestionnaires plats — Python typé, pas un DSL textuel

**Révision de conception (consignée pendant l'implémentation).** La
première version de ce document spécifiait une grammaire
d'expressions textuelles dans `schema_overrides.toml`
(`name = "text('name')"`). L'examen des gestionnaires plats réels
(`ingest_file`, `ingest_series`, `ingest_group`,
`ingest_data_collection_event`, …) a montré que la grammaire devrait
gérer des chaînes `or` (`text('.//fileURI') or attr('URI')`), des
alias de champs (`label = name`), le passage de paramètres
`metadata(label=...)`, et l'idiome *textual avec remplacement de
label* (`t = textual(elem); if t['label'] is None: t['label'] =
<expr>`). Un mini-langage textuel qui gère tout cela cesse d'être
« minuscule » et devient un interpréteur — ce qui contredit
l'objectif de simplicité et est précisément le genre de machinerie
sur mesure que ce travail vise à supprimer.

À la place, chaque gestionnaire plat est une entrée
`CompositionSpec` dans un **registre Python typé** situé dans
`src/ddigraph/ingest/_composition_specs.py`. C'est tout aussi
déclaratif (un seul endroit, piloté par les données, aucun flux de
contrôle par gestionnaire), mais c'est vérifié par mypy, ne nécessite
aucun analyseur syntaxique, et compose directement les primitives
`_compose` sous forme d'appelables. Le TOML de surcharge reste le
foyer des métadonnées de *nœud/relation* (gérées par les refontes
de génération de schéma antérieures) ; la recette d'extraction,
ayant la forme de code, vit dans le code.

```python
from ddigraph.ingest import _compose as c
from ddigraph.ingest._composition_specs import CompositionSpec, Field

SPECS = {
    "filedscr": CompositionSpec(
        collection="data_files",
        record="DataFileRecord",        # resolved by name against loader
        id_field="file_id",
        # No slug -> if the element has no id, skip it (matches the
        # current ``if not file_id ... return``). A slug enables the
        # ``<dataset>:<slug>_<counter>`` synthesised fallback instead.
        id_slug=None,
        dedup="seen_files",
        fields=(
            Field("name", lambda e: c.text(e, ".//fileName")),
            Field("uri", lambda e: c.text(e, ".//fileURI") or c.attr(e, "URI")),
            Field("label", alias="name"),          # reuse another field's value
        ),
        splat_metadata=True,                       # **_common_metadata(elem)
    ),
}
```

`Field` est l'un des suivants : un appelable `select=`
`(elem) -> value`, une référence `alias=` vers un autre champ déjà
calculé dans la même spécification, ou une littérale `const=`. Les
booléens `splat_metadata` / `splat_textual` couvrent les idiomes
`**_common_metadata` / `**_textual_metadata` ;
`textual_label_fallback=<Field>` couvre l'idiome de remplacement en
un seul emplacement déclaratif. Voilà toute la surface — aucune
condition, aucune boucle, aucune récursion. Tout ce qui dépasse cela
est un gestionnaire récursif et reste en Python (section suivante).

Le marcheur, `BatchBuilder._run_composition(tag, elem)` dans
`loader.py`, fait ~40 lignes : résoudre l'id (repli par slug ou
saut), réclamer la déduplication, évaluer les champs dans l'ordre
(pour qu'`alias` puisse voir les résultats précédents), étaler les
métadonnées/textual, construire l'enregistrement par son nom,
l'ajouter. Les ~33 corps de méthodes des gestionnaires plats se
réduisent à un unique appel `self._run_composition("<tag>", elem)`
(ou sont entièrement supprimés une fois que la table de répartition
route les balises plates directement vers le marcheur lors du
regroupement de la répartition).

Cela maintient le registre relisible, le runtime minuscule, et chaque
ligne vérifiée par mypy — et le test d'instantané prouve que la
sortie est identique octet par octet à celle des gestionnaires écrits
à la main.

## Gestionnaires récursifs (restent en Python, réutilisent les primitives)

`ingest_variable` après la migration est représentatif — il passe de
115 lignes à ~40 en déléguant toute extraction à une primitive et
chaque sous-enregistrement à une petite fonction auxiliaire typée,
tout en gardant le flux de contrôle explicite (et le contrat « lever
une erreur sur ID de variable en double ») en Python, là où un
lecteur peut le voir :

```python
def ingest_variable(self, elem: etree._Element) -> None:
    variable_id = self._resolve_id(elem, slug="var")
    if not self._claim_id(self.seen_variable_ids, variable_id, strict=True):
        raise ValueError(f"Duplicate variable ID {variable_id!r}")

    self._spawn_question(elem.find("qstn"), parent_id=variable_id)
    universe_id = self._spawn_universe(elem.find("universe"), parent_id=variable_id)
    self._spawn_categories(elem.findall("catgry"))
    self._spawn_concept(elem.find("concept"))

    self._append_and_count(
        self.variables,
        VariableRecord(
            dataset_id=self.dataset_id,
            dataset_name=self.dataset_name,
            variable_id=variable_id,
            file_id=compose.attr(elem.find("location"), None, "fileid"),
            universe_id=universe_id,
            **compose.textual(elem),
            **compose.metadata(elem),
        ),
        "variables",
    )
```

Les fonctions auxiliaires `_spawn_*` sont le seul nouveau Python ;
chacune fait ~10 lignes et utilise elle-même les primitives.
`_claim_id` reçoit un paramètre optionnel `strict=True` pour
préserver l'exception de variable en double.

## Séquence de migration

Chaque commit maintient au vert la barrière de qualité par commit
(ruff format/check, mypy, `generate_schema_definitions --check`,
`xsd_coverage --structural --structural-threshold 100`, pytest complet
incluant le nouveau test d'instantané) et garde le test d'instantané
identique octet par octet.

1. **`_compose.py` + tests unitaires** — primitives uniquement,
   aucun changement de loader. Instantané inchangé. (`_coerce.py`
   reporté jusqu'à ce que le générateur émette les types simples XSD
   par propriété.)
2. **Registre `_composition_specs.py` + marcheur `_run_composition`** —
   ajouter les entrées `CompositionSpec` pour les gestionnaires plats
   (par lots, en validant d'abord le marcheur sur un sous-ensemble
   représentatif) et le marcheur `_run_composition(tag, elem)`.
   Remplacer le corps de ces gestionnaires par un unique appel au
   marcheur. L'instantané doit rester identique octet par octet à
   chaque commit.
3. **Réécritures des gestionnaires récursifs** — un commit par
   gestionnaire (`ingest_variable`, `ingest_study`,
   `ingest_question_item`, `ingest_question`,
   `ingest_contributor_role`, `ingest_var_group`,
   `ingest_category_group`), chacun réécrivant le corps sous forme
   primitive + `_spawn_*`. Instantané identique octet par octet par
   commit.
4. **Regroupement de la répartition** — la table `_build_handlers`
   à `loader.py:1836` devient `tag -> _run_composition` pour les
   balises plates ; seules les sept balises récursives conservent des
   entrées de méthode explicites.
5. **CHANGELOG** sous `## [0.4.0]`.

## Vérification

Le harnais d'instantané dans
`tests/test_codebook_loader_snapshot.py` (déjà commité) capture
chaque lot que le loader produit pour
`tests/fixtures/codebook_sample.xml`. C'est la barrière d'égalité
octet par octet pour chaque commit du registre et du regroupement
de la répartition. Les changements
de schéma intentionnels régénèrent l'instantané via `REGEN=1 pytest
tests/test_codebook_loader_snapshot.py`, le diff JSON étant relu dans
le même commit. `test_snapshot_covers_the_bespoke_handlers` garde la
fixture pertinente (elle doit continuer à produire des variables, des
études, des questions, des question_items, des organisations, des
data_files).
