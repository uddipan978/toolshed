#!/usr/bin/env python3
"""slop.py — HLD's slop check: wrapper first, own rules narrow.

1. Runs impeccable's detect.mjs when present (THE generic detector; exit 2 = findings).
   Absent => recorded COULD-NOT-RUN — never a failure, never an install.
2. Runs HLD's own rules, which obey one admission rule: a check enters ONLY if it is
   parameterized by .hld/contract.json. Anything expressible without the contract is
   generic and belongs to detect.mjs (or the post-v1 fixture loop). See data/slop-rules.csv.

Usage:
  slop.py --root DIR [--paths a,b,...] [--contract FILE] [--out findings.csv] [--dry]
  slop.py --self-test

Findings are DATA (appended to findings.csv, severity-ranked); gates decide, this
script never blocks. Exit 0 unless the script itself errors. Stdlib only.
"""
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

SCAN_EXT = {".css", ".scss", ".tsx", ".jsx", ".ts", ".js", ".html", ".vue", ".svelte"}
COLOR_RE = re.compile(r"(#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\()")
DETECT_CANDIDATES = [
    os.environ.get("HLD_DETECT_MJS", ""),
    "~/.agents/skills/impeccable/scripts/detect.mjs",
    "~/.claude/skills/impeccable/scripts/detect.mjs",
]


def find_detect():
    for c in DETECT_CANDIDATES:
        if c and Path(c).expanduser().is_file():
            return Path(c).expanduser()
    return None


def run_detect(target):
    mjs = find_detect()
    if mjs is None or shutil.which("node") is None:
        why = "detect.mjs not found" if mjs is None else "node not on PATH"
        return {"status": "COULD-NOT-RUN", "why": why}, []
    try:
        r = subprocess.run(["node", str(mjs), str(target)], capture_output=True,
                           text=True, timeout=120)
    except subprocess.TimeoutExpired:
        return {"status": "COULD-NOT-RUN", "why": "detect.mjs timed out"}, []
    findings = []
    if r.returncode == 2:  # detect.mjs contract: exit 2 = findings
        for line in r.stdout.splitlines():
            m = re.match(r"(.+?):(\d+)[:\s]+(.*)", line.strip())
            if m:
                findings.append({"severity": "2", "rule": "detect",
                                 "source": "detect", "file": m.group(1),
                                 "line": m.group(2), "note": m.group(3)[:200]})
        if not findings:  # unparseable output still counts, summarized
            findings.append({"severity": "2", "rule": "detect", "source": "detect",
                             "file": str(target), "line": "",
                             "note": (r.stdout.strip() or "findings reported")[:400]})
    return {"status": "ran", "exit": r.returncode}, findings


def iter_files(root, paths, skipped=None):
    if paths:
        for raw in paths:
            p = Path(raw)
            if not p.is_absolute():
                p = Path(root) / p
            if p.is_file():
                yield p.resolve()
            elif p.is_dir():
                for f in p.rglob("*"):
                    if f.suffix in SCAN_EXT and f.is_file():
                        yield f.resolve()
            elif skipped is not None:
                skipped.append(raw)
    else:
        for p in Path(root).rglob("*"):
            if p.suffix in SCAN_EXT and p.is_file() and ".hld" not in p.parts \
                    and "node_modules" not in p.parts:
                yield p.resolve()


def contract_rules(root, contract, paths=None, skipped=None):
    """The admission rule in code: every check below reads the contract."""
    findings = []
    token_files = {str((Path(root) / t).resolve())
                   for t in contract.get("token_files", [])}
    primitives = contract.get("primitives", [])
    banned = contract.get("banned_patterns", [])
    has_tokens = bool(contract.get("tokens") or token_files)
    prim_res = [(name, re.compile(rf"\b(function|const|class)\s+{re.escape(name)}\b"))
                for name in primitives]
    prim_allowed = [str((Path(root) / d).resolve())
                    for d in contract.get("primitive_sources", [])]

    for f in iter_files(root, paths, skipped):
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        fs = str(f)
        for i, line in enumerate(text.splitlines(), 1):
            if has_tokens and fs not in token_files and COLOR_RE.search(line):
                findings.append({"severity": "3", "rule": "literal-color",
                                 "source": "contract", "file": fs, "line": str(i),
                                 "note": "literal color where the contract has tokens: "
                                         + line.strip()[:120]})
            for pat in banned:
                if re.search(pat.get("pattern", r"(?!)"), line):
                    findings.append({"severity": str(pat.get("severity", 3)),
                                     "rule": "banned-pattern", "source": "contract",
                                     "file": fs, "line": str(i),
                                     "note": pat.get("note", pat.get("pattern", ""))[:160]})
        if not any(fs.startswith(a) for a in prim_allowed):
            for name, rx in prim_res:
                if rx.search(text):
                    findings.append({"severity": "3", "rule": "primitive-clone",
                                     "source": "contract", "file": fs, "line": "",
                                     "note": f"re-implements contract primitive '{name}' "
                                             "outside its source dirs"})
    return findings


