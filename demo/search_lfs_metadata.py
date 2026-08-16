#!/usr/bin/env python3
"""Standalone metadata search and discovery for Ireland LFS 2020.

Reads LFS.xml + Ireland_LabourSurvey.xml offline (no Neo4j, no sdmx1).
Demonstrates four NSO metadata-discovery patterns:

  1. Free-text search   — tf-idf-style scoring across name, label, question text
  2. Concept discovery  — keyword-group theming (employment, education, …)
  3. Cross-quarter diff — variables added/removed between any two quarters
  4. Codelist reuse     — most-shared controlled vocabularies ranked by coverage

Usage:
    python search_lfs_metadata.py                 # run all four showcases
    python search_lfs_metadata.py "seeking work"  # free-text search only

Requirements:
    lxml (already in project deps)
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lxml import etree

# ── DDI-L 3.3 namespaces ─────────────────────────────────────────────────────

_NS = {
    "r": "ddi:reusable:3_3",
    "lp": "ddi:logicalproduct:3_3",
    "pi": "ddi:physicalinstance:3_3",
    "dc": "ddi:datacollection:3_3",
    "inst": "ddi:instance:3_3",
}

# ── LFS concept theme vocabulary ─────────────────────────────────────────────

CONCEPT_THEMES: dict[str, list[str]] = {
    "employment": [
        "employ",
        "job",
        "work",
        "nace",
        "isco",
        "occupation",
        "sector",
        "industry",
        "self_empl",
        "selfempl",
    ],
    "unemployment": [
        "unemploy",
        "seekdur",
        "lookwork",
        "seek",
        "benefit",
        "activation",
        "ltur",
        "register",
    ],
    "hours_wages": ["hour", "hwusual", "hwactual", "earning", "pay", "salary", "wage", "overtime"],
    "education": ["educ", "school", "degree", "study", "training", "qualif", "hatlevel", "course"],
    "demographics": [
        "age",
        "sex",
        "gender",
        "marital",
        "citizen",
        "birth",
        "national",
        "country_b",
    ],
    "household": ["household", "hhseq", "hhsize", "family", "child", "dwell", "tenure", "hh"],
    "geography": ["region", "nuts", "urban", "rural", "area", "country", "county"],
    "contract": [
        "contract",
        "temp",
        "permanent",
        "fixed",
        "casual",
        "part_time",
        "parttime",
        "full_time",
    ],
}

# ── Stop-words for search tokenisation ───────────────────────────────────────

_STOP = frozenset(
    {
        "the",
        "a",
        "an",
        "is",
        "in",
        "of",
        "to",
        "and",
        "or",
        "for",
        "at",
        "by",
        "with",
        "from",
        "this",
        "that",
        "be",
        "are",
        "was",
        "were",
        "it",
    }
)


# ── Data classes ──────────────────────────────────────────────────────────────


@dataclass
class VarRecord:
    id: str
    name: str
    label: str
    rep_type: str  # "code" | "numeric" | "text"
    codelist_id: str | None
    question_ref_id: str | None
    question_text: str = ""
    quarters: list[str] = field(default_factory=list)


@dataclass
class CLRecord:
    id: str
    name: str
    n_codes: int


# ── XML helpers ───────────────────────────────────────────────────────────────


def _t(elem: etree._Element, path: str) -> str:
    found = elem.find(path, _NS)
    return (found.text or "").strip() if found is not None else ""


def _iter_fragments(path: Path) -> Iterator[tuple[str, etree._Element]]:
    tag_frag = "{ddi:instance:3_3}Fragment"
    for _, elem in etree.iterparse(str(path), events=("end",), recover=True):
        if elem.tag == tag_frag:
            kids = list(elem)
            if kids:
                yield etree.QName(kids[0]).localname, kids[0]
            elem.clear()


# ── Index builder ─────────────────────────────────────────────────────────────


class LFSMetadataIndex:
    """In-memory index built from both DDI-L source files."""

    def __init__(self, lfs_path: Path, survey_path: Path) -> None:
        self._vars: dict[str, VarRecord] = {}
        self._cls: dict[str, CLRecord] = {}
        self._dr_vars: dict[str, set[str]] = {}  # quarter → {var_name}
        self._quarters: list[str] = []

        questions: dict[str, str] = {}  # id → question_text
        dr_lookup: dict[str, str] = {}  # dr_id → quarter_label
        pi_to_dr: dict[str, str] = {}  # pi_id → dr_id

        # ── Pass 1: LFS.xml ─────────────────────────────────────────────────
        raw_vars: dict[str, dict[str, Any]] = {}  # var_id → attrs
        raw_drs: dict[str, dict[str, Any]] = {}  # dr_id  → attrs

        for local, elem in _iter_fragments(lfs_path):
            if local == "PhysicalInstance":
                pi_id = _t(elem, "r:ID")
                dr_id = _t(elem, "r:DataRelationshipReference/r:ID")
                pi_to_dr[pi_id] = dr_id

            elif local == "DataRelationship":
                dr_id = _t(elem, "r:ID")
                name = _t(elem, "lp:DataRelationshipName/r:String")
                quarter = _t(elem, "r:Label/r:Content") or name
                var_ids = [
                    e.text.strip()
                    for e in elem.findall(".//lp:VariableUsedReference/r:ID", _NS)
                    if e.text
                ]
                raw_drs[dr_id] = {"quarter": quarter, "var_ids": var_ids}
                dr_lookup[dr_id] = quarter

            elif local == "Variable":
                vid = _t(elem, "r:ID")
                name = _t(elem, "lp:VariableName/r:String")
                label = _t(elem, "r:Label/r:Content")
                q_ref = _t(elem, "r:QuestionReference/r:ID") or None

                rep_type, cl_id = "text", None
                rep = elem.find("lp:VariableRepresentation", _NS)
                if rep is not None:
                    if (cr := rep.find("r:CodeRepresentation", _NS)) is not None:
                        rep_type = "code"
                        cl_id = _t(cr, "r:CodeListReference/r:ID") or None
                    elif rep.find("r:NumericRepresentation", _NS) is not None:
                        rep_type = "numeric"

                raw_vars[vid] = {
                    "name": name,
                    "label": label,
                    "rep_type": rep_type,
                    "cl_id": cl_id,
                    "q_ref": q_ref,
                }

            elif local == "CodeList":
                cl_id = _t(elem, "r:ID")
                cl_name = _t(elem, "r:Label/r:Content") or _t(elem, "lp:CodeListName/r:String")
                n = sum(1 for _ in elem.findall("lp:Code", _NS))
                self._cls[cl_id] = CLRecord(id=cl_id, name=cl_name, n_codes=n)

        # Build quarter membership
        for _dr_id, dr_data in raw_drs.items():
            quarter = dr_data["quarter"]
            var_ids = dr_data["var_ids"]
            if quarter not in self._quarters:
                self._quarters.append(quarter)
            self._dr_vars[quarter] = set()
            for vid in var_ids:
                if vid in raw_vars:
                    self._dr_vars[quarter].add(raw_vars[vid]["name"])

        # Collect question IDs needed
        needed_q_ids = {d["q_ref"] for d in raw_vars.values() if d["q_ref"]}

        # ── Pass 2: Ireland_LabourSurvey.xml (filtered) ──────────────────────
        for local, elem in _iter_fragments(survey_path):
            if local == "QuestionItem":
                qid = _t(elem, "r:ID")
                if qid not in needed_q_ids:
                    continue
                text = _t(elem, "dc:QuestionText/dc:LiteralText/dc:Text")
                questions[qid] = text

            elif local == "CodeList":
                cl_id = _t(elem, "r:ID")
                cl_name = _t(elem, "r:Label/r:Content") or _t(elem, "lp:CodeListName/r:String")
                n = sum(1 for _ in elem.findall("lp:Code", _NS))
                if cl_id not in self._cls:
                    self._cls[cl_id] = CLRecord(id=cl_id, name=cl_name, n_codes=n)

        # ── Build VarRecord index (deduplicated by name) ──────────────────────
        seen: dict[str, VarRecord] = {}  # name → VarRecord
        for _dr_id, dr_data in raw_drs.items():
            quarter = dr_data["quarter"]
            for vid in dr_data["var_ids"]:
                if vid not in raw_vars:
                    continue
                d = raw_vars[vid]
                name = d["name"]
                if name in seen:
                    if quarter not in seen[name].quarters:
                        seen[name].quarters.append(quarter)
                else:
                    q_text = questions.get(d["q_ref"] or "", "")
                    rec = VarRecord(
                        id=vid,
                        name=name,
                        label=d["label"],
                        rep_type=d["rep_type"],
                        codelist_id=d["cl_id"],
                        question_ref_id=d["q_ref"],
                        question_text=q_text,
                        quarters=[quarter],
                    )
                    seen[name] = rec

        self._vars = {r.id: r for r in seen.values()}
        self._name_idx: dict[str, VarRecord] = seen  # name → VarRecord

    # ── 1. Free-text search ──────────────────────────────────────────────────

    def search(self, query: str, limit: int = 10) -> list[tuple[int, VarRecord]]:
        """Score each variable by token hits across name, label, question text."""
        tokens = {t for t in re.split(r"\W+", query.lower()) if t and t not in _STOP}
        results: list[tuple[int, VarRecord]] = []
        for rec in self._name_idx.values():
            score = 0
            name_low = rec.name.lower()
            label_low = rec.label.lower()
            q_low = rec.question_text.lower()
            for tok in tokens:
                score += 4 * (tok in name_low)
                score += 2 * (tok in label_low)
                score += 1 * (tok in q_low)
            if score > 0:
                results.append((score, rec))
        results.sort(key=lambda x: (-x[0], x[1].name))
        return results[:limit]

    # ── 2. Concept-theme discovery ───────────────────────────────────────────

    def concept_discovery(self, theme: str) -> list[VarRecord]:
        """Return variables matching a concept theme keyword group."""
        keywords = CONCEPT_THEMES.get(theme, [theme.lower()])
        hits: list[VarRecord] = []
        for rec in self._name_idx.values():
            combined = (rec.name + " " + rec.label + " " + rec.question_text).lower()
            if any(kw in combined for kw in keywords):
                hits.append(rec)
        return sorted(hits, key=lambda r: r.name)

    # ── 3. Cross-quarter diff ────────────────────────────────────────────────

    def quarter_diff(self, q1: str, q2: str) -> dict[str, set[str]]:
        """Return variable-name sets: only_in_q1, only_in_q2, in_both."""
        s1 = self._dr_vars.get(q1, set())
        s2 = self._dr_vars.get(q2, set())
        return {
            "only_in_q1": s1 - s2,
            "only_in_q2": s2 - s1,
            "in_both": s1 & s2,
        }

    # ── 4. Codelist reuse ranking ────────────────────────────────────────────

    def codelist_reuse_ranking(self, top_n: int = 15) -> list[tuple[CLRecord, list[str]]]:
        """Rank codelists by number of unique variables that reference them."""
        usage: dict[str, list[str]] = defaultdict(list)
        for rec in self._name_idx.values():
            if rec.codelist_id and rec.codelist_id in self._cls:
                usage[rec.codelist_id].append(rec.name)
        ranked = sorted(usage.items(), key=lambda x: -len(x[1]))
        return [(self._cls[cl_id], sorted(names)) for cl_id, names in ranked[:top_n]]

    @property
    def quarters(self) -> list[str]:
        return list(self._quarters)

    @property
    def n_vars(self) -> int:
        return len(self._name_idx)


# ── Display helpers ───────────────────────────────────────────────────────────


def _section(title: str) -> None:
    print()
    print("=" * 66)
    print(f"  {title}")
    print("=" * 66)


def _show_var(rec: VarRecord, score: int | None = None, indent: str = "  ") -> None:
    score_tag = f"[{score:2d}]  " if score is not None else "      "
    quarters = ",".join(q.split()[0] for q in rec.quarters)  # "Q1,Q2,…"
    print(f"{indent}{score_tag}{rec.name:<26} [{rec.rep_type:<7}] ({quarters})  {rec.label[:42]}")
    if rec.question_text:
        snippet = rec.question_text[:90].replace("\n", " ")
        print(f'{indent}         Q: "{snippet}…"')


# ── Showcase functions ────────────────────────────────────────────────────────


def showcase_free_text(idx: LFSMetadataIndex, query: str) -> None:
    _section(f'FREE-TEXT SEARCH  "{query}"')
    hits = idx.search(query, limit=12)
    if not hits:
        print(f"\n  (no results for '{query}')")
        return
    print(f"\n  {len(hits)} result(s)  — scored on name(x4), label(x2), question(x1)\n")
    for score, rec in hits:
        _show_var(rec, score=score)


def showcase_concept_discovery(idx: LFSMetadataIndex) -> None:
    _section("CONCEPT-THEME DISCOVERY")
    print(f"\n  Available themes: {', '.join(sorted(CONCEPT_THEMES))}\n")

    for theme in ("employment", "unemployment", "hours_wages", "education", "demographics"):
        hits = idx.concept_discovery(theme)
        names = ", ".join(r.name for r in hits[:6])
        suffix = f"  …+{len(hits) - 6}" if len(hits) > 6 else ""
        print(f"  {theme:<18} ({len(hits):3d} vars)   {names}{suffix}")

    # Drill into one theme
    theme = "unemployment"
    _section(f"CONCEPT DRILL-DOWN — {theme}")
    print()
    for rec in idx.concept_discovery(theme)[:10]:
        _show_var(rec)


def showcase_cross_quarter(idx: LFSMetadataIndex) -> None:
    quarters = sorted(idx.quarters)
    if len(quarters) < 2:
        return

    _section(f"CROSS-QUARTER DIFF  {quarters[0]}  vs  {quarters[-1]}")
    diff = idx.quarter_diff(quarters[0], quarters[-1])

    for key, label in [
        ("only_in_q1", f"Only in {quarters[0]}"),
        ("only_in_q2", f"Only in {quarters[-1]}"),
    ]:
        names = sorted(diff[key])
        if names:
            print(f"\n  {label} ({len(names)} variable{'s' if len(names) != 1 else ''}):")
            for n in names[:10]:
                print(f"    {n}")
            if len(names) > 10:
                print(f"    … +{len(names) - 10} more")
        else:
            print(f"\n  {label}: (none)")

    print(f"\n  Common to both : {len(diff['in_both'])} variables")

    # Stability across all quarters
    all_quarters = idx.quarters
    stable = {name for name, rec in idx._name_idx.items() if set(rec.quarters) >= set(all_quarters)}
    print(f"  Stable (all {len(all_quarters)} quarters) : {len(stable)} variables")

    if len(all_quarters) >= 3:
        print("\n  Quarter-by-quarter variable counts:")
        for q in sorted(all_quarters):
            n_vars = len(idx._dr_vars.get(q, set()))
            print(f"    {q:<20}  {n_vars:4d} variables")


def showcase_codelist_reuse(idx: LFSMetadataIndex) -> None:
    _section("CODELIST REUSE RANKING  (most-shared controlled vocabularies)")
    print(f"\n  {'Rank':<5} {'#Vars':>5}  {'#Codes':>6}  {'Codelist':<40}  Sample variables")
    print(f"  {'-' * 5} {'-' * 5}  {'-' * 6}  {'-' * 40}  {'-' * 30}")

    for rank, (cl, var_names) in enumerate(idx.codelist_reuse_ranking(top_n=15), 1):
        sample = ", ".join(var_names[:3])
        suffix = f" +{len(var_names) - 3}" if len(var_names) > 3 else ""
        print(
            f"  {rank:<5} {len(var_names):>5}  {cl.n_codes:>6}  "
            f"{cl.name[:40]:<40}  {sample}{suffix}"
        )

    # NSO insight: identify standardised YES/NO-type codelists
    binary_cls = [
        (cl, names) for cl, names in idx.codelist_reuse_ranking(top_n=50) if cl.n_codes <= 3
    ]
    if binary_cls:
        print("\n  Binary / ternary codelists (≤3 codes) — candidates for harmonisation:")
        for cl, names in binary_cls[:5]:
            print(f"    {cl.name[:50]:<50}  ({cl.n_codes} codes, {len(names)} vars)")


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    demo_dir = Path(__file__).parent
    lfs_path = demo_dir / "LFS.xml"
    survey_path = demo_dir / "Ireland_LabourSurvey.xml"

    for p in (lfs_path, survey_path):
        if not p.exists():
            print(f"Error: {p} not found")
            sys.exit(1)

    _section("LFS 2020 METADATA SEARCH & DISCOVERY")
    print(f"\n  Building index from {lfs_path.name} + {survey_path.name} …")
    idx = LFSMetadataIndex(lfs_path, survey_path)
    print(
        f"  ✓ {idx.n_vars} unique variables indexed  |  "
        f"{len(idx._cls)} codelists  |  "
        f"{len(idx.quarters)} quarters: {', '.join(sorted(idx.quarters))}"
    )

    # If a query argument is given, run free-text search only
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        showcase_free_text(idx, query)
        return

    # Full showcase
    for query in ("employment status", "seeking work", "hours worked"):
        showcase_free_text(idx, query)

    showcase_concept_discovery(idx)
    showcase_cross_quarter(idx)
    showcase_codelist_reuse(idx)

    _section("SUMMARY")
    print(f"""
  Index statistics
    Unique variables  : {idx.n_vars}
    Quarters covered  : {", ".join(sorted(idx.quarters))}
    Codelists indexed : {len(idx._cls)}

  Run with a query argument for targeted search:
    python search_lfs_metadata.py "education level"
    python search_lfs_metadata.py "nationality"
""")


if __name__ == "__main__":
    main()
