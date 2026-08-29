#!/usr/bin/env python3
"""why.py - look up the principle behind an observed symptom, with its evidence grade.

Every result row prints its evidence_grade. That is the point of this script: a principle
recited without its grade is the failure mode the human-like-thinking skill exists to prevent.
`contested`, `null-result` and `my-inference` rows are marked with a visible warning.

Data lives in ../data/*.csv, resolved from __file__, so the script runs from any directory.
Stdlib only.
"""

import argparse
import csv
import json
import math
import os
import re
import sys
from collections import Counter
from pathlib import Path

# ponytail: env override exists so tests and build.py can point at a staging data dir.
# The default still resolves from __file__ - never from cwd.
DATA_DIR = Path(os.environ.get("HLT_DATA_DIR") or Path(__file__).resolve().parent.parent / "data")

PRINCIPLE_COLS = [
    "id", "name", "family", "claim", "key_number", "formula", "evidence_grade",
    "design_lever", "anti_pattern", "symptoms", "applies_to", "conflicts_with",
    "ethics_axis", "quote", "source",
]
SYMPTOM_COLS = ["symptom_phrase", "principle_ids", "surface", "confidence"]
CONFLICT_COLS = ["id_a", "id_b", "tension", "resolution_rule"]

EVIDENCE_GRADES = ("replicated", "contested", "null-result", "heuristic", "my-inference")
# Grades that must never be quoted as settled fact. `heuristic` is honest about itself;
# these three read like laws unless the marker stops you.
WEAK_GRADES = {"contested", "null-result", "my-inference"}


# ---------------------------------------------------------------- io

def die(msg):
    """User error: one clear line on stderr, exit 1. No traceback."""
    print(f"why.py: {msg}", file=sys.stderr)
    sys.exit(1)