FIELDS = ["id", "severity", "rule", "source", "file", "line", "note", "disposition"]


def finding_id(f):
    return "F" + hashlib.sha1(
        f"{f['rule']}|{f['file']}|{f['line']}|{f['note']}".encode()).hexdigest()[:8]


def append_findings(out, findings):
    """Append, deduplicated: a finding already recorded (dispositioned or not) is
    never re-appended — re-runs must not demand a second disposition."""
    seen = set()
    exists = Path(out).is_file()
    if exists:
        with open(out, newline="", encoding="utf-8") as fh:
            seen = {row.get("id") for row in csv.DictReader(fh)}
    written = 0
    with open(out, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if not exists:
            w.writeheader()
        for f in findings:
            f = dict(f)
            f.setdefault("disposition", "")
            f["id"] = finding_id(f)
            if f["id"] in seen:
                continue
            seen.add(f["id"])
            w.writerow(f)
            written += 1
    return written


def self_test():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        Path(d, "bad.css").write_text(".x{color:#ff00aa}\n.y{color:var(--primary)}\n")
        Path(d, "tokens.css").write_text(":root{--primary:#0e5f52}\n")
        Path(d, "Chip.tsx").write_text("export function Button(){return null}\n")
        c = {"tokens": {"--primary": True}, "token_files": ["tokens.css"],
             "primitives": ["Button"], "primitive_sources": ["ui/"],
             "banned_patterns": [{"pattern": "lorem ipsum", "note": "placeholder copy",
                                  "severity": 2}]}
        f = contract_rules(d, c)
        rules = sorted({x["rule"] for x in f})
        assert "literal-color" in rules, f
        assert "primitive-clone" in rules, f
        assert not any(x["file"].endswith("tokens.css") for x in f), "token file exempt"
        assert len([x for x in f if x["rule"] == "literal-color"]) == 1, \
            "var(--) line must not flag"
        clean = contract_rules(d, {"tokens": {}, "primitives": []})
        assert clean == [], clean
    print("slop.py self-test: ok")
    return 0


def main(argv):
    if "--self-test" in argv:
        return self_test()
    args = dict(zip(argv, argv[1:]))
    root = Path(args.get("--root", ".")).resolve()
    paths = args.get("--paths", "")
    paths = [p for p in paths.split(",") if p] or None
    contract_path = Path(args.get("--contract", root / ".hld" / "contract.json"))
    out = args.get("--out", str(root / ".hld" / "findings.csv"))

    # detect.mjs runs over EVERY target — a path silently skipped reads as covered
    findings = []
    if paths is None:
        detect_status, findings = run_detect(root)
    else:
        detect_status = {"status": "ran", "per_path": {}}
        for p in paths:
            st, fs = run_detect(Path(root) / p if not Path(p).is_absolute() else p)
            detect_status["per_path"][p] = st.get("status", "?")
            if st.get("status") != "ran":
                detect_status["status"] = st["status"]
                detect_status["why"] = st.get("why")
            findings += fs

    contract, skipped = {}, []
    if contract_path.is_file():
        try:
            contract = json.loads(contract_path.read_text())
        except json.JSONDecodeError as e:
            print(f"contract.json unreadable: {e}", file=sys.stderr)
    if contract:
        findings += contract_rules(root, contract, paths, skipped)
    else:
        detect_status["contract"] = "absent — contract rules skipped (recorded)"
    if skipped:
        detect_status["skipped_paths"] = skipped  # visible, never silent

    written = 0
    if "--dry" not in argv and findings:
        written = append_findings(out, findings)
    print(json.dumps({"detect": detect_status, "findings": len(findings),
                      "new_rows": written,
                      "by_rule": sorted({f['rule'] for f in findings}),
                      "out": out if written else None}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
