#!/usr/bin/env python3
"""gate.py — HLD's gate checker. The gates live here, not in prose.

Usage:
  gate.py check g0|g1|g2|g3|g4|g5 [--root DIR]
  gate.py boundary "<task text>"
  gate.py status [--root DIR]
  gate.py --final            (Stop-hook mode: refuses FALSE completion, never honest pauses)
  gate.py --self-test

Exit codes: 0 = pass · 2 = fail (reasons printed) · 3 = kill-door KILL (valid terminal verdict).
Artifact grammar: reference/hld-gates.md. Python3 stdlib only.
"""
import csv
import io
import json
import re
import sys
from pathlib import Path

STATUS_TOKENS = "[ ] [>] [~] [t] [b] [x] [!] [?]"
TASK_RE = re.compile(r"^- \[(.)\] (T\d+) · worker=(\S+) · scope=(\S+) · (.+)$")
AGENTIC_RE = re.compile(
    r"\b(agentic|ai agent|llm loop|multi-agent|sub-?agent|autonomous execution|"
    r"tool orchestration|agent workflow)\b", re.I)

# Boundary: "existing <thing>" clauses are UI wiring — strip them before testing.
EXISTING_RE = re.compile(r"\b(existing|current)\b(\s+\S+){0,4}", re.I)
STOP_RULES = [
    (re.compile(
        r"\b(create|add|build|stand[- ]?up|introduce|expose|implement|write|"
        r"design|develop)\b[^.;]{0,50}\b((rest |backend |public |graphql )?api\b(?!-)|"
        r"endpoint|api route|webhook|graphql (mutation|resolver)|"
        r"(micro|backend)[- ]?service)", re.I), "backend api/service"),
    (re.compile(r"\b(schema|migration)s?\b", re.I), "schema/migration"),
    (re.compile(r"\b(alter|add|create|change|modify|update)\b[^.;]{0,50}"
                r"\b(column|table)\b(?!\s*(view|component|layout|of contents))",
                re.I), "database table/column"),
    (re.compile(r"\b(implement|write|create|set up|build)\s+(the\s+|an?\s+)?"
                r"auth\w*\s+(middleware|service|flow|backend|provider|logic|layer)|"
                r"\bauth\w*\s+(middleware|backend|service|provider)\b|\bnew auth\b",
                re.I), "auth"),
    (re.compile(r"\bnew backend\b", re.I), "new backend"),
]


def find_hld(root, stop_at_git=False):
    p = Path(root).resolve()
    if p.name == ".hld":
        return p
    cur = p
    while True:
        if (cur / ".hld").is_dir():
            return cur / ".hld"
        if stop_at_git and (cur / ".git").exists():
            return None  # never wander into an unrelated project above this repo
        if cur.parent == cur:
            return None
        cur = cur.parent


def read(hld, name):
    p = hld / name
    return p.read_text(encoding="utf-8", errors="replace") if p.is_file() else None


def section(text, heading):
    """Non-whitespace content between '## <heading>' and the next '## '."""
    m = re.search(rf"^## {re.escape(heading)}\s*$(.*?)(?=^## |\Z)",
                  text, re.M | re.S)
    return m.group(1).strip() if m else None


def parse_tasks(plan_text):
    tasks, bad = [], []
    for line in plan_text.splitlines():
        if not line.startswith("- ["):
            continue
        m = TASK_RE.match(line)
        if m:
            tasks.append({"status": m.group(1), "id": m.group(2),
                          "worker": m.group(3),
                          "scope": [s for s in m.group(4).split(",") if s],
                          "desc": m.group(5)})
        else:
            bad.append(line)
    return tasks, bad


def scopes_overlap(tasks):
    """Pairs whose scopes share a path, or where one path is a dir-prefix of another."""
    clashes = []
    for i, a in enumerate(tasks):
        for b in tasks[i + 1:]:
            for pa in a["scope"]:
                for pb in b["scope"]:
                    if pa == pb or pa.startswith(pb.rstrip("/") + "/") \
                            or pb.startswith(pa.rstrip("/") + "/"):
                        clashes.append((a["id"], b["id"], pa, pb))
    return clashes


def is_agentic(*texts):
    return any(AGENTIC_RE.search(t or "") for t in texts)


def boundary(desc):
    cleaned = EXISTING_RE.sub(" ", desc or "")
    for rx, label in STOP_RULES:
        m = rx.search(cleaned)
        if m:
            return f"STOP — {label} ({m.group(0).strip()[:60]})"
    return "BUILD"