def load(filename, required):
    path = DATA_DIR / filename
    if not path.is_file():
        die(f"missing data file: {path}\n"
            f"       expected columns: {','.join(required)}\n"
            f"       set HLT_DATA_DIR to point elsewhere, or run scripts/build.py")
    try:
        with path.open(newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
    except OSError as exc:
        die(f"cannot read {path}: {exc}")
    if not rows:
        die(f"{path} has a header but no rows")
    missing = [c for c in required if c not in rows[0]]
    if missing:
        die(f"{path} is missing column(s): {', '.join(missing)}")
    return [{k: (v or "").strip() for k, v in r.items() if k} for r in rows]


def split_list(value):
    return [p.strip() for p in value.split("|") if p.strip()]


# ---------------------------------------------------------------- bm25

# Minimum token length is 1 on purpose. "ui", "ux", "3d", "ai" are real queries; dropping
# short tokens silently returns nothing for them and looks like "no such principle".
_TOKEN = re.compile(r"[a-z0-9]+")


def tokens(text):
    return _TOKEN.findall(text.lower())


def bm25(query, docs, k1=1.5, b=0.75):
    """Rank tokenised docs against a query string. Returns [(index, score)] best first.

    A query token absent from the vocabulary expands to vocabulary terms that start with it
    ("onboard" -> "onboarding") at half weight, so a near-miss returns the right row instead
    of nothing. Docs scoring zero are dropped rather than returned in arbitrary order.
    """
    n_docs = len(docs)
    q = tokens(query)
    if not n_docs or not q:
        return []
    lengths = [len(d) for d in docs]
    avgdl = (sum(lengths) / n_docs) or 1.0
    freqs = [Counter(d) for d in docs]
    df = Counter()
    for f in freqs:
        df.update(f.keys())

    scores = [0.0] * n_docs
    for term in q:
        if df.get(term):
            expanded = [(term, 1.0)]
        else:
            expanded = [(v, 0.5) for v in sorted(df) if v.startswith(term)]
        for t, weight in expanded:
            n_t = df.get(t, 0)
            if not n_t:
                continue
            idf = math.log(1 + (n_docs - n_t + 0.5) / (n_t + 0.5))
            for i, f in enumerate(freqs):
                tf = f.get(t, 0)
                if not tf:
                    continue
                denom = tf + k1 * (1 - b + b * lengths[i] / avgdl)
                scores[i] += weight * idf * (tf * (k1 + 1)) / denom
    return sorted(
        ((i, s) for i, s in enumerate(scores) if s > 0),
        key=lambda pair: (-pair[1], pair[0]),
    )


def principle_doc(row):
    """Searchable text for one principle. Repetition is the field weighting."""
    ident = row["id"].replace("-", " ")
    symptoms = row["symptoms"].replace("|", " ")
    return tokens(" ".join([
        row["name"], row["name"], row["name"],
        ident, ident,
        symptoms, symptoms,
        row["claim"], row["design_lever"], row["anti_pattern"],
        row["family"], row["applies_to"].replace("|", " "), row["key_number"],
    ]))


def symptom_doc(row):
    phrase = row["symptom_phrase"]
    return tokens(" ".join([
        phrase, phrase, phrase,
        row["surface"].replace("|", " "),
        row["principle_ids"].replace("|", " ").replace("-", " "),
    ]))


# ---------------------------------------------------------------- output

def grade_label(grade):
    return f"⚠ {grade}" if grade in WEAK_GRADES else grade


def print_principle(row, rank=None, via=None):
    head = f"{row['id']} · {row['name']} · {grade_label(row['evidence_grade'])}"
    print(f"[{rank}] {head}" if rank else head)
    if via:
        print(f"    {'via':<10}{via}")
    print(f"    {'claim':<10}{row['claim']}")
    if row["key_number"]:
        print(f"    {'number':<10}{row['key_number']}")
    print(f"    {'do':<10}{row['design_lever']}")
    print(f"    {'avoid':<10}{row['anti_pattern']}")
    if row["conflicts_with"]:
        others = ", ".join(split_list(row["conflicts_with"]))
        print(f"    {'conflicts':<10}{others}  (why.py --conflicts {row['id']})")
    print(f"    {'source':<10}{row['source']}")


def emit(rows, args, via_by_id=None):
    """Print principle rows, honouring --json and --limit. Truncation is always announced."""
    limit = args.limit if args.limit > 0 else len(rows)
    shown, dropped = rows[:limit], max(0, len(rows) - limit)
    if args.json:
        out = []
        for row in shown:
            item = dict(row)
            if via_by_id and row["id"] in via_by_id:
                item["matched_symptom"], item["confidence"] = via_by_id[row["id"]]
            out.append(item)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return
    if not shown:
        print("no match")
        return
    for i, row in enumerate(shown, 1):
        via = None
        if via_by_id and row["id"] in via_by_id:
            phrase, confidence = via_by_id[row["id"]]
            via = f'symptom "{phrase}" [confidence: {confidence or "unrecorded"}]'
        print_principle(row, rank=i, via=via)
    if dropped:
        print(f"... {dropped} more (--limit {len(rows)} to see all)")


# ---------------------------------------------------------------- modes

def by_evidence(rows, grade):
    if not grade:
        return rows
    present = sorted({r["evidence_grade"] for r in rows if r["evidence_grade"]})
    if grade not in EVIDENCE_GRADES:
        die(f"unknown evidence grade: {grade}\n"
            f"       allowed: {', '.join(EVIDENCE_GRADES)}\n"
            f"       present in this data: {', '.join(present) or '(none)'}")
    return [r for r in rows if r["evidence_grade"] == grade]


def mode_symptom(principles, args):
    """symptoms.csv is the entry index: people arrive saying what hurts, not naming a law."""
    symptoms = load("symptoms.csv", SYMPTOM_COLS)
    by_id = {r["id"]: r for r in principles}
    ranked = bm25(args.symptom, [symptom_doc(r) for r in symptoms])
    if not ranked:
        ranked = bm25(args.symptom, [principle_doc(r) for r in principles])
        if not ranked:
            print(f'no symptom or principle matched: "{args.symptom}"', file=sys.stderr)
            return
        # stderr, not stdout: --json output must stay parseable when the index misses.
        print(f'no symptom row matched "{args.symptom}"; falling back to principle text',
              file=sys.stderr)
        emit(by_evidence([principles[i] for i, _ in ranked], args.evidence), args)
        return

    ordered, via = [], {}
    for i, _score in ranked:
        srow = symptoms[i]
        for pid in split_list(srow["principle_ids"]):
            if pid in via:
                continue
            if pid not in by_id:
                print(f"warning: symptoms.csv references unknown principle id: {pid}",
                      file=sys.stderr)
                continue
            via[pid] = (srow["symptom_phrase"], srow["confidence"])
            ordered.append(by_id[pid])
    emit(by_evidence(ordered, args.evidence), args, via_by_id=via)


def name_hits(principles, name):
    """Two tiers: literal id/name, then punctuation-insensitive containment.

    Deliberately no fuzzy tier. --name is a lookup; --symptom is the search. Ranking a
    nonsense name against every claim returns confident junk - "quantum flux law" scored
    against every row whose name ends in "law". Returns [] when nothing matches; the caller
    turns that into a did-you-mean and exit 1.
    """
    raw = name.strip().lower()
    norm = " ".join(tokens(name))
    hits = [r for r in principles if r["id"].lower() == raw or r["name"].lower() == raw]
    if not hits and norm:
        hits = [r for r in principles
                if norm in " ".join(tokens(r["id"]))
                or norm in " ".join(tokens(r["name"]))]
    return hits


def mode_name(principles, args):
    if not args.name.strip():
        die("--name needs a principle id or name, e.g. --name hicks-law")
    hits = name_hits(principles, args.name)
    if not hits:
        ranked = bm25(args.name, [tokens(f"{r['id']} {r['name']}") for r in principles])[:3]
        suggest = ", ".join(principles[i]["id"] for i, _ in ranked)
        tail = (f"did you mean: {suggest}" if suggest
                else 'browse with --surface <value> or --symptom "<phrase>"')
        die(f"unknown principle: {args.name}\n       {tail}")
    emit(by_evidence(hits, args.evidence), args)


def mode_surface(principles, args):
    wanted = args.surface.strip().lower()
    known = sorted({s.lower() for r in principles for s in split_list(r["applies_to"])})
    if wanted not in known:
        die(f"unknown surface: {args.surface}\n       known surfaces: {', '.join(known)}")
    hits = [r for r in principles if wanted in [s.lower() for s in split_list(r["applies_to"])]]
    emit(by_evidence(hits, args.evidence), args)


def mode_conflicts(principles, args):
    conflicts = load("conflicts.csv", CONFLICT_COLS)
    by_id = {r["id"]: r for r in principles}
    target = args.conflicts.strip().lower()
    if target not in by_id:
        die(f"unknown principle: {args.conflicts}\n"
            f"       --conflicts takes a principle id, e.g. --conflicts hicks-law")

    pairs = []
    for row in conflicts:
        if row["id_a"] == target:
            pairs.append((row["id_b"], row))
        elif row["id_b"] == target:
            pairs.append((row["id_a"], row))
    if args.json:
        print(json.dumps([r for _, r in pairs], ensure_ascii=False, indent=2))
        return
    if not pairs:
        print(f"{target}: no conflicts recorded in conflicts.csv")
        return
    print(f"{target} · {grade_label(by_id[target]['evidence_grade'])} "
          f"· {len(pairs)} conflict(s)")
    for other, row in pairs:
        og = grade_label(by_id[other]["evidence_grade"]) if other in by_id else "unknown-id"
        print(f"  vs {other} · {og}")
        print(f"    {'tension':<10}{row['tension']}")
        print(f"    {'resolve':<10}{row['resolution_rule']}")


# ---------------------------------------------------------------- cli

EXAMPLES = """examples:
  why.py --symptom "nobody finishes onboarding"
  why.py --symptom "the settings page feels cluttered" --limit 5
  why.py --name hicks-law
  why.py --name "Fitts's Law" --json
  why.py --surface checkout
  why.py --surface form --evidence replicated
  why.py --conflicts hicks-law
  why.py --evidence contested --limit 10

evidence grades: replicated, contested, null-result, heuristic, my-inference
weak grades print with a marker, e.g. "⚠ contested". Never quote one as settled fact.
"""


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="why.py",
        description="Look up the UX principle behind a symptom, with its evidence grade.",
        epilog=EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--symptom", metavar="PHRASE",
                        help="what the human experienced; searches symptoms.csv first")
    parser.add_argument("--name", metavar="ID-OR-NAME", help="a principle id or its full name")
    parser.add_argument("--surface", metavar="APPLIES_TO",
                        help="one applies_to value, e.g. form, checkout, nav")
    parser.add_argument("--conflicts", metavar="ID",
                        help="principles that pull against this id, either direction")
    parser.add_argument("--evidence", metavar="GRADE",
                        help="filter by evidence grade; combines with the other modes")
    parser.add_argument("--json", action="store_true", help="emit full rows as JSON")
    parser.add_argument("--limit", type=int, default=3, metavar="N",
                        help="max results (default 3; 0 for all)")
    parser.add_argument("--selftest", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args.selftest:
        _selftest()
        return

    if not any([args.symptom, args.name, args.surface, args.conflicts, args.evidence]):
        parser.print_help(sys.stderr)
        sys.exit(1)

    principles = load("principles.csv", PRINCIPLE_COLS)
    if args.symptom:
        mode_symptom(principles, args)
    elif args.name:
        mode_name(principles, args)
    elif args.surface:
        mode_surface(principles, args)
    elif args.conflicts:
        mode_conflicts(principles, args)
    else:
        emit(by_evidence(principles, args.evidence), args)


# ---------------------------------------------------------------- selftest

def _selftest():
    """Fixture-backed checks for the four things that break silently. `why.py --selftest`."""
    p_rows = [
        {"id": "hicks-law", "name": "Hick's Law", "family": "decision",
         "claim": "Decision time grows with the number and complexity of choices.",
         "key_number": "RT = a + b log2(n+1)", "evidence_grade": "replicated",
         "design_lever": "Cut the visible options at the fork.",
         "anti_pattern": "Do not hide a needed option to shrink the count.",
         "symptoms": "too many options|users freeze at the menu", "applies_to": "nav|form",
         "conflicts_with": "pareto-principle"},
        {"id": "zeigarnik-effect", "name": "Zeigarnik Effect", "family": "motivation",
         "claim": "Unfinished tasks are recalled better than finished ones.",
         "key_number": "", "evidence_grade": "null-result",
         "design_lever": "Show a progress bar with the remaining step.",
         "anti_pattern": "Do not manufacture incompleteness to nag.",
         "symptoms": "nobody finishes onboarding|users abandon the form",
         "applies_to": "onboarding|form", "conflicts_with": ""},
        {"id": "ui-density", "name": "UI Density", "family": "perception",
         "claim": "Dense UI raises scan cost per element.", "key_number": "",
         "evidence_grade": "heuristic", "design_lever": "Group and give whitespace.",
         "anti_pattern": "Do not pad until scrolling replaces scanning.",
         "symptoms": "the ui feels cluttered", "applies_to": "dashboard",
         "conflicts_with": ""},
    ]
    s_rows = [
        {"symptom_phrase": "nobody finishes onboarding",
         "principle_ids": "zeigarnik-effect|hicks-law", "surface": "onboarding",
         "confidence": "high"},
        {"symptom_phrase": "the ui feels cluttered", "principle_ids": "ui-density",
         "surface": "dashboard", "confidence": "medium"},
    ]
    c_rows = [{"id_a": "hicks-law", "id_b": "pareto-principle",
               "tension": "Fewer options vs covering the long tail.",
               "resolution_rule": "Default to the 80% path; the rest goes behind 'More'."}]

    # 1. BM25 returns a sensible top hit for a known symptom phrase.
    ranked = bm25("nobody finishes onboarding", [symptom_doc(r) for r in s_rows])
    assert ranked and s_rows[ranked[0][0]]["symptom_phrase"] == "nobody finishes onboarding", ranked

    # 2. Short tokens survive. "ui" must not be dropped as noise.
    assert tokens("UI UX 3d ai") == ["ui", "ux", "3d", "ai"]
    hit = bm25("ui", [principle_doc(r) for r in p_rows])
    assert hit and p_rows[hit[0][0]]["id"] == "ui-density", hit

    # 3. Prefix expansion rescues a near-miss instead of returning nothing.
    assert bm25("onboard", [symptom_doc(r) for r in s_rows]), "prefix expansion regressed"

    # 4. Evidence filtering keeps only the asked-for grade.
    ids = [r["id"] for r in by_evidence(p_rows, "null-result")]
    assert ids == ["zeigarnik-effect"], ids
    assert len(by_evidence(p_rows, None)) == 3

    # 5. Weak grades are marked; replicated is not.
    assert grade_label("null-result").startswith("⚠")
    assert grade_label("contested").startswith("⚠")
    assert grade_label("replicated") == "replicated"

    # 6. Conflict lookup is symmetric: it matches on either side of the pair.
    def _partners(target):
        out = []
        for row in c_rows:
            if row["id_a"] == target:
                out.append(row["id_b"])
            elif row["id_b"] == target:
                out.append(row["id_a"])
        return out
    assert _partners("hicks-law") == ["pareto-principle"]
    assert _partners("pareto-principle") == ["hicks-law"]

    # 7. --name is a lookup: it finds by id, name and punctuation variants, and it
    #    returns nothing rather than a confident wrong row for a name that does not exist.
    for query in ("hicks-law", "Hick's Law", "hicks law", "hicks"):
        assert [r["id"] for r in name_hits(p_rows, query)] == ["hicks-law"], query
    assert name_hits(p_rows, "quantum flux law") == []

    print("why.py selftest: ok (7 checks)")


if __name__ == "__main__":
    main()