# ---------------------------------------------------------------- gates
def g0(hld):
    brief = read(hld, "BRIEF.md")
    if brief is None:
        return ["BRIEF.md missing"]
    errs = []
    n = brief.count("[NEEDS CLARIFICATION]")
    if n:
        errs.append(f"{n} [NEEDS CLARIFICATION] marker(s) still in BRIEF.md")
    if not re.search(r"^Contract:\s*\S", brief, re.M):
        errs.append("BRIEF.md has no 'Contract:' line (paths or NONE-EXISTS)")
    return errs


def g1(hld):
    rep = read(hld, "UX-REPORT.md")
    if rep is None:
        return ["UX-REPORT.md missing"]
    if re.search(r"^Kill-door verdict:\s*KILL\b", rep, re.M):
        return "KILL"
    if re.search(r"^Kill-door verdict:\s*PROCEED\b", rep, re.M):
        return []
    return ["UX-REPORT.md records no kill-door verdict "
            "('Kill-door verdict: PROCEED' or 'Kill-door verdict: KILL — reason')"]


def g2(hld):
    errs = []
    ia = read(hld, "IA.md")
    if ia is None:
        errs.append("IA.md missing (the IA beat)")
    else:
        for h in ("Object model", "Copy inventory"):
            if not section(ia, h):
                errs.append(f"IA.md '## {h}' missing or empty")
    spec = read(hld, "UI-SPEC.md")
    if spec is None:
        errs.append("UI-SPEC.md missing")
    elif not section(spec, "Rejected alternatives"):
        errs.append("UI-SPEC.md '## Rejected alternatives' missing or empty")
    errs += undispositioned(hld)
    return errs


def undispositioned(hld):
    text = read(hld, "findings.csv")
    if not text:
        return []
    errs = []
    for row in csv.DictReader(io.StringIO(text)):
        try:
            sev = int(row.get("severity") or 0)
        except (ValueError, TypeError):
            continue
        if sev >= 3 and not (row.get("disposition") or "").strip():
            errs.append(f"finding {row.get('id')} (sev {sev}) has no disposition")
    return errs


def g3(hld):
    plan = read(hld, "BUILD-PLAN.md")
    if plan is None:
        return ["BUILD-PLAN.md missing"]
    tasks, bad = parse_tasks(plan)
    errs = [f"unparseable task line: {b}" for b in bad]
    if not tasks and not bad:
        errs.append("BUILD-PLAN.md has no task lines")
    errs += [f"scope overlap {a}/{b}: {pa} vs {pb}"
             for a, b, pa, pb in scopes_overlap(tasks)]
    if is_agentic(read(hld, "BRIEF.md"), plan):
        if "## Workflow architecture" not in plan or not all(
                re.search(rf"^{k}:", plan, re.M)
                for k in ("Agent-as-graph", "SDD", "Workflow-conversion")):
            errs.append("run is agentic but BUILD-PLAN.md lacks the "
                        "'## Workflow architecture' verdict block")
    return errs


def g4(hld):
    tp = read(hld, "TEST-PLAN.md")
    if tp is None:
        return ["TEST-PLAN.md missing"]
    shots = re.findall(r"^- (H4-\S+\.png)\b", tp, re.M)
    malformed = [ln for ln in tp.splitlines()
                 if ln.startswith("- H4-") and not re.match(r"^- H4-\S+\.png\b", ln)]
    if malformed:
        return [f"unparseable required-shot line: {ln}" for ln in malformed]
    if not shots:
        return ["TEST-PLAN.md lists no required shots ('- H4-...png' lines)"]
    report = read(hld, "TEST-REPORT.md") or ""
    shot_dir = hld / "work" / "screenshots"
    errs = []
    for s in shots:
        png, sc = shot_dir / s, shot_dir / (s + ".json")
        if png.is_file() and sc.is_file():
            continue
        if re.search(rf"^COULD-NOT-RUN: {re.escape(s)} — .+", report, re.M):
            continue
        missing = "shot" if not png.is_file() else "sidecar"
        errs.append(f"{s}: {missing} missing and no COULD-NOT-RUN line in TEST-REPORT.md")
    return errs


def g5(hld):
    errs = []
    ho = read(hld, "HANDOFF.md")
    if ho is None:
        errs.append("HANDOFF.md missing")
    elif not section(ho, "Auto-decisions"):
        errs.append("HANDOFF.md '## Auto-decisions' missing or empty")
    plan = read(hld, "BUILD-PLAN.md")
    if plan is not None:
        # only [x] done and [b] blocked-and-packaged are closed states at handoff
        open_tasks = [f"{t['id']}[{t['status']}]"
                      for t in parse_tasks(plan)[0] if t["status"] in " >~t!?"]
        if open_tasks:
            errs.append(f"tasks not closed in BUILD-PLAN.md: {', '.join(open_tasks)}")
    return errs


GATES = {"g0": g0, "g1": g1, "g2": g2, "g3": g3, "g4": g4, "g5": g5}


def run_check(gate, root):
    hld = find_hld(root)
    if hld is None:
        print(f"no .hld directory found at or above {root}")
        return 2
    res = GATES[gate](hld)
    if res == "KILL":
        m = re.search(r"^Kill-door verdict:\s*(KILL.*)$",
                      read(hld, "UX-REPORT.md"), re.M)
        print(f"g1: {m.group(1)}")
        print("Valid terminal verdict. Skip H2–H4; run H5 to package the no.")
        return 3
    if res:
        print(f"{gate} FAIL:")
        for e in res:
            print(f"  - {e}")
        return 2
    print(f"{gate} pass")
    return 0


def read_status(hld):
    text = read(hld, "STATUS.md") or ""
    get = lambda k: (re.search(rf"^{k}:\s*(\S+)", text, re.M) or [None, ""])[1]
    return get("state"), get("gate")


def check_run_honest(hld):
    """Exit-2 message if this run's STATUS makes a claim its gates don't back."""
    state, _ = read_status(hld)
    if state == "done":
        for gate in ("g0", "g1", "g2", "g3", "g4", "g5"):
            res = GATES[gate](hld)
            if res and res != "KILL":
                return (f"{hld}: STATUS.md claims done, but {gate} fails: {res[0]} "
                        f"(run gate.py check {gate}). Fix the gate or set an honest state.")
    if state == "killed" and g5(hld):
        return (f"{hld}: STATUS.md says killed, but HANDOFF.md doesn't package the no "
                "(g5 fails). A kill still ships its handoff.")
    return None


def final():
    """Stop hook. Refuse FALSE completion; never refuse an honest pause; never crash."""
    try:
        try:
            payload = json.load(sys.stdin)
        except Exception:
            payload = {}
        if payload.get("stop_hook_active"):
            return 0  # already looping on this hook; never trap the session
        cwd = Path(payload.get("cwd") or Path.cwd())
        runs = []
        hld = find_hld(cwd, stop_at_git=True)  # never wander above this repo
        if hld is not None:
            runs.append(hld)
        else:
            runs = [p for pat in ("*/.hld", "*/*/.hld")
                    for p in sorted(cwd.glob(pat)) if p.is_dir()][:5]
        for hld in runs:
            msg = check_run_honest(hld)
            if msg:
                print(msg, file=sys.stderr)
                return 2
        return 0  # running/absent state: pausing unfinished work is honest
    except Exception as e:  # a corrupt artifact must never trap or traceback a session
        print(f"gate.py --final internal error (not blocking): {e}", file=sys.stderr)
        return 0


def self_test():
    a = {"id": "T1", "scope": ["src/a.tsx", "src/x/"]}
    b = {"id": "T2", "scope": ["src/x/y.css"]}
    assert scopes_overlap([a, b]), "dir-prefix overlap must be caught"
    assert not scopes_overlap([a, {"id": "T3", "scope": ["src/b.tsx"]}])
    t, bad = parse_tasks("- [ ] T1 · worker=drive · scope=a.ts · Do it\n- [x] junk line")
    assert len(t) == 1 and len(bad) == 1
    assert boundary("Create a new endpoint POST /x").startswith("STOP")
    assert boundary("Add a fetch call to the existing /api/users endpoint") == "BUILD"
    assert boundary("Add a route into the existing settings page") == "BUILD"
    assert boundary("Write the auth middleware").startswith("STOP")
    assert is_agentic("the surface is an autonomous execution dashboard for agents")
    assert not is_agentic("redesign the checkout flow", "- [ ] T1 · worker=drive ...")
    print("gate.py self-test: ok")
    return 0


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    if argv[0] == "--final":
        return final()
    if argv[0] == "--self-test":
        return self_test()
    root = Path.cwd()
    if "--root" in argv:
        i = argv.index("--root")
        if i + 1 >= len(argv):
            print("--root needs a value")
            return 2
        root = Path(argv[i + 1])
    if argv[0] == "check" and len(argv) > 1 and argv[1] in GATES:
        return run_check(argv[1], root)
    if argv[0] == "boundary" and len(argv) > 1:
        print(boundary(argv[1]))
        return 0
    if argv[0] == "status":
        hld = find_hld(root)
        if hld is None:
            print("no .hld found")
            return 2
        state, gate = read_status(hld)
        print(f"root: {hld}\nstate: {state or '?'}\ngate: {gate or '?'}")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
